export type AgentType = 'presentation' | 'latex' | 'video';

export type JobStatus = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';

export interface VideoOptions {
  aspect_ratio?: string;
  target_duration_seconds?: number;
  /** 'kokoro' (local, Apache-2.0) or 'edge' (Edge-TTS cloud). Omit for the server default. */
  tts_engine?: string;
  /**
   * Narration language, 'en' or 'fr'. Drives the whole chain, not just the voice: the
   * director and screenwriter write the script in this language, the TTS engine picks the
   * matching voice and phonemiser, and subtitles follow from the narration text.
   */
  language?: string;
  /**
   * Apply the user's saved brand kit. The server resolves the kit and snapshots its
   * values into the job, so the video keeps the brand it was made with even if the kit
   * changes later.
   */
  use_brand_kit?: boolean;

  /**
   * Report cover page. Optional — a field left out keeps the PDF's bracketed placeholder
   * ("[Nom de l'étudiant]") rather than printing a blank line, so a student can see at a
   * glance which parts of the cover still need filling in.
   */
  student_name?: string;
  university?: string;
  supervisor?: string;
  co_supervisor?: string;
  academic_year?: string;
  degree?: string;
}

export interface JobCreate {
  prompt: string;
  agent_type: AgentType;
  /** Create the job without starting it, so media can be uploaded first. */
  defer_start?: boolean;
  video_options?: VideoOptions;
}

export interface Job {
  id: string;
  user_id: string;
  prompt: string;
  /**
   * Short display name generated from the prompt when the job was created.
   * Absent on jobs created before titles existed, so callers fall back to the prompt.
   */
  title?: string | null;
  /**
   * Relative path to the job's poster frame, or null when it cannot have one
   * (not completed, or not a video). Needs ?token= appended before use as an <img> src.
   */
  thumbnail_url?: string | null;
  agent_type: AgentType;
  status: JobStatus;
  progress_percent: number;
  current_step: string;
  /**
   * Alias of progress_percent — 0-100, advanced as each pipeline stage completes.
   * Optional so the UI keeps compiling against an older backend that predates these two
   * fields; consumers fall back to progress_percent / current_step.
   */
  progress?: number;
  /** Alias of current_step, e.g. "Collecting video footage...". */
  stage_label?: string;
  artifact_path?: string;
  /**
   * False once the deliverable is no longer on the server — swept by storage retention,
   * or removed by hand. The job is still COMPLETED (it did complete); there is simply
   * nothing left to download, so the button must not be offered.
   */
  artifact_available?: boolean;
  /** COMPLETED but the file is gone. Distinct from a job that never produced one. */
  artifact_expired?: boolean;
  /** When the artifact was found to be missing. */
  artifact_expired_at?: string | null;
  /**
   * The render settings this job was created with, parsed by the server. The Library's
   * re-run replays them so a regenerated 9:16 French video comes back 9:16 and French,
   * rather than silently reverting to the create page's defaults.
   */
  video_options?: VideoOptions | null;
  created_at: string;
  completed_at?: string;
}
