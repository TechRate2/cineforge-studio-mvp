/**
 * Master Storyboard Board — shared FE config.
 *
 * Single source of truth for the FE-side rules around the optional 9/12-panel
 * master canvas anchor. Previously duplicated in 3 files (PromptCardV2,
 * page.tsx, DirectorPlanModal) — V5.16.3 consolidates here so adding a new
 * eligible model is one edit instead of three.
 *
 * MUST stay in sync with backend scene_generation_agent.py's
 * `is_seedance_ref_for_board` check (which whitelists the ATLAS vendor keys
 * resolved from these user model keys).
 */
import type { VideoModel } from '@/lib/types/backend';

/** Models that benefit from Master Board global anchor injection. */
export const MASTER_BOARD_ELIGIBLE_MODELS = new Set<VideoModel>([
  'auto',
  'seedance_2_0',
  'seedance_2_0_fast',
]);

/** Minimum shot count to auto-trigger Master Board (single-shot doesn't need anchor). */
export const MASTER_BOARD_MIN_SHOTS = 2;

/** Master Board generation cost in USD (Seedream v4.5 ultra-wide image). */
export const MASTER_BOARD_COST_USD = 0.04;

/** Helper — is the given model (any string from settings) eligible? */
export function isMasterBoardEligible(model: string): boolean {
  return MASTER_BOARD_ELIGIBLE_MODELS.has(model as VideoModel);
}
