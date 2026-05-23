'use client';
import { useCallback, useState } from 'react';
import type { DirectorPlan } from './use-director-plan';

export interface RefineResponse {
  job_id: string;
  polling_url: string;
  shot_id: string;
  estimated_duration_s: number;
  mode: string;
}

export function useRefineShot() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResponse, setLastResponse] = useState<RefineResponse | null>(null);

  const refine = useCallback(
    async (args: {
      plan: DirectorPlan;
      shotId: string;
      referenceImages: string[];
      settings: Record<string, unknown>;
      previousLastFrameUrl?: string;
      shotOverrides?: Record<string, unknown>;
    }) => {
      setIsLoading(true);
      setError(null);
      try {
        const res = await fetch('/api/v1/director/refine', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            plan: args.plan,
            shot_id: args.shotId,
            reference_images: args.referenceImages,
            settings: args.settings,
            previous_last_frame_url: args.previousLastFrameUrl,
            shot_overrides: args.shotOverrides,
          }),
        });
        if (!res.ok) {
          const err = await res.text().catch(() => `HTTP ${res.status}`);
          throw new Error(err.slice(0, 200));
        }
        const data = (await res.json()) as RefineResponse;
        setLastResponse(data);
        return data;
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        throw e;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  return { refine, isLoading, error, lastResponse };
}
