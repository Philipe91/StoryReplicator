import React from "react";
import { AbsoluteFill, staticFile, Video, useCurrentFrame, useVideoConfig } from "remotion";
import { ImageLayer } from "./ImageLayer";
import { BrollOverlay } from "./BrollOverlay";
import { sceneOpacity } from "../effects/transitions";
import { TimelineScene, EditDecision } from "../types";

interface Props {
  scene:        TimelineScene;
  editDecision: EditDecision;
  startFrame:   number;   // frame global em que esta cena começa
}

export const SceneRenderer: React.FC<Props> = ({ scene, editDecision, startFrame }) => {
  const frame              = useCurrentFrame();
  const { fps }            = useVideoConfig();
  const localFrame         = frame - startFrame;
  const sceneDurationFrames = Math.round(scene.duration * fps);

  // Opacidade de transição
  const opacityStyle = sceneOpacity(
    localFrame,
    sceneDurationFrames,
    editDecision.transition_in,
    editDecision.transition_out,
    fps,
  );

  // Determina se usa vídeo ou imagem
  const hasVideo = scene.asset_type === "video" && scene.video_file;
  const hasImage = !hasVideo && scene.image_file;

  return (
    <AbsoluteFill style={{ ...opacityStyle }}>
      {/* Camada base: imagem ou vídeo */}
      {hasVideo ? (
        <AbsoluteFill>
          <Video
            src={staticFile(scene.video_file)}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
            volume={0}   // sem áudio do vídeo histórico — usamos áudio narração
          />
        </AbsoluteFill>
      ) : hasImage ? (
        <ImageLayer
          imageSrc={scene.image_file}
          editDecision={editDecision}
          startFrame={startFrame}
        />
      ) : (
        <PlaceholderBackground text={scene.subtitle || `Cena ${scene.scene_id}`} />
      )}

      {/* Camadas de B-roll (sobreposição documental) */}
      {editDecision.layers.includes("document_overlay") && (
        <BrollOverlay
          brollSrc={`broll/broll_${String(scene.scene_id).padStart(2, "0")}_doc.jpg`}
          position="top-right"
          startSec={scene.start + scene.duration * 0.2}
          endSec={scene.end - scene.duration * 0.1}
          overlayType="document"
        />
      )}
    </AbsoluteFill>
  );
};

// ─── Placeholder quando não há asset ─────────────────────────────────────────

const PlaceholderBackground: React.FC<{ text: string }> = ({ text }) => (
  <AbsoluteFill
    style={{
      background:      "linear-gradient(135deg, #0a0a1a 0%, #1a1a3a 100%)",
      display:         "flex",
      alignItems:      "center",
      justifyContent:  "center",
    }}
  >
    <div
      style={{
        fontFamily: "Arial, sans-serif",
        fontSize:   "48px",
        color:      "rgba(255,255,255,0.3)",
        textAlign:  "center",
        padding:    "40px",
      }}
    >
      {text}
    </div>
  </AbsoluteFill>
);
