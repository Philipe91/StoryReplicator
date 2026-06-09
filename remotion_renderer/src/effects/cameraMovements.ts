import { interpolate, spring } from "remotion";
import { CSSProperties } from "react";
import { CameraMovement } from "../types";

// ─── Easing ───────────────────────────────────────────────────────────────────

function easeInOut(t: number): number {
  return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
}

function easeOut(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

// ─── Calculadora principal ───────────────────────────────────────────────────

export function getCameraStyle(
  movement:         CameraMovement,
  frame:            number,
  durationInFrames: number,
  intensity:        number = 0.7,
  speed:            number = 1.0,
  fps:              number = 30,
): CSSProperties {
  // Progresso normalizado [0, 1]
  const rawProgress = Math.min(1, frame / Math.max(durationInFrames, 1));
  const progress    = easeInOut(rawProgress);
  const fastProgress= easeOut(rawProgress);

  // Fator de escala do movimento (intensity * speed)
  const factor = intensity * speed;

  switch (movement) {
    // ── Ken Burns entrando ──────────────────────────────────────────────────
    case "slow_push_in": {
      const scale = interpolate(progress, [0, 1], [1, 1 + factor * 0.22]);
      return { transform: `scale(${scale})` };
    }

    // ── Ken Burns saindo ───────────────────────────────────────────────────
    case "slow_push_out": {
      const scale = interpolate(progress, [0, 1], [1 + factor * 0.22, 1]);
      return { transform: `scale(${scale})` };
    }

    // ── Pan esquerda ───────────────────────────────────────────────────────
    case "pan_left": {
      const x = interpolate(progress, [0, 1], [0, -factor * 8]);
      return { transform: `translateX(${x}%) scale(1.15)` };
    }

    // ── Pan direita ────────────────────────────────────────────────────────
    case "pan_right": {
      const x = interpolate(progress, [0, 1], [0, factor * 8]);
      return { transform: `translateX(${x}%) scale(1.15)` };
    }

    // ── Tilt para cima ─────────────────────────────────────────────────────
    case "tilt_up": {
      const y = interpolate(progress, [0, 1], [factor * 6, 0]);
      return { transform: `translateY(${y}%) scale(1.15)` };
    }

    // ── Tilt para baixo ────────────────────────────────────────────────────
    case "tilt_down": {
      const y = interpolate(progress, [0, 1], [0, factor * 6]);
      return { transform: `translateY(${y}%) scale(1.15)` };
    }

    // ── Parallax (zoom + deslocamento lateral) ─────────────────────────────
    case "parallax": {
      const scale = interpolate(progress, [0, 1], [1.2, 1.05]);
      const x     = interpolate(progress, [0, 1], [0, -factor * 5]);
      return { transform: `scale(${scale}) translateX(${x}%)` };
    }

    // ── Reveal com desfoque ────────────────────────────────────────────────
    case "focus_reveal": {
      const blur  = interpolate(rawProgress, [0, 0.35, 1], [8 * intensity, 0, 0], {
        extrapolateRight: "clamp",
      });
      const scale = interpolate(progress, [0, 1], [1.12, 1]);
      return {
        transform: `scale(${scale})`,
        filter:    `blur(${blur}px)`,
      };
    }

    // ── Zoom com profundidade ──────────────────────────────────────────────
    case "depth_zoom": {
      const scale = interpolate(fastProgress, [0, 1], [1, 1 + factor * 0.35]);
      const blur  = interpolate(rawProgress, [0, 0.15, 0.5, 1], [0, factor * 1.5, 0.5, 0]);
      return {
        transform: `scale(${scale})`,
        filter:    `blur(${blur}px)`,
      };
    }

    // ── Estático (leve drift) ──────────────────────────────────────────────
    case "static":
    default: {
      const scale = interpolate(progress, [0, 1], [1, 1.04]);
      return { transform: `scale(${scale})` };
    }
  }
}

// ─── Opacidade de transição ───────────────────────────────────────────────────

export function getTransitionOpacity(
  frame:            number,
  durationInFrames: number,
  transitionFrames: number = 10,
): number {
  return interpolate(
    frame,
    [0, transitionFrames, durationInFrames - transitionFrames, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
}

// ─── Número de frames por tipo de transição ──────────────────────────────────

export function transitionFrameCount(type: string, fps: number = 30): number {
  switch (type) {
    case "dissolve": return Math.round(fps * 0.5);    // 15 frames
    case "fade":     return Math.round(fps * 0.4);    // 12 frames
    case "cut":      return 0;
    default:         return 0;
  }
}
