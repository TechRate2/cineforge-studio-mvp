/**
 * Shared types match Pydantic schemas của backend FastAPI.
 * Source of truth: ./backend/api/schemas.py
 */

// ============================================
// AUDIO + MODEL ENUMS
// ============================================

export type AudioMode = 'silent_native' | 'dialogue_vo' | 'asmr_macro';

// AUDIT-C1: sync với backend Pydantic Literal 6 models (REMOVED wan_2_2_turbo — no Atlas endpoint)
// V3: thêm 'auto' — let model-aware picker chấm 6 strategies + pick fit script nhất
export type VideoModel =
  | 'auto'
  | 'vidu_q3'
  | 'vidu_q3_mix'
  | 'wan_2_7'
  | 'seedance_1_5_pro'
  | 'seedance_2_0'
  | 'seedance_2_0_fast';

export type AspectRatio = '9:16' | '16:9' | '1:1';

export type JobStatusEnum =
  | 'pending'
  | 'scraping'
  | 'analyzing'
  | 'generating'
  | 'rendering'
  | 'voicing'
  | 'sfx'
  | 'assembling'
  | 'uploading'
  | 'done'
  | 'failed';

// ============================================
// REQUEST TYPES
// ============================================

export interface ProductInput {
  url?: string;                  // Shopee/Lazada/Tiki link
  text_description?: string;     // Mô tả text nếu không có link
  image_urls?: string[];         // Ảnh sản phẩm upload
}

// Resolution loose string — mỗi model AtlasCloud có enum riêng (vidu_q3: 540p/720p/1080p,
// wan_2_7: 720P/1080P uppercase, seedance_2_0: 480p/720p/1080p/720p-SR/1080p-SR/...).
// Per-model validation ở backend agent/model_specs.py build_payload().
export type Resolution = string;

export interface VideoSettings {
  audio_mode: AudioMode;
  model: VideoModel;
  duration_s: number;
  aspect_ratio: AspectRatio;
  resolution: Resolution;
  setting_location?: string;
  voice_persona?: string;
  seed?: number;
  // V3.1 — num_shots override (chỉ Seedance 2.0/Fast). null/undefined = Director tự quyết.
  num_shots?: number | null;
}

// BUG-L3 fix: sync ApprovedScript Pydantic schema
export interface ApprovedScript {
  variant_id: string;
  hook_text_vn: string;
  body_text_vn?: string;
  cta_text_vn: string;
  framework?: string;
  total_duration_s?: number;
}

export interface CreateJobRequest {
  product_input: ProductInput;
  reference_images: string[];    // 1-12 ảnh tham chiếu (count tùy model)
  settings: VideoSettings;

  // Phase 2 → Phase 3 wire (Director Agent approval)
  proposal_id?: string;
  approved_script?: ApprovedScript;
  reference_mapping?: Record<string, any>;  // ReferenceMapping JSON

  // Legacy / advanced override
  template_id?: string;
  // avatar_id + avatar_image_url DEPRECATED — Casting Director đã thay bằng Reference Analyzer
  // Backend còn accept để backward compat nhưng frontend KHÔNG dùng nữa.
  avatar_id?: string;
  avatar_image_url?: string;
}

// ============================================
// RESPONSE TYPES
// ============================================

export interface JobCreatedResponse {
  job_id: string;
  status: 'pending';
  estimated_duration_s: number;
  estimated_cost_usd: number;
  polling_url: string;
}

export interface JobStatus {
  job_id: string;
  status: JobStatusEnum;
  progress: number;              // 0-100
  current_step?: string;
  estimated_remaining_s?: number;
  output_url?: string;
  thumbnail_url?: string;
  duration_s?: number;
  cost_actual_usd?: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface Template {
  id: string;
  name_vn: string;
  name_en: string;
  category: string;
  tier: 'S' | 'A' | 'B';
  default_duration_s: number;
  default_audio_mode: AudioMode;
  aspect_ratio: AspectRatio;
  thumbnail_url?: string;
  sample_video_url?: string;
  use_cases_vn: string[];
}

export interface Avatar {
  id: string;
  name: string;
  ethnicity: string;
  age: number;
  gender: 'female' | 'male';
  style: string;
  vibe: string;
  image_url: string;
  is_preset: boolean;
}
