import React from "react";
import { useCurrentFrame, useVideoConfig, Img, staticFile, interpolate } from "remotion";

interface Props {
  brollSrc:  string;
  position:  "top-right" | "bottom-left" | "bottom-right";
  startSec:  number;
  endSec:    number;
  overlayType: "document" | "newspaper" | "map" | "portrait";
}

export const BrollOverlay: React.FC<Props> = ({
  brollSrc,
  position,
  startSec,
  endSec,
  overlayType,
}) => {
  const frame       = useCurrentFrame();
  const { fps }     = useVideoConfig();
  const currentSec  = frame / fps;

  if (currentSec < startSec || currentSec > endSec) return null;

  const localProgress = (currentSec - startSec) / Math.max(endSec - startSec, 0.01);

  // Fade in/out suave
  const opacity = interpolate(
    localProgress,
    [0, 0.15, 0.85, 1],
    [0, 0.88, 0.88, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Leve rotação para documento (parecer autêntico)
  const rotation = overlayType === "document" ? -2.5 : overlayType === "newspaper" ? 1.5 : 0;

  return (
    <div
      style={{
        position:    "absolute",
        ...POSITION_STYLES[position],
        opacity,
        transform:   `rotate(${rotation}deg)`,
        zIndex:      50,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          position:     "relative",
          overflow:     "hidden",
          borderRadius: overlayType === "portrait" ? "50%" : "4px",
          boxShadow:    "0 8px 32px rgba(0,0,0,0.6), 0 2px 8px rgba(0,0,0,0.4)",
          border:       overlayType === "document" ? "2px solid rgba(255,255,210,0.6)" : "none",
        }}
      >
        <Img
          src={staticFile(brollSrc)}
          style={{
            ...SIZE_STYLES[overlayType],
            objectFit:  "cover",
            filter:     "sepia(0.3) contrast(1.1) brightness(0.9)",
          }}
        />
        {/* Overlay escuro nas bordas */}
        <div
          style={{
            position: "absolute",
            inset:    0,
            background: "radial-gradient(ellipse at center, transparent 60%, rgba(0,0,0,0.3) 100%)",
          }}
        />
      </div>
    </div>
  );
};

// ─── Estilos de posição ───────────────────────────────────────────────────────

const POSITION_STYLES: Record<string, React.CSSProperties> = {
  "top-right":    { top: "8%",  right:  "4%"  },
  "bottom-left":  { bottom: "22%", left: "4%"  },
  "bottom-right": { bottom: "22%", right: "4%"  },
};

const SIZE_STYLES: Record<string, React.CSSProperties> = {
  document:  { width: "240px", height: "320px" },
  newspaper: { width: "260px", height: "200px" },
  map:       { width: "220px", height: "220px" },
  portrait:  { width: "180px", height: "180px" },
};
