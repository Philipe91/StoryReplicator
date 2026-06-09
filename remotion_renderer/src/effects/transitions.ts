import { interpolate } from "remotion";
import { CSSProperties } from "react";
import { TransitionType } from "../types";

/** Retorna propriedades de opacidade para entrada de cena */
export function fadeInStyle(
  frame: number,
  transitionFrames: number,
): CSSProperties {
  if (transitionFrames <= 0) return {};
  const opacity = interpolate(frame, [0, transitionFrames], [0, 1], {
    extrapolateLeft:  "clamp",
    extrapolateRight: "clamp",
  });
  return { opacity };
}

/** Retorna propriedades de opacidade para saída de cena */
export function fadeOutStyle(
  frame:            number,
  durationInFrames: number,
  transitionFrames: number,
): CSSProperties {
  if (transitionFrames <= 0) return {};
  const startFade = durationInFrames - transitionFrames;
  const opacity   = interpolate(frame, [startFade, durationInFrames], [1, 0], {
    extrapolateLeft:  "clamp",
    extrapolateRight: "clamp",
  });
  return { opacity };
}

/** Combina fade in e fade out numa única propriedade */
export function sceneOpacity(
  frame:            number,
  durationInFrames: number,
  transitionIn:     TransitionType,
  transitionOut:    TransitionType,
  fps:              number = 30,
): CSSProperties {
  const frIn  = transitionIn  === "cut" ? 0 : transitionIn  === "fade" ? Math.round(fps * 0.4) : Math.round(fps * 0.5);
  const frOut = transitionOut === "cut" ? 0 : transitionOut === "fade" ? Math.round(fps * 0.4) : Math.round(fps * 0.5);

  let opacity = 1;

  if (frIn > 0 && frame < frIn) {
    opacity = frame / frIn;
  }
  if (frOut > 0 && frame > durationInFrames - frOut) {
    opacity = Math.min(opacity, (durationInFrames - frame) / frOut);
  }

  return { opacity: Math.max(0, Math.min(1, opacity)) };
}
