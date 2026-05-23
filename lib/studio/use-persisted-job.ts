'use client';
import { useCallback, useEffect, useState } from 'react';

/**
 * V5.1 — persist active jobId across page refresh.
 * V5.3 — also persist `startedAt` so JobResultModal ETA stays stable across
 *        modal close/reopen (was: ETA reset every time the modal remounted).
 *
 * Without persistence, the user refreshes mid-render → loses jobId → can't see
 * progress → loses the video they already paid for. We stash the job ID +
 * startedAt timestamp in localStorage so the JobResultModal can resume polling
 * + show accurate ETA on next mount.
 *
 * TTL 24h: a render older than that is almost certainly done / abandoned.
 */
const STORAGE_KEY = 'cineforge:active_job';
const TTL_MS = 24 * 60 * 60 * 1000;

interface PersistedJob {
  job_id: string;
  started_at: number;
  saved_at: number;
}

export function usePersistedJob() {
  const [jobId, setJobIdState] = useState<string | null>(null);
  const [startedAt, setStartedAtState] = useState<number | null>(null);

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
      setStartedAtState(parsed.started_at ?? parsed.saved_at);
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const setJobId = useCallback((id: string | null) => {
    setJobIdState(id);
    if (typeof window === 'undefined') return;
    if (id) {
      const now = Date.now();
      setStartedAtState(now);
      try {
        localStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({ job_id: id, started_at: now, saved_at: now } satisfies PersistedJob)
        );
      } catch {}
    } else {
      setStartedAtState(null);
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  return { jobId, startedAt, setJobId };
}
