import React from "react";
import { Composition, staticFile } from "remotion";
import { getAudioDurationInSeconds } from "@remotion/media-utils";
import { z } from "zod";
import { DefaultVideo } from "./DefaultVideo";
import { ScenesVideo } from "./Scenes";

const captionSchema = z.object({
  text: z.string(),
  start: z.number(),
  end: z.number(),
});

const sceneSchema = z.object({
  id: z.string(),
  visual: z.string().optional(),
  title: z.string().optional(),
  text: z.string().optional(),
  startFrame: z.number(),
  durationInFrames: z.number(),
});

export const scenesVideoSchema = z.object({
  scenes: z.array(sceneSchema).default([]),
  captions: z.array(captionSchema).default([]),
  voiceover: z.string().optional(),
  bgm: z.string().optional(),
  bgmVolume: z.number().default(0.12),
  durationInSeconds: z.number().default(8),
});

export const defaultVideoSchema = z.object({
  title: z.string().default("Video Studio"),
  subtitle: z.string().optional(),
  // Captions are part of the contract: a narrative/social video ships with them.
  captions: z.array(captionSchema).default([]),
  // Audio under public/. Wire at least one of voiceover/bgm so the video is not silent.
  voiceover: z.string().optional(),
  bgm: z.string().optional(),
  bgmVolume: z.number().default(0.12),
  durationInSeconds: z.number().default(8),
});

const FPS = 30;

const lastFrame = (props: { scenes?: { startFrame: number; durationInFrames: number }[]; durationInSeconds?: number }) => {
  if (props.scenes && props.scenes.length > 0) {
    return Math.max(...props.scenes.map((s) => s.startFrame + s.durationInFrames));
  }
  return Math.round((props.durationInSeconds ?? 8) * FPS);
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
    <Composition
      id="VideoStudio"
      component={DefaultVideo}
      durationInFrames={Math.round(8 * FPS)}
      fps={FPS}
      width={1080}
      height={1920}
      schema={defaultVideoSchema}
      // The voiceover is the source of truth for length: a video that is
      // shorter than its narration cuts the audio; longer leaves it silent.
      // Derive duration from the voiceover when present, else from captions.
      calculateMetadata={async ({ props }) => {
        let seconds = props.durationInSeconds ?? 8;
        if (props.voiceover) {
          try {
            seconds = await getAudioDurationInSeconds(staticFile(props.voiceover));
          } catch {
            // Keep the fallback if the audio cannot be read at metadata time.
          }
        } else if (props.captions && props.captions.length > 0) {
          seconds = Math.max(seconds, props.captions[props.captions.length - 1].end);
        }
        return { durationInFrames: Math.max(1, Math.round(seconds * FPS)) };
      }}
      defaultProps={{
        title: "Video Studio",
        subtitle: "Manifest driven render",
        // Replace with real cues, e.g. from scripts/captions_from_script.py.
        captions: [
          { text: "Put the script lines into captions", start: 0, end: 3 },
          { text: "Wire up subtitles, voiceover and BGM", start: 3, end: 6 },
        ],
        // Put files under public/audio/ and reference them here, or QA fails.
        voiceover: "",
        bgm: "",
        bgmVolume: 0.12,
        durationInSeconds: 8,
      }}
    />

    {/* Scene-by-scene composition. Feed it scene_timing.py --props-out so each
        scene's frame window matches its narration segment exactly. */}
    <Composition
      id="ScenesVideo"
      component={ScenesVideo}
      durationInFrames={Math.round(8 * FPS)}
      fps={FPS}
      width={1080}
      height={1920}
      schema={scenesVideoSchema}
      calculateMetadata={async ({ props }) => {
        let frames = lastFrame(props);
        if (props.voiceover) {
          try {
            frames = Math.round((await getAudioDurationInSeconds(staticFile(props.voiceover))) * FPS);
          } catch {
            // Keep the scene/caption-derived length if the audio cannot be read.
          }
        }
        return { durationInFrames: Math.max(1, frames) };
      }}
      defaultProps={{
        scenes: [
          { id: "s1", visual: "chart-a", text: "First narration line", startFrame: 0, durationInFrames: 60 },
          { id: "s2", visual: "chart-b", text: "Second narration line", startFrame: 60, durationInFrames: 105 },
          { id: "s3", visual: "chart-c", text: "Third narration line", startFrame: 165, durationInFrames: 45 },
        ],
        captions: [
          { text: "First narration line", start: 0, end: 2 },
          { text: "Second narration line", start: 2, end: 5.5 },
          { text: "Third narration line", start: 5.5, end: 7 },
        ],
        voiceover: "",
        bgm: "",
        bgmVolume: 0.12,
        durationInSeconds: 7,
      }}
    />
    </>
  );
};
