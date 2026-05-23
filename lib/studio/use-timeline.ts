'use client';

/**
 * use-timeline — Manage Timeline Editor state cho 1 history job:
 *  - Load chain meta (per-shot clip URLs) từ /director/history/{id}
 *  - Track per-shot override URL (khi user swap với refined clip)
 *  - Track order (drag-reorder)
 *  - submit() → POST /director/reassemble + poll → return final MP4 URL
 */

import { useCallback, useEffect, useState } from 'react';
import type { HistoryDetail } from './use-project-history';

export interface TimelineClip {
  shot_id: string;
  video_url: string | null;      // current URL (may be override or original)
  original_url: string | null;   // immutable original from history.chain
  refined_url?: string | null;   // optional override (set after Refine job)
  duration_s: number;
  model_key: string;
  render_mode: string;
}

export interface ReassembleState {
  jobId: string | null;
  status: 'idle' | 'submitting' | 'downloading' | 'assembling' | 'grading' | 'uploading' | 'done' | 'failed';
  progress: number;
  currentStep?: string;
  outputUrl?: string;
  error?: string;
}

const INITIAL: ReassembleState = { jobId: null, status: 'idle', progress: 0 };

export function useTimeline(historyJobId: string | null) {
  const [detail, setDetail] = useState<HistoryDetail | null>(null);
  const [clips, setClips] = useState<TimelineClip[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reassembleState, setReassembleState] = useState<ReassembleState>(INITIAL);

  // Load history detail when jobId changes
  useEffect(() => {
    let cancelled = false;
    if (!historyJobId) {
      setDetail(null); setClips([]); setReassembleState(INITIAL);
      return;
    }
    (async () => {
      setLoading(true); setError(null); setReassembleState(INITIAL);
      try {
        const r = await fetch(`/api/v1/director/history/${historyJobId}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const body = (await r.json()) as HistoryDetail;
        if (cancelled) return;
        setDetail(body);
        const initial: TimelineClip[] = (body.chain ?? []).map((c) => ({
          shot_id: c.shot_id,
          video_url: c.video_url,
          original_url: c.video_url,
          refined_url: null,
          duration_s: c.duration_s,
          model_key: c.model_key,
          render_mode: c.render_mode,
        }));
        setClips(initial);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [historyJobId]);

  // ---- Mutators ----
  const moveClip = useCallback((fromIdx: number, toIdx: number) => {
    setClips((prev) => {
      if (fromIdx < 0 || fromIdx >= prev.length || toIdx < 0 || toIdx >= prev.length) return prev;
      if (fromIdx === toIdx) return prev;
      const next = [...prev];
      const [moved] = next.splice(fromIdx, 1);
      next.splice(toIdx, 0, moved);
      return next;
    });
  }, []);

  const removeClip = useCallback((shotId: string) => {
    setClips((prev) => prev.filter((c) => c.shot_id !== shotId));
  }, []);

  const swapClipUrl = useCallback((shotId: string, newUrl: string) => {
    setClips((prev) => prev.map((c) =>
      c.shot_id === shotId
        ? { ...c, video_url: newUrl, refined_url: newUrl }
        : c,
    ));
  }, []);

  const revertClip = useCallback((shotId: string) => {
    setClips((prev) => prev.map((c) =>
      c.shot_id === shotId
        ? { ...c, video_url: c.original_url, refined_url: null }
        : c,
    ));
  }, []);

  // ---- Reassemble ----
  const submitReassemble = useCallback(async () => {
    if (!historyJobId) return;
    const urls = clips.map((c) => c.video_url).filter((u): u is string => !!u);
    if (urls.length === 0) {
      setReassembleState({ ...INITIAL, status: 'failed', error: 'No clips to assemble' });
      return;
    }
    setReassembleState({ ...INITIAL, status: 'submitting' });
    try {
      const aspect = detail?.plan?.continuity_bible?.aspect_ratio ?? '9:16';
      const r = await fetch('/api/v1/director/reassemble', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          parent_job_id: historyJobId,
          clip_urls_in_order: urls,
          aspect_ratio: aspect,
          resolution: '720p',
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${(await r.text()).slice(0, 200)}`);
      const body = await r.json();
      const newJobId: string = body.job_id;
      setReassembleState({ jobId: newJobId, status: 'downloading', progress: 5 });
      void pollReassemble(newJobId, setReassembleState);
    } catch (e) {
      setReassembleState({ ...INITIAL, status: 'failed', error: e instanceof Error ? e.message : String(e) });
    }
  }, [historyJobId, clips, detail]);

  const isDirty =
    clips.length !== (detail?.chain?.length ?? 0) ||
    clips.some((c, i) =>
      c.shot_id !== detail?.chain?.[i]?.shot_id || c.video_url !== c.original_url,
    );

  return {
    detail, clips, loading, error, reassembleState,
    moveClip, removeClip, swapClipUrl, revertClip, submitReassemble,
    isDirty,
  };
}

// ============================================================
// Internal poll loop
// ============================================================
async function pollReassemble(
  jobId: string,
  setState: (s: ReassembleState | ((p: ReassembleState) => ReassembleState)) => void,
) {
  const interval = 2500;
  for (let attempt = 0; attempt < 240; attempt++) {  // ~10 min max
    try {
      const r = await fetch(`/api/v1/director/jobs/${jobId}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      const status = (j.status as ReassembleState['status']) || 'assembling';
      const progress = typeof j.progress === 'number' ? j.progress : 0;
      setState((prev) => ({
        ...prev,
        status,
        progress,
        currentStep: j.current_step,
        outputUrl: j.output_url,
        error: j.error_message,
      }));
      if (status === 'done' || status === 'failed') return;
    } catch {
      // network blip — continue
    }
    await new Promise((res) => setTimeout(res, interval));
  }
}
