# Remotion Patterns

Use Remotion when the video is generated from code, data, scenes, or reusable templates. Do not use Remotion for basic trimming or compression.

## Project Setup

Use a local project dependency, not global Remotion:

```bash
npx create-video@latest --yes --blank --no-tailwind my-video
cd my-video
npm install
```

Recommended dependencies:

```bash
npm install remotion @remotion/cli @remotion/media @remotion/media-utils @remotion/captions @remotion/transitions @remotion/shapes react react-dom zod
```

## Scene Config

Drive generated videos from config:

```ts
export const scenes = [
  {
    id: "s1",
    title: "Hook",
    startFrame: 0,
    durationInFrames: 120,
    visual: "title-card",
    primaryText: "Key point",
    assets: []
  }
];
```

Config is the truth. Components read config; components do not invent timing.

When there is narration, the voiceover is the timing truth. Derive the
composition length from the voiceover (the template's `calculateMetadata` uses
`getAudioDurationInSeconds`) so the picture never ends before the audio or runs
on after it, and drive scene `startFrame`/`durationInFrames` and caption cues
from the voiceover's real segment timings — not hand-typed frames — so visuals
land on what is being said. Author aligned cues with
`captions_from_script.py --voiceover ...`.

For a multi-scene narrated video, build the timeline with
`scripts/scene_timing.py` and render the bundled `ScenesVideo` composition: it
places one `<Sequence from={startFrame} durationInFrames={...}>` per scene at the
scene's narration window, with a single concatenated voiceover across the whole
composition. The scene on screen therefore always matches the segment being
spoken. Pass `scene_timing.py --props-out props.json` straight to
`remotion render ScenesVideo --props=props.json`.

## Component Rules

- Use `Composition` for dimensions, fps, and duration.
- Use `Sequence` for timeline layout.
- Use `useCurrentFrame()` plus `interpolate()` for animation.
- Prefer `interpolate()` over CSS transitions. CSS transitions do not render reliably.
- Put static assets under `public/` and use `staticFile()`.
- Use `OffthreadVideo` for frame-accurate video playback.
- Use Zod for parameterized props.

## Preview and QA

Before final render:

```bash
npx remotion still CompositionId --frame=30 --scale=0.5 --output verify/frame-030.png
npx remotion render CompositionId renders/preview.mp4 --scale=0.5
```

Final:

```bash
npx remotion render CompositionId renders/final.mp4 --codec=h264 --crf=20
```

Run the skill QA after Remotion render, with the delivery profile so missing
sound/subtitles/music are caught:

```bash
python3 {skill}/scripts/qa_video.py renders/final.mp4 \
  --profile social --captions public/captions.srt --bgm-declared
```

## Low-Spec Rules

- Preview at `--scale=0.5`.
- Avoid 4K, heavy blur, huge Lottie files, multiple videos stacked at once, and default 3D.
- Do not default to `@remotion/three`.
- If using 3D, render only the active scene and configure headless GL carefully.

## Sound, Captions & Music Are Required

A generated narrative/social video must ship with audio, subtitles, and music.
The bundled template (`assets/remotion-template`) already wires all three; keep
them wired. A render with no `<Audio>` produces an mp4 with no audio stream, and
`scripts/qa_video.py --profile social` will FAIL it.

Every generated video includes, by default:

- a `<Captions>` overlay driven by script-authored cues
- background music via `<Audio loop volume={0.12}>` (ducked under narration)
- a voiceover `<Audio>` when narration is intended

```tsx
import { Audio, staticFile } from "remotion";
import { Captions } from "./Captions";

// captions: [{ text, start, end }] in seconds — author from the script.
<Captions captions={captions} />
{voiceover ? <Audio src={staticFile(voiceover)} /> : null}
{bgm ? <Audio src={staticFile(bgm)} volume={bgmVolume} loop /> : null}
```

## Captions

You already have the script, so authoring subtitles needs no ASR:

```bash
python3 {skill}/scripts/captions_from_script.py \
  --script storyboard-lines.json \
  --srt-out public/captions.srt
```

Pass the resulting cues to `<Captions>` (convert SRT → `{text,start,end}`), or
feed the `.srt` to FFmpeg burn-in for a final ffmpeg pass.

- Use `@remotion/captions` only when you need word-level animated captions.
- Keep a dedicated caption layer; do not duplicate full caption sentences as
  primary scene text.

## Voiceover & Music

This skill does not run TTS or generate music, but it is responsible for the
finished soundtrack — never ship a silent video:

- Voiceover: if narration is wanted and the user did not supply a track, decide
  how to produce one (ask the user for a clip, or use an available external TTS
  the environment provides) and place it under `public/audio/`.
- BGM: source a fitting royalty-free track, record its source/license in package
  metadata, and reference it under `public/audio/`. Mix it low so narration wins.
- If a video genuinely has no speaker, it still gets BGM plus on-screen captions
  so it is never silent.
