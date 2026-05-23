'use client';

/**
 * use-director-plan-editor — Local mutable wrapper around a DirectorPlan.
 *
 * The Director Agent produces a `DirectorPlan` which the user reviews in
 * `DirectorPlanModal`. The legacy flow only supported Approve/Cancel. This
 * hook adds HitL inline editing — the user can tweak the Bible, the Shot
 * List, even the storyboard prompts BEFORE clicking Approve. The render
 * endpoint receives the edited plan and re-validates continuity.
 *
 * Design:
 *   - Deep-clones the incoming plan once into local React state.
 *   - Exposes typed mutators per editable field (`updateShot`,
 *     `updateCharacter`, `updateVisualStyle`, …) so each call only touches
 *     the slice that changed (no full structural replacements that lose
 *     focus on inputs).
 *   - Tracks `isDirty` so the UI can show "● Modified" indicators and
 *     enable a "Reset to original" button.
 *   - All editable fields are deliberately SCALARS or short lists — we do
 *     NOT support restructuring the plan (adding/removing characters,
 *     reordering shots) here because those changes invalidate continuity
 *     chains in ways the user usually doesn't intend.
 */

import { useCallback, useMemo, useRef, useState } from 'react';
import type {
  DirectorPlan,
  Shot,
  Character,
  VisualStyle,
} from './use-director-plan';

// ============================================================
// Editable field paths (limited scope per V3 contract)
// ============================================================
export interface ShotEdits {
  duration_s?: number;
  visual?: { action?: string; subject?: string; camera_shot?: string; camera_movement?: string };
  audio?: { dialogue_vn?: string | null; caption_on_screen?: string | null };
  continuity?: { reference_indices?: number[]; previous_shot_id?: string | null };
}

export interface CharacterEdits {
  face_signature?: string;
  outfit?: string;
}

export interface VisualStyleEdits {
  color_grading?: string;
  lighting_design?: string;
  cinematography?: string;
}

// ============================================================
// Hook
// ============================================================
export function useDirectorPlanEditor(initialPlan: DirectorPlan | null) {
  // The original (immutable snapshot) — used for the "Reset" affordance.
  const originalRef = useRef<DirectorPlan | null>(null);
  if (initialPlan && originalRef.current?.plan_id !== initialPlan.plan_id) {
    originalRef.current = structuredClone(initialPlan);
  }

  const [plan, setPlan] = useState<DirectorPlan | null>(initialPlan);
  const [dirtyShots, setDirtyShots] = useState<Set<string>>(new Set());
  const [bibleDirty, setBibleDirty] = useState(false);

  // Sync when a fresh plan arrives (e.g. after Re-plan).
  if (initialPlan && plan?.plan_id !== initialPlan.plan_id) {
    setPlan(structuredClone(initialPlan));
    setDirtyShots(new Set());
    setBibleDirty(false);
  }

  const isDirty = bibleDirty || dirtyShots.size > 0;

  // -------------------- Shot mutators --------------------
  const updateShot = useCallback((shotId: string, edits: ShotEdits) => {
    setPlan((p) => {
      if (!p) return p;
      const next = structuredClone(p);
      const shot = next.shot_list.find((s) => s.shot_id === shotId);
      if (!shot) return p;

      if (edits.duration_s !== undefined && Number.isFinite(edits.duration_s)) {
        // Clamp to schema range; keep 1-decimal start/end recompute later in normalize step
        shot.duration_s = Math.max(2, Math.min(20, Math.round(edits.duration_s)));
      }
      if (edits.visual) Object.assign(shot.visual, edits.visual);
      if (edits.audio) Object.assign(shot.audio, edits.audio);
      if (edits.continuity) {
        if (edits.continuity.reference_indices !== undefined) {
          shot.continuity.reference_indices = [...edits.continuity.reference_indices];
        }
        if (edits.continuity.previous_shot_id !== undefined) {
          shot.continuity.previous_shot_id = edits.continuity.previous_shot_id;
        }
      }

      // Re-normalize start_s / end_s so the timeline stays continuous.
      let cursor = 0;
      for (const s of next.shot_list) {
        s.start_s = Math.round(cursor * 100) / 100;
        s.end_s = Math.round((cursor + s.duration_s) * 100) / 100;
        cursor = s.end_s;
      }
      next.continuity_bible.duration_s = Math.round(cursor);

      return next;
    });
    setDirtyShots((d) => {
      const n = new Set(d);
      n.add(shotId);
      return n;
    });
  }, []);

  // -------------------- Bible mutators --------------------
  const updateCharacter = useCallback((characterId: string, edits: CharacterEdits) => {
    setPlan((p) => {
      if (!p) return p;
      const next = structuredClone(p);
      const c = next.continuity_bible.characters.find((c) => c.id === characterId);
      if (!c) return p;
      if (edits.face_signature !== undefined) c.face_signature = edits.face_signature;
      if (edits.outfit !== undefined) c.outfit = edits.outfit;
      return next;
    });
    setBibleDirty(true);
  }, []);

  const updateVisualStyle = useCallback((edits: VisualStyleEdits) => {
    setPlan((p) => {
      if (!p) return p;
      const next = structuredClone(p);
      Object.assign(next.continuity_bible.visual_style, edits);
      return next;
    });
    setBibleDirty(true);
  }, []);

  // -------------------- Reset to original --------------------
  const reset = useCallback(() => {
    if (originalRef.current) {
      setPlan(structuredClone(originalRef.current));
      setDirtyShots(new Set());
      setBibleDirty(false);
    }
  }, []);

  // Summary for the UI (totals after edits)
  const summary = useMemo(() => {
    if (!plan) return null;
    return {
      total_duration_s: plan.shot_list.reduce((s, x) => s + x.duration_s, 0),
      shot_count: plan.shot_list.length,
      dirty_shot_ids: Array.from(dirtyShots),
      bible_dirty: bibleDirty,
    };
  }, [plan, dirtyShots, bibleDirty]);

  return {
    plan,                // edited plan (or original if not yet edited)
    isDirty,
    bibleDirty,
    dirtyShots,          // Set<shot_id>
    summary,
    updateShot,
    updateCharacter,
    updateVisualStyle,
    reset,
  };
}
