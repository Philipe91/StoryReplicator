// StoryReplicator v3.5 — Shared TypeScript types

export type CameraMovement =
  | "slow_push_in"
  | "slow_push_out"
  | "pan_left"
  | "pan_right"
  | "tilt_up"
  | "tilt_down"
  | "parallax"
  | "focus_reveal"
  | "depth_zoom"
  | "static";

export type SubtitleStyle = "DOCUMENTARY" | "CINEMATIC" | "MODERN_SHORTS";

export type TransitionType = "cut" | "fade" | "dissolve";

export type AssetType = "image" | "video";

export interface TimelineScene {
  scene_id:       number;
  start:          number;   // seconds
  end:            number;
  duration:       number;
  segment:        string;
  emotion:        string;
  asset_type:     AssetType;
  voice:          string;   // narration text for this scene
  subtitle:       string;   // short subtitle label
  image_file:     string;   // path relative to /public
  video_file:     string;
  visual_type:    string;
  transition_in:  string;
  transition_out: string;
  camera_angle:   string;
  needs_visual_variety: boolean;
}

export interface Timeline {
  version:        string;
  mode:           string;
  total_duration: number;
  audio_duration: number;
  resolution:     string;
  fps:            number;
  audio_file:     string;
  scenes:         TimelineScene[];
}

export interface EditDecision {
  scene_id:         number;
  segment:          string;
  emotion:          string;
  camera:           CameraMovement;
  camera_intensity: number;   // 0.0 – 1.0
  camera_speed:     number;   // 0.5 – 2.0
  transition_in:    TransitionType;
  transition_out:   TransitionType;
  subtitle_style:   SubtitleStyle;
  rhythm:           "slow" | "medium" | "fast";
  broll_needed:     boolean;
  broll_queries:    string[];
  duration:         number;
  layers:           string[];
}

export interface EditingTimeline {
  version:      string;
  total_scenes: number;
  decisions:    EditDecision[];
}

export interface WordTiming {
  word:  string;
  start: number;
  end:   number;
}

export interface SubtitleEntry {
  start:        number;
  end:          number;
  text:         string;
  style:        SubtitleStyle;
  word_timings: WordTiming[];
}

export interface SubtitlesData {
  version: string;
  entries: SubtitleEntry[];
}

export interface CompositionProps {
  fps:           number;
  width:         number;
  height:        number;
  totalFrames:   number;
  subtitleStyle: SubtitleStyle;
}
