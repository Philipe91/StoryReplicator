"use client";

import { Player } from "@remotion/player";
import { MainVideo } from "@/remotion/Composition";

export function VideoPreview() {
  return (
    <div className="w-full h-full flex items-center justify-center bg-black/50 border border-border rounded-xl overflow-hidden shadow-2xl">
      <Player
        component={MainVideo}
        inputProps={{
          titleText: "StoryReplicator Studio",
          titleColor: "white",
        }}
        durationInFrames={300}
        compositionWidth={1080}
        compositionHeight={1920}
        fps={30}
        controls
        style={{
          width: "auto",
          height: "100%",
          maxHeight: "60vh",
          aspectRatio: "9/16",
        }}
      />
    </div>
  );
}
