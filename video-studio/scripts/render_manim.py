#!/usr/bin/env python3
"""Render a transparent math/formula overlay layer with Manim (engine="manim").

This is the "code-render" math path for video-studio, used in *overlay* mode:
Manim renders ONLY the math (equations, plots, geometry) on a transparent
background, producing an alpha `.mov` (qtrle). `composite_overlay.py` then lays
that layer over any background (a Remotion render, a solid colour, an image, or
another video). The composited result flows through the normal pipeline
(captions, BGM, QA, packaging) unchanged.

Why a separate engine: Remotion/CSS is weak at LaTeX, equation morphing,
function graphing and geometric construction; Manim is purpose-built for them.

Timing is bound to narration, never hand-typed. Pass `--storyboard` (the output
of `scene_timing.py`); each spec scene is matched to a storyboard scene by `id`
and appears exactly during that scene's narration window, so the on-screen math
matches the spoken line by construction. The overlay's total length equals the
storyboard total, so it overlays the whole background.

Two input modes:

1. Declarative (recommended): `--spec spec.json` describes scenes + elements;
   this script generates the Manim Scene for you. See `references/manim-patterns.md`
   for the element vocabulary.
2. Escape hatch: `--scene-file my_scene.py --scene-name MyScene` runs a Manim
   Scene you authored directly, transparently. You own its timing in that case.

Requires `manim` on PATH for the actual render (plus a TeX distribution for
`mathtex`/`tex_transform`, or Manim's Typst backend). Use `--emit-only` to
generate and inspect the Manim Python without rendering (no manim needed).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# --- spec vocabulary -> manim mappings ------------------------------------

POSITIONS: dict[str, str] = {
    "center": "ORIGIN",
    "up": "UP * 2.5",
    "down": "DOWN * 2.5",
    "left": "LEFT * 4",
    "right": "RIGHT * 4",
    "ul": "UL * 2.5",
    "ur": "UR * 2.5",
    "dl": "DL * 2.5",
    "dr": "DR * 2.5",
}

# Manim ManimColor constants are ALL-CAPS identifiers; allow only those.
_COLOR_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
# Hex colours are also valid (passed as a string literal to manim).
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Function expressions for axes_plot: numbers, x, operators, dots, parens and a
# small allowlist of numpy maths. Blocks arbitrary code injection in codegen.
_EXPR_RE = re.compile(r"^[0-9xX_+\-*/%.,()\s]*(?:(?:np\.)?(?:sin|cos|tan|exp|log|sqrt|abs|pi|e)[0-9xX_+\-*/%.,()\s]*)*$")
_ALLOWED_ANIM = {"write", "create", "fadein", "grow"}
_VALID_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class SpecError(ValueError):
    pass


def _color(value: str | None, default: str = "WHITE") -> str:
    if value is None:
        return default
    value = str(value).strip()
    if _HEX_RE.match(value):
        return f'"{value}"'
    if _COLOR_RE.match(value):
        return value
    raise SpecError(f"invalid color {value!r}: use a manim color constant (e.g. YELLOW) or #RRGGBB")


def _position(value: str | None) -> str:
    if value is None:
        return "ORIGIN"
    key = str(value).strip().lower()
    if key in POSITIONS:
        return POSITIONS[key]
    raise SpecError(f"invalid position {value!r}: one of {sorted(POSITIONS)}")


def _tex_literal(value: str) -> str:
    """Quote a LaTeX/text string as a Python raw-string literal safely."""
    if '"""' in value:
        raise SpecError("triple double-quotes are not allowed in tex/text content")
    return 'r"""' + value + '"""'


def _expr(value: str) -> str:
    value = str(value).strip()
    if not _EXPR_RE.match(value):
        raise SpecError(
            f"unsafe or invalid plot expression {value!r}: use x, numbers, + - * / ( ), and np.sin/cos/exp/log/sqrt/pi"
        )
    return value


def _intro_anim(kind: str, var: str) -> str:
    kind = (kind or "write").lower()
    if kind not in _ALLOWED_ANIM:
        raise SpecError(f"invalid animation {kind!r}: one of {sorted(_ALLOWED_ANIM)}")
    return {
        "write": f"Write({var})",
        "create": f"Create({var})",
        "fadein": f"FadeIn({var})",
        "grow": f"GrowFromCenter({var})",
    }[kind]


# --- element codegen -------------------------------------------------------


def _emit_element(el: dict[str, Any], idx: int, lines: list[str]) -> tuple[str, str]:
    """Append construction lines for one element; return (var_name, intro_play)."""
    etype = el.get("type")
    var = f"m{idx}"
    scale = float(el.get("scale", 1.0))
    pos = _position(el.get("position"))
    color = _color(el.get("color"))

    if etype == "text":
        content = _tex_literal(str(el.get("content", el.get("text", ""))))
        lines.append(f"        {var} = Text({content}, color={color}).scale({scale}).move_to({pos})")
        return var, _intro_anim(el.get("animation", "write"), var)

    if etype == "mathtex":
        tex = _tex_literal(str(el.get("tex", el.get("content", ""))))
        lines.append(f"        {var} = MathTex({tex}, color={color}).scale({scale}).move_to({pos})")
        return var, _intro_anim(el.get("animation", "write"), var)

    if etype == "tex_transform":
        from_tex = _tex_literal(str(el["from"]))
        to_tex = _tex_literal(str(el["to"]))
        lines.append(f"        {var} = MathTex({from_tex}, color={color}).scale({scale}).move_to({pos})")
        lines.append(f"        {var}_to = MathTex({to_tex}, color={color}).scale({scale}).move_to({pos})")
        # intro writes the first equation; the morph is emitted by the caller as
        # a mid-window play so it reads as a derivation step.
        return var, _intro_anim(el.get("animation", "write"), var)

    if etype == "axes_plot":
        xr = el.get("x_range", [-5, 5, 1])
        yr = el.get("y_range", [-3, 3, 1])
        expr = _expr(str(el.get("function", el.get("plot", "x"))))
        lines.append(f"        {var}_ax = Axes(x_range={list(xr)}, y_range={list(yr)}, tips=False)")
        lines.append(f"        {var}_g = {var}_ax.plot(lambda x: {expr}, color={color})")
        lines.append(f"        {var} = VGroup({var}_ax, {var}_g).scale({scale}).move_to({pos})")
        return var, f"Create({var})"

    raise SpecError(f"unknown element type {etype!r}")


def generate_scene(spec: dict[str, Any], storyboard: dict[str, Any] | None, scene_name: str) -> str:
    """Generate a transparent Manim Scene whose timeline is bound to narration."""
    spec_scenes = spec.get("scenes", [])
    if not spec_scenes:
        raise SpecError("spec has no scenes")

    # Build timing windows from the storyboard (narration is the source of truth).
    windows: dict[str, tuple[float, float]] = {}
    total = float(spec.get("durationInSeconds", 0.0))
    if storyboard:
        total = float(storyboard.get("durationInSeconds", total))
        for sc in storyboard.get("scenes", []):
            windows[str(sc.get("id"))] = (float(sc["start"]), float(sc["duration"]))

    body: list[str] = []
    cursor = 0.0  # absolute time already consumed on the manim timeline
    ordered = sorted(
        spec_scenes,
        key=lambda s: windows.get(str(s.get("id")), (float(s.get("start", 0.0)), 0.0))[0],
    )

    for sc in ordered:
        sid = str(sc.get("id"))
        if not _VALID_ID.match(sid):
            raise SpecError(f"scene id {sid!r} is not a valid identifier")
        if sid in windows:
            start, dur = windows[sid]
        else:
            start = float(sc.get("start", cursor))
            dur = float(sc.get("duration", 3.0))
        if start < cursor - 1e-6:
            raise SpecError(f"scene {sid!r} starts at {start} but timeline is already at {cursor}; check ordering")

        # Idle gap until this scene's narration begins.
        if start - cursor > 1e-3:
            body.append(f"        self.wait({round(start - cursor, 3)})  # gap before {sid}")

        elements = sc.get("elements", [])
        if not elements:
            raise SpecError(f"scene {sid!r} has no elements")

        lines: list[str] = [f"        # --- scene {sid}: window [{round(start,3)}, {round(start+dur,3)}]s ---"]
        intros: list[str] = []
        vars_: list[str] = []
        morphs: list[str] = []
        for j, el in enumerate(elements):
            var, intro = _emit_element(el, len(vars_) + len(morphs) + j, lines)
            vars_.append(var)
            intros.append(intro)
            if el.get("type") == "tex_transform":
                morphs.append(f"        self.play(Transform({var}, {var}_to), run_time={{morph_t}})")

        # Time budget inside the window: intro, optional morph, hold, outro.
        intro_t = round(min(1.0, dur * 0.35), 3)
        outro_t = round(min(0.5, dur * 0.2), 3)
        morph_t = round(min(1.2, dur * 0.3), 3) if morphs else 0.0
        hold_t = round(max(0.1, dur - intro_t - outro_t - morph_t), 3)

        body.extend(lines)
        group = "VGroup(" + ", ".join(vars_) + ")"
        body.append(f"        _g_{sid} = {group}")
        body.append(f"        self.play({', '.join(intros)}, run_time={intro_t})")
        for m in morphs:
            body.append(m.format(morph_t=morph_t))
        body.append(f"        self.wait({hold_t})")
        body.append(f"        self.play(FadeOut(_g_{sid}), run_time={outro_t})")
        cursor = round(start + dur, 3)

    if total - cursor > 1e-3:
        body.append(f"        self.wait({round(total - cursor, 3)})  # tail pad to storyboard total")

    indented = "\n".join(body)
    return (
        "# Auto-generated by video-studio/scripts/render_manim.py — do not edit by hand.\n"
        "# Transparent math overlay; timeline bound to narration (storyboard).\n"
        "from manim import *\n\n\n"
        f"class {scene_name}(Scene):\n"
        "    def construct(self):\n"
        f"{indented}\n"
    )


# --- rendering -------------------------------------------------------------


def render_with_manim(
    py_file: Path,
    scene_name: str,
    out_dir: Path,
    width: int,
    height: int,
    fps: int,
    quality_flag: str | None,
) -> Path:
    if not shutil.which("manim"):
        raise SpecError(
            "manim not found on PATH. Install it (pip install manim) plus a TeX "
            "distribution for MathTex, then re-run. Use --emit-only to generate "
            "the scene without rendering."
        )
    media_dir = out_dir / "manim_media"
    cmd = [
        "manim", "render",
        "--transparent",
        "--format", "mov",
        "--fps", str(fps),
        "-r", f"{width},{height}",
        "--media_dir", str(media_dir),
        "-o", scene_name,
        str(py_file), scene_name,
    ]
    if quality_flag:
        cmd.insert(2, quality_flag)
    proc = subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        raise SpecError(f"manim render failed:\n{proc.stdout[-4000:]}")
    movs = sorted(media_dir.rglob(f"{scene_name}.mov"))
    if not movs:
        movs = sorted(media_dir.rglob("*.mov"))
    if not movs:
        raise SpecError(f"manim reported success but no .mov found under {media_dir}")
    return movs[-1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--spec", help="Declarative overlay spec JSON")
    src.add_argument("--scene-file", help="Author-written Manim .py (escape hatch)")
    ap.add_argument("--scene-name", default="MathOverlay", help="Scene class name")
    ap.add_argument("--storyboard", help="storyboard.json from scene_timing.py (narration timing)")
    ap.add_argument("--out-dir", default=".", help="Where to write generated .py and the .mov")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--quality", default=None, help="Optional manim quality flag, e.g. -qh")
    ap.add_argument("--emit-only", action="store_true", help="Generate the Manim .py but do not render")
    args = ap.parse_args()

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    storyboard = None
    if args.storyboard:
        storyboard = json.loads(Path(args.storyboard).expanduser().read_text(encoding="utf-8"))
        args.fps = int(storyboard.get("fps", args.fps))

    if args.spec:
        spec = json.loads(Path(args.spec).expanduser().read_text(encoding="utf-8"))
        if "resolution" in spec:
            args.width, args.height = int(spec["resolution"][0]), int(spec["resolution"][1])
        try:
            code = generate_scene(spec, storyboard, args.scene_name)
        except SpecError as e:
            print(json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False))
            return 2
        py_file = out_dir / f"{args.scene_name}.py"
        py_file.write_text(code, encoding="utf-8")
    else:
        py_file = Path(args.scene_file).expanduser().resolve()
        if not py_file.exists():
            print(json.dumps({"status": "error", "error": f"scene file not found: {py_file}"}))
            return 2

    result: dict[str, Any] = {
        "status": "ok",
        "sceneFile": str(py_file),
        "sceneName": args.scene_name,
        "fps": args.fps,
        "resolution": [args.width, args.height],
        "durationInSeconds": float(storyboard["durationInSeconds"]) if storyboard else None,
    }

    if args.emit_only:
        result["emittedOnly"] = True
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    try:
        mov = render_with_manim(
            py_file, args.scene_name, out_dir, args.width, args.height, args.fps, args.quality
        )
    except SpecError as e:
        print(json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False))
        return 2

    overlay = out_dir / f"{args.scene_name}.mov"
    if mov.resolve() != overlay.resolve():
        shutil.copy2(mov, overlay)
    result["overlay"] = str(overlay)
    result["hasAlpha"] = True
    result["codec"] = "qtrle"
    sidecar = out_dir / f"{args.scene_name}.overlay.json"
    sidecar.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result["sidecar"] = str(sidecar)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
