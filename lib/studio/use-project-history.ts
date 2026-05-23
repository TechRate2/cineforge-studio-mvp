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

// V5.3 — module-level cache so multiple mounts (e.g. RecentGenerations carousel
// + History page) share the same fetch result for up to CACHE_TTL_MS. Without
// this every component remount fired a fresh /history request.
const HISTORY_CACHE_TTL_MS = 30_000;  // 30s
let _historyCache: { items: HistoryItem[]; fetchedAt: number } | null = null;
let _inflight: Promise<HistoryItem[]> | null = null;

async function _fetchHistory(force = false): Promise<HistoryItem[]> {
  if (!force && _historyCache && Date.now() - _historyCache.fetchedAt < HISTORY_CACHE_TTL_MS) {
    return _historyCache.items;
  }
  if (_inflight) return _inflight;
  _inflight = (async () => {
    try {
      const r = await fetch('/api/v1/director/history?limit=50');
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      const items: HistoryItem[] = Array.isArray(body?.items) ? body.items : [];
      _historyCache = { items, fetchedAt: Date.now() };
      return items;
    } finally {
      _inflight = null;
    }
  })();
  return _inflight;
}

export function useProjectHistory() {
  const [items, setItems] = useState<HistoryItem[]>(() => _historyCache?.items ?? []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (opts?: { force?: boolean }) => {
    setLoading(true);
    setError(null);
    try {
      const items = await _fetchHistory(opts?.force ?? false);
      setItems(items);
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
    // V5.3 — bust shared cache so other mounts see the deletion
    if (_historyCache) {
      _historyCache.items = _historyCache.items.filter((it) => it.job_id !== jobId);
    }
  }, []);

  return { items, loading, error, refresh, getDetail, remove };
}
