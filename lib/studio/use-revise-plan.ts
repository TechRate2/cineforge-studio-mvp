'use client';
import { useCallback, useState } from 'react';
import type { DirectorPlan } from './use-director-plan';
import type { VideoSettings } from '@/lib/types/backend';

export function useRevisePlan() {
  const [isRevising, setIsRevising] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const revise = useCallback(
    async (args: {
      plan: DirectorPlan;
      instruction: string;
      settings: VideoSettings;
    }): Promise<DirectorPlan> => {
      setIsRevising(true);
      setError(null);
      try {
        const res = await fetch('/api/v1/director/revise', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            plan: args.plan,
            instruction: args.instruction,
            settings: args.settings,
          }),
        });
        if (!res.ok) {
          const err = await res.text().catch(() => `HTTP ${res.status}`);
          throw new Error(err.slice(0, 240));
        }
        return (await res.json()) as DirectorPlan;
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        throw e;
      } finally {
        setIsRevising(false);
      }
    },
    []
  );

  return { revise, isRevising, error };
}
