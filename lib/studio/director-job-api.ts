'use client';

export interface DirectorPlan {
  plan_id?: string;
  created_at?: string;
  continuity_bible?: {
    title?: string;
    logline?: string;
    intent?: string;
    duration_s?: number;
    [key: string]: unknown;
  };
  shot_list?: Array<Record<string, unknown>>;
  storyboard_grid?: Array<Record<string, unknown>>;
  evaluation?: Record<string, unknown>;
  elapsed_s?: number;
  [key: string]: unknown;
}

export async function fetchDirectorJob(jobId: string) {
  const res = await fetch(`/api/v1/director/jobs/${jobId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
