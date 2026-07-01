# Manim Patterns (math / formula / geometry overlay)

Use Manim when the video needs **real math**: LaTeX equations, equation
derivations (one formula morphing into the next), function graphs, coordinate
systems, or geometric construction. Remotion/CSS is weak at all of these; Manim
(the 3Blue1Brown engine) is purpose-built for them.

Manim is used here in **overlay mode**: it renders ONLY the math on a
transparent background (an alpha `.mov`), and `composite_overlay.py` lays that
layer over a background (a Remotion render, a solid colour, an image, or a
video). The composited result is a normal mp4 that flows through the rest of the
pipeline (captions, BGM, QA, packaging) unchanged.

Do not use Manim for talking-head edits, trims, crops, or generic motion
graphics — those stay on ffmpeg / Remotion / web-to-video.

## Requirements

- `manim` on PATH (`pip install manim`, or the `manimcommunity/manim` Docker image).
- A TeX distribution for `mathtex` / `tex_transform` (e.g. TeX Live / MacTeX), or
  Manim's Typst backend. `text` and `axes_plot` do NOT need TeX.
- Run `scripts/doctor.py` — it reports `manim` and `latex` as optional deps.

Pin the Manim version (it is mid-refactor). This integration targets ManimCE
0.20.x and shells out to the stable `manim render` CLI.

## Workflow

```
scenes.json ──scene_timing.py──> storyboard.json   (narration = timing truth)
                                      │
spec.json ───render_manim.py ────────┘──> MathOverlay.mov  (transparent, qtrle)
                                                │
background ──composite_overlay.py───────────────┘──> composited.mp4
                                                          │
                                          render_ffmpeg.py / qa_video.py / package
```

1. **Build the timeline first.** Author `scenes.json` with one entry per math
   beat (id + narration, plus per-scene `audio` or explicit `start`/`duration`).
   Run `scene_timing.py` to get `storyboard.json`. The narration is the source
   of truth for timing — never hand-type frame counts.
2. **Author the math spec** (`spec.json`, below). Scene ids MUST match the
   storyboard ids.
3. **Render the transparent layer:**
   ```bash
   python3 scripts/render_manim.py \
     --spec spec.json --storyboard storyboard.json \
     --scene-name MathOverlay --out-dir work/manim
   ```
   Each scene's animations are scaled to fit its narration window
   (intro → optional morph → hold → fade-out), and the overlay's total length
   equals the storyboard total. Output: `MathOverlay.mov` (+ `.overlay.json`).
   Use `--emit-only` to inspect the generated Manim Python without rendering.
4. **Composite over a background:**
   ```bash
   python3 scripts/composite_overlay.py \
     --overlay work/manim/MathOverlay.mov \
     --background color:#0b1020 \
     --out media/raw/math_layer.mp4 --sidecar work/manim/MathOverlay.overlay.json
   ```
   Background forms: `color:#RRGGBB`, `image:bg.png`, `video:bg.mp4` (e.g. a
   Remotion render). Overlay length drives output length, so picture and
   narration stay in lockstep.
5. **Finish through the normal pipeline.** Reference `math_layer.mp4` as a
   `source` in `render_manifest.json` (engine `ffmpeg`) for captions + BGM +
   voiceover, then `qa_video.py --manifest ...`. Captions still come from
   `captions_from_script.py`; the math layer is just the visual.

## spec.json schema

```json
{
  "resolution": [1920, 1080],
  "scenes": [
    { "id": "s1", "elements": [ { "type": "mathtex", "tex": "a^2 + b^2 = c^2" } ] }
  ]
}
```

- `id` — matches a storyboard scene id (timing comes from there).
- `elements` — one or more drawn objects, shown together during the window.

### Element types

| type            | required keys        | renders                                  | needs TeX |
| --------------- | -------------------- | ---------------------------------------- | --------- |
| `text`          | `content`            | plain text (Pango)                       | no        |
| `mathtex`       | `tex`                | a LaTeX formula                          | yes       |
| `tex_transform` | `from`, `to`         | one formula morphing into another        | yes       |
| `axes_plot`     | `function`           | axes + a plotted function of `x`         | no        |

Common optional keys: `position` (`center`/`up`/`down`/`left`/`right`/`ul`/`ur`/
`dl`/`dr`), `scale` (float), `color` (a Manim colour constant like `YELLOW` or a
`#RRGGBB` hex), `animation` (`write`/`create`/`fadein`/`grow`). For `axes_plot`:
`x_range`/`y_range` as `[min, max, step]`.

`function` is restricted to `x`, numbers, `+ - * / ( )`, and
`np.sin/cos/tan/exp/log/sqrt/pi/e` — arbitrary code is rejected at generation
time. `tex`/`from`/`to`/`content` are emitted as raw-string literals.

### Example (Pythagoras → rearrange → parabola)

See `assets/manim-overlay-example/{spec.json,scenes.json}`. It writes
`a^2+b^2=c^2`, morphs it to `c=\sqrt{a^2+b^2}`, then draws `y=x^2` on axes —
each beat bound to its narration line.

## Escape hatch: author the Manim Scene directly

For anything the declarative vocabulary can't express (3D, vector fields, custom
geometry, `ValueTracker` updaters), write a normal Manim `Scene` and render it
transparently:

```bash
python3 scripts/render_manim.py \
  --scene-file my_scene.py --scene-name MyScene --out-dir work/manim
```

You own the timeline in this mode — make the Scene's total duration match the
narration (probe the voiceover) so the composite stays in sync. Then composite
and finish as above.

## Pitfalls

- **No TeX installed** → `mathtex`/`tex_transform` fail; use `text`/`axes_plot`,
  install TeX, or use the Typst backend.
- **Transparent output is `.mov` (qtrle), not mp4** — mp4 has no alpha. Keep the
  overlay as `.mov` until after compositing.
- **Drawing onto a transparent canvas**: an opaque element must actually carry
  alpha=255 (Manim handles this; if you hand-build test clips, overlay an opaque
  source onto the transparent canvas rather than `drawbox`, which can leave
  alpha at 0).
- **Sync**: always derive the overlay length and scene windows from the
  storyboard, never from guessed seconds.
```
