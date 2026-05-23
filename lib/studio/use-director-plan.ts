'use client';

/**
 * use-director-plan — V3 hook for POST /api/v1/director/plan/stream.
 *
 * Replaces the legacy use-propose-job hook (which targeted the removed
 * /api/v1/jobs/propose endpoint).
 *
 * Flow:
 *   1. createPlan({ ... })  → SSE stream events: stage / complete / error
 *   2. progress updates per stage (init → vision → director → evaluation)
 *   3. final DirectorPlan returned in `plan`
 *   4. user reviews Continuity Bible + Shot List in DirectorPlanTab
 *   5. user clicks Approve → caller fires POST /api/v1/director/generate
 */

import { useCallback, useRef, useState } from 'react';
import type { VideoSettings } from '@/lib/types/backend';

// ============================================================
// Schemas mirror backend agent/schemas.py
// ============================================================
export interface Character {
  id: string;
  name: string;
  role: string;
  age_apparent?: string;
  gender?: string;
  face_signature: string;
  outfit: string;
  voice_persona?: string;
  personality: string[];
}

export interface Product {
  id: string;
  name: string;
  hero_features: string[];
  packaging_description: string;
  color_palette: string[];
  forbidden_claims: string[];
}

export interface VisualStyle {
  cinematography: string;
  color_grading: string;
  lighting_design: string;
  camera_language: string;
  film_grain: string;
  aspect_ratio: string;
}

export interface AudioDesign {
  mood: string;
  tempo: string;
  music_genre: string;
  sfx_emphasis: string[];
  dialogue_style: string;
}

export interface ReferenceAsset {
  index: number;
  url: string;
  role: string;
  apply_to_shots: string[];
  notes: string;
}

export interface ContinuityBible {
  title: string;
  logline: string;
  intent: string;
  duration_s: number;
  aspect_ratio: string;
  characters: Character[];
  products: Product[];
  visual_style: VisualStyle;
  audio_design: AudioDesign;
  setting: { location: string; time_of_day: string; atmosphere: string };
  constraints: { must_have: string[]; must_avoid: string[]; brand_safety: string[] };
  reference_assets: ReferenceAsset[];
  director_notes: string;
}

export interface Shot {
  shot_id: string;
  index: number;
  start_s: number;
  end_s: number;
  duration_s: number;
  purpose: string;
  emotion_beat: string;
  visual: {
    subject: string;
    action: string;
    camera_shot: string;
    camera_movement: string;
    composition: string;
    lighting_override: string | null;
    background: string;
  };
  audio: {
    dialogue_vn: string | null;
    caption_on_screen: string | null;
    sfx: string[];
    music_cue?: string;
  };
  continuity: {
    character_ids: string[];
    product_ids: string[];
    reference_indices: number[];
    previous_shot_id: string | null;
    style_anchor: string;
  };
  model_routing: { preferred_model: string; reasoning: string };
}

export interface StoryboardFrame {
  shot_id: string;
  prompt: string;
  image_size: string;
  user_uploaded_url: string | null;
  generated_url: string | null;
}

export interface EvaluationReport {
  consistency_score: number;
  viral_potential_score: number;
  cinematic_score: number;
  pacing_score: number;
  brand_safety_score: number;
  overall_score: number;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  red_flags: string[];
}

export interface DirectorPlan {
  plan_id: string;
  created_at: string;
  continuity_bible: ContinuityBible;
  shot_list: Shot[];
  storyboard_grid: StoryboardFrame[];
  evaluation: EvaluationReport;
  cost_estimate: {
    plan_cost_usd: number;
    storyboard_gen_cost_usd: number;
    render_cost_usd: number;
    audio_cost_usd: number;
    total_cost_usd: number;
  };
  llm_calls_total: number;
  elapsed_s: number;
}

// ============================================================
// Request
// ============================================================
export interface PlanRequest {
  product_input: { url?: string; text_description?: string; image_urls?: string[] };
  reference_images: string[];
  /** Optional per-image role hints (same length as reference_images, null = AI auto-detect).
   *  Backend uses these to skip the vision pass when zones tagged refs explicitly. */
  reference_role_hints?: (string | null)[];
  reference_videos: string[];
  user_brief: string;
  context_injection: {
    pain_points?: string;
    real_reviews?: string;
    usps?: string;
    forbidden_to_say?: string;
    mood_hint?: string;
  };
  settings: VideoSettings;
  niche_hint?: string;
}

export interface ProgressEvent {
  stage: string;
  status: 'running' | 'done';
  message?: string;
  [key: string]: unknown;
}

export const DIRECTOR_STAGE_LABELS_VN: Record<string, string> = {
  init: 'Khởi động Director Agent',
  vision: 'Phân tích reference images',
  director: 'Soạn Continuity Bible + Shot List',
  evaluation: 'Tự chấm điểm plan',
};

// ============================================================
// Hook
// ============================================================
export function useDirectorPlan() {
  const [plan, setPlan] = useState<DirectorPlan | null>(null);
  const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const createPlan = useCallback(async (req: PlanRequest) => {
    setIsLoading(true);
    setError(null);
    setPlan(null);
    setProgress({ stage: 'init', status: 'running', message: 'Connecting...' });

    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    try {
      const res = await fetch('/api/v1/director/plan/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
        signal: ctrl.signal,
      });
      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Parse SSE blocks (event: <type>\ndata: <json>\n\n)
        const parts = buffer.split('\n\n');
        buffer = parts.pop() ?? '';
        for (const block of parts) {
          if (!block.trim() || block.startsWith(':')) continue;
          const eventMatch = block.match(/^event:\s*(\S+)/m);
          const dataMatch = block.match(/^data:\s*(.+)$/m);
          if (!dataMatch) continue;
          const evType = eventMatch?.[1] ?? 'message';
          let payload: unknown;
          try {
            payload = JSON.parse(dataMatch[1]);
          } catch {
            continue;
          }
          if (evType === 'stage') {
            setProgress(payload as ProgressEvent);
          } else if (evType === 'complete') {
            const finalPlan = payload as DirectorPlan;
            setPlan(finalPlan);
            setProgress({ stage: 'done', status: 'done' });
          } else if (evType === 'error') {
            throw new Error((payload as { error: string }).error || 'unknown');
          } else if (evType === '__end__') {
            // Sprint3 B4 — backend M14 force-emits __end__ as terminal sentinel.
            // Consume it to guarantee the reader loop exits even if the network
            // keeps the response body open after the final SSE block.
            try { await reader.cancel(); } catch { /* noop */ }
            return;
          }
        }
      }
    } catch (e) {
      if ((e as { name?: string })?.name === 'AbortError') return;
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setProgress(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setPlan(null);
    setProgress(null);
    setError(null);
    setIsLoading(false);
  }, []);

  return { createPlan, plan, progress, isLoading, error, reset };
}

// ============================================================
// Approve + render — POST /api/v1/director/generate
// ============================================================
export async function generateFromPlan(args: {
  plan: DirectorPlan;
  reference_images: string[];
  settings: VideoSettings;
  audio_plan?: Record<string, unknown>;
  use_llm_scene_gen?: boolean;
  idempotencyKey?: string;
}): Promise<{ job_id: string; polling_url: string; estimated_duration_s: number; estimated_cost_usd: number }> {
  // Sprint3 B5 — Idempotency-Key header so double-click / network retry doesn't
  // spawn two render jobs (24h TTL on backend, matches Stripe convention).
  const idemKey = args.idempotencyKey
    ?? (typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`);
  const res = await fetch('/api/v1/director/generate', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idemKey,
    },
    body: JSON.stringify({
      plan: args.plan,
      reference_images: args.reference_images,
      settings: args.settings,
      audio_plan: args.audio_plan,
      use_llm_scene_gen: args.use_llm_scene_gen ?? true,
    }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchDirectorJob(jobId: string) {
  const res = await fetch(`/api/v1/director/jobs/${jobId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function generateStoryboardImages(args: {
  plan: DirectorPlan;
  image_model?: string;
}): Promise<DirectorPlan> {
  const res = await fetch('/api/v1/director/storyboard', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      plan: args.plan,
      image_model: args.image_model ?? 'bytedance/seedream-v4.5',
    }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
