'use client';
import { useCallback, useEffect, useRef, useState } from 'react';

export interface EnhanceBriefResponse {
  original_brief: string;
  enhanced_brief: string;
  char_count: number;
  /** V5.12 — "vision" when refs were sent (Qwen3-VL), "text" otherwise (DeepSeek Flash). */
  mode?: 'vision' | 'text';
  refs_seen?: number;
  // V5.17 Smart Enhance — structured suggestions. Null if LLM returned non-JSON.
  suggested_niche?: string | null;
  suggested_mood?: string | null;
  suggested_hook_pattern?: string | null;
  suggested_num_shots?: number | null;
  /** EXACTLY 1 of: auto | seedance_2_0 | seedance_2_0_fast | wan_2_7.
   *  Whitelisted server-side. */
  suggested_model?: string | null;
  /** EXACTLY 1 of: silent_native | dialogue_vo | asmr_macro */
  suggested_audio_mode?: string | null;
  /** Vision-extracted details (character/product/style_ref). Director reuses
   *  this via context_injection to skip its own vision pass. */
  vision_notes?: {
    character?: string | null;
    product?: string | null;
    style_ref?: string | null;
  } | null;
  /** V5.17.5 H3 — 3 bool flags LLM returns; backend deduces suggested_model from them.
   *  Surfaced for debug transparency — FE can show "vì có dialogue VN → pick Wan 2.7". */
  model_deduction_flags?: {
    needs_dialogue_lip_sync?: boolean;
    is_multi_shot_cinematic?: boolean;
    is_budget_tier?: boolean;
  };
}

const ENHANCE_TIMEOUT_MS = 30_000;

export function useEnhanceBrief() {
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // V5.3 — clean up any pending request on unmount so we don't leak hang-callbacks
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const enhance = useCallback(
    async (args: {
      brief: string;
      niche_hint?: string | null;
      duration_s?: number;
      /** V5.12 — pass reference image URLs so backend uses vision LLM
       *  (Qwen3-VL) to ground brief in actual visual content. */
      reference_image_urls?: string[];
    }): Promise<EnhanceBriefResponse> => {
      // V5.3 — cancel any in-flight enhance before starting a new one (double-click guard)
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const timeoutId = setTimeout(() => controller.abort(), ENHANCE_TIMEOUT_MS);

      setIsEnhancing(true);
      setError(null);
      try {
        const res = await fetch('/api/v1/llm/enhance-brief', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            brief: args.brief,
            niche_hint: args.niche_hint ?? null,
            duration_s: args.duration_s ?? 15,
            reference_image_urls: args.reference_image_urls ?? [],
          }),
          signal: controller.signal,
        });
        if (!res.ok) {
          const err = await res.text().catch(() => `HTTP ${res.status}`);
          throw new Error(err.slice(0, 200));
        }
        return (await res.json()) as EnhanceBriefResponse;
      } catch (e) {
        const msg = e instanceof Error && e.name === 'AbortError'
          ? 'Enhance hủy hoặc timeout (>30s)'
          : e instanceof Error ? e.message : String(e);
        setError(msg);
        throw new Error(msg);
      } finally {
        clearTimeout(timeoutId);
        if (abortRef.current === controller) abortRef.current = null;
        setIsEnhancing(false);
      }
    },
    []
  );

  return { enhance, isEnhancing, error };
}
