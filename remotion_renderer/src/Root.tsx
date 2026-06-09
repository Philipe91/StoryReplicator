import React from "react";
import { Composition } from "remotion";
import { DocumentaryVideo } from "./compositions/DocumentaryVideo";
import { CompositionProps } from "./types";

const DEFAULT_PROPS: CompositionProps = {
  fps:           30,
  width:         1080,
  height:        1920,
  totalFrames:   5400,   // 180s × 30fps — overridden at render time
  subtitleStyle: "CINEMATIC",
};

export const RemotionRoot: React.FC = () => (
  <Composition
    id="DocumentaryVideo"
    component={DocumentaryVideo}
    durationInFrames={DEFAULT_PROPS.totalFrames}
    fps={DEFAULT_PROPS.fps}
    width={DEFAULT_PROPS.width}
    height={DEFAULT_PROPS.height}
    defaultProps={DEFAULT_PROPS}
    calculateMetadata={({ props }) => ({
      durationInFrames: props.totalFrames,
      fps:   props.fps,
      width: props.width,
      height: props.height,
    })}
  />
);
