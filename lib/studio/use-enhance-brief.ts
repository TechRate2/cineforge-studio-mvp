'use client';
import { useCallback, useState } from 'react';

export interface EnhanceBriefResponse {
  original_brief: string;
  enhanced_brief: string;
  char_count: number;
}

export function useEnhanceBrief() {
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enhance = useCallback(
    async (args: { brief: string; niche_hint?: string | null; duration_s?: number }): Promise<EnhanceBriefResponse> => {
      setIsEnhancing(true);
      setError(null);
      try {
        const res = await fetch('/api/v1/llm/enhance-brief', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            brief: args.brief,
            niche_hint: args.niche_hint ?? null,
            duration_s: args.duration_s ?? 15,
          }),
        });
        if (!res.ok) {
          const err = await res.text().catch(() => `HTTP ${res.status}`);
          throw new Error(err.slice(0, 200));
        }
        return (await res.json()) as EnhanceBriefResponse;
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        throw e;
      } finally {
        setIsEnhancing(false);
      }
    },
    []
  );

  return { enhance, isEnhancing, error };
}
