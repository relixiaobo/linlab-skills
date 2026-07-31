# Platform Profiles

Use profiles to keep platform differences out of the core workflow.

## Common Fields

```json
{
  "platform": "instagram",
  "canvas": { "width": 1080, "height": 1350, "fps": 30 },
  "safeZone": { "top": 96, "right": 72, "bottom": 168, "left": 72 },
  "captionZone": { "yMin": 0.66, "yMax": 0.82 },
  "maxDurationSeconds": null,
  "cover": { "width": 1080, "height": 1350 },
  "text": { "maxPrimaryWords": 8, "maxSubtitleWords": 16 }
}
```

Safe zones are conservative. User-provided platform specs override these. Each
profile below uses the platform's real aspect ratio and recommended resolution.

## Delivery Requirements

Short-form social platforms (Instagram, TikTok, Reels, Shorts, Snapchat) expect a
complete soundtrack. For every social package, unless the user explicitly opts
out, the deliverable must have:

- an audible audio track (narration and/or BGM) — never silent
- burned-in or attached captions, kept inside `captionZone`
- a fitting background music bed, ducked under any narration

Treat these as `delivery.profile: "social"` and verify with
`qa_video.py --profile social`. If an element is missing and cannot be sourced
or authored, stop and report it rather than shipping an empty video.

## Instagram Feed (portrait)

```json
{
  "platform": "instagram",
  "canvas": { "width": 1080, "height": 1350, "fps": 30 },
  "safeZone": { "top": 96, "right": 72, "bottom": 168, "left": 72 },
  "captionZone": { "yMin": 0.66, "yMax": 0.82 },
  "cover": { "width": 1080, "height": 1350 },
  "package": ["video", "cover", "title", "body", "tags", "subtitles"]
}
```

Instagram's feed video is 4:5 (1080x1350). Use when the request says Instagram
feed, portrait post, or 4:5. Instagram Reels and Stories are 9:16 — use the
vertical-short profile below for those.

## TikTok / Instagram Reels / YouTube Shorts (9:16)

```json
{
  "platform": "vertical-short",
  "canvas": { "width": 1080, "height": 1920, "fps": 30 },
  "safeZone": { "top": 132, "right": 132, "bottom": 384, "left": 60 },
  "captionZone": { "yMin": 0.58, "yMax": 0.76 },
  "cover": { "width": 1080, "height": 1920 },
  "package": ["video", "cover", "title", "body", "tags", "subtitles"]
}
```

All three are full-screen 9:16 (1080x1920). Keep primary text and captions out of
the right action rail and the tall bottom region (handle, caption, and CTA).
TikTok and Reels crowd the bottom most; YouTube Shorts adds a bottom title/CTA
bar — the conservative bottom margin above covers all three.

## Snapchat (9:16)

```json
{
  "platform": "snapchat",
  "canvas": { "width": 1080, "height": 1920, "fps": 30 },
  "safeZone": { "top": 160, "right": 110, "bottom": 320, "left": 64 },
  "captionZone": { "yMin": 0.56, "yMax": 0.74 },
  "cover": { "width": 1080, "height": 1920 },
  "package": ["video", "cover", "title", "tags"]
}
```

Full-screen 9:16 (1080x1920). Snapchat reserves the top (profile/attachment) and
a tall bottom (CTA/swipe-up), so keep text more central than on TikTok.

## YouTube Horizontal

```json
{
  "platform": "youtube",
  "canvas": { "width": 1920, "height": 1080, "fps": 30 },
  "safeZone": { "top": 54, "right": 96, "bottom": 120, "left": 96 },
  "captionZone": { "yMin": 0.72, "yMax": 0.90 },
  "cover": { "width": 1280, "height": 720 },
  "package": ["video", "thumbnail", "title", "description", "subtitles"]
}
```

## Square

```json
{
  "platform": "square",
  "canvas": { "width": 1080, "height": 1080, "fps": 30 },
  "safeZone": { "top": 54, "right": 54, "bottom": 54, "left": 54 },
  "captionZone": { "yMin": 0.70, "yMax": 0.88 },
  "cover": { "width": 1080, "height": 1080 },
  "package": ["video", "cover", "title", "body", "tags"]
}
```

## Cover Rules

- Mobile covers must prioritize readable title over decorative detail.
- Keep the primary title short (about 4-10 characters for CJK, 3-6 words for Latin).
- Use one primary message and one optional subtitle.
- If the source frame is visually noisy, use a simple solid or blurred background.

## Handoff Rules

Always produce a package rather than uploading:

```text
package/
  publish_package.json
  cover.png
  final.srt
  final.vtt
  copy.md
```

Use the bundled helper:

```bash
python3 {skill}/scripts/build_publish_package.py \
  --platform instagram \
  --video renders/final.mp4 \
  --cover package/cover.png \
  --title "Title" \
  --body "Body text" \
  --tags "AI,tutorial" \
  --qa verify/qa.json \
  --output package/publish_package.json
```

Generate a simple cover when the user has not supplied one:

```bash
python3 {skill}/scripts/make_cover.py \
  --title "Title" \
  --subtitle "Subtitle" \
  --video renders/final.mp4 \
  --timestamp 00:00:03 \
  --output package/cover.png \
  --width 1080 \
  --height 1350
```
