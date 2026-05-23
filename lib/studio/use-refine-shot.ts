'use client';

/**
 * use-refine-shot — Client wrapper for POST /api/v1/director/refine.
 *
 * Triggered from the Evaluation tab or per-shot "Refine" button. Sends the
 * full plan + a target shot_id + optional `shot_overrides` (shallow merge)
 * + optional `previous_last_frame_url` (so the refined clip keeps identity
 * continuity with the prior shot from the original render).
 *
 * Polls /director/jobs/{id} until done; exposes a single `state` object so
 * the drawer can show "rendering 60% → uploading → done (url)".
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { DirectorPlan } from './use-director-plan';
import type { VideoSettings } from '@/lib/types/backend';

export interface RefineRequest {
  plan: DirectorPlan;
  shot_id: string;
  reference_images: string[];
  settings: VideoSettings;
  previous_last_frame_url?: string | null;
  shot_overrides?: {
    duration_s?: number;
    visual?: { action?: string; subject?: string; camera_shot?: string; camera_movement?: string };
    audio?: { dialogue_vn?: string | null; caption_on_screen?: string | null };
    continuity?: { reference_indices?: number[] };
  };
  use_llm_scene_gen?: boolean;
}

export type RefineStatus =
  | 'idle'
  | 'submitting'
  | 'pending'
  | 'rendering'
  | 'uploading'
  | 'done'
  | 'failed'
  | 'cancelled';

export interface RefineState {
  jobId: string | null;
  status: RefineStatus;
  progress: number;             // 0-100
  currentStep?: string;
  outputUrl?: string;            // R2 or file:// from refine_result
  videoUrl?: string;             // AtlasCloud-hosted clip
  lastFrameUrl?: string;
  error?: string;
}

const INITIAL: RefineState = { jobId: null, status: 'idle', progress: 0 };

export function useRefineShot() {
  const [state, setState] = useState<RefineState>(INITIAL);
  const pollAbort = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    pollAbort.current?.abort();
    setState(INITIAL);
  }, []);

  const refine = useCallback(async (req: RefineRequest) => {
    reset();
    setState({ ...INITIAL, status: 'submitting' });
    try {
      const res = await fetch('/api/v1/director/refine', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan: req.plan,
          shot_id: req.shot_id,
          reference_images: req.reference_images,
          settings: req.settings,
          previous_last_frame_url: req.previous_last_frame_url ?? null,
          shot_overrides: req.shot_overrides,
          use_llm_scene_gen: req.use_llm_scene_gen ?? true,
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`HTTP ${res.status}: ${detail.slice(0, 200)}`);
      }
      const body = await res.json();
      const jobId: string = body.job_id;
      setState({ jobId, status: 'rendering', progress: 5 });

      // Start polling
      const ctrl = new AbortController();
      pollAbort.current = ctrl;
      void pollJob(jobId, ctrl, setState);
    } catch (e) {
      setState({ ...INITIAL, status: 'failed', error: e instanceof Error ? e.message : String(e) });
    }
  }, [reset]);

  // Cleanup on unmount
  useEffect(() => {
    return () => pollAbort.current?.abort();
  }, []);

  return { state, refine, reset };
}

// ============================================================
// Internal poll loop
// ============================================================
async function pollJob(
  jobId: string,
  ctrl: AbortController,
  setState: (next: RefineState | ((prev: RefineState) => RefineState)) => void,
) {
  const interval = 2500;
  while (!ctrl.signal.aborted) {
    try {
      const r = await fetch(`/api/v1/director/jobs/${jobId}`, { signal: ctrl.signal });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      const status = (j.status as RefineState['status']) || 'rendering';
      const progress = typeof j.progress === 'number' ? j.progress : 0;
      const result = j.refine_result;
      setState((prev) => ({
        ...prev,
        status,
        progress,
        currentStep: j.current_step,
        outputUrl: j.output_url ?? result?.output_url ?? result?.video_url,
        videoUrl: result?.video_url,
        lastFrameUrl: result?.last_frame_url,
        error: j.error_message,
      }));
      if (status === 'done' || status === 'failed' || status === 'cancelled') {
        return;
      }
    } catch (e) {
      if (ctrl.signal.aborted) return;
      // Network blip — keep polling
    }
    await new Promise((res) => setTimeout(res, interval));
  }
}
