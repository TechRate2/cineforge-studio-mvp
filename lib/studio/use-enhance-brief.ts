'use client';
import { useCallback, useEffect, useRef, useState } from 'react';

export interface EnhanceBriefResponse {
  original_brief: string;
  enhanced_brief: string;
  char_count: number;
}

const ENHANCE_TIMEOUT_MS = 30_000;

export function useEnhanceBrief() {
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // V5.3 — clean up any pending request on unmount so we don't leak hang-callbacks
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const enhance = useCallback(
    async (args: { brief: string; niche_hint?: string | null; duration_s?: number }): Promise<EnhanceBriefResponse> => {
      // V5.3 — cancel any in-flight enhance before starting a new one (double-click guard)
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const timeoutId = setTimeout(() => controller.abort(), ENHANCE_TIMEOUT_MS);

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
          signal: controller.signal,
        });
        if (!res.ok) {
          const err = await res.text().catch(() => `HTTP ${res.status}`);
          throw new Error(err.slice(0, 200));
        }
        return (await res.json()) as EnhanceBriefResponse;
      } catch (e) {
        const msg = e instanceof Error && e.name === 'AbortError'
          ? 'Enhance hủy hoặc timeout (>30s)'
          : e instanceof Error ? e.message : String(e);
        setError(msg);
        throw new Error(msg);
      } finally {
        clearTimeout(timeoutId);
        if (abortRef.current === controller) abortRef.current = null;
        setIsEnhancing(false);
      }
    },
    []
  );

  return { enhance, isEnhancing, error };
}
