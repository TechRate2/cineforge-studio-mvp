'use client';
import { useCallback, useEffect, useState } from 'react';

export interface VoicePreset {
  alias: string;
  voice_id: string;
  provider: 'elevenlabs' | 'minimax';
  label_vn: string;
  gender: 'female' | 'male';
  tier: 'premium' | 'budget';
}

export interface TTSResponse {
  job_id: string;
  history_id: string;
  status: string;
  audio_url: string | null;
  voice_id: string;
  provider: string;
  error?: string | null;
}

export function useTTSVoices() {
  const [voices, setVoices] = useState<VoicePreset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetch('/api/v1/audio/direct/voices')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (!alive) return;
        const list = Array.isArray(data?.voices)
          ? data.voices
          : Array.isArray(data?.items)
          ? data.items
          : Array.isArray(data)
          ? data
          : [];
        setVoices(list);
      })
      .catch((e) => alive && setError(e instanceof Error ? e.message : String(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  return { voices, loading, error };
}

export function useTTSGenerate() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = useCallback(
    async (args: {
      text: string;
      voicePreset: string;
      speed?: number;
    }): Promise<TTSResponse> => {
      setIsLoading(true);
      setError(null);
      try {
        const res = await fetch('/api/v1/audio/direct/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: args.text,
            voice_preset: args.voicePreset,
            speed: args.speed ?? 1.0,
          }),
        });
        if (!res.ok) {
          const err = await res.text().catch(() => `HTTP ${res.status}`);
          throw new Error(err.slice(0, 240));
        }
        return (await res.json()) as TTSResponse;
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        throw e;
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  return { generate, isLoading, error };
}
