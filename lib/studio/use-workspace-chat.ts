'use client';

/**
 * use-workspace-chat — Send user instruction → POST /api/v1/director/revise,
 * receive revised DirectorPlan, append both turns to chat history.
 */

import { useCallback, useState } from 'react';
import type { DirectorPlan } from './use-director-plan';
import type { VideoSettings } from '@/lib/types/backend';

export interface ChatTurn {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  /** Only set on assistant turns when the revise call succeeded — the FE can
   *  click "Apply" to swap this plan into the editor. */
  revisedPlan?: DirectorPlan;
  applied?: boolean;
  error?: string;
}

export function useWorkspaceChat() {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [busy, setBusy] = useState(false);

  const send = useCallback(async (
    instruction: string,
    currentPlan: DirectorPlan,
    settings: VideoSettings,
  ) => {
    const userTurn: ChatTurn = {
      id: `u_${Date.now()}`,
      role: 'user',
      text: instruction,
    };
    setTurns((prev) => [...prev, userTurn]);
    setBusy(true);
    try {
      const r = await fetch('/api/v1/director/revise', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan: currentPlan,
          instruction,
          settings,
        }),
      });
      if (!r.ok) {
        const detail = await r.text();
        throw new Error(`HTTP ${r.status}: ${detail.slice(0, 240)}`);
      }
      const revised = (await r.json()) as DirectorPlan;

      // Naive diff summary — count what changed
      const diffSummary = summarizeDiff(currentPlan, revised);

      setTurns((prev) => [
        ...prev,
        {
          id: `a_${Date.now()}`,
          role: 'assistant',
          text: diffSummary || 'Đã chỉnh xong. Click "Apply" để đưa vào plan.',
          revisedPlan: revised,
        },
      ]);
    } catch (e) {
      setTurns((prev) => [
        ...prev,
        {
          id: `e_${Date.now()}`,
          role: 'assistant',
          text: 'Revise lỗi.',
          error: e instanceof Error ? e.message : String(e),
        },
      ]);
    } finally {
      setBusy(false);
    }
  }, []);

  const markApplied = useCallback((turnId: string) => {
    setTurns((prev) =>
      prev.map((t) => (t.id === turnId ? { ...t, applied: true } : t)),
    );
  }, []);

  const reset = useCallback(() => setTurns([]), []);

  return { turns, busy, send, markApplied, reset };
}

// ============================================================
// Diff summarizer (best-effort, human-readable)
// ============================================================
function summarizeDiff(before: DirectorPlan, after: DirectorPlan): string {
  const changes: string[] = [];

  // Total duration delta
  const beforeDur = before.shot_list.reduce((s, x) => s + x.duration_s, 0);
  const afterDur = after.shot_list.reduce((s, x) => s + x.duration_s, 0);
  if (beforeDur !== afterDur) {
    changes.push(`Total duration ${beforeDur}s → ${afterDur}s`);
  }

  // Shot count delta
  if (before.shot_list.length !== after.shot_list.length) {
    changes.push(`Shots ${before.shot_list.length} → ${after.shot_list.length}`);
  }

  // Per-shot action changes (best-effort match by shot_id)
  const beforeMap = new Map(before.shot_list.map((s) => [s.shot_id, s]));
  for (const a of after.shot_list) {
    const b = beforeMap.get(a.shot_id);
    if (!b) {
      changes.push(`+ Thêm ${a.shot_id}`);
      continue;
    }
    if (b.duration_s !== a.duration_s) {
      changes.push(`${a.shot_id}: ${b.duration_s}s → ${a.duration_s}s`);
    }
    if (b.visual.action !== a.visual.action) {
      changes.push(`${a.shot_id} action thay đổi`);
    }
    if (b.audio.dialogue_vn !== a.audio.dialogue_vn) {
      changes.push(`${a.shot_id} dialogue thay đổi`);
    }
  }
  const afterIds = new Set(after.shot_list.map((s) => s.shot_id));
  for (const b of before.shot_list) {
    if (!afterIds.has(b.shot_id)) changes.push(`− Xoá ${b.shot_id}`);
  }

  // Bible visual_style changes
  if (before.continuity_bible.visual_style.color_grading !== after.continuity_bible.visual_style.color_grading) {
    changes.push('Color grading đổi');
  }
  if (before.continuity_bible.visual_style.lighting_design !== after.continuity_bible.visual_style.lighting_design) {
    changes.push('Lighting đổi');
  }

  return changes.length > 0 ? changes.join(' · ') : '';
}
