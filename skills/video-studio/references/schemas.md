# Schemas

Use these schemas as the stable contracts between planning, rendering, QA, and handoff. Keep them small in v1.

## brief.json

```json
{
  "id": "my-video",
  "workflow": "local-edit",
  "platform": "instagram",
  "intent": "Trim and package a talking-head video",
  "inputs": {
    "videos": ["media/raw/input.mp4"],
    "images": [],
    "audio": [],
    "transcript": "media/assets/transcript.json",
    "subtitles": "media/assets/subtitles.srt",
    "voiceover": null,
    "url": null
  },
  "output": {
    "dir": "renders",
    "basename": "final"
  }
}
```

## transcript.json

This comes from an external ASR tool. Do not create it with this skill.

```json
{
  "language": "en",
  "segments": [
    {
      "id": 1,
      "start": 0.0,
      "end": 4.2,
      "text": "This is the first sentence",
      "words": [
        { "start": 0.0, "end": 0.4, "text": "This" }
      ]
    }
  ]
}
```

`words` is optional. If absent, use sentence-level subtitles.

## script-lines.json

Input for `scripts/captions_from_script.py`. You author this from the script you
already have — this is NOT ASR. Either give explicit timing, or give plain lines
plus a total `duration` to distribute evenly.

```json
{
  "duration": 18,
  "lines": [
    { "text": "Open with the hook", "start": 0.0, "end": 2.4 },
    { "text": "Then give the reason", "start": 2.4, "end": 5.1 }
  ]
}
```

```json
{ "duration": 18, "lines": ["Open with the hook", "Then give the reason", "End with the takeaway"] }
```

## scenes.json

Input for `scripts/scene_timing.py`. Each scene carries its own narration so the
tool can bind scene timing to speech. Give each scene an `audio` clip (preferred)
or pass a single `--voiceover` to split by silence.

```json
{
  "fps": 30,
  "scenes": [
    { "id": "s1", "visual": "chart-a", "narration": "First line of narration.", "audio": "media/audio/s1.mp3" },
    { "id": "s2", "visual": "chart-b", "narration": "Second line of narration.", "audio": "media/audio/s2.mp3" }
  ]
}
```

`scene_timing.py` emits a storyboard whose scenes gain `start`, `duration`,
`startFrame`, and `durationInFrames` derived from the narration, plus a
concatenated voiceover, aligned captions, and Remotion props.

## storyboard.json

Use for generated, platform-packaged, and web-to-video projects.

```json
{
  "version": 1,
  "chapters": [
    { "id": "ch1-hook", "title": "Hook", "sceneIds": ["s1"] }
  ],
  "scenes": [
    {
      "id": "s1",
      "chapter": "ch1-hook",
      "start": 0.0,
      "duration": 4.0,
      "source": "main",
      "visual": "video",
      "message": "Key point",
      "safeZone": true,
      "notes": "Keep original talking-head shot"
    }
  ]
}
```

`chapter` is the future unit of local edits. Do not make every tiny shot a chapter.

## render_manifest.json

See `assets/example-render-manifest.json` for a complete v1 example.

```json
{
  "version": 1,
  "engine": "ffmpeg",
  "platform": "instagram",
  "canvas": {
    "width": 1080,
    "height": 1350,
    "fps": 30
  },
  "sources": [
    { "id": "main", "type": "video", "path": "media/raw/input.mp4" }
  ],
  "clips": [
    {
      "id": "c1",
      "source": "main",
      "start": 0.0,
      "end": 12.5,
      "timelineStart": 0.0,
      "fit": "cover",
      "crop": "center"
    }
  ],
  "subtitles": {
    "path": "media/assets/subtitles.srt",
    "format": "srt",
    "style": "short-video-bold",
    "burnIn": true,
    "sourceHasCaptions": false
  },
  "overlays": [],
  "audio": {
    "keepOriginal": true,
    "voiceover": "media/audio/voiceover.mp3",
    "bgm": "media/audio/bgm.mp3",
    "bgmVolume": 0.12,
    "timingDriver": "voiceover"
  },
  "delivery": {
    "profile": "social"
  },
  "output": {
    "path": "renders/final.mp4",
    "codec": "h264",
    "crf": 20,
    "preset": "fast"
  },
  "qa": {
    "extractFrames": 6,
    "expectedAudio": true,
    "expectCaptions": true,
    "expectBgm": true
  }
}
```

`delivery.profile` (`social`, `narrative`, `raw`) sets the default QA
expectations; the `qa.expect*` fields override per check. `qa_video.py
--manifest render_manifest.json` reads these to decide what to enforce, so a
render that drops sound or music fails QA instead of shipping empty. Captions are
opt-in — no profile requires them; set `qa.expectCaptions: true` only when the
user asked for subtitles. For a deliverable, prefer non-null `audio.bgm` (and
`audio.voiceover` when there is narration). Use `raw` only for plain
trims/conversions where silence is acceptable.

`subtitles.sourceHasCaptions: true` declares that the source video already shows
captions (a burned-in/design caption layer, or a soft track). `render_ffmpeg.py`
then SKIPS the burn so you do not stack a second, offset caption layer over an
already-captioned video. The renderer also warns on its own when a clip source
carries a soft subtitle stream. Burned-in/on-screen captions are invisible to
`ffprobe` — confirm them from provenance or extracted frames. See SKILL.md
"No double captions".

`audio.timingDriver: "voiceover"` makes the narration the source of truth for
length: `render_ffmpeg.py` extends the video (freezing the last frame) to cover
a longer voiceover instead of cutting it. `audio.padVideoToAudio: true` forces
the same freeze-extend without naming a driver. Without either, a voiceover
longer than the clip timeline is cut and the renderer warns. QA reads
`audio.voiceover` and fails the output when narration is cut off.

Allowed `engine` values:

- `ffmpeg`
- `remotion`
- `web-frames`
- `manim`
- `external`

`engine: "manim"` is the math/formula/geometry path and runs in *overlay* mode:
`render_manim.py` produces a transparent alpha `.mov` from a `manim_spec.json`,
then `composite_overlay.py` lays it over a background and emits a normal mp4 that
you reference as a `source` in an `ffmpeg` manifest for captions/BGM/QA. See
`references/manim-patterns.md`. Manim renders the visual only — it is never the
final delivery engine on its own.

Allowed `fit` values:

- `cover`
- `contain`
- `stretch`
- `original`

## manim_spec.json (math overlay)

Declarative input for `render_manim.py`. Scene `id`s must match the
`storyboard.json` ids so timing comes from narration. Full element vocabulary and
examples are in `references/manim-patterns.md`.

```json
{
  "resolution": [1920, 1080],
  "scenes": [
    { "id": "s1", "elements": [
      { "type": "mathtex", "tex": "a^2 + b^2 = c^2", "animation": "write", "position": "center", "scale": 2.0, "color": "WHITE" }
    ] },
    { "id": "s2", "elements": [
      { "type": "tex_transform", "from": "a^2 + b^2 = c^2", "to": "c = \\sqrt{a^2 + b^2}", "color": "YELLOW" }
    ] },
    { "id": "s3", "elements": [
      { "type": "axes_plot", "x_range": [-3, 3, 1], "y_range": [-1, 9, 1], "function": "x*x", "color": "TEAL" }
    ] }
  ]
}
```

Element `type` is one of `text`, `mathtex`, `tex_transform`, `axes_plot`. The
render writes a sidecar `*.overlay.json` (`overlay` path, `fps`, `resolution`,
`hasAlpha`, `codec`) for `composite_overlay.py --sidecar` to consume.

## publish_package.json

```json
{
  "version": 1,
  "platform": "instagram",
  "video": "renders/final.mp4",
  "cover": "package/cover.png",
  "subtitles": {
    "srt": "package/final.srt",
    "vtt": null,
    "ass": null
  },
  "copy": {
    "title": "Title",
    "body": "Body text",
    "tags": ["AI", "tutorial"]
  },
  "qa": "verify/final.qa.json",
  "ready": false,
  "blocking": []
}
```

The package is a handoff artifact only. Do not upload.

## run-log.jsonl

One JSON object per line:

```json
{"ts":"2026-06-25T10:00:00Z","stage":"probe","event":"start","note":"probing input.mp4"}
{"ts":"2026-06-25T10:00:01Z","stage":"probe","event":"done","note":"duration 31.2s"}
```

Stages should be idempotent. If a stage output exists and inputs are older, log `skip`.
