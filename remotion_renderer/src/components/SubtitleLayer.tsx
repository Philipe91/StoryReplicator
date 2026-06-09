import React, { CSSProperties } from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { SubtitleEntry, SubtitleStyle } from "../types";

interface Props {
  entries: SubtitleEntry[];
}

export const SubtitleLayer: React.FC<Props> = ({ entries }) => {
  const frame            = useCurrentFrame();
  const { fps, height }  = useVideoConfig();
  const currentSec       = frame / fps;

  const active = entries.find(
    (e) => currentSec >= e.start && currentSec <= e.end + 0.05,
  );

  if (!active) return null;

  const localProgress = (currentSec - active.start) / Math.max(active.end - active.start, 0.01);

  return (
    <SubtitleBlock
      entry={active}
      currentSec={currentSec}
      progress={localProgress}
      height={height}
    />
  );
};

// ─── Bloco de legenda individual ──────────────────────────────────────────────

interface BlockProps {
  entry:      SubtitleEntry;
  currentSec: number;
  progress:   number;
  height:     number;
}

const SubtitleBlock: React.FC<BlockProps> = ({ entry, currentSec, progress, height }) => {
  const style = entry.style ?? "CINEMATIC";

  // Animação de entrada (fade + slide up)
  const opacity     = interpolate(progress, [0, 0.12, 0.88, 1], [0, 1, 1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const translateY  = interpolate(progress, [0, 0.12], [14, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position:    "absolute",
        left:        0,
        right:       0,
        bottom:      style === "CINEMATIC" ? "14%" : "10%",
        display:     "flex",
        justifyContent: "center",
        alignItems:  "center",
        padding:     "0 32px",
        opacity,
        transform:   `translateY(${translateY}px)`,
        zIndex:      100,
        pointerEvents: "none",
      }}
    >
      <SubtitleText entry={entry} currentSec={currentSec} style={style} />
    </div>
  );
};

// ─── Texto com word highlighting ──────────────────────────────────────────────

interface TextProps {
  entry:      SubtitleEntry;
  currentSec: number;
  style:      SubtitleStyle;
}

const SubtitleText: React.FC<TextProps> = ({ entry, currentSec, style }) => {
  const containerStyle = CONTAINER_STYLES[style];
  const wordStyle      = WORD_STYLES[style];
  const activeStyle    = ACTIVE_WORD_STYLES[style];
  const words          = entry.word_timings?.length ? entry.word_timings : null;

  if (!words) {
    return (
      <div style={containerStyle}>
        <span style={wordStyle}>{entry.text}</span>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {words.map((wt, i) => {
        const isActive = currentSec >= wt.start && currentSec <= wt.end;
        const isPast   = currentSec > wt.end;
        return (
          <span
            key={i}
            style={{
              ...wordStyle,
              ...(isActive ? activeStyle : {}),
              ...(isPast && style === "MODERN_SHORTS" ? { opacity: 0.7 } : {}),
            }}
          >
            {wt.word}{" "}
          </span>
        );
      })}
    </div>
  );
};

// ─── Estilos por modo ─────────────────────────────────────────────────────────

const CONTAINER_STYLES: Record<SubtitleStyle, CSSProperties> = {
  DOCUMENTARY: {
    display:         "flex",
    flexWrap:        "wrap",
    justifyContent:  "center",
    textAlign:       "center",
    gap:             "0 4px",
    maxWidth:        "900px",
    padding:         "10px 20px",
    background:      "rgba(0, 0, 0, 0.0)",
    borderRadius:    "4px",
  },
  CINEMATIC: {
    display:         "flex",
    flexWrap:        "wrap",
    justifyContent:  "center",
    textAlign:       "center",
    gap:             "0 4px",
    maxWidth:        "940px",
    padding:         "14px 28px",
    background:      "rgba(0, 0, 0, 0.55)",
    borderRadius:    "6px",
    backdropFilter:  "blur(2px)",
  },
  MODERN_SHORTS: {
    display:         "flex",
    flexWrap:        "wrap",
    justifyContent:  "center",
    textAlign:       "center",
    gap:             "0 6px",
    maxWidth:        "960px",
    padding:         "8px 16px",
  },
};

const WORD_STYLES: Record<SubtitleStyle, CSSProperties> = {
  DOCUMENTARY: {
    fontFamily:      "'Georgia', 'Times New Roman', serif",
    fontSize:        "64px",
    fontWeight:      "400",
    color:           "#FFFFFF",
    textShadow:      "2px 2px 6px rgba(0,0,0,0.95), 0 0 20px rgba(0,0,0,0.7)",
    lineHeight:      1.25,
    letterSpacing:   "0.01em",
    display:         "inline-block",
  },
  CINEMATIC: {
    fontFamily:      "'Arial', 'Helvetica Neue', sans-serif",
    fontSize:        "72px",
    fontWeight:      "700",
    color:           "#FFFFFF",
    textShadow:      "0 0 0 transparent",
    lineHeight:      1.2,
    letterSpacing:   "0.02em",
    display:         "inline-block",
  },
  MODERN_SHORTS: {
    fontFamily:      "'Impact', 'Arial Black', 'Arial', sans-serif",
    fontSize:        "80px",
    fontWeight:      "900",
    color:           "#FFFFFF",
    // Contorno pesado (método cross-shadow)
    textShadow:      "-3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 3px 3px 0 #000, 0 0 12px rgba(0,0,0,0.8)",
    lineHeight:      1.1,
    letterSpacing:   "0.04em",
    textTransform:   "uppercase" as const,
    display:         "inline-block",
  },
};

const ACTIVE_WORD_STYLES: Record<SubtitleStyle, CSSProperties> = {
  DOCUMENTARY: {
    color:      "#FFE066",
    textShadow: "2px 2px 6px rgba(0,0,0,0.95), 0 0 20px rgba(255,200,0,0.4)",
  },
  CINEMATIC: {
    color:      "#00D4FF",
    background: "rgba(0, 180, 230, 0.15)",
    borderRadius: "3px",
    padding:    "0 2px",
  },
  MODERN_SHORTS: {
    color:      "#FFD700",
    textShadow: "-3px -3px 0 #000, 3px -3px 0 #000, -3px 3px 0 #000, 3px 3px 0 #000, 0 0 20px rgba(255,200,0,0.5)",
    transform:  "scale(1.08)",
  },
};
