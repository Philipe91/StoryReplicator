import { AbsoluteFill, useVideoConfig, useCurrentFrame, spring } from "remotion";

export const MainVideo: React.FC<{ titleText: string; titleColor: string }> = ({
  titleText,
  titleColor,
}) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();

  const opacity = spring({
    frame,
    fps,
    config: {
      damping: 100,
    },
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#09090B",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <h1
        style={{
          color: titleColor,
          fontFamily: "sans-serif",
          fontSize: 60,
          fontWeight: "bold",
          opacity,
          textAlign: "center",
          padding: "0 40px",
        }}
      >
        {titleText}
      </h1>
      <p style={{ color: "#A1A1AA", fontSize: 32, marginTop: 20 }}>
        Frame atual: {frame}
      </p>
    </AbsoluteFill>
  );
};
