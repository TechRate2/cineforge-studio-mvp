'use client';
import { useEffect, useState } from 'react';
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

export function useDirectorJobPoll(jobId: string | null, intervalMs: number = 2500) {
  const [job, setJob] = useState<DirectorJobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      return;
    }
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const tick = async () => {
      if (!alive) return;
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

  return { job, error };
}
