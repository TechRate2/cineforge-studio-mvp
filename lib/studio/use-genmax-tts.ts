'use client';

/**
 * use-genmax-tts — Wrapper cho /api/v1/audio/direct/* (12 voice VN preset).
 *
 * Dùng trong Audio Studio: list voices → pick preset → preview cost → gen →
 * lưu URL vào plan.audio_plan.driven_audio_urls[shot_id] cho Wan lip-sync.
 */

import { useCallback, useEffect, useState } from 'react';

export interface VoicePreset {
  alias: string;
  voice_id: string;
  provider: 'elevenlabs' | 'minimax';
  label_vn: string;
  gender: 'male' | 'female';
  tier: 'premium' | 'budget';
}

export interface TtsResult {
  audio_url: string;
  duration_s?: number;
  cost_credits?: number;
}

export function useGenmaxTts() {
  const [voices, setVoices] = useState<VoicePreset[]>([]);
  const [voicesLoading, setVoicesLoading] = useState(false);
  const [voicesError, setVoicesError] = useState<string | null>(null);

  // Load voice catalog once on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setVoicesLoading(true);
      setVoicesError(null);
      try {
        const r = await fetch('/api/v1/audio/direct/voices');
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const body = await r.json();
        if (!cancelled) setVoices(Array.isArray(body?.voices) ? body.voices : []);
      } catch (e) {
        if (!cancelled) setVoicesError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setVoicesLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const previewCost = useCallback(async (text: string, voicePreset: string) => {
    const r = await fetch('/api/v1/audio/direct/preview-cost', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice_preset: voicePreset, provider: 'elevenlabs' }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json() as Promise<{ char_count: number; estimated_credits: number; estimated_vnd: number; provider: string }>;
  }, []);

  const generate = useCallback(async (
    text: string,
    voicePreset: string,
    opts?: { stability?: number; speed?: number },
  ): Promise<TtsResult> => {
    const r = await fetch('/api/v1/audio/direct/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        voice_preset: voicePreset,
        stability: opts?.stability ?? 0.5,
        similarity_boost: 0.75,
        speed: opts?.speed ?? 1.0,
      }),
    });
    if (!r.ok) {
      const detail = await r.text();
      throw new Error(`HTTP ${r.status}: ${detail.slice(0, 200)}`);
    }
    const body = await r.json();
    // Backend AUDIO_JOBS returns { job_id, audio_url, duration_s, ... } or similar.
    const audioUrl: string = body.audio_url ?? body.url ?? body.output_url;
    if (!audioUrl) throw new Error('TTS response missing audio_url');
    return {
      audio_url: audioUrl,
      duration_s: body.duration_s,
      cost_credits: body.cost_credits,
    };
  }, []);

  return {
    voices, voicesLoading, voicesError,
    previewCost, generate,
  };
}
