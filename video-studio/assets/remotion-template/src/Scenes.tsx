import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { Captions, type Caption } from "./Captions";

export type Scene = {
  id: string;
  /** Logical visual key the agent maps to a custom component. */
  visual?: string;
  title?: string;
  /** The narration text for this scene (shown for reference / fallback). */
  text?: string;
  startFrame: number;
  durationInFrames: number;
};

export type ScenesVideoProps = {
  scenes: Scene[];
  captions: Caption[];
  voiceover?: string;
  bgm?: string;
  bgmVolume?: number;
  durationInSeconds?: number;
};

/**
 * One <Sequence> per scene, each placed at the frame window that matches its
 * narration segment (from scripts/scene_timing.py). A single concatenated
 * voiceover plays across the whole composition, so the scene on screen ALWAYS
 * matches the segment being spoken — "wrong scene under narration" cannot happen
 * because both come from the same timeline. Build scenes/captions/voiceover with
 * scene_timing.py and pass its --props-out JSON straight in.
 */
export const ScenesVideo: React.FC<ScenesVideoProps> = ({
  scenes,
  captions,
  voiceover,
  bgm,
  bgmVolume = 0.12,
}) => {
  return (
    <AbsoluteFill style={{ background: "#0b0b0f" }}>
      {scenes.map((scene) => (
        <Sequence
          key={scene.id}
          from={scene.startFrame}
          durationInFrames={scene.durationInFrames}
          name={scene.id}
        >
          <SceneCard scene={scene} />
        </Sequence>
      ))}

      {/* Captions and audio span the whole timeline. */}
      <Captions captions={captions} />
      {voiceover ? <Audio src={staticFile(voiceover)} /> : null}
      {bgm ? <Audio src={staticFile(bgm)} volume={bgmVolume} loop /> : null}
    </AbsoluteFill>
  );
};

/**
 * Default scene renderer. Replace the body with a real visual per `scene.visual`
 * (chart, image, code, etc.); keep it inside the Sequence so timing is fixed.
 */
const SceneCard: React.FC<{ scene: Scene }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const enter = interpolate(frame, [0, 16], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        padding: 96,
        color: "white",
        fontFamily: '"Noto Sans CJK SC", "PingFang SC", system-ui, sans-serif',
        opacity: enter,
      }}
    >
      <div style={{ textAlign: "center", maxWidth: 900 }}>
        <div style={{ fontSize: 34, opacity: 0.55, marginBottom: 24 }}>{scene.visual ?? scene.id}</div>
        <h1 style={{ fontSize: 84, lineHeight: 1.1, margin: 0 }}>{scene.title ?? scene.text}</h1>
      </div>
    </AbsoluteFill>
  );
};
