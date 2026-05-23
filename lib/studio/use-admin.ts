'use client';

/**
 * use-admin — Wrapper cho /api/v1/admin/* endpoints (Style Presets, Prompts,
 * Credits, Config).
 */

import { useCallback, useEffect, useState } from 'react';

// ============================================================
// Style Presets
// ============================================================
export interface StylePreset {
  id: string;
  name: string;
  description: string;
  visual_style: {
    cinematography: string;
    color_grading: string;
    lighting_design: string;
    camera_language: string;
    film_grain: string;
    aspect_ratio: string;
  };
  audio_design: {
    mood: string;
    tempo: string;
    music_genre: string;
    sfx_emphasis: string[];
    dialogue_style: string;
  };
  setting: { location: string; time_of_day: string; atmosphere: string };
  constraints: { must_have: string[]; must_avoid: string[]; brand_safety: string[] };
  tags: string;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
}

export function useStylePresets() {
  const [items, setItems] = useState<StylePreset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const url = new URL('/api/v1/admin/presets', window.location.origin);
      if (search.trim()) url.searchParams.set('q', search.trim());
      const r = await fetch(url.toString());
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      setItems(Array.isArray(body?.items) ? body.items : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => { void refresh(); }, [refresh]);

  const create = useCallback(async (preset: Omit<StylePreset, 'id' | 'is_builtin' | 'created_at' | 'updated_at' | 'last_used_at'>) => {
    const r = await fetch('/api/v1/admin/presets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(preset),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${(await r.text()).slice(0, 200)}`);
    const saved = (await r.json()) as StylePreset;
    setItems((prev) => [saved, ...prev]);
    return saved;
  }, []);

  const remove = useCallback(async (id: string) => {
    const r = await fetch(`/api/v1/admin/presets/${id}`, { method: 'DELETE' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    setItems((prev) => prev.filter((p) => p.id !== id));
  }, []);

  return { items, loading, error, search, setSearch, refresh, create, remove };
}

// ============================================================
// Prompts
// ============================================================
export interface PromptMeta {
  name: string;
  size: number;
  lines?: number;
  updated_at?: number;
}

export function usePromptLibrary() {
  const [items, setItems] = useState<PromptMeta[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch('/api/v1/admin/prompts');
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const body = await r.json();
      setItems(Array.isArray(body?.items) ? body.items : []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const load = useCallback(async (name: string) => {
    const r = await fetch(`/api/v1/admin/prompts/${name}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json() as Promise<{ name: string; content: string; size: number }>;
  }, []);

  const save = useCallback(async (name: string, content: string) => {
    const r = await fetch(`/api/v1/admin/prompts/${name}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}: ${(await r.text()).slice(0, 200)}`);
    await refresh();
    return r.json();
  }, [refresh]);

  return { items, loading, refresh, load, save };
}

// ============================================================
// Credits + Config
// ============================================================
export interface CreditsView {
  atlascloud: { key_set: boolean; key_masked: string; base_url: string; balance_usd: number | null; balance_source: string };
  atlascloud_llm: { key_set: boolean; key_masked: string; base_url: string; balance_usd: number | null; balance_source: string };
  genmax: { key_set: boolean; key_masked: string; base_url: string; balance_credits: number | null; balance_source: string };
  anthropic: { key_set: boolean; key_masked: string; balance_usd: number | null; balance_source: string };
  r2: { configured: boolean; bucket: string; public_url: string | null };
}

export interface ConfigView {
  llm: { provider: string; models: Record<string, string> };
  cost_gate: { default_mode: string; default_threshold: number; draft_model_map: Record<string, string> };
  video_models: { auto_picker_default: string; available_user_models: string[] };
  app: { env: string; port: number; worker_concurrency: number };
}

export function useAdminConfig() {
  const [credits, setCredits] = useState<CreditsView | null>(null);
  const [config, setConfig] = useState<ConfigView | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [creditsRes, configRes] = await Promise.all([
        fetch('/api/v1/admin/credits'),
        fetch('/api/v1/admin/config'),
      ]);
      if (!creditsRes.ok) throw new Error(`credits HTTP ${creditsRes.status}`);
      if (!configRes.ok) throw new Error(`config HTTP ${configRes.status}`);
      setCredits(await creditsRes.json());
      setConfig(await configRes.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  return { credits, config, loading, error, refresh };
}
