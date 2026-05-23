/**
 * Model config — config max_references + max_duration + features per model.
 * Sync với backend agent/model_adapter.py MODEL_REGISTRY.
 *
 * Quan trọng: UI dynamic theo model selected:
 * - Vidu Q3 chọn → max upload 4 ảnh
 * - Wan 2.7 chọn → max upload 9 ảnh
 * - Seedance 1.5 Pro → max 9, silent only
 * - Seedance 2.0 → max 12 files (9 images + 3 videos + 3 audio)
 */

import type { VideoModel } from '../types/backend';

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
  best_for: string[];
  syntax_style: string;
  // Resolution enum per model — sync với backend agent/model_specs.py
  // Vidu Q3 dùng 540p/720p/1080p (KHÔNG có 480p); Wan dùng 720P/1080P uppercase
  resolution_options: string[];
  resolution_default: string;
  // V3.1 — num_shots override (Seedance 2.0/Fast multi-shot pattern Topview)
  // Khi supports_num_shots_override=true → UI hiện dropdown "Số shot: Auto/2/3/4/5"
  supports_num_shots_override?: boolean;
  num_shots_range?: [number, number];  // [min, max] cho dropdown
  // V3.1 — Reference upload UI hint per-model (Vidu Q3 multi-angle product, ...)
  reference_hint_vn?: string;
}

export const MODEL_CONFIGS: Record<VideoModel, ModelConfig> = {
  // V3 — 'auto' = let backend picker decide. UI hiển thị placeholder, backend dispatch.
  auto: {
    id: 'auto',
    name_vn: 'Mặc định (Seedance 2.0)',
    name_short: 'Default',
    description: 'Mặc định Seedance 2.0 — multi-shot native, audio, max 9 refs.',
    // Limits match what `auto` actually resolves to on the backend (seedance_2_0).
    max_references: 9,
    max_duration_s: 15,
    cost_per_second_usd: 0.096,
    supports_audio_driven: false,
    supports_silent_only: false,
    supports_multi_shot_native: true,
    supports_native_audio: true,
    best_for: ['Mặc định an toàn cho mọi niche'],
    syntax_style: 'Multi-shot timeline + @image refs',
    resolution_options: ['480p', '720p', '720p-SR', '1080p', '1080p-SR'],
    resolution_default: '720p',
  },
  vidu_q3: {
    id: 'vidu_q3',
    name_vn: 'Vidu Q3',
    name_short: 'Vidu Q3',
    description: 'Reference-to-video, multi-entity consistency, native audio. Rẻ nhất.',
    max_references: 4,
    max_duration_s: 16,
    cost_per_second_usd: 0.042,
    supports_audio_driven: false,
    supports_silent_only: false,
    supports_multi_shot_native: false,
    supports_native_audio: true,
    best_for: ['UGC budget', 'Multi-character scene', 'Aesthetic lifestyle'],
    syntax_style: 'Detailed scene description với 1-4 ảnh anchor',
    resolution_options: ['540p', '720p', '1080p'],
    resolution_default: '720p',
    reference_hint_vn: '💡 Vidu Q3 mạnh nhất khi upload 2-3 ảnh product MULTI-ANGLE (front + side + detail). Identity consistency tăng rõ rệt.',
  },

  vidu_q3_mix: {
    id: 'vidu_q3_mix',
    name_vn: 'Vidu Q3-Mix',
    name_short: 'Vidu Q3-Mix',
    description: 'Premium variant — hỗ trợ @image_N tags + 720p/1080p.',
    max_references: 4,
    max_duration_s: 16,
    cost_per_second_usd: 0.106,
    supports_audio_driven: false,
    supports_silent_only: false,
    // BUG #4 fix — Vidu Q3 Mix DOES understand `@image_N` tags (vs Q3 non-mix
    // which binds by array order). This matches backend `_MODELS_SUPPORT_IMAGE_TAGS`.
    supports_multi_shot_native: true,
    supports_native_audio: true,
    best_for: ['Premium ad', '720p/1080p', 'Multi-subject scene'],
    syntax_style: 'Descriptive + @image_1, @image_2 tags để bind subject',
    // BUG #4 fix — backend spec cho phép 720p + 1080p. Lock 1080p only trước đó
    // làm user mất tuỳ chọn rẻ hơn (~30%) ở quality 720p.
    resolution_options: ['720p', '1080p'],
    resolution_default: '720p',
    reference_hint_vn: '💡 Vidu Q3 Mix hiểu @image_1, @image_2 tags. Upload tối đa 4 ảnh — primary subject ở vị trí đầu.',
  },

  wan_2_7: {
    id: 'wan_2_7',
    name_vn: 'Wan 2.7',
    name_short: 'Wan 2.7',
    description: 'Lip-sync VN driven by audio URL — 1 portrait + 1 audio file.',
    max_references: 1,
    max_duration_s: 10,
    duration_discrete: [5, 10],  // BUG #4 fix — explicit lock in FE
    cost_per_second_usd: 0.1,
    // BUG #4 fix — Wan uses DRIVEN audio (field `audio` URL), NOT native gen.
    // FE should NOT advertise native audio — would mislead users into thinking
    // the model auto-generates dialogue.
    supports_audio_driven: true,
    supports_silent_only: false,
    supports_multi_shot_native: false,
    supports_native_audio: false,
    best_for: ['Talking head VN', 'Lip-sync khớp môi', 'Dialogue presenter'],
    syntax_style: 'Portrait + pre-rendered TTS URL (driven audio)',
    resolution_options: ['480p', '720p', '1080p'],
    resolution_default: '720p',
    reference_hint_vn: '💡 Wan 2.7: upload 1 ảnh PORTRAIT (front-facing, MOUTH UNOBSTRUCTED). Duration CHỈ chọn 5s hoặc 10s. Audio dialogue cần TTS pre-render → backend tự pass vào field `audio` để lip-sync.',
  },

  // AUDIT-C1: REMOVED wan_2_2_turbo (KHÔNG có endpoint Atlas thật)
  seedance_1_5_pro: {
    id: 'seedance_1_5_pro',
    name_vn: 'Seedance 1.5 Pro',
    name_short: 'Seedance 1.5 Pro',
    // BUG #4 fix — Seedance 1.5 Pro chỉ có variants i2v / t2v / i2v-fast trên
    // AtlasCloud, KHÔNG có ref-to-video. Backend route i2v variant nhận max 1 image.
    description: 'Image-to-video budget tier — 1 anchor + native audio, 4-12s.',
    max_references: 1,
    max_duration_s: 12,
    cost_per_second_usd: 0.047,
    supports_audio_driven: false,
    supports_silent_only: false,
    supports_multi_shot_native: false,
    // BUG #4 fix — spec `extra_fields.generate_audio` default=True → native.
    supports_native_audio: true,
    best_for: ['Budget shots', 'Product showcase từ 1 anchor', 'B-roll'],
    syntax_style: 'Image-to-video — pass 1 anchor image, prompt mô tả motion',
    resolution_options: ['480p', '720p'],
    resolution_default: '720p',
    reference_hint_vn: '💡 Seedance 1.5 Pro chỉ nhận 1 ảnh anchor (image-to-video). Prompt mô tả motion + camera move; reference khác đưa qua Storyboard zone.',
  },

  seedance_2_0: {
    id: 'seedance_2_0',
    name_vn: 'Seedance 2.0',
    name_short: 'Seedance 2.0',
    description: 'Multi-shot native (@image_1..9), audio, cao cấp nhất.',
    // BUG #4 fix — AtlasCloud spec: max 9 reference_images (NOT 12).
    max_references: 9,
    max_duration_s: 15,
    cost_per_second_usd: 0.096,
    supports_audio_driven: false,
    supports_silent_only: false,
    supports_multi_shot_native: true,
    supports_native_audio: true,
    best_for: ['Cinematic multi-shot', 'Narrative storytelling', 'Premium ad'],
    syntax_style: 'Multi-shot timeline S1[0-4s]/S2[4-9s]/S3[9-15s] + @Image refs',
    // BUG #4 fix — backend spec also lists 1440p-SR; expose it here.
    resolution_options: ['480p', '720p', '720p-SR', '1080p', '1080p-SR', '1440p-SR'],
    resolution_default: '720p',
    supports_num_shots_override: true,
    num_shots_range: [2, 5],
    reference_hint_vn: '💡 Seedance 2.0 nhận tới 9 ảnh + 3 video refs. Upload: 1 nhân vật + 1 product + 2-3 setting/lighting refs. Mỗi shot 3-5s sweet spot.',
  },

  seedance_2_0_fast: {
    id: 'seedance_2_0_fast',
    name_vn: 'Seedance 2.0 Fast',
    name_short: 'Seedance 2.0 Fast',
    description: 'Fast variant Seedance 2.0, audio native, cost balance.',
    // BUG #4 fix — AtlasCloud spec: max 9 (not 12).
    max_references: 9,
    max_duration_s: 15,
    cost_per_second_usd: 0.076,
    supports_audio_driven: false,
    supports_silent_only: false,
    supports_multi_shot_native: true,
    supports_native_audio: true,
    best_for: ['Daily UGC', 'Mid-tier quality', 'Voice + visual balance'],
    syntax_style: 'Multi-shot timeline với audio native',
    resolution_options: ['480p', '720p', '720p-SR', '1080p-SR', '1440p-SR'],
    resolution_default: '720p',
    supports_num_shots_override: true,
    num_shots_range: [1, 3],  // Fast variant best 1-2 shots
    reference_hint_vn: '💡 Seedance 2.0 Fast = rapid preview. 1-2 ref đủ. Sweet spot 1 shot 3-5s. Iterate ý tưởng rẻ trước khi gen full.',
  },
};

export function getModelConfig(model: VideoModel): ModelConfig {
  return MODEL_CONFIGS[model];
}

/**
 * Audio mode compatibility per model.
 * Một số model KHÔNG support 1 số audio mode.
 */
export function isAudioModeSupported(model: VideoModel, audioMode: string): boolean {
  const config = MODEL_CONFIGS[model];

  // Seedance 1.5 Pro silent only — nếu user chọn dialogue_vo phải overlay post
  if (config.supports_silent_only && audioMode === 'dialogue_vo') {
    return false; // ⚠️ Not native, must overlay TTS post-production
  }

  return true;
}

/**
 * Get reference image upload instructions per model.
 */
export function getReferenceInstructions(model: VideoModel): string {
  const config = MODEL_CONFIGS[model];
  switch (model) {
    case 'vidu_q3':
      return `Upload 1-${config.max_references} ảnh tham chiếu (subject, product, setting). Multi-entity consistency strong.`;
    case 'vidu_q3_mix':
      return `Upload 1-${config.max_references} ảnh — Vidu Q3-Mix premium 1080p, focus chi tiết texture.`;
    case 'wan_2_7':
      return `Upload tối đa ${config.max_references} ảnh (3×3 grid synthesis). Tối ưu: 3 góc subject + 3 lighting variation + 3 environment.`;
    case 'seedance_1_5_pro':
      return `Upload tối đa ${config.max_references} ảnh refs — Seedance 1.5 Pro silent, post-prod overlay TTS.`;
    case 'seedance_2_0':
    case 'seedance_2_0_fast':
      return `Upload tối đa ${config.max_references} files (9 images + 3 videos + 3 audio). @Image1=primary, @Image2=outfit, @Character1=face lock.`;
    default:
      return `Upload tối đa ${config.max_references} ảnh tham chiếu.`;
  }
}
