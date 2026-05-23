'use client';

/**
 * use-project-history — Wrapper cho /api/v1/director/history endpoint.
 */

import { useCallback, useEffect, useState } from 'react';
import type { DirectorPlan } from './use-director-plan';

export interface HistoryItem {
  job_id: string;
  plan_id: string | null;
  mode: string;
  status: string;
  output_url: string | null;
  title: string | null;
  duration_s: number | null;
  cost_estimate_usd: number | null;
  created_at: string;
  finished_at: string | null;
}

export interface HistoryDetail extends HistoryItem {
  plan: DirectorPlan | null;
  chain: Array<{
    shot_id: string;
    model_key: string;
    render_mode: string;
    video_url: string | null;
    last_frame_url: string | null;
    duration_s: number;
    chained_from?: string | null;
  }> | null;
}

export function useProjectHistory() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch('/api/v1/director/history?limit=50');
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      setItems(Array.isArray(body?.items) ? body.items : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const getDetail = useCallback(async (jobId: string): Promise<HistoryDetail> => {
    const r = await fetch(`/api/v1/director/history/${jobId}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }, []);

  const remove = useCallback(async (jobId: string) => {
    const r = await fetch(`/api/v1/director/history/${jobId}`, { method: 'DELETE' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    setItems((prev) => prev.filter((it) => it.job_id !== jobId));
  }, []);

  return { items, loading, error, refresh, getDetail, remove };
}
