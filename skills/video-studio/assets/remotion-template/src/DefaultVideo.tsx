import React from "react";
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from "remotion";
import { Captions, type Caption } from "./Captions";

export type DefaultVideoProps = {
  title: string;
  subtitle?: string;
  /** Caption cues in seconds. Required for narrative/social videos. */
  captions: Caption[];
  /** Narration audio under public/, e.g. "audio/voiceover.mp3". Empty = no narration. */
  voiceover?: string;
  /** Background music under public/, e.g. "audio/bgm.mp3". Empty = no music. */
  bgm?: string;
  /** BGM gain. Keep low (0.08-0.18) so it sits under narration. */
  bgmVolume?: number;
};

/**
 * Default scaffold. The audio (<Audio>) and <Captions> layers are deliberately
 * wired in so a generated video ships with SOUND, SUBTITLES, and MUSIC by
 * default. If you remove them the QA gate (scripts/qa_video.py) will FAIL the
 * render. Set `voiceover`/`bgm` to real files under public/ and pass `captions`.
 */
export const DefaultVideo: React.FC<DefaultVideoProps> = ({
  title,
  subtitle,
  captions,
  voiceover,
  bgm,
  bgmVolume = 0.12,
}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 24], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const translateY = interpolate(frame, [0, 24], [32, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return (
    <AbsoluteFill
      style={{
        background: "#111111",
        color: "white",
        justifyContent: "center",
        alignItems: "center",
        padding: 96,
        fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      <div
        style={{
          opacity,
          translate: `0 ${translateY}px`,
          textAlign: "center",
          maxWidth: 860,
        }}
      >
        <h1 style={{ fontSize: 92, lineHeight: 1.05, margin: 0 }}>{title}</h1>
        {subtitle ? (
          <p style={{ fontSize: 42, lineHeight: 1.2, opacity: 0.82 }}>{subtitle}</p>
        ) : null}
      </div>

      {/* Subtitle track — authored from the script, never silent-by-omission. */}
      <Captions captions={captions} />

      {/* Voiceover at full level. */}
      {voiceover ? <Audio src={staticFile(voiceover)} /> : null}

      {/* Background music, looped and ducked under narration. */}
      {bgm ? <Audio src={staticFile(bgm)} volume={bgmVolume} loop /> : null}
    </AbsoluteFill>
  );
};
