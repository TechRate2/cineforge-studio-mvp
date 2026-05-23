'use client';
import { useCallback, useState } from 'react';

export interface CancelResponse {
  job_id: string;
  status: 'cancelled' | string;
  message?: string;
}

export function useJobCancel() {
  const [isCancelling, setIsCancelling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cancel = useCallback(async (jobId: string): Promise<CancelResponse> => {
    setIsCancelling(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/director/jobs/${jobId}/cancel`, {
        method: 'POST',
      });
      if (!res.ok) {
        const detail = await res.text().catch(() => `HTTP ${res.status}`);
        throw new Error(detail.slice(0, 200));
      }
      return (await res.json()) as CancelResponse;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      throw e;
    } finally {
      setIsCancelling(false);
    }
  }, []);

  return { cancel, isCancelling, error };
}
