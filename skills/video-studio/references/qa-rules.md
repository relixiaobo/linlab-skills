# QA Rules

Run QA for every final video, regardless of render engine. Use
`scripts/qa_video.py` with a delivery profile so the soundtrack contract is
enforced, not just measured:

```bash
python3 {skill}/scripts/qa_video.py renders/final.mp4 \
  --manifest render_manifest.json        # derives expectations + voiceover from the manifest
# or
python3 {skill}/scripts/qa_video.py renders/final.mp4 \
  --profile social --captions media/assets/subtitles.srt \
  --bgm-declared --voiceover media/audio/voiceover.mp3
```

A non-zero exit means a delivery requirement failed (silent audio, missing
captions, missing BGM, wrong dimensions). Do not present the video as final
until it passes. Use `--profile raw` (or `--allow-silent`) only for plain
trims/conversions where silence is acceptable.

## Required Checks

1. `ffprobe` metadata:
   - container duration
   - video stream exists
   - audio stream exists if expected
   - width/height
   - fps
   - codec
2. Audio is audible, not just present: `qa_video.py` runs `volumedetect` and
   fails a track whose peak is below the silence threshold (default −50 dBFS).
3. Captions and BGM are present when the profile/manifest expects them.
4. A/V sync: when a voiceover is given (`--voiceover`/manifest), `qa_video.py`
   compares its duration to the output and fails when narration is cut off.
   With `--storyboard storyboard.json` it also checks scene/narration alignment
   (output length vs storyboard, scene starts vs detected speech) and drops one
   midpoint frame per scene for a visual "right scene under the line?" review.
5. Extract representative keyframes:
   - first 1s
   - last 1s
   - 3-6 middle points
   - cut boundaries if a cut list exists
6. Detect obvious failures:
   - black frames
   - long static frames
   - no audio when expected
   - narration cut off or drifting from the picture
   - wrong aspect ratio
   - text outside safe zones
   - captions hidden by overlays
   - browser UI/debug HUD in captured web video

## QA Output

Write:

```text
verify/
  final.qa.json
  frames/
    frame-000001.png
    frame-000002.png
```

`final.qa.json` should include:

```json
{
  "status": "pass",
  "video": "renders/final.mp4",
  "metadata": {},
  "checks": [],
  "warnings": [],
  "errors": [],
  "frames": []
}
```

Use `pass`, `warn`, or `fail`.

## Delivery Labels

- `PASSED`: no errors and no material warnings.
- `DELIVERED WITH WARNINGS`: output usable but has visible or technical concerns.
- `FAILED QA`: do not present as final unless the user explicitly accepts.

## Manual Review

After extracting frames, actually inspect them when visual quality matters. Automated metadata checks cannot catch:

- text overlap
- bad composition
- unreadable subtitles
- wrong screenshot moment
- off-brand visuals
- crop cutting off a face or UI control
