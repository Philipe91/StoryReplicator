import React, { useEffect, useMemo, useState } from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  staticFile,
  useVideoConfig,
  delayRender,
  continueRender,
} from "remotion";
import { SceneRenderer }   from "../components/SceneRenderer";
import { SubtitleLayer }   from "../components/SubtitleLayer";
import { transitionFrameCount } from "../effects/cameraMovements";
import {
  Timeline,
  EditingTimeline,
  SubtitlesData,
  CompositionProps,
  EditDecision,
} from "../types";

// ─── Carregamento assíncrono de JSON via staticFile + fetch ───────────────────
// Padrão correto do Remotion: usar delayRender enquanto os dados carregam.

function useStaticJson<T>(filename: string, fallback: T): T {
  const [data, setData]   = useState<T>(fallback);
  const [handle]          = useState(() => delayRender(`load-${filename}`));

  useEffect(() => {
    let cancelled = false;
    fetch(staticFile(filename))
      .then((res) => (res.ok ? res.json() : fallback))
      .then((json) => {
        if (!cancelled) {
          setData(json as T);
          continueRender(handle);
        }
      })
      .catch(() => {
        if (!cancelled) continueRender(handle);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return data;
}

// ─── Composição principal ─────────────────────────────────────────────────────

export const DocumentaryVideo: React.FC<CompositionProps> = ({
  fps: fpsProp,
  subtitleStyle,
}) => {
  const { fps, durationInFrames } = useVideoConfig();
  const resolvedFps = fpsProp ?? fps;

  const timeline: Timeline = useStaticJson("timeline.json", {
    version: "", mode: "", total_duration: 0, audio_duration: 0,
    resolution: "", fps: resolvedFps, audio_file: "audio.wav",
    scenes: [],
  });

  const editingData: EditingTimeline = useStaticJson("editing_timeline.json", {
    version: "", total_scenes: 0, decisions: [],
  });

  const subtitlesData: SubtitlesData = useStaticJson("subtitles.json", {
    version: "", entries: [],
  });

  // Mapa de decisões de edição por scene_id
  const editMap = useMemo<Record<number, EditDecision>>(() => {
    const map: Record<number, EditDecision> = {};
    for (const d of editingData.decisions) {
      map[d.scene_id] = d;
    }
    return map;
  }, [editingData]);

  const scenes = timeline.scenes ?? [];

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {/* ── Cenas ────────────────────────────────────────────────────────── */}
      {scenes.map((scene) => {
        // Fallback seguro: sem decisão do Editor AI (arquivo ausente ou
        // scene_id sem correspondência), a cena renderiza com uma decisão
        // neutra em vez de sumir (antes: return null → vídeo preto).
        const editDecision: EditDecision = editMap[scene.scene_id] ?? {
          scene_id:         scene.scene_id,
          segment:          scene.segment ?? "",
          emotion:          scene.emotion ?? "mystery",
          camera:           "slow_push_in" as EditDecision["camera"],
          camera_intensity: 0.5,
          camera_speed:     1.0,
          transition_in:    "fade" as EditDecision["transition_in"],
          transition_out:   "fade" as EditDecision["transition_out"],
          subtitle_style:   "CINEMATIC" as EditDecision["subtitle_style"],
          rhythm:           "medium",
          broll_needed:     false,
          broll_queries:    [],
          duration:         scene.duration,
          layers:           [],
        };

        const startFrame     = Math.round(scene.start * resolvedFps);
        const durationFrames = Math.round(scene.duration * resolvedFps);
        const transIn        = transitionFrameCount(editDecision.transition_in,  resolvedFps);
        const transOut       = transitionFrameCount(editDecision.transition_out, resolvedFps);

        // A Sequence começa um pouco antes para overlap das transições
        const seqFrom     = Math.max(0, startFrame - transIn);
        const seqDuration = durationFrames + transIn + transOut;

        return (
          <Sequence
            key={scene.scene_id}
            from={seqFrom}
            durationInFrames={seqDuration}
            layout="none"
          >
            <SceneRenderer
              scene={scene}
              editDecision={editDecision}
              startFrame={startFrame - seqFrom}
            />
          </Sequence>
        );
      })}

      {/* ── Legendas (sempre no topo) ─────────────────────────────────────── */}
      <SubtitleLayer entries={subtitlesData.entries} />

      {/* ── Áudio narração ───────────────────────────────────────────────── */}
      <Audio src={staticFile(timeline.audio_file ?? "audio.wav")} />
    </AbsoluteFill>
  );
};
