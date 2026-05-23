'use client';
import { useCallback, useEffect, useState } from 'react';

export interface CreditProvider {
  key_set: boolean;
  key_masked?: string;
  base_url?: string;
  balance_usd?: number | null;
  balance_credits?: number | null;
  balance_source?: string;
}

export interface R2Status {
  configured: boolean;
  bucket?: string;
  public_url?: string | null;
}

export interface CreditsResponse {
  atlascloud?: CreditProvider;
  atlascloud_llm?: CreditProvider;
  genmax?: CreditProvider;
  anthropic?: CreditProvider;
  r2?: R2Status;
}

export function useAdminCredits(autoRefresh: boolean = false, intervalMs: number = 60_000) {
  const [credits, setCredits] = useState<CreditsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/v1/admin/credits');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as CreditsResponse;
      setCredits(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    if (!autoRefresh) return;
    const t = setInterval(() => void refresh(), intervalMs);
    return () => clearInterval(t);
  }, [refresh, autoRefresh, intervalMs]);

  return { credits, loading, error, refresh };
}
