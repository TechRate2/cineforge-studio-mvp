/**
 * Model config — V6 refactor (3 user-facing models).
 *
 * SEEDANCE 2.0 CORE PATH:
 *   - seedance_2_0       — premium tier, 9 refs, multi-shot, quad-modal
 *   - seedance_2_0_fast  — mid tier (20% cheaper), same capability
 *
 * FALLBACK PATH:
 *   - wan_2_7            — driven-audio lip-sync VN, 1 portrait + 1 TTS, 5 or 10s
 *
 * Sync với backend/agent/model_specs.py VIDEO_MODEL_SPECS.
 */

import type { VideoModel, AspectRatio } from '../types/backend';

export interface ModelConfig {
  id: VideoModel;
  name_vn: string;
  name_short: string;
  description: string;
  max_references: number;
  max_duration_s: number;
  /** When set, the model only accepts these discrete duration values (e.g. Wan 2.7 = [5, 10]).
   *  UI must constrain the duration picker to these values. */
  duration_discrete?: number[];
  cost_per_second_usd: number;
  supports_audio_driven: boolean;
  supports_silent_only: boolean;
  supports_multi_shot_native: boolean;
  supports_native_audio: boolean;
  supports_quad_modal?: boolean;  // image + video + audio refs in 1 call
  best_for: string[];
  syntax_style: string;
  resolution_options: string[];
  resolution_default: string;
  aspect_ratio_options: AspectRatio[];
  supports_num_shots_override?: boolean;
  num_shots_range?: [number, number];
  reference_hint_vn?: string;
}

export const MODEL_CONFIGS: Record<VideoModel, ModelConfig> = {
  // 'auto' = let backend picker decide between Seedance 2.0 / Fast / Wan 2.7
  auto: {
    id: 'auto',
    name_vn: 'Mặc định (Seedance 2.0)',
    name_short: 'Default',
    description: 'Backend tự pick Seedance 2.0 hoặc fallback Wan 2.7 nếu cần lip-sync.',
    max_references: 9,
    max_duration_s: 15,
    cost_per_second_usd: 0.096,
    supports_audio_driven: false,
    supports_silent_only: false,
    supports_multi_shot_native: true,
    supports_native_audio: true,
    supports_quad_modal: true,
    best_for: ['Mặc định an toàn cho mọi niche'],
    syntax_style: 'Multi-shot timeline + @image / @video / @audio refs',
    resolution_options: ['480p', '720p', '720p-SR', '1080p', '1080p-SR'],
    resolution_default: '720p',
    aspect_ratio_options: ['9:16', '16:9', '1:1', '4:3', '3:4', '21:9', 'adaptive'],
  },

  // ─── SEEDANCE 2.0 CORE PATH ──────────────────────────────
  seedance_2_0: {
    id: 'seedance_2_0',
    name_vn: 'Seedance 2.0',
    name_short: 'Seedance 2.0',
    description: 'Quad-modal premium (9 images + 3 videos + 3 audio refs) — chất lượng cao nhất.',
    max_references: 9,
    max_duration_s: 15,
    cost_per_second_usd: 0.096,
    supports_audio_driven: false,
    supports_silent_only: false,
    supports_multi_shot_native: true,
    supports_native_audio: true,
    supports_quad_modal: true,
    best_for: ['Cinematic multi-shot', 'Narrative storytelling', 'Premium ad'],
    syntax_style: 'Multi-shot timeline [Shot N | Xs] + @image / @video / @audio refs',
    resolution_options: ['480p', '720p', '720p-SR', '1080p', '1080p-SR', '1440p-SR'],
    resolution_default: '720p',
    aspect_ratio_options: ['9:16', '16:9', '1:1', '4:3', '3:4', '21:9', 'adaptive'],
    supports_num_shots_override: true,
    num_shots_range: [2, 5],
    reference_hint_vn: '💡 Seedance 2.0 nhận quad-modal: 9 ảnh + 3 video refs (camera/motion) + 3 audio refs (beat/lip-sync). Sweet spot: 1 nhân vật + 1 product + 2-3 style refs.',
  },

  seedance_2_0_fast: {
    id: 'seedance_2_0_fast',
    name_vn: 'Seedance 2.0 Fast',
    name_short: 'Seedance 2.0 Fast',
    description: 'Quad-modal mid tier — rẻ hơn 2.0 20%, same capability.',
    max_references: 9,
    max_duration_s: 15,
    cost_per_second_usd: 0.076,
    supports_audio_driven: false,
    supports_silent_only: false,
    supports_multi_shot_native: true,
    supports_native_audio: true,
    supports_quad_modal: true,
    best_for: ['Daily UGC', 'Mid-tier quality', 'Volume content'],
    syntax_style: 'Same Seedance 2.0 — rapid preview tier',
    resolution_options: ['480p', '720p', '720p-SR', '1080p-SR', '1440p-SR'],
    resolution_default: '720p',
    aspect_ratio_options: ['9:16', '16:9', '1:1', '4:3', '3:4', '21:9', 'adaptive'],
    supports_num_shots_override: true,
    num_shots_range: [1, 4],
    reference_hint_vn: '💡 Seedance 2.0 Fast = preview rapid. Iterate ý tưởng rẻ trước khi gen full quality 2.0.',
  },

  // ─── FALLBACK PATH ───────────────────────────────────────
  wan_2_7: {
    id: 'wan_2_7',
    name_vn: 'Wan 2.7 (Lip-sync VN)',
    name_short: 'Wan 2.7',
    description: 'Driven-audio lip-sync VN — 1 portrait + 1 TTS file → model tự sync môi.',
    max_references: 1,
    max_duration_s: 10,
    duration_discrete: [5, 10],   // hard constraint — only 5 or 10
    cost_per_second_usd: 0.10,
    supports_audio_driven: true,
    supports_silent_only: false,
    supports_multi_shot_native: false,
    supports_native_audio: false,
    supports_quad_modal: false,
    best_for: ['Talking head VN', 'Lip-sync khớp môi', 'Dialogue presenter'],
    syntax_style: 'Portrait + pre-rendered TTS URL (driven audio)',
    resolution_options: ['480p', '720p', '1080p'],
    resolution_default: '720p',
    aspect_ratio_options: [],  // i2v derives aspect from input portrait
    reference_hint_vn: '💡 Wan 2.7: upload 1 ảnh PORTRAIT (front-facing, MOUTH UNOBSTRUCTED). Duration CHỈ 5s hoặc 10s. Audio dialogue cần TTS pre-render → backend pass vào field `audio` để lip-sync.',
  },
};

export function getModelConfig(model: VideoModel): ModelConfig {
  return MODEL_CONFIGS[model];
}

/**
 * Audio mode compatibility per model. All 3 modes accepted by all 3 models —
 * audio overlay/lip-sync handled at audio layer independently from video render.
 */
export function isAudioModeSupported(model: VideoModel, audioMode: string): boolean {
  void model;
  void audioMode;
  return true;
}

/**
 * Get reference image upload instructions per model.
 */
export function getReferenceInstructions(model: VideoModel): string {
  const config = MODEL_CONFIGS[model];
  switch (model) {
    case 'wan_2_7':
      return `Upload 1 ảnh PORTRAIT (front-facing). Driven-audio sẽ sync môi — duration chỉ 5s hoặc 10s.`;
    case 'seedance_2_0':
    case 'seedance_2_0_fast':
      return `Upload tối đa ${config.max_references} ảnh + 3 video refs + 3 audio refs (quad-modal). @image_1=primary character, @image_2=product, @video_1=camera motion.`;
    default:
      return `Upload tối đa ${config.max_references} ảnh tham chiếu.`;
  }
}
