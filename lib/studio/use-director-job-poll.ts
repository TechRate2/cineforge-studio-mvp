'use client';
import { useEffect, useRef, useState } from 'react';
import { fetchDirectorJob } from './use-director-plan';

export interface DirectorJobStatus {
  job_id: string;
  status: 'pending' | 'planning' | 'rendering' | 'assembling' | 'uploading' | 'done' | 'failed' | 'cancelled';
  progress: number;
  current_step?: string;
  output_path?: string | null;
  output_url?: string | null;
  error_message?: string | null;
  elapsed_s?: number;
  cost_actual_usd?: number;
}

/** V5.1 — job stuck timeout (15 min). When exceeded, polling stops and
 *  `timedOut` becomes true so the UI can prompt the user to check History
 *  or manually cancel. Render rarely exceeds 5 min on healthy AtlasCloud. */
const STUCK_TIMEOUT_MS = 15 * 60 * 1000;

export function useDirectorJobPoll(jobId: string | null, intervalMs: number = 2500) {
  const [job, setJob] = useState<DirectorJobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const startedAtRef = useRef<number | null>(null);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      setTimedOut(false);
      startedAtRef.current = null;
      return;
    }
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | null = null;
    startedAtRef.current = Date.now();
    setTimedOut(false);

    const tick = async () => {
      if (!alive) return;
      // V5.1 — abort polling if job has been alive past stuck threshold
      const elapsed = Date.now() - (startedAtRef.current ?? Date.now());
      if (elapsed > STUCK_TIMEOUT_MS) {
        setTimedOut(true);
        return;
      }
      try {
        const res = await fetchDirectorJob(jobId);
        if (!alive) return;
        setJob(res);
        setError(null);
        const status = res.status as DirectorJobStatus['status'];
        if (status === 'done' || status === 'failed' || status === 'cancelled') {
          return;
        }
        timer = setTimeout(tick, intervalMs);
      } catch (e) {
        if (!alive) return;
        setError(e instanceof Error ? e.message : String(e));
        timer = setTimeout(tick, intervalMs * 2);
      }
    };
    tick();
    return () => {
      alive = false;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, intervalMs]);

  return { job, error, timedOut };
}
