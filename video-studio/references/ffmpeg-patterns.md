# FFmpeg Patterns

Use FFmpeg for local-edit and final packaging whenever possible.

## Default Renderer

Use the bundled renderer for v1 manifests:

```bash
python3 {skill}/scripts/render_ffmpeg.py render_manifest.json --base-dir /path/to/project
```

Inspect the generated command plan without requiring FFmpeg:

```bash
python3 {skill}/scripts/render_ffmpeg.py render_manifest.json --dry-run --plan-output verify/render-plan.json
```

The renderer supports:

- clip trim by `start` / `end`
- `cover`, `contain`, `stretch`, and `original` fit modes
- canvas normalization to manifest width/height/fps
- concat of normalized clips
- optional burned subtitles
- optional external voiceover/BGM mix

Render overlays with Remotion or web-to-video first, then reference the rendered media as sources. `render_ffmpeg.py` v1 intentionally does not implement arbitrary overlay timelines.

## Core Rules

- Probe first with `ffprobe`.
- Prefer one final encode from source media.
- Avoid repeated `input -> intermediate -> intermediate -> final` encodes.
- Normalize mixed source frame rates before concat.
- Apply subtitles/captions after overlays unless captions are a separate dedicated track.
- Add 30ms audio fades at spoken cut boundaries.
- Use `libx264 + aac + yuv420p` for broad platform compatibility.

## Recommended Output Defaults

Preview:

```text
720x1280 or 1280x720, 30fps, crf 24, preset veryfast
```

Final:

```text
1080x1920 / 1080x1440 / 1920x1080, 30fps, crf 18-22, preset fast
```

Encoding pattern:

```bash
ffmpeg -y -i input.mp4 \
  -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 128k \
  output.mp4
```

## Reframe

Vertical cover crop:

```bash
ffmpeg -y -i input.mp4 \
  -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" \
  -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 128k \
  output.mp4
```

Vertical contain with padding:

```bash
ffmpeg -y -i input.mp4 \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black" \
  -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 128k \
  output.mp4
```

## Segment Concatenation

For mixed frame rates or any filtered output, re-encode the final result. Do not use `-c copy` concat on mixed sources.

Safe simple concat after normalization:

```bash
ffmpeg -y -f concat -safe 0 -i concat.txt \
  -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 128k \
  output.mp4
```

## Subtitles

Use ASS for styled burned subtitles. Generate ASS from SRT or transcript before final render.

```bash
ffmpeg -y -i input.mp4 \
  -vf "subtitles=subtitles.ass" \
  -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p \
  -c:a copy \
  output.mp4
```

If an overlay layer is also present, compose overlays first in the filter graph and put subtitle rendering last.

Do not double-caption. Before burning subtitles onto an existing/previously-generated
video, confirm it has none: `probe_media.py` reports soft subtitle streams, but
burned-in or on-screen design captions (a bottom bar, or large narration text)
are invisible to `ffprobe` — check provenance or sample frames. Re-caption from a
caption-free master, not the delivered file. When the source already shows
captions, set `subtitles.sourceHasCaptions: true`: `render_ffmpeg.py` skips the
burn (and warns when a source carries a subtitle stream) instead of stacking a
second, offset caption layer.

Some FFmpeg builds, including minimal/Homebrew variants, may not include the `subtitles` filter. `render_ffmpeg.py` detects this. For `.srt` files it falls back to rendering transparent caption PNG layers with Pillow and compositing them with FFmpeg `overlay`. For `.ass` burn-in, install an FFmpeg build with libass/subtitles support.

## Audio

Add short fades around clips when cutting spoken media:

```text
afade=t=in:st=0:d=0.03,afade=t=out:st=<duration-0.03>:d=0.03
```

If combining original audio, voiceover, and BGM, keep voices dominant. Default volumes:

- original ambience: 0.2-0.6
- BGM: 0.08-0.18
- voiceover: 1.0

Do not put complicated audio padding, tempo, and multi-video filter chains into one fragile command if a simpler two-step audio render is safer.

Never deliver a silent video. If the source has no usable audio and there is no
voiceover, add a royalty-free BGM bed so the output still has sound. Set
`audio.bgm` in the manifest (and a non-null `audio.voiceover` when narration
exists); `render_ffmpeg.py` mixes them in the final pass. The QA gate
(`qa_video.py`) measures loudness with `volumedetect` and fails an output whose
audio track is effectively silent.

## Narration Sync

By default `render_ffmpeg.py` makes the output as long as the clip timeline,
which silently CUTS a longer voiceover. When narration drives the video, set
`audio.timingDriver: "voiceover"` (or `audio.padVideoToAudio: true`): the
renderer takes the voiceover's real length, freeze-extends the last frame to
cover it, and never trims narration. It also warns when the voiceover and the
clip timeline differ. Align captions/scene changes to the narration with
`captions_from_script.py --voiceover ...`, and verify the result with
`qa_video.py --voiceover ...`.

## Known Failure Rules

- Mixed frame rates + concat copy can freeze playback. Normalize fps first.
- Complex `filter_complex` with `amix`, `apad`, `atempo`, and video filters can truncate audio. Split audio processing when needed.
- `drawtext` requires FFmpeg built with freetype/fontconfig. Prefer ASS for CJK subtitles.
- CJK subtitles require an installed CJK font. On Linux, use `fonts-noto-cjk`.
