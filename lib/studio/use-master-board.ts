'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { DirectorPlan } from './use-director-plan';

export interface MasterBoardResponse {
  plan_id: string;
  board_url: string;
  prompt: string;
  size: string;
  cost_usd: number;
  elapsed_s: number;
}

export function useMasterBoard() {
  const [board, setBoard] = useState<MasterBoardResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // V5.15.2 M3 — Abort in-flight request when generate() is fired again or
  // component unmounts. Prevents 2 racing fetches (user revises mid-gen) from
  // overwriting each other in random order, and stops setState-on-unmounted
  // warnings during teardown.
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const generate = useCallback(async (
    plan: DirectorPlan,
    imageModel?: string,
    referenceImages?: string[],
  ) => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/v1/director/storyboard/master', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan,
          image_model: imageModel ?? 'bytedance/seedream-v4.5',
          // V5.17.3 — Pass user refs so BE auto-switches to EDIT variant
          // and locks character/product to user's actual uploads (instead
          // of Seedream text-to-image bịa random subject).
          reference_images: (referenceImages ?? []).filter((u) => u && u.startsWith('http')).slice(0, 10),
        }),
        signal: ctrl.signal,
      });
      if (!res.ok) {
        const err = await res.text().catch(() => `HTTP ${res.status}`);
        throw new Error(err.slice(0, 200));
      }
      const data = (await res.json()) as MasterBoardResponse;
      if (ctrl.signal.aborted) return data;
      setBoard(data);
      return data;
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') {
        throw e;
      }
      if (ctrl.signal.aborted) throw e;
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      throw e;
    } finally {
      if (!ctrl.signal.aborted) setIsLoading(false);
      if (abortRef.current === ctrl) abortRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setBoard(null);
    setError(null);
    setIsLoading(false);
  }, []);

  return { board, isLoading, error, generate, reset };
}
