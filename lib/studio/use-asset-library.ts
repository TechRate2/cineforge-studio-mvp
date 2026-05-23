'use client';

/**
 * use-asset-library — Client wrapper cho /api/v1/assets/* CRUD.
 *
 * Asset = ảnh reference user lưu lại để dùng cho nhiều plan khác nhau
 * (Character / Product / Storyboard). Backend: backend/api/routes/assets.py.
 */

import { useCallback, useEffect, useState } from 'react';

export type AssetType = 'character' | 'product' | 'storyboard';

export interface Asset {
  id: string;
  type: AssetType;
  name: string;
  image_url: string;
  payload: Record<string, unknown>;
  tags: string;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
}

export interface CreateAssetInput {
  type: AssetType;
  name: string;
  image_url: string;
  payload?: Record<string, unknown>;
  tags?: string;
}

// ============================================================
// Hook
// ============================================================
export function useAssetLibrary(initialType?: AssetType) {
  const [items, setItems] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<AssetType | undefined>(initialType);
  const [search, setSearch] = useState('');

  const fetchList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const url = new URL('/api/v1/assets/', window.location.origin);
      if (typeFilter) url.searchParams.set('type', typeFilter);
      if (search.trim()) url.searchParams.set('q', search.trim());
      const r = await fetch(url.toString());
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      setItems(Array.isArray(body?.items) ? body.items : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [typeFilter, search]);

  useEffect(() => {
    void fetchList();
  }, [fetchList]);

  const create = useCallback(async (input: CreateAssetInput): Promise<Asset> => {
    const r = await fetch('/api/v1/assets/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    });
    if (!r.ok) {
      const detail = await r.text();
      throw new Error(`HTTP ${r.status}: ${detail.slice(0, 200)}`);
    }
    const asset = (await r.json()) as Asset;
    setItems((prev) => [asset, ...prev]);
    return asset;
  }, []);

  const remove = useCallback(async (assetId: string) => {
    const r = await fetch(`/api/v1/assets/${assetId}`, { method: 'DELETE' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    setItems((prev) => prev.filter((a) => a.id !== assetId));
  }, []);

  const touch = useCallback(async (assetId: string) => {
    try {
      await fetch(`/api/v1/assets/${assetId}/touch`, { method: 'POST' });
    } catch {
      /* swallow — touch is fire-and-forget */
    }
  }, []);

  return {
    items, loading, error,
    typeFilter, setTypeFilter,
    search, setSearch,
    refresh: fetchList,
    create, remove, touch,
  };
}
