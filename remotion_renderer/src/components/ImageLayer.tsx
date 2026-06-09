import React from "react";
import { useCurrentFrame, useVideoConfig, Img, staticFile } from "remotion";
import { getCameraStyle } from "../effects/cameraMovements";
import { EditDecision } from "../types";

interface Props {
  imageSrc:     string;
  editDecision: EditDecision;
  startFrame:   number;   // frame em que a cena começou no timeline global
}

export const ImageLayer: React.FC<Props> = ({ imageSrc, editDecision, startFrame }) => {
  const frame           = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const localFrame      = frame - startFrame;
  const sceneDuration   = Math.round(editDecision.duration * fps);

  const cameraStyle = getCameraStyle(
    editDecision.camera,
    Math.max(0, localFrame),
    Math.max(1, sceneDuration),
    editDecision.camera_intensity,
    editDecision.camera_speed,
    fps,
  );

  return (
    <div
      style={{
        position:   "absolute",
        inset:      0,
        overflow:   "hidden",
      }}
    >
      <Img
        src={staticFile(imageSrc)}
        style={{
          width:      "140%",
          height:     "140%",
          objectFit:  "cover",
          position:   "absolute",
          top:        "-20%",
          left:       "-20%",
          // Color grade: quente e cinematográfico
          filter:     "sepia(0.18) contrast(1.08) saturate(0.88) brightness(0.96)",
          transformOrigin: "center center",
          ...cameraStyle,
        }}
      />
      {/* Film grain overlay */}
      <FilmGrain />
      {/* Vinheta suave */}
      <Vignette />
    </div>
  );
};

// ─── Film grain (noise CSS) ───────────────────────────────────────────────────
const FilmGrain: React.FC = () => (
  <div
    style={{
      position: "absolute",
      inset:    0,
      opacity:  0.12,
      mixBlendMode: "overlay" as const,
      backgroundImage:
        "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
      pointerEvents: "none",
    }}
  />
);

// ─── Vinheta ──────────────────────────────────────────────────────────────────
const Vignette: React.FC = () => (
  <div
    style={{
      position:   "absolute",
      inset:      0,
      background: "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.45) 100%)",
      pointerEvents: "none",
    }}
  />
);
