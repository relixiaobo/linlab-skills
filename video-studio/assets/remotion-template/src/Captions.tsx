import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

export type Caption = {
  text: string;
  /** Seconds from the start of the composition. */
  start: number;
  end: number;
};

/**
 * Burned-in caption layer. This is a REQUIRED layer for narrative/social
 * videos — do not delete it. Feed it captions authored from the script
 * (see scripts/captions_from_script.py) or from an external transcript.
 *
 * captionZone keeps text inside the platform safe area (fraction of height).
 */
export const Captions: React.FC<{
  captions: Caption[];
  captionZone?: { yMin: number; yMax: number };
  fontFamily?: string;
}> = ({ captions, captionZone = { yMin: 0.66, yMax: 0.84 }, fontFamily }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const t = frame / fps;

  const active = captions.find((c) => t >= c.start && t < c.end);
  if (!active) return null;

  const bottom = Math.round(height * (1 - captionZone.yMax));

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: "7%",
          right: "7%",
          bottom,
          display: "flex",
          justifyContent: "center",
        }}
      >
        <span
          style={{
            fontFamily: fontFamily ?? '"Noto Sans CJK SC", "PingFang SC", system-ui, sans-serif',
            fontWeight: 800,
            fontSize: Math.round(height * 0.042),
            lineHeight: 1.3,
            color: "white",
            textAlign: "center",
            padding: "0.3em 0.6em",
            borderRadius: 16,
            background: "rgba(0,0,0,0.5)",
            // Stroke for legibility over any background.
            WebkitTextStroke: "2px rgba(0,0,0,0.55)",
            paintOrder: "stroke fill",
            textShadow: "0 2px 8px rgba(0,0,0,0.6)",
          }}
        >
          {active.text}
        </span>
      </div>
    </AbsoluteFill>
  );
};
