'use client';
import { useCallback, useEffect, useState } from 'react';

/**
 * V5.1 — persist active jobId across page refresh.
 *
 * Without this, the user refreshes mid-render → loses jobId → can't see
 * progress → loses the video they already paid for. We stash the job ID in
 * localStorage so the JobResultModal can resume polling on next mount.
 *
 * TTL 24h: a render older than that is almost certainly done / abandoned;
 * we don't want stale IDs cluttering the UI forever.
 */
const STORAGE_KEY = 'cineforge:active_job';
const TTL_MS = 24 * 60 * 60 * 1000;

interface PersistedJob {
  job_id: string;
  saved_at: number;
}

export function usePersistedJob() {
  const [jobId, setJobIdState] = useState<string | null>(null);

  // Hydrate on mount
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as PersistedJob;
      if (!parsed.job_id || typeof parsed.saved_at !== 'number') return;
      if (Date.now() - parsed.saved_at > TTL_MS) {
        localStorage.removeItem(STORAGE_KEY);
        return;
      }
      setJobIdState(parsed.job_id);
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const setJobId = useCallback((id: string | null) => {
    setJobIdState(id);
    if (typeof window === 'undefined') return;
    if (id) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ job_id: id, saved_at: Date.now() }));
      } catch {}
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  return { jobId, setJobId };
}
