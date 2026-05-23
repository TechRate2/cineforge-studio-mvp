'use client';
import { useCallback, useState } from 'react';
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

  const generate = useCallback(async (plan: DirectorPlan, imageModel?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/v1/director/storyboard/master', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan,
          image_model: imageModel ?? 'bytedance/seedream-v4.5',
        }),
      });
      if (!res.ok) {
        const err = await res.text().catch(() => `HTTP ${res.status}`);
        throw new Error(err.slice(0, 200));
      }
      const data = (await res.json()) as MasterBoardResponse;
      setBoard(data);
      return data;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      throw e;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setBoard(null);
    setError(null);
    setIsLoading(false);
  }, []);

  return { board, isLoading, error, generate, reset };
}
