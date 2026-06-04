'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { RotateCcw, Sparkles } from 'lucide-react';
import { CommandComposer } from '@/components/studio/CommandComposer';
import {
  CommercialControls,
  type BrandKitOption,
  type CommercialAnalyticsSummary,
  type CommercialTemplateOption,
  type CommercialUsageSummary,
} from '@/components/studio/CommercialControls';
import { JobResultModal } from '@/components/studio/JobResultModal';
import { PipelinePreview } from '@/components/studio/PipelinePreview';
import { PipelineTraceView } from '@/components/studio/PipelineTraceView';
import { RecentGenerations } from '@/components/studio/RecentGenerations';
import { ReferenceTray } from '@/components/studio/ReferenceTray';
import { RenderReviewPanel } from '@/components/studio/RenderReviewPanel';
import { SettingsBar } from '@/components/studio/SettingsBar';
import { StoryboardTimeline } from '@/components/studio/StoryboardTimeline';
import { usePersistedJob } from '@/lib/studio/use-persisted-job';
import { uploadMediaToR2 } from '@/lib/studio/upload-media';

const DRAFT_STORAGE_KEY = 'cineforge:autonomous_draft_v1';
const AUTONOMOUS_MAX_IMAGES = 9;
const AUTONOMOUS_MAX_VIDEOS = 3;
const AUTONOMOUS_MAX_AUDIO = 3;
const AUTONOMOUS_MAX_TOTAL_REFS = 12;
const CHAT_HISTORY_LIMIT = 12;
const CONSISTENCY_REVIEW_HISTORY_LIMIT = 10;
const BRIEF_MAX_CHARS = 3000;
const CHAT_INPUT_MAX_CHARS = 1000;
const SCENE_PREVIEW_MAX = 12;
const DEFAULT_SCENE_DURATION_S = 8;
const COMMERCIAL_USER_ID = 'default_user';

const VIDEO_MODEL_OPTIONS = [
  { value: 'auto', label: 'Auto route', hint: 'Agent selects Fast T2V/I2V/Reference from the uploaded refs.' },
  { value: 'seedance_2_0_fast', label: 'Seedance Fast', hint: 'Lower-cost Seedance 2.0 family; resolves to Fast T2V/I2V/Ref.' },
  { value: 'seedance_2_0', label: 'Seedance Pro', hint: 'Higher-fidelity Seedance 2.0 family for premium hero shots.' },
  { value: 'wan_2_7', label: 'Wan lip-sync', hint: 'Use only for image-driven talking-head/lip-sync jobs.' },
] as const;

const ASPECT_OPTIONS = [
  { value: 'auto', label: 'Auto frame', hint: 'Agent picks the safest output frame from platform and brief.' },
  { value: '9:16', label: '9:16 vertical', hint: 'TikTok, Reels, Shorts default.' },
  { value: '16:9', label: '16:9 wide', hint: 'YouTube, landing pages, cinematic landscape.' },
  { value: '1:1', label: '1:1 square', hint: 'Feed posts and marketplace/product tiles.' },
] as const;

const QUALITY_OPTIONS = [
  { value: 'balanced', label: 'Balanced', resolution: '720p', hint: 'recommended cost/speed' },
  { value: 'high', label: 'High', resolution: '1080p', hint: 'sharper final render' },
] as const;

const DURATION_OPTIONS = [
  { value: 0, label: 'Auto', hint: 'Agent decides' },
  { value: 8, label: '8s', hint: 'single Seedance clip' },
  { value: 12, label: '12s', hint: 'short Seedance clip' },
  { value: 15, label: '15s', hint: 'maximum single Seedance clip' },
  { value: 30, label: '30s', hint: 'long-form segmented, 3 clips' },
  { value: 45, label: '45s', hint: 'long-form segmented, 4 clips' },
  { value: 60, label: '60s', hint: 'long-form segmented, 5 clips' },
] as const;

type QualityPreset = (typeof QUALITY_OPTIONS)[number]['value'];
type VideoModelChoice = (typeof VIDEO_MODEL_OPTIONS)[number]['value'];
type AspectRatioChoice = (typeof ASPECT_OPTIONS)[number]['value'];

const TARGET_MARKET_OPTIONS = [
  { value: 'auto', label: 'Auto', hint: 'detect from idea' },
  { value: 'vn', label: 'VN', hint: 'Vietnam market' },
  { value: 'us', label: 'US', hint: 'United States' },
  { value: 'sea', label: 'SEA', hint: 'Southeast Asia' },
  { value: 'jp', label: 'JP', hint: 'Japan' },
  { value: 'kr', label: 'KR', hint: 'Korea' },
  { value: 'global', label: 'Global', hint: 'international' },
] as const;

const STARTER_PROMPTS = [
  'TikTok VN beauty serum launch with proof-first hook and soft creator voice',
  '15s founder story for a Vietnamese cafe, emotional but premium',
  'Short drama episode about betrayal, one twist, cinematic vertical style',
  'Product demo for a SaaS tool, global market, fast social ad pacing',
] as const;

interface ResponsibleContentGate {
  render_allowed?: boolean;
  rewrite_guidance?: string[];
}

interface NicheResolution {
  clarifying_questions?: string[];
}

interface LlmBrainRouteSummary {
  complexity_score?: number;
  complexity_band?: string;
  primary_text_model?: string;
  analyzer_model?: string;
  vision_model?: string | null;
  pro_candidate?: string | null;
  pro_selected?: boolean;
  premium_candidate?: string | null;
  premium_selected?: boolean;
  cost_mode?: string;
  safe_default?: boolean;
}

interface CreativeBriefContract {
  parsed?: {
    output_intent?: string;
    subject?: {
      status?: string;
      summary?: string;
      hints?: string[];
    };
    goals?: Array<{ key?: string; score?: number; hits?: string[] }>;
    audiences?: Array<{ key?: string; score?: number; hits?: string[] }>;
    style_signals?: Array<{ key?: string; score?: number; hits?: string[] }>;
    target_platform?: string;
    duration?: {
      requested_s?: number | null;
      source?: string;
    };
  };
  missing_fields?: Array<{ key?: string; severity?: string; question?: string }>;
  readiness?: {
    status?: string;
    completeness_score?: number;
    can_build_preflight?: boolean;
    should_ask_before_paid_render?: boolean;
  };
}

interface CreativeProducerV2 {
  producer_id?: string;
  selected_angle?: {
    angle_id?: string;
    label?: string;
    score?: number;
    risk_level?: string;
    selection_reason?: string;
    hook?: string;
    story_engine?: string;
  };
  script_beats?: Array<{
    beat_id?: string;
    beat?: string;
    duration_s?: number;
    purpose?: string;
    script?: string;
    turn?: string;
  }>;
  shot_graph?: {
    node_count?: number;
    edge_count?: number;
    nodes?: Array<{
      shot_id?: string;
      beat_id?: string;
      duration_s?: number;
      purpose?: string;
      visual_intent?: string;
      camera_intent?: string;
      model_route_hint?: string;
    }>;
  };
}

interface PromptExecutionContractV3 {
  readiness?: {
    status?: string;
    compiled_shot_count?: number;
    warning_count?: number;
  };
  model_plan?: {
    primary_visual_model?: string;
    continuity_model?: string;
    model_counts?: Record<string, number>;
    render_mode_counts?: Record<string, number>;
    llm_text_brain?: string;
    llm_cost_mode?: string;
  };
  compiled_shots?: Array<{
    shot_id?: string;
    duration_s?: number;
    model_key?: string;
    render_mode?: string;
    prompt?: string;
  }>;
  warnings?: string[];
}

interface ViralCreativeBrain {
  readiness?: {
    status?: string;
    creative_score?: number;
    hook_variant_count?: number;
    variant_count?: number;
  };
  selected_viral_pattern?: {
    pattern_id?: string;
    label?: string;
    score?: number;
    risk_level?: string;
    hook_formula?: string;
    retention_engine?: string;
  };
  hook_variants?: Array<{
    id?: string;
    type?: string;
    opening_frame?: string;
    first_3s_line?: string;
    camera?: string;
  }>;
  platform_package?: {
    title_variants?: string[];
    caption_draft?: string;
    cover_frame_cue?: string;
    cta?: string;
    hashtags?: string[];
  };
  risk_guards?: Array<{ severity?: string; risk?: string; fix?: string }>;
}

interface OutputQaRetryBrain {
  readiness?: {
    status?: string;
    qa_confidence_score?: number;
    qa_node_count?: number;
    retry_recipe_count?: number;
    warning_count?: number;
  };
  retry_policy?: {
    max_retries_per_shot?: number;
    retry_scope?: string;
    requires_user_approval_before_paid_retry?: boolean;
  };
  acceptance_gate?: {
    minimum_sequence_score?: number;
    minimum_shot_score?: number;
    hard_failures_block_delivery?: boolean;
  };
  issue_taxonomy?: Array<{ issue_tag?: string; severity?: string; detection?: string; retry_action?: string }>;
  warnings?: Array<{ severity?: string; risk?: string; fix?: string }>;
}

interface ProductionDecision {
  decision?: {
    niche_resolution_review_required?: boolean;
    responsible_review_required?: boolean;
    render_blocked_by_responsible_gate?: boolean;
    niche?: string;
    runtime_class?: string;
    target_duration_s?: number;
    graph_required?: boolean;
    primary_model_route?: {
      primary_visual_model?: string;
      route_source_of_truth?: string;
      legacy_primary_visual_model?: string;
    };
    llm_brain_route?: LlmBrainRouteSummary;
  };
  input_summary?: {
    niche_resolution?: NicheResolution;
  };
  responsible_content_gate?: ResponsibleContentGate;
  llm_brain_policy?: {
    route_summary?: LlmBrainRouteSummary;
    complexity?: { score?: number; band?: string };
    cost_guard?: Record<string, unknown>;
  };
  creative_brief_contract?: CreativeBriefContract;
  creative_producer_v2?: CreativeProducerV2;
  prompt_execution_contract_v3?: PromptExecutionContractV3;
  viral_creative_brain?: ViralCreativeBrain;
  output_qa_retry_brain?: OutputQaRetryBrain;
  model_route_strategy?: {
    summary?: {
      primary_visual_model?: string;
      continuity_model?: string;
      route_mode?: string;
    };
  };
}

interface ProductIntelligence {
  status?: string;
  source_url?: string;
  title?: string;
  description?: string;
  primary_image_url?: string;
  brief_addition?: string;
  product_keywords?: string[];
  error?: { code?: string; message?: string };
  reference_suggestion?: {
    kind?: ReferenceKind;
    role?: ReferenceRole;
    url?: string;
    name?: string;
    why?: string;
  } | null;
}

interface DeepPreflightBrain {
  mode?: string;
  vendor_calls_performed?: boolean;
  llm_calls_performed?: boolean;
  paid_video_vendor_calls_allowed?: boolean;
  cost_guard?: {
    text_model?: string;
    vision_model?: string | null;
    trigger?: string;
  };
  route_source_of_truth?: {
    primary_visual_model?: string;
    continuity_model?: string;
    route_mode?: string;
    source?: string;
  };
  deep_brief?: {
    one_sentence_goal?: string;
    target_viewer?: string;
    viewer_payoff?: string;
    creative_angle?: string;
    tone?: string;
  };
  reference_brain?: {
    source?: string;
    role_mix_safe_for_paid_render?: boolean;
    vision_suggestions?: Array<{
      tag?: string;
      role?: ReferenceRole;
      confidence?: number;
      reason?: string;
      role_confirmed?: boolean;
    }>;
  };
  missing_inputs?: Array<{ priority?: string; kind?: string; action?: string; why?: string }>;
  user_message?: string;
  errors?: Array<{ stage?: string; error?: string }>;
  production_decision?: ProductionDecision;
}

interface AutonomousPreview {
  caption_vn?: string;
  hashtags_vn?: string[];
  hook_first_3s?: string;
  niche?: string;
  n_shots?: number;
  distribution_package?: Record<string, unknown>;
  producer_strategy?: Record<string, unknown>;
  autonomous_preflight?: Record<string, unknown>;
  auto_pin_selection?: Record<string, unknown>;
  approved_plan?: {
    id?: string;
    source_hash?: string;
    source_length?: number;
    included_in_render_source?: boolean;
  };
  execution_mode?: string;
  job_id?: string;
  render_dry_run_report?: Record<string, unknown>;
  longform_plan?: LongformPlanPreview | null;
  requires_consistency_review?: boolean;
  consistency_policy?: ConsistencyPolicyPreview;
}

interface LongformSegmentPreview {
  segment_id?: string;
  index?: number;
  start_s?: number;
  duration_s?: number;
  objective?: string;
  entry_state?: Record<string, unknown>;
  exit_state?: Record<string, unknown>;
  handoff_requirements?: string[];
  status?: string;
}

interface LongformPlanPreview {
  longform_plan_id?: string;
  total_duration_s?: number;
  continuity_pressure?: string;
  segment_graph_hash?: string;
  continuity_bible_hash?: string;
  segments?: LongformSegmentPreview[];
  handoffs?: Array<Record<string, unknown>>;
  warnings?: string[];
}

interface ConsistencyPolicyPreview {
  action?: string;
  reasons?: string[];
  review_approved?: boolean;
  review_decision?: string;
  review_reason?: string;
  reviewed_segment_ids?: string[];
}

interface ConsistencyReviewHistoryItem {
  decision: 'approved' | 'rejected';
  reason: string;
  segmentIds: string[];
  createdAt: string;
}

interface ConversationalPreflight {
  status?: 'needs_user_input' | 'ready_for_approval' | 'approved_for_render' | string;
  render_ready?: boolean;
  approval_required?: boolean;
  planning_trace?: {
    engine_mode?: string;
    vendor_calls_performed?: boolean;
    llm_calls_performed?: boolean;
    paid_video_vendor_calls_allowed?: boolean;
    why_response_is_fast?: string;
    next_live_vendor_stage?: string;
    planned_llm_route?: LlmBrainRouteSummary;
    source_modules?: string[];
  };
  assistant_message?: string;
  blocking_questions?: Array<{ id?: string; question?: string; why?: string; suggested_replies?: string[] }>;
  suggested_replies?: string[];
  approved_brief?: string;
  approved_plan?: {
    id?: string;
    source_hash?: string;
    source_length?: number;
    included_in_render_source?: boolean;
  };
  summary?: {
    niche?: string;
    market?: string;
    target_platform?: string;
    runtime_class?: string;
    target_duration_s?: number;
    graph_required?: boolean;
    primary_visual_model?: string;
    llm_brain_route?: LlmBrainRouteSummary;
    brief_readiness?: string;
    brief_completeness_score?: number;
    producer_angle?: string;
    producer_angle_id?: string;
    script_beat_count?: number;
    shot_graph_node_count?: number;
    prompt_contract_status?: string;
    compiled_shot_count?: number;
    prompt_contract_warning_count?: number;
    prompt_primary_visual_model?: string;
    viral_brain_status?: string;
    viral_creative_score?: number;
    viral_pattern?: string;
    viral_pattern_id?: string;
    viral_hook_count?: number;
    output_qa_status?: string;
    qa_confidence_score?: number;
    qa_node_count?: number;
    retry_recipe_count?: number;
    qa_warning_count?: number;
  };
  creative_brief_contract?: CreativeBriefContract;
  creative_producer_v2?: CreativeProducerV2;
  prompt_execution_contract_v3?: PromptExecutionContractV3;
  viral_creative_brain?: ViralCreativeBrain;
  output_qa_retry_brain?: OutputQaRetryBrain;
  creative_plan?: {
    title?: string;
    logline?: string;
    creative_angle?: string;
    viewer_promise?: string;
    tone?: string;
    runtime?: string;
  };
  script_outline?: Array<{
    beat?: string;
    duration_s?: number;
    purpose?: string;
    script?: string;
    turn?: string;
  }>;
  storyboard?: Array<{
    id?: string;
    frame?: string;
    visual?: string;
    camera?: string;
    audio?: string;
  }>;
  input_suggestions?: Array<{ priority?: string; action?: string; why?: string }>;
  approval_checklist?: Array<{ key?: string; label?: string; status?: string; detail?: string }>;
  distribution_preview?: {
    caption_language?: string;
    hook_style?: string;
    hook_first_3s?: string;
    caption_draft?: string;
    title_hint?: string;
    cover_frame_cue?: string;
    hashtags?: string[];
  };
  conversation_context?: {
    message_count?: number;
    user_turn_count?: number;
    assistant_turn_count?: number;
    latest_user_turn?: string;
  };
  production_decision?: ProductionDecision;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  intent?: 'idea' | 'revision';
}

const INITIAL_CHAT_MESSAGES: ChatMessage[] = [
  {
    id: 'assistant_welcome',
    role: 'assistant',
    text: 'Tell me the video idea, audience, product or story. I will turn it into a script and storyboard before render.',
  },
];

function compactModelName(model?: string | null): string {
  if (!model) return 'off';
  return model
    .replace('deepseek-ai/', '')
    .replace('qwen/', '')
    .replace('anthropic/', '')
    .replace(/-/g, ' ');
}

type ReferenceKind = 'image' | 'video' | 'audio';
type ReferenceRole =
  | 'character_anchor'
  | 'secondary_character'
  | 'product_hero'
  | 'product_detail'
  | 'style_reference'
  | 'environment'
  | 'brand_asset'
  | 'camera_motion'
  | 'motion_style'
  | 'shot_pacing'
  | 'beat_reference'
  | 'sfx_layer'
  | 'lip_sync_source'
  | 'unknown';

const IMAGE_REFERENCE_ROLE_OPTIONS = [
  { role: 'product_hero', label: 'Product', hint: 'main product / packaging' },
  { role: 'character_anchor', label: 'Character', hint: 'face / outfit identity' },
  { role: 'style_reference', label: 'Style', hint: 'mood / lighting' },
  { role: 'environment', label: 'Location', hint: 'place / setting' },
  { role: 'brand_asset', label: 'Brand', hint: 'logo / typography' },
  { role: 'product_detail', label: 'Detail', hint: 'macro / texture' },
] as const;

const VIDEO_REFERENCE_ROLE_OPTIONS = [
  { role: 'camera_motion', label: 'Camera', hint: 'movement path' },
  { role: 'motion_style', label: 'Motion', hint: 'body/action rhythm' },
  { role: 'shot_pacing', label: 'Pacing', hint: 'edit/reveal timing' },
] as const;

const AUDIO_REFERENCE_ROLE_OPTIONS = [
  { role: 'beat_reference', label: 'Beat', hint: 'music rhythm' },
  { role: 'sfx_layer', label: 'SFX', hint: 'foley / ambience' },
  { role: 'lip_sync_source', label: 'Voice', hint: 'dialogue timing' },
] as const;

interface ReferenceAsset {
  id: string;
  url: string;
  previewUrl?: string;
  name: string;
  kind: ReferenceKind;
  role: ReferenceRole;
  roleConfirmed?: boolean;
  roleSource?: 'auto' | 'user';
  roleConfidence?: number;
  roleReason?: string;
  uploading?: boolean;
}

interface StudioPreviewScene {
  id: string;
  label: string;
  durationS: number;
  prompt: string;
  visual: string;
  camera: string;
  audio: string;
  modelKey: string;
  renderMode: string;
  refs: string[];
  status: 'draft' | 'locked' | 'needs-review';
  spendUsd: number;
}

interface SpendPreview {
  totalSeconds: number;
  lowUsd: number;
  highUsd: number;
}

interface RenderBlocker {
  key: string;
  label: string;
  detail: string;
  severity: 'hard' | 'soft';
}

function getReferencePreviewUrl(ref: ReferenceAsset): string {
  return ref.previewUrl || ref.url;
}

function revokeReferencePreview(ref: ReferenceAsset) {
  if (ref.previewUrl?.startsWith('blob:')) {
    URL.revokeObjectURL(ref.previewUrl);
  }
}

export default function StudioPage() {
  const [brief, setBrief] = useState('');
  const [refs, setRefs] = useState<ReferenceAsset[]>([]);
  const [durationHintS, setDurationHintS] = useState<number>(0);
  const [qualityPreset, setQualityPreset] = useState<QualityPreset>('balanced');
  const [videoModelChoice, setVideoModelChoice] = useState<VideoModelChoice>('auto');
  const [aspectRatioChoice, setAspectRatioChoice] = useState<AspectRatioChoice>('9:16');
  const [targetMarket, setTargetMarket] = useState<string>('auto');
  const [seriesKey, setSeriesKey] = useState<string>('');
  const [selectedBrandKitId, setSelectedBrandKitId] = useState('');
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [brandKits, setBrandKits] = useState<BrandKitOption[]>([]);
  const [commercialTemplates, setCommercialTemplates] = useState<CommercialTemplateOption[]>([]);
  const [commercialUsage, setCommercialUsage] = useState<CommercialUsageSummary | null>(null);
  const [commercialAnalytics, setCommercialAnalytics] = useState<CommercialAnalyticsSummary | null>(null);
  const [brandDraftName, setBrandDraftName] = useState('');
  const [brandDraftVoice, setBrandDraftVoice] = useState('');
  const [brandDraftStyleGuide, setBrandDraftStyleGuide] = useState('');
  const [brandDraftColors, setBrandDraftColors] = useState('');
  const [commercialLoading, setCommercialLoading] = useState(false);
  const [chatInput, setChatInput] = useState('');
  const [revisionInput, setRevisionInput] = useState('');
  const [revisionNotes, setRevisionNotes] = useState('');
  const [planVersion, setPlanVersion] = useState(1);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => [...INITIAL_CHAT_MESSAGES]);
  const [conversationalPreflight, setConversationalPreflight] = useState<ConversationalPreflight | null>(null);
  const [conversationalPreflightLoading, setConversationalPreflightLoading] = useState(false);
  const [preflightApproved, setPreflightApproved] = useState(false);
  const [approvedInputKey, setApprovedInputKey] = useState('');
  const [approvalLockRevision, setApprovalLockRevision] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [dryRunLoading, setDryRunLoading] = useState(false);
  const [dryRunPreview, setDryRunPreview] = useState<AutonomousPreview | null>(null);
  const [approvedDryRunJobId, setApprovedDryRunJobId] = useState('');
  const [approvedSegmentIds, setApprovedSegmentIds] = useState<string[]>([]);
  const [consistencyReviewApproved, setConsistencyReviewApproved] = useState(false);
  const [consistencyReviewDecision, setConsistencyReviewDecision] = useState<'pending' | 'approved' | 'rejected'>('pending');
  const [consistencyReviewReason, setConsistencyReviewReason] = useState('');
  const [consistencyReviewHistory, setConsistencyReviewHistory] = useState<ConsistencyReviewHistoryItem[]>([]);
  const [autonomousPreview, setAutonomousPreview] = useState<AutonomousPreview | null>(null);
  const [productionDecision, setProductionDecision] = useState<ProductionDecision | null>(null);
  const [productionDecisionLoading, setProductionDecisionLoading] = useState(false);
  const [productIntelligence, setProductIntelligence] = useState<ProductIntelligence | null>(null);
  const [productIntelligenceLoading, setProductIntelligenceLoading] = useState(false);
  const [deepPreflight, setDeepPreflight] = useState<DeepPreflightBrain | null>(null);
  const [deepPreflightLoading, setDeepPreflightLoading] = useState(false);
  const [showJobModal, setShowJobModal] = useState(false);
  const [activePreviewSceneId, setActivePreviewSceneId] = useState<string | null>(null);
  const chatInputRef = useRef<HTMLTextAreaElement | null>(null);
  const hydratedRef = useRef(false);
  const refsCleanupRef = useRef<ReferenceAsset[]>([]);
  const { jobId, startedAt: jobStartedAt, setJobId } = usePersistedJob();

  useEffect(() => {
    refsCleanupRef.current = refs;
  }, [refs]);

  useEffect(() => {
    return () => {
      refsCleanupRef.current.forEach(revokeReferencePreview);
    };
  }, []);

  useEffect(() => {
    if (hydratedRef.current || typeof window === 'undefined') return;
    hydratedRef.current = true;
    try {
      const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
      if (!raw) return;
      const draft = JSON.parse(raw) as {
        brief?: string;
        duration_hint_s?: number;
        quality_preset?: QualityPreset;
        video_model_choice?: VideoModelChoice;
        aspect_ratio_choice?: AspectRatioChoice;
        target_market?: string;
        series_key?: string;
        selected_brand_kit_id?: string;
        selected_template_id?: string;
        revision_notes?: string;
        plan_version?: number;
        saved_at?: number;
      };
      if (!draft.saved_at || Date.now() - draft.saved_at > 24 * 60 * 60 * 1000) {
        localStorage.removeItem(DRAFT_STORAGE_KEY);
        return;
      }
      if (draft.brief) setBrief(draft.brief);
      if (typeof draft.duration_hint_s === 'number') setDurationHintS(draft.duration_hint_s);
      if (draft.quality_preset === 'balanced' || draft.quality_preset === 'high') setQualityPreset(draft.quality_preset);
      if (isVideoModelChoice(draft.video_model_choice)) setVideoModelChoice(draft.video_model_choice);
      if (isAspectRatioChoice(draft.aspect_ratio_choice)) setAspectRatioChoice(draft.aspect_ratio_choice);
      if (typeof draft.target_market === 'string') setTargetMarket(draft.target_market);
      if (typeof draft.series_key === 'string') setSeriesKey(draft.series_key);
      if (typeof draft.selected_brand_kit_id === 'string') setSelectedBrandKitId(draft.selected_brand_kit_id);
      if (typeof draft.selected_template_id === 'string') setSelectedTemplateId(draft.selected_template_id);
      if (typeof draft.revision_notes === 'string') setRevisionNotes(draft.revision_notes.slice(0, 1200));
      if (typeof draft.plan_version === 'number') setPlanVersion(Math.max(1, draft.plan_version));
    } catch {
      localStorage.removeItem(DRAFT_STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    if (!hydratedRef.current) return;
    const t = setTimeout(() => {
      try {
        localStorage.setItem(
          DRAFT_STORAGE_KEY,
          JSON.stringify({
            brief,
            duration_hint_s: durationHintS,
            quality_preset: qualityPreset,
            video_model_choice: videoModelChoice,
            aspect_ratio_choice: aspectRatioChoice,
            target_market: targetMarket,
            series_key: seriesKey.trim(),
            selected_brand_kit_id: selectedBrandKitId,
            selected_template_id: selectedTemplateId,
            revision_notes: revisionNotes.trim(),
            plan_version: planVersion,
            saved_at: Date.now(),
          }),
        );
      } catch {
        /* localStorage can be unavailable in private sessions */
      }
    }, 600);
    return () => clearTimeout(t);
  }, [aspectRatioChoice, brief, durationHintS, planVersion, qualityPreset, revisionNotes, selectedBrandKitId, selectedTemplateId, seriesKey, targetMarket, videoModelChoice]);

  useEffect(() => {
    if (jobId && !showJobModal) {
      setShowJobModal(true);
      toast.info('Resuming the previous render job', { duration: 3500 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refreshCommercialData = useCallback(async () => {
    setCommercialLoading(true);
    try {
      const [brandRes, templateRes, usageRes, analyticsRes] = await Promise.all([
        fetch(`/api/v1/director/commercial/brand-kits?owner_user_id=${encodeURIComponent(COMMERCIAL_USER_ID)}`),
        fetch('/api/v1/director/commercial/templates'),
        fetch(`/api/v1/director/commercial/usage/${encodeURIComponent(COMMERCIAL_USER_ID)}`),
        fetch(`/api/v1/director/commercial/analytics/summary?user_id=${encodeURIComponent(COMMERCIAL_USER_ID)}`),
      ]);
      if (brandRes.ok) {
        const data = await brandRes.json() as { brand_kits?: BrandKitOption[] };
        setBrandKits(data.brand_kits ?? []);
      }
      if (templateRes.ok) {
        const data = await templateRes.json() as { templates?: CommercialTemplateOption[] };
        setCommercialTemplates(data.templates ?? []);
      }
      if (usageRes.ok) {
        setCommercialUsage(await usageRes.json() as CommercialUsageSummary);
      }
      if (analyticsRes.ok) {
        setCommercialAnalytics(await analyticsRes.json() as CommercialAnalyticsSummary);
      }
    } catch (error) {
      console.warn('Commercial data refresh failed', error);
    } finally {
      setCommercialLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshCommercialData();
  }, [refreshCommercialData]);

  const readyRefs = useMemo(
    () => refs.filter((r) => !r.uploading && r.url),
    [refs],
  );
  const referenceImageUrls = useMemo(
    () => readyRefs.filter((r) => r.kind === 'image').map((r) => r.url),
    [readyRefs],
  );
  const referenceVideoUrls = useMemo(
    () => readyRefs.filter((r) => r.kind === 'video').map((r) => r.url),
    [readyRefs],
  );
  const referenceAudioUrls = useMemo(
    () => readyRefs.filter((r) => r.kind === 'audio').map((r) => r.url),
    [readyRefs],
  );
  const referenceManifest = useMemo(
    () => buildReferenceManifest(readyRefs),
    [readyRefs],
  );
  const referenceRolesConfirmed = useMemo(
    () => readyRefs.length === 0 || readyRefs.every((r) => r.roleConfirmed && r.role !== 'unknown'),
    [readyRefs],
  );
  const referenceStateKey = useMemo(
    () => readyRefs
      .map((r) => `${r.kind}:${r.url}:${r.role}:${r.roleConfirmed ? 'confirmed' : 'auto'}`)
      .sort()
      .join('|'),
    [readyRefs],
  );
  const targetPlatform = 'tiktok';
  const targetPlatformLabel = durationHintS > 15 ? 'Segmented long-form' : 'Short-form vertical';
  const selectedQuality = QUALITY_OPTIONS.find((option) => option.value === qualityPreset) ?? QUALITY_OPTIONS[0];
  const selectedResolution = selectedQuality.resolution;
  const selectedVideoModel = VIDEO_MODEL_OPTIONS.find((option) => option.value === videoModelChoice) ?? VIDEO_MODEL_OPTIONS[0];
  const selectedAspectRatio = ASPECT_OPTIONS.find((option) => option.value === aspectRatioChoice) ?? ASPECT_OPTIONS[1];
  const renderAspectRatio = aspectRatioChoice === 'auto' ? undefined : aspectRatioChoice;
  const preflightBrief = brief.trim();
  const conversationMessages = useMemo(
    () => chatMessages
      .filter((message) => message.id !== 'assistant_welcome')
      .slice(-CHAT_HISTORY_LIMIT)
      .map((message) => ({ role: message.role, text: message.text, intent: message.intent ?? 'idea' })),
    [chatMessages],
  );
  const conversationHistoryKey = useMemo(
    () => conversationMessages
      .filter((message) => message.role === 'user')
      .map((message) => `${message.role}:${message.intent ?? 'idea'}:${message.text}`)
      .join('\n'),
    [conversationMessages],
  );
  const currentInputKey = useMemo(
    () => [
      preflightBrief,
      durationHintS || 0,
      qualityPreset,
      selectedResolution,
      videoModelChoice,
      aspectRatioChoice,
      targetMarket,
      targetPlatform,
      selectedBrandKitId,
      selectedTemplateId,
      revisionNotes.trim(),
      referenceStateKey,
      conversationHistoryKey,
    ].join('\n---\n'),
    [
      conversationHistoryKey,
      durationHintS,
      preflightBrief,
      aspectRatioChoice,
      qualityPreset,
      referenceStateKey,
      revisionNotes,
      selectedBrandKitId,
      selectedTemplateId,
      selectedResolution,
      targetMarket,
      targetPlatform,
      videoModelChoice,
    ],
  );
  const previewScenes = useMemo(
    () => buildStudioPreviewScenes(conversationalPreflight, readyRefs),
    [conversationalPreflight, readyRefs],
  );
  const reviewScenes = useMemo(
    () => dryRunPreview?.longform_plan
      ? buildLongformReviewScenes(dryRunPreview.longform_plan, dryRunPreview.render_dry_run_report)
      : previewScenes,
    [dryRunPreview, previewScenes],
  );
  const spendPreview = useMemo(
    () => summarizePreviewSpend(reviewScenes),
    [reviewScenes],
  );
  const isLongformReview = Boolean(dryRunPreview?.longform_plan);
  const requiresConsistencyReview = Boolean(
    dryRunPreview?.requires_consistency_review
    || dryRunPreview?.consistency_policy?.action === 'requires_review',
  );
  const consistencyReviewedSegmentIds = useMemo(
    () => (dryRunPreview?.longform_plan?.segments ?? [])
      .map((segment) => segment.segment_id)
      .filter((id): id is string => Boolean(id)),
    [dryRunPreview?.longform_plan?.segments],
  );
  const generationNeedsClarification = Boolean(productionDecision?.decision?.niche_resolution_review_required);
  const generationBlockedByResponsibleGate = Boolean(
    productionDecision?.decision?.render_blocked_by_responsible_gate
      || productionDecision?.responsible_content_gate?.render_allowed === false,
  );
  const selectedModelNeedsImage = videoModelChoice === 'wan_2_7' && referenceImageUrls.length === 0;
  const preflightHasBlockedChecks = Boolean(
    conversationalPreflight?.approval_checklist?.some((item) => item.status === 'blocked'),
  );
  const renderSourceReady = Boolean(
    preflightApproved
    && conversationalPreflight?.status === 'approved_for_render'
    && conversationalPreflight?.render_ready
    && conversationalPreflight?.approved_brief?.trim()
    && conversationalPreflight?.approved_plan?.id
    && conversationalPreflight?.approved_plan?.source_hash
    && conversationalPreflight?.approved_plan?.included_in_render_source
    && conversationalPreflight?.approved_plan?.source_length === conversationalPreflight?.approved_brief?.length
    && approvedInputKey === currentInputKey
  );
  const renderBlockers = useMemo(
    () => buildRenderBlockers({
      isGenerating,
      planning: productionDecisionLoading || conversationalPreflightLoading || dryRunLoading,
      approved: preflightApproved,
      renderSourceReady,
      needsUserInput: conversationalPreflight?.status === 'needs_user_input',
      preflightHasBlockedChecks,
      generationNeedsClarification,
      generationBlockedByResponsibleGate,
      hasBrief: Boolean(brief.trim()),
      referenceRolesConfirmed,
      uploadingRefs: refs.some((r) => r.uploading),
      hasPreview: reviewScenes.length > 0,
      selectedModelNeedsImage,
      selectedModelLabel: selectedVideoModel.label,
      isLongform: durationHintS > 15 || isLongformReview,
      hasApprovedDryRun: Boolean(approvedDryRunJobId),
      segmentReviewComplete: !isLongformReview || (
        (dryRunPreview?.longform_plan?.segments ?? []).every((segment) => (
          segment.segment_id ? approvedSegmentIds.includes(segment.segment_id) : true
        ))
      ),
      consistencyReviewRequired: requiresConsistencyReview,
      consistencyReviewApproved,
    }),
    [
      brief,
      conversationalPreflight?.status,
      conversationalPreflightLoading,
      dryRunLoading,
      dryRunPreview?.longform_plan?.segments,
      durationHintS,
      generationBlockedByResponsibleGate,
      generationNeedsClarification,
      isGenerating,
      isLongformReview,
      approvedDryRunJobId,
      approvedSegmentIds,
      consistencyReviewApproved,
      requiresConsistencyReview,
      preflightApproved,
      preflightHasBlockedChecks,
      reviewScenes.length,
      productionDecisionLoading,
      referenceRolesConfirmed,
      referenceImageUrls.length,
      refs,
      renderSourceReady,
      selectedModelNeedsImage,
      selectedVideoModel.label,
    ],
  );
  const generateDisabled = (
    isGenerating
    || productionDecisionLoading
    || conversationalPreflightLoading
    || dryRunLoading
    || !preflightApproved
    || !renderSourceReady
    || ((durationHintS > 15 || isLongformReview) && !approvedDryRunJobId)
    || (isLongformReview && !(dryRunPreview?.longform_plan?.segments ?? []).every((segment) => (
      segment.segment_id ? approvedSegmentIds.includes(segment.segment_id) : true
    )))
    || (requiresConsistencyReview && !consistencyReviewApproved)
    || conversationalPreflight?.status === 'needs_user_input'
    || preflightHasBlockedChecks
    || generationNeedsClarification
    || generationBlockedByResponsibleGate
    || !brief.trim()
    || !referenceRolesConfirmed
    || selectedModelNeedsImage
    || refs.some((r) => r.uploading)
  );
  const suggestedReplies = useMemo(
    () => {
      const direct = conversationalPreflight?.suggested_replies ?? [];
      const nested = (conversationalPreflight?.blocking_questions ?? []).flatMap((item) => item.suggested_replies ?? []);
      return Array.from(new Set([...direct, ...nested].filter(Boolean))).slice(0, 4);
    },
    [conversationalPreflight?.blocking_questions, conversationalPreflight?.suggested_replies],
  );

  useEffect(() => {
    if (reviewScenes.length === 0) {
      if (activePreviewSceneId) setActivePreviewSceneId(null);
      return;
    }
    if (!reviewScenes.some((scene) => scene.id === activePreviewSceneId)) {
      setActivePreviewSceneId(reviewScenes[0]?.id ?? null);
    }
  }, [activePreviewSceneId, reviewScenes]);

  useEffect(() => {
    const idea = preflightBrief;
    if (idea.length < 5 || refs.some((r) => r.uploading)) {
      setProductionDecision(null);
      setProductionDecisionLoading(false);
      return;
    }

    const counts = countReferenceKinds(readyRefs);
    let cancelled = false;
    setProductionDecisionLoading(true);
    const timer = window.setTimeout(() => {
      fetch('/api/v1/director/autonomous/production-decision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_idea: idea,
          target_market: targetMarket,
          target_platform: targetPlatform,
          duration_hint_s: durationHintS || undefined,
          aspect_ratio: renderAspectRatio,
          speaker_count: Math.min(4, Math.max(1, counts.audio || 1)),
          reference_counts: {
            images: counts.image,
            videos: counts.video,
            audios: counts.audio,
            pinned_assets: 0,
          },
          reference_image_urls: referenceImageUrls,
          reference_video_urls: referenceVideoUrls,
          reference_audio_urls: referenceAudioUrls,
          reference_manifest: referenceManifest,
        }),
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (!cancelled) setProductionDecision(data);
        })
        .catch(() => {
          if (!cancelled) setProductionDecision(null);
        })
        .finally(() => {
          if (!cancelled) setProductionDecisionLoading(false);
        });
    }, 500);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [preflightBrief, durationHintS, readyRefs, referenceAudioUrls, referenceImageUrls, referenceManifest, referenceStateKey, referenceVideoUrls, refs, renderAspectRatio, targetMarket, targetPlatform]);

  useEffect(() => {
    setPreflightApproved(false);
    setApprovedInputKey('');
    setDeepPreflight(null);
  }, [brief, currentInputKey]);

  useEffect(() => {
    const idea = preflightBrief;
    if (idea.length < 5 || refs.some((r) => r.uploading)) {
      setConversationalPreflight(null);
      setConversationalPreflightLoading(false);
      return;
    }

    const counts = countReferenceKinds(readyRefs);
    let cancelled = false;
    setConversationalPreflightLoading(true);
    const timer = window.setTimeout(() => {
      fetch('/api/v1/director/autonomous/conversation/preflight', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_idea: idea,
          target_market: targetMarket,
          target_platform: targetPlatform,
          duration_hint_s: durationHintS || undefined,
          aspect_ratio: renderAspectRatio,
          speaker_count: Math.min(4, Math.max(1, counts.audio || 1)),
          approved: preflightApproved,
          revision_notes: revisionNotes.trim() || undefined,
          conversation_messages: conversationMessages,
          reference_counts: {
            images: counts.image,
            videos: counts.video,
            audios: counts.audio,
            pinned_assets: 0,
          },
          reference_image_urls: referenceImageUrls,
          reference_video_urls: referenceVideoUrls,
          reference_audio_urls: referenceAudioUrls,
          reference_manifest: referenceManifest,
        }),
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data: ConversationalPreflight | null) => {
          if (cancelled) return;
          setConversationalPreflight(data);
          if (data?.production_decision) setProductionDecision(data.production_decision);
        })
        .catch(() => {
          if (!cancelled) setConversationalPreflight(null);
        })
        .finally(() => {
          if (!cancelled) setConversationalPreflightLoading(false);
        });
    }, 450);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [preflightBrief, conversationHistoryKey, durationHintS, preflightApproved, readyRefs, referenceAudioUrls, referenceImageUrls, referenceManifest, referenceStateKey, referenceVideoUrls, refs, renderAspectRatio, revisionNotes, targetMarket, targetPlatform]);

  const lastAssistantPreflightRef = useRef('');
  useEffect(() => {
    const message = conversationalPreflight?.assistant_message?.trim();
    if (!message || message === lastAssistantPreflightRef.current) return;
    lastAssistantPreflightRef.current = message;
    setChatMessages((prev) => [
      ...prev,
      {
        id: `assistant_${Date.now()}`,
        role: 'assistant' as const,
        text: message,
      },
    ].slice(-CHAT_HISTORY_LIMIT));
  }, [conversationalPreflight?.assistant_message]);

  const handleChatSubmit = useCallback(() => {
    const text = chatInput.trim();
    if (!text) return;
    const isPlanRevision = Boolean(
      conversationalPreflight?.creative_plan
      && conversationalPreflight.status !== 'needs_user_input'
      && brief.trim(),
    );
    const intent: ChatMessage['intent'] = isPlanRevision ? 'revision' : 'idea';
    setChatMessages((prev) => [
      ...prev,
      { id: `user_${Date.now()}`, role: 'user' as const, text, intent },
    ].slice(-CHAT_HISTORY_LIMIT));
    if (isPlanRevision) {
      setRevisionNotes((prev) => {
        const next = prev.trim() ? `${prev.trim()}\n${text}` : text;
        return next.slice(0, 1200);
      });
      setPlanVersion((version) => version + 1);
      toast.info('Agent is revising the approved blueprint.');
    } else {
      setBrief((prev) => {
        const base = prev.trim();
        if (!base) return text.slice(0, BRIEF_MAX_CHARS);
        return `${base}\n${text}`.slice(0, BRIEF_MAX_CHARS);
      });
    }
    setChatInput('');
    setPreflightApproved(false);
    setDeepPreflight(null);
  }, [brief, chatInput, conversationalPreflight?.creative_plan, conversationalPreflight?.status]);

  const handleStarterPrompt = useCallback((text: string) => {
    setChatInput(text);
    window.requestAnimationFrame(() => chatInputRef.current?.focus());
  }, []);

  const applyVisionRoleSuggestions = useCallback((suggestions: NonNullable<DeepPreflightBrain['reference_brain']>['vision_suggestions']) => {
    if (!suggestions?.length) return;
    setRefs((prev) => prev.map((ref) => {
      if (ref.kind !== 'image' || ref.roleConfirmed) return ref;
      const tag = getReferenceTag(ref, prev);
      const suggestion = suggestions.find((item) => item.tag === tag && isReferenceRole(item.role));
      if (!suggestion || !isReferenceRole(suggestion.role)) return ref;
      return {
        ...ref,
        role: suggestion.role,
        roleSource: 'auto',
        roleConfidence: typeof suggestion.confidence === 'number' ? suggestion.confidence : 0.65,
        roleReason: suggestion.reason || 'Vision model role suggestion.',
      };
    }));
  }, []);

  const handleExtractProductUrl = useCallback(async () => {
    const url = extractFirstUrl(chatInput || brief);
    if (!url) {
      toast.error('Paste a product/page URL in the command box or mission brief first.');
      return;
    }
    setProductIntelligenceLoading(true);
    try {
      const res = await fetch('/api/v1/director/autonomous/product-intelligence', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, user_idea: preflightBrief || chatInput }),
      });
      const data = await res.json() as ProductIntelligence;
      setProductIntelligence(data);
      if (!res.ok || data.status === 'error') {
        toast.error(data.error?.message || 'Could not extract URL metadata.', { duration: 7000 });
        return;
      }
      if (data.brief_addition) {
        setBrief((prev) => appendUniqueBlock(prev, data.brief_addition || '', BRIEF_MAX_CHARS));
      }
      const suggestion = data.reference_suggestion;
      if (
        suggestion?.url
        && suggestion.kind === 'image'
        && isReferenceRole(suggestion.role)
        && !refs.some((ref) => ref.url === suggestion.url)
      ) {
        const importedRef: ReferenceAsset = {
          id: `url-ref-${Date.now()}`,
          name: cleanAssetName(suggestion.name || data.title || 'URL product image'),
          url: suggestion.url || '',
          kind: 'image',
          role: suggestion.role || 'product_hero',
          roleConfirmed: false,
          roleSource: 'auto',
          roleConfidence: 0.72,
          roleReason: suggestion.why || 'Imported from product URL metadata.',
        };
        setRefs((prev) => [
          ...prev,
          importedRef,
        ].slice(0, AUTONOMOUS_MAX_TOTAL_REFS));
      }
      setChatMessages((prev) => [
        ...prev,
        {
          id: `assistant_url_${Date.now()}`,
          role: 'assistant' as const,
          text: `URL intelligence added: ${data.title || data.source_url || url}. Confirm any imported product image role before render.`,
        },
      ].slice(-CHAT_HISTORY_LIMIT));
      setPreflightApproved(false);
      setApprovedInputKey('');
      toast.success('Product URL intelligence added.');
    } catch (e) {
      toast.error(`URL extraction failed: ${e instanceof Error ? e.message : String(e)}`, { duration: 7000 });
    } finally {
      setProductIntelligenceLoading(false);
    }
  }, [brief, chatInput, preflightBrief, refs]);

  const handleDeepAnalyze = useCallback(async () => {
    const idea = preflightBrief || chatInput.trim();
    if (idea.length < 5) {
      toast.error('Enter a video idea before deep analysis.');
      return;
    }
    if (refs.some((ref) => ref.uploading)) {
      toast.error('Wait until references finish uploading before deep analysis.');
      return;
    }
    if (!preflightBrief && chatInput.trim()) {
      setBrief(chatInput.trim().slice(0, BRIEF_MAX_CHARS));
    }
    const liveConfirm = window.confirm(
      `Deep analysis will call AtlasCloud Flash${referenceImageUrls.length > 0 ? ' and Qwen Vision' : ''}. `
      + 'This can use paid quota, but it will not render video. Continue?',
    );
    if (!liveConfirm) {
      toast.info('Deep analysis cancelled. Use Send for the normal planning flow.');
      return;
    }
    const counts = countReferenceKinds(readyRefs);
    setDeepPreflightLoading(true);
    try {
      const res = await fetch('/api/v1/director/autonomous/deep-preflight', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_idea: idea,
          target_market: targetMarket,
          target_platform: targetPlatform,
          duration_hint_s: durationHintS || undefined,
          aspect_ratio: renderAspectRatio,
          speaker_count: Math.min(4, Math.max(1, counts.audio || 1)),
          reference_counts: {
            images: counts.image,
            videos: counts.video,
            audios: counts.audio,
            pinned_assets: 0,
          },
          reference_image_urls: referenceImageUrls,
          reference_video_urls: referenceVideoUrls,
          reference_audio_urls: referenceAudioUrls,
          reference_manifest: referenceManifest,
          product_context: productIntelligence || {},
          allow_live_llm: true,
          allow_vision_llm: referenceImageUrls.length > 0,
        }),
      });
      const data = await res.json() as DeepPreflightBrain;
      if (!res.ok) {
        throw new Error(JSON.stringify(data).slice(0, 220));
      }
      setDeepPreflight(data);
      if (data.production_decision) setProductionDecision(data.production_decision);
      applyVisionRoleSuggestions(data.reference_brain?.vision_suggestions || []);
      if (data.user_message) {
        setChatMessages((prev) => [
          ...prev,
          {
            id: `assistant_deep_${Date.now()}`,
            role: 'assistant' as const,
            text: data.user_message || 'Deep analysis completed.',
          },
        ].slice(-CHAT_HISTORY_LIMIT));
      }
      setPreflightApproved(false);
      setApprovedInputKey('');
      toast.success(
        data.vendor_calls_performed
          ? 'Deep analysis completed with Flash/Qwen. No video render started.'
          : 'Deep analysis fallback completed without vendor calls.',
        { duration: 6500 },
      );
    } catch (e) {
      toast.error(`Deep analysis failed: ${e instanceof Error ? e.message : String(e)}`, { duration: 8000 });
    } finally {
      setDeepPreflightLoading(false);
    }
  }, [
    applyVisionRoleSuggestions,
    chatInput,
    durationHintS,
    preflightBrief,
    productIntelligence,
    readyRefs,
    referenceAudioUrls,
    referenceImageUrls,
    referenceManifest,
    referenceVideoUrls,
    refs,
    renderAspectRatio,
    targetMarket,
    targetPlatform,
  ]);

  const handleApprovePreflight = useCallback(async () => {
    if (!conversationalPreflight || conversationalPreflight.status === 'needs_user_input') {
      const question = conversationalPreflight?.blocking_questions?.[0]?.question;
      toast.error(question || 'Add the missing detail before approval.', { duration: 6500 });
      return;
    }
    const blockedCheck = conversationalPreflight.approval_checklist?.find((item) => item.status === 'blocked');
    if (blockedCheck) {
      toast.error(blockedCheck.detail || `${blockedCheck.label || 'A pre-render check'} is blocked.`, { duration: 6500 });
      return;
    }
    if (!referenceRolesConfirmed) {
      toast.error('Confirm each reference role first so @image/@video/@audio bindings cannot be misread before paid render.', { duration: 7000 });
      return;
    }
    setDryRunLoading(true);
    setDryRunPreview(null);
    setApprovedDryRunJobId('');
    setApprovedSegmentIds([]);
    setConsistencyReviewApproved(false);
    setConsistencyReviewDecision('pending');
    setConsistencyReviewReason('');
    setConsistencyReviewHistory([]);
    try {
      const res = await fetch('/api/v1/director/autonomous', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_idea: conversationalPreflight?.approved_brief?.trim() || brief.trim(),
          user_id: COMMERCIAL_USER_ID,
          brand_kit_id: selectedBrandKitId || undefined,
          template_id: selectedTemplateId || undefined,
          reference_image_urls: referenceImageUrls,
          reference_video_urls: referenceVideoUrls,
          reference_audio_urls: referenceAudioUrls,
          pinned_asset_ids: [],
          auto_select_asset_pins: true,
          series_key: seriesKey.trim(),
          target_platform: targetPlatform,
          target_market: targetMarket,
          duration_hint_s: durationHintS || undefined,
          user_model: videoModelChoice,
          resolution: selectedResolution,
          aspect_ratio: renderAspectRatio,
          use_vision_llm_for_tagging: referenceImageUrls.length > 0,
          reference_manifest: referenceManifest,
          approved_plan_id: conversationalPreflight?.approved_plan?.id,
          approved_plan_source_hash: conversationalPreflight?.approved_plan?.source_hash,
          approved_plan_source_length: conversationalPreflight?.approved_plan?.source_length,
          dry_run_only: true,
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(`${res.status}: ${detail.slice(0, 220)}`);
      }
      const data = await res.json() as AutonomousPreview & { job_id?: string; execution_mode?: string };
      const segmentIds = (data.longform_plan?.segments ?? [])
        .map((segment) => segment.segment_id)
        .filter((id): id is string => Boolean(id));
      setDryRunPreview(data);
      setApprovedDryRunJobId(data.execution_mode === 'long_form_segmented' ? String(data.job_id || '') : '');
      setApprovedSegmentIds(segmentIds);
      const needsReview = data.requires_consistency_review || data.consistency_policy?.action === 'requires_review';
      setConsistencyReviewApproved(!needsReview);
      setConsistencyReviewDecision(needsReview ? 'pending' : 'approved');
      setPreflightApproved(true);
      setApprovedInputKey(currentInputKey);
      toast.success(
        data.execution_mode === 'long_form_segmented'
          ? `Long-form dry-run ready with ${segmentIds.length} segments.`
          : 'Dry-run ready. Render source locked.',
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Dry-run failed: ${msg}`, { duration: 8000 });
    } finally {
      setDryRunLoading(false);
    }
  }, [brief, conversationalPreflight, currentInputKey, durationHintS, referenceAudioUrls, referenceImageUrls, referenceManifest, referenceRolesConfirmed, referenceVideoUrls, renderAspectRatio, selectedBrandKitId, selectedResolution, selectedTemplateId, seriesKey, targetMarket, targetPlatform, videoModelChoice]);

  const handleConsistencyReviewApprove = useCallback(() => {
    const reason = consistencyReviewReason.trim();
    if (reason.length < 3) {
      toast.error('Add a short consistency review note before approving.', { duration: 6000 });
      return;
    }
    const segmentIds = consistencyReviewedSegmentIds.length > 0 ? consistencyReviewedSegmentIds : approvedSegmentIds;
    const entry: ConsistencyReviewHistoryItem = {
      decision: 'approved',
      reason,
      segmentIds,
      createdAt: new Date().toISOString(),
    };
    setConsistencyReviewApproved(true);
    setConsistencyReviewDecision('approved');
    setConsistencyReviewHistory((current) => [
      ...current,
      entry,
    ].slice(-CONSISTENCY_REVIEW_HISTORY_LIMIT));
    toast.success('Consistency review approved for paid render.');
  }, [approvedSegmentIds, consistencyReviewReason, consistencyReviewedSegmentIds]);

  const handleConsistencyReviewReject = useCallback(() => {
    const reason = consistencyReviewReason.trim();
    if (reason.length < 3) {
      toast.error('Add a rejection reason first.', { duration: 6000 });
      return;
    }
    const segmentIds = consistencyReviewedSegmentIds.length > 0 ? consistencyReviewedSegmentIds : approvedSegmentIds;
    const entry: ConsistencyReviewHistoryItem = {
      decision: 'rejected',
      reason,
      segmentIds,
      createdAt: new Date().toISOString(),
    };
    setConsistencyReviewApproved(false);
    setConsistencyReviewDecision('rejected');
    setConsistencyReviewHistory((current) => [
      ...current,
      entry,
    ].slice(-CONSISTENCY_REVIEW_HISTORY_LIMIT));
    toast.error('Consistency review rejected. Adjust the plan before paid render.', { duration: 7000 });
  }, [approvedSegmentIds, consistencyReviewReason, consistencyReviewedSegmentIds]);

  const handleCopyPreviewPrompt = useCallback(async (prompt: string) => {
    try {
      await navigator.clipboard.writeText(prompt);
      toast.success('Scene prompt copied.');
    } catch {
      toast.error('Could not copy the scene prompt.');
    }
  }, []);

  const handleRequestRevision = useCallback(() => {
    const text = revisionInput.trim();
    if (!text) return;
    setRevisionNotes((prev) => {
      const next = prev.trim() ? `${prev.trim()}\n${text}` : text;
      return next.slice(0, 1200);
    });
    setPlanVersion((version) => version + 1);
    setChatMessages((prev) => [
      ...prev,
      { id: `revision_${Date.now()}`, role: 'user' as const, text, intent: 'revision' as const },
    ].slice(-CHAT_HISTORY_LIMIT));
    setRevisionInput('');
    setPreflightApproved(false);
    toast.info('Agent is revising the script and storyboard.');
  }, [revisionInput]);

  const handleNewProject = useCallback(() => {
    setBrief('');
    setRefs((prev) => {
      prev.forEach(revokeReferencePreview);
      return [];
    });
    setDurationHintS(0);
    setQualityPreset('balanced');
    setVideoModelChoice('auto');
    setAspectRatioChoice('9:16');
    setTargetMarket('auto');
    setSeriesKey('');
    setChatInput('');
    setRevisionInput('');
    setRevisionNotes('');
    setPlanVersion(1);
    setChatMessages([...INITIAL_CHAT_MESSAGES]);
    setConversationalPreflight(null);
    setConversationalPreflightLoading(false);
    setPreflightApproved(false);
    setApprovedInputKey('');
    setApprovalLockRevision(0);
    setDryRunLoading(false);
    setDryRunPreview(null);
    setApprovedDryRunJobId('');
    setApprovedSegmentIds([]);
    setConsistencyReviewApproved(false);
    setConsistencyReviewDecision('pending');
    setConsistencyReviewReason('');
    setConsistencyReviewHistory([]);
    setAutonomousPreview(null);
    setProductionDecision(null);
    setProductionDecisionLoading(false);
    setProductIntelligence(null);
    setProductIntelligenceLoading(false);
    setDeepPreflight(null);
    setDeepPreflightLoading(false);
    setActivePreviewSceneId(null);
    lastAssistantPreflightRef.current = '';
    if (typeof window !== 'undefined') {
      localStorage.removeItem(DRAFT_STORAGE_KEY);
    }
    toast.success('New autonomous project started.');
  }, []);

  const invalidateApprovalLock = useCallback((message?: string) => {
    setPreflightApproved(false);
    setApprovedInputKey('');
    setDryRunPreview(null);
    setApprovedDryRunJobId('');
    setApprovedSegmentIds([]);
    setConsistencyReviewApproved(false);
    setConsistencyReviewDecision('pending');
    setConsistencyReviewReason('');
    setConsistencyReviewHistory([]);
    setApprovalLockRevision((revision) => revision + 1);
    if (message) toast.info(message, { duration: 4200 });
  }, []);

  const handleSaveBrandKit = useCallback(async () => {
    const name = brandDraftName.trim();
    if (name.length < 2) {
      toast.error('Add a brand name before saving.');
      return;
    }
    const primaryColors = brandDraftColors
      .split(/[\s,]+/)
      .map((value) => value.trim())
      .filter(Boolean)
      .slice(0, 8);
    setCommercialLoading(true);
    try {
      const response = await fetch('/api/v1/director/commercial/brand-kits', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          owner_user_id: COMMERCIAL_USER_ID,
          name,
          logo_urls: referenceImageUrls.slice(0, 3),
          primary_colors: primaryColors,
          fonts: [],
          voice: brandDraftVoice.trim(),
          style_guide: brandDraftStyleGuide.trim(),
        }),
      });
      if (!response.ok) {
        throw new Error(`${response.status}: ${(await response.text()).slice(0, 180)}`);
      }
      const data = await response.json() as { brand_kit?: BrandKitOption };
      const saved = data.brand_kit;
      if (saved?.brand_id) {
        setSelectedBrandKitId(saved.brand_id);
        invalidateApprovalLock('Brand kit changed. Review the pipeline again before paid render.');
      }
      setBrandDraftName('');
      setBrandDraftVoice('');
      setBrandDraftStyleGuide('');
      setBrandDraftColors('');
      await refreshCommercialData();
      toast.success('Brand kit saved and applied.');
    } catch (error) {
      toast.error(`Brand kit save failed: ${error instanceof Error ? error.message : String(error)}`, { duration: 7500 });
    } finally {
      setCommercialLoading(false);
    }
  }, [
    brandDraftColors,
    brandDraftName,
    brandDraftStyleGuide,
    brandDraftVoice,
    invalidateApprovalLock,
    referenceImageUrls,
    refreshCommercialData,
  ]);

  const uploadReferences = useCallback(async (files: FileList | File[]) => {
    const detected = Array.from(files).map((file) => ({ file, kind: detectReferenceKind(file) }));
    const incoming = detected.filter((item): item is { file: File; kind: ReferenceKind } => item.kind !== null);
    const rejected = detected.length - incoming.length;
    if (incoming.length === 0) {
      toast.error('Unsupported reference file. Use image, video, or audio media files only.');
      return;
    }
    if (rejected > 0) {
      toast.warning(`${rejected} unsupported file${rejected > 1 ? 's were' : ' was'} skipped.`);
    }

    const counts = countReferenceKinds(refs);
    const remaining = AUTONOMOUS_MAX_TOTAL_REFS - refs.length;
    if (remaining <= 0) {
      toast.error(`Maximum ${AUTONOMOUS_MAX_TOTAL_REFS} references for the Autonomous Agent`);
      return;
    }

    const selected: Array<{ file: File; kind: ReferenceKind }> = [];
    for (const item of incoming) {
      if (selected.length >= remaining) break;
      const nextCounts = countReferenceKinds([
        ...refs,
        ...selected.map(({ file, kind }) => ({
          id: file.name,
          name: file.name,
          url: '',
          kind,
        })),
      ]);
      if (
        (item.kind === 'image' && nextCounts.image >= AUTONOMOUS_MAX_IMAGES)
        || (item.kind === 'video' && nextCounts.video >= AUTONOMOUS_MAX_VIDEOS)
        || (item.kind === 'audio' && nextCounts.audio >= AUTONOMOUS_MAX_AUDIO)
      ) {
        continue;
      }
      selected.push(item);
    }

    if (selected.length === 0) {
      toast.error('Reference limits reached for this media type');
      return;
    }
    if (selected.length < incoming.length) {
      toast.warning(`Added ${selected.length}/${incoming.length} references`);
    }

    const existingRefs = refs;
    const placeholders: ReferenceAsset[] = selected.map(({ file, kind }, index) => ({
      id: `${file.name}-${file.lastModified}-${Math.random().toString(36).slice(2)}`,
      name: file.name,
      kind,
      role: inferReferenceRole(file, kind, [...existingRefs, ...selected.slice(0, index).map((item) => ({
        id: item.file.name,
        name: item.file.name,
        kind: item.kind,
        url: '',
        role: 'unknown' as const,
      }))]),
      roleConfirmed: false,
      roleSource: 'auto',
      url: '',
      previewUrl: kind === 'image' ? URL.createObjectURL(file) : undefined,
      uploading: true,
    }));
    setRefs((prev) => [...prev, ...placeholders]);
    invalidateApprovalLock('Reference set changed. Review the pipeline again before paid render.');

    await Promise.all(placeholders.map(async (placeholder, index) => {
      try {
        const url = await uploadMediaToR2(selected[index].file);
        setRefs((prev) => prev.map((item) => (
          item.id === placeholder.id ? { ...item, url, uploading: false } : item
        )));
      } catch (e) {
        setRefs((prev) => {
          const removed = prev.find((item) => item.id === placeholder.id);
          if (removed) revokeReferencePreview(removed);
          return prev.filter((item) => item.id !== placeholder.id);
        });
        const message = e instanceof Error ? e.message : String(e);
        toast.error(`Upload failed: ${selected[index].file.name}. ${message}`, { duration: 8000 });
        console.error(e);
      }
    }));
  }, [invalidateApprovalLock, refs]);

  const removeReference = useCallback((id: string) => {
    setRefs((prev) => {
      const removed = prev.find((r) => r.id === id);
      if (removed) revokeReferencePreview(removed);
      return prev.filter((r) => r.id !== id);
    });
    invalidateApprovalLock('Reference removed. ApprovalLock will be rebuilt after review.');
  }, [invalidateApprovalLock]);

  const updateReferenceRole = useCallback((id: string, role: ReferenceRole) => {
    setRefs((prev) => prev.map((item) => (
      item.id === id ? { ...item, role, roleConfirmed: true, roleSource: 'user' } : item
    )));
    invalidateApprovalLock('Reference role changed. ApprovalLock will be rebuilt after review.');
  }, [invalidateApprovalLock]);

  const confirmAllReferenceRoles = useCallback(() => {
    setRefs((prev) => prev.map((item) => (
      item.uploading || !item.url
        ? item
        : { ...item, roleConfirmed: item.role !== 'unknown', roleSource: item.roleSource || 'user' }
    )));
    invalidateApprovalLock();
    toast.success('Reference manifest confirmed.');
  }, [invalidateApprovalLock]);

  const handleAutonomousGenerate = useCallback(async () => {
    if (!brief.trim() || brief.trim().length < 5) {
      toast.error('Enter a video idea with at least 5 characters');
      return;
    }
    if (refs.some((r) => r.uploading)) {
      toast.error('Wait for reference uploads to finish before rendering');
      return;
    }

    if (productionDecisionLoading || conversationalPreflightLoading) {
      toast.info('Agent is checking the script, storyboard and market fit. Try again in a moment.');
      return;
    }
    if (!preflightApproved || conversationalPreflight?.status === 'needs_user_input') {
      const question = conversationalPreflight?.blocking_questions?.[0]?.question;
      toast.error(question || 'Review and approve the agent plan before render.', { duration: 7000 });
      return;
    }
    if (!renderSourceReady) {
      toast.info('Wait for the approved render source to lock, then render.');
      return;
    }
    if ((durationHintS > 15 || dryRunPreview?.execution_mode === 'long_form_segmented') && !approvedDryRunJobId) {
      toast.error('Run and approve the long-form dry-run before paid segmented render.', { duration: 7000 });
      return;
    }
    if (requiresConsistencyReview && !consistencyReviewApproved) {
      toast.error(
        consistencyReviewDecision === 'rejected'
          ? 'Consistency review was rejected. Adjust the plan before paid render.'
          : 'Approve the consistency review step before paid render.',
        { duration: 7000 },
      );
      return;
    }
    if (productionDecision?.decision?.niche_resolution_review_required) {
      const question = productionDecision.input_summary?.niche_resolution?.clarifying_questions?.[0];
      toast.error(question || 'Clarify the primary niche before render.', { duration: 7000 });
      return;
    }
    if (
      productionDecision?.decision?.render_blocked_by_responsible_gate
      || productionDecision?.responsible_content_gate?.render_allowed === false
    ) {
      const guidance = productionDecision.responsible_content_gate?.rewrite_guidance?.[0];
      toast.error(guidance || 'This brief needs likeness, voice, or IP review before render.', { duration: 8000 });
      return;
    }

    setIsGenerating(true);
    setAutonomousPreview(null);
    try {
      const res = await fetch('/api/v1/director/autonomous', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_idea: conversationalPreflight?.approved_brief?.trim() || brief.trim(),
          user_id: COMMERCIAL_USER_ID,
          brand_kit_id: selectedBrandKitId || undefined,
          template_id: selectedTemplateId || undefined,
          reference_image_urls: referenceImageUrls,
          reference_video_urls: referenceVideoUrls,
          reference_audio_urls: referenceAudioUrls,
          pinned_asset_ids: [],
          auto_select_asset_pins: true,
          series_key: seriesKey.trim(),
          target_platform: targetPlatform,
          target_market: targetMarket,
          duration_hint_s: durationHintS || undefined,
          user_model: videoModelChoice,
          resolution: selectedResolution,
          aspect_ratio: renderAspectRatio,
          use_vision_llm_for_tagging: referenceImageUrls.length > 0,
          reference_manifest: referenceManifest,
          approved_plan_id: conversationalPreflight?.approved_plan?.id,
          approved_plan_source_hash: conversationalPreflight?.approved_plan?.source_hash,
          approved_plan_source_length: conversationalPreflight?.approved_plan?.source_length,
          approved_dry_run_job_id: approvedDryRunJobId || undefined,
          approved_segment_ids: approvedSegmentIds,
          consistency_review_approved: consistencyReviewApproved,
          consistency_review_decision: consistencyReviewDecision === 'approved' ? 'approved' : consistencyReviewDecision === 'rejected' ? 'rejected' : undefined,
          consistency_review_reason: consistencyReviewReason.trim() || undefined,
          consistency_reviewed_segment_ids: consistencyReviewedSegmentIds.length > 0 ? consistencyReviewedSegmentIds : approvedSegmentIds,
        }),
      });
      if (!res.ok) {
        const errText = await res.text();
        let detail: unknown = null;
        try {
          detail = JSON.parse(errText)?.detail;
        } catch {
          detail = null;
        }
        if (
          res.status === 422
          && typeof detail === 'object'
          && detail
          && (detail as { code?: string }).code === 'niche_resolution_requires_clarification'
        ) {
          const resolution = (detail as { niche_resolution?: NicheResolution }).niche_resolution;
          const question = resolution?.clarifying_questions?.[0];
          setProductionDecision((prev) => (
            prev
              ? {
                ...prev,
                decision: {
                  ...(prev.decision ?? {}),
                  niche_resolution_review_required: true,
                },
                input_summary: {
                  ...(prev.input_summary ?? {}),
                  niche_resolution: resolution ?? prev.input_summary?.niche_resolution,
                },
              }
              : prev
          ));
          toast.error(question || 'Clarify the primary niche before render.', { duration: 8000 });
          return;
        }
        if (
          res.status === 422
          && typeof detail === 'object'
          && detail
          && (detail as { code?: string }).code === 'responsible_content_requires_review'
        ) {
          const gate = (detail as { responsible_content_gate?: ResponsibleContentGate }).responsible_content_gate;
          setProductionDecision((prev) => (
            prev
              ? {
                ...prev,
                decision: {
                  ...(prev.decision ?? {}),
                  responsible_review_required: true,
                  render_blocked_by_responsible_gate: true,
                },
                responsible_content_gate: gate ?? prev.responsible_content_gate,
              }
              : prev
          ));
          toast.error(
            gate?.rewrite_guidance?.[0] || 'This brief needs likeness, voice, or IP review before render.',
            { duration: 9000 },
          );
          return;
        }
        throw new Error(`${res.status}: ${errText.slice(0, 220)}`);
      }

      const data = await res.json();
      setAutonomousPreview({
        job_id: data.job_id,
        execution_mode: data.execution_mode,
        caption_vn: data.editor_preview?.caption_vn,
        hashtags_vn: data.editor_preview?.hashtags_vn,
        distribution_package: data.editor_preview?.distribution_package,
        hook_first_3s: data.hook_preview?.first_3s,
        niche: data.hook_preview?.niche,
        n_shots: data.n_shots,
        producer_strategy: data.producer_strategy,
        autonomous_preflight: data.autonomous_preflight,
        auto_pin_selection: data.auto_pin_selection,
        approved_plan: data.approved_plan,
        longform_plan: data.longform_plan,
        render_dry_run_report: data.render_dry_run_report,
        consistency_policy: data.consistency_policy,
        requires_consistency_review: data.requires_consistency_review,
      });
      setJobId(data.job_id);
      setShowJobModal(true);
      toast.success(`Autonomous Agent started rendering ${data.n_shots ?? ''} shots`, {
        duration: 4500,
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Autonomous failed: ${msg}`, { duration: 8000 });
      console.error(e);
    } finally {
      setIsGenerating(false);
    }
  }, [approvedDryRunJobId, approvedSegmentIds, brief, consistencyReviewApproved, consistencyReviewDecision, consistencyReviewReason, consistencyReviewedSegmentIds, conversationalPreflight, conversationalPreflightLoading, dryRunPreview?.execution_mode, durationHintS, preflightApproved, productionDecision, productionDecisionLoading, referenceAudioUrls, referenceImageUrls, referenceManifest, referenceVideoUrls, refs, renderAspectRatio, renderSourceReady, requiresConsistencyReview, selectedBrandKitId, selectedResolution, selectedTemplateId, seriesKey, setJobId, targetMarket, targetPlatform, videoModelChoice]);

  const refCounts = countReferenceKinds(refs.filter((r) => !r.uploading));
  const showStarterPrompts = !brief.trim() && chatMessages.length <= 1;
  const chatRevisionMode = Boolean(
    conversationalPreflight?.creative_plan
    && conversationalPreflight.status !== 'needs_user_input'
    && brief.trim(),
  );
  return (
    <div className="min-h-full bg-canvas">
      <section className="mx-auto max-w-7xl px-5 pb-10 pt-5 md:px-8">
        <div className="mb-4 rounded-sheet border border-hairline bg-surface-1/80 p-3 shadow-card-soft sm:p-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="mb-2 hidden items-center gap-2 rounded-full border border-accent-cyan/25 bg-accent-cyan/10 px-3 py-1 text-[10px] font-bold uppercase text-accent-cyan sm:inline-flex">
                <Sparkles size={12} />
                CineJelly Agent Studio
              </div>
              <h1 className="text-xl font-extrabold text-text sm:text-2xl md:text-3xl">
                Tell the Agent once. Review the film plan. Then render.
              </h1>
              <p className="mt-1 max-w-3xl text-xs leading-relaxed text-text-muted sm:text-sm">
                No prompt skill required. Add a product URL, images, motion or voice if you have them; CineJelly turns the request into script, shots, reference roles and a locked render plan.
              </p>
              <div className="mt-3 hidden flex-wrap gap-2 sm:flex">
                <span className="rounded-full border border-hairline bg-surface-2 px-3 py-1 text-xs font-semibold text-text-muted">
                  {targetPlatformLabel}
                </span>
                <span className="rounded-full border border-hairline bg-surface-2 px-3 py-1 text-xs font-semibold text-text-muted">
                  {targetMarket === 'auto' ? 'Market auto-detect' : `${targetMarket.toUpperCase()} market`}
                </span>
                <span className="rounded-full border border-hairline bg-surface-2 px-3 py-1 text-xs font-semibold text-text-muted">
                  {durationHintS ? `${durationHintS}s target` : 'Runtime auto'}
                </span>
                <span className="rounded-full border border-hairline bg-surface-2 px-3 py-1 text-xs font-semibold text-text-muted">
                  {selectedQuality.label} {selectedResolution}
                </span>
                <span className="rounded-full border border-hairline bg-surface-2 px-3 py-1 text-xs font-semibold text-text-muted">
                  {selectedAspectRatio.label}
                </span>
                <span className="rounded-full border border-hairline bg-surface-2 px-3 py-1 text-xs font-semibold text-text-muted">
                  {selectedVideoModel.label}
                </span>
                <span className="rounded-full border border-accent-cyan/20 bg-accent-cyan/10 px-3 py-1 text-xs font-semibold text-accent-cyan">
                  Prompt-free creator flow
                </span>
                <span className="rounded-full border border-accent-orange/20 bg-accent-orange/10 px-3 py-1 text-xs font-semibold text-accent-orange">
                  Paid render locked until approval
                </span>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={handleNewProject}
                className="btn-outline px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm"
              >
                <RotateCcw size={15} /> New project
              </button>
            </div>
          </div>
        </div>

        <CreatorJourneyBar
          hasBrief={Boolean(brief.trim())}
          refCount={readyRefs.length}
          referenceRolesConfirmed={referenceRolesConfirmed}
          hasPlan={Boolean(conversationalPreflight?.creative_plan)}
          hasPreview={reviewScenes.length > 0}
          needsInput={conversationalPreflight?.status === 'needs_user_input'}
          loading={conversationalPreflightLoading || productionDecisionLoading}
          approved={preflightApproved}
          renderSourceReady={renderSourceReady}
          qualityLabel={`${selectedQuality.label} ${selectedResolution}`}
          durationLabel={durationHintS ? `${durationHintS}s` : 'Auto'}
          marketLabel={targetMarket === 'auto' ? 'Auto market' : `${targetMarket.toUpperCase()} market`}
        />

        <div className="mb-5 grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
          <div className="space-y-5">
            <CommandComposer
              value={brief}
              chatValue={chatInput}
              revisionMode={chatRevisionMode}
              loading={conversationalPreflightLoading || productionDecisionLoading}
              deepAnalyzeLoading={deepPreflightLoading}
              productIntelligenceLoading={productIntelligenceLoading}
              charLimit={CHAT_INPUT_MAX_CHARS}
              starterPrompts={STARTER_PROMPTS}
              showStarterPrompts={showStarterPrompts}
              inputRef={chatInputRef}
              onChange={setBrief}
              onChatChange={setChatInput}
              onSubmit={handleChatSubmit}
              onStarterPrompt={handleStarterPrompt}
              onExtractProductUrl={handleExtractProductUrl}
              onDeepAnalyze={handleDeepAnalyze}
            />

            <SettingsBar
              modelValue={videoModelChoice}
              durationValue={durationHintS}
              aspectRatioValue={aspectRatioChoice}
              qualityValue={qualityPreset}
              targetMarketValue={targetMarket}
              selectedResolution={selectedResolution}
              modelOptions={VIDEO_MODEL_OPTIONS}
              durationOptions={DURATION_OPTIONS}
              aspectRatioOptions={ASPECT_OPTIONS}
              qualityOptions={QUALITY_OPTIONS}
              targetMarketOptions={TARGET_MARKET_OPTIONS}
              onModelChange={(value) => {
                setVideoModelChoice(value as VideoModelChoice);
                invalidateApprovalLock();
              }}
              onDurationChange={(value) => {
                setDurationHintS(value);
                invalidateApprovalLock();
              }}
              onAspectRatioChange={(value) => {
                setAspectRatioChoice(value as AspectRatioChoice);
                invalidateApprovalLock();
              }}
              onQualityChange={(value) => {
                setQualityPreset(value as QualityPreset);
                invalidateApprovalLock();
              }}
              onTargetMarketChange={(value) => {
                setTargetMarket(value);
                invalidateApprovalLock();
              }}
            />

            <CommercialControls
              brandKits={brandKits}
              templates={commercialTemplates}
              selectedBrandKitId={selectedBrandKitId}
              selectedTemplateId={selectedTemplateId}
              usage={commercialUsage}
              analytics={commercialAnalytics}
              loading={commercialLoading}
              brandDraftName={brandDraftName}
              brandDraftVoice={brandDraftVoice}
              brandDraftStyleGuide={brandDraftStyleGuide}
              brandDraftColors={brandDraftColors}
              onBrandKitChange={(brandId) => {
                setSelectedBrandKitId(brandId);
                invalidateApprovalLock('Brand kit changed. Review the pipeline again before paid render.');
              }}
              onTemplateChange={(templateId) => {
                setSelectedTemplateId(templateId);
                invalidateApprovalLock('Template changed. Review the pipeline again before paid render.');
              }}
              onBrandDraftNameChange={setBrandDraftName}
              onBrandDraftVoiceChange={setBrandDraftVoice}
              onBrandDraftStyleGuideChange={setBrandDraftStyleGuide}
              onBrandDraftColorsChange={setBrandDraftColors}
              onSaveBrandKit={handleSaveBrandKit}
            />

            <ReferenceTray
              refs={refs}
              readyRefs={readyRefs}
              rolesConfirmed={referenceRolesConfirmed}
              approvalLockRevision={approvalLockRevision}
              roleOptionsForKind={roleOptionsForKind}
              getReferenceTag={(ref) => getReferenceTag(ref, readyRefs)}
              getPreviewUrl={(ref) => getReferencePreviewUrl(ref as ReferenceAsset)}
              onFilesSelected={uploadReferences}
              onRemoveReference={removeReference}
              onConfirmRoles={confirmAllReferenceRoles}
              onRoleChange={(id, role) => updateReferenceRole(id, role as ReferenceRole)}
            />
          </div>

          <div className="space-y-5">
            <PipelinePreview
              loading={conversationalPreflightLoading || productionDecisionLoading}
              approved={preflightApproved}
              renderSourceReady={renderSourceReady}
              referencesConfirmed={referenceRolesConfirmed}
              preflight={conversationalPreflight}
              productionDecision={productionDecision}
              scenes={reviewScenes}
              spendPreview={spendPreview}
            />

            <RenderReviewPanel
              approved={preflightApproved}
              renderSourceReady={renderSourceReady}
              loading={isGenerating}
              planning={conversationalPreflightLoading || productionDecisionLoading || dryRunLoading}
              renderDisabled={generateDisabled}
              referencesConfirmed={referenceRolesConfirmed}
              approvalLockRevision={approvalLockRevision}
              spendPreview={spendPreview}
              scenes={reviewScenes}
              blockers={renderBlockers}
              dryRunReport={dryRunPreview?.render_dry_run_report ?? null}
              longformPlan={dryRunPreview?.longform_plan ?? null}
              consistencyPolicy={dryRunPreview?.consistency_policy ?? null}
              consistencyReviewApproved={consistencyReviewApproved}
              consistencyReviewDecision={consistencyReviewDecision}
              consistencyReviewReason={consistencyReviewReason}
              consistencyReviewHistory={consistencyReviewHistory}
              approvedSegmentIds={approvedSegmentIds}
              onToggleSegmentApproval={(segmentId) => {
                setApprovedSegmentIds((current) => (
                  current.includes(segmentId)
                    ? current.filter((id) => id !== segmentId)
                    : [...current, segmentId]
                ));
                if (requiresConsistencyReview) {
                  setConsistencyReviewApproved(false);
                  setConsistencyReviewDecision('pending');
                }
              }}
              onApproveAllSegments={() => {
                const segmentIds = (dryRunPreview?.longform_plan?.segments ?? [])
                  .map((segment) => segment.segment_id)
                  .filter((id): id is string => Boolean(id));
                setApprovedSegmentIds(segmentIds);
                if (requiresConsistencyReview) {
                  setConsistencyReviewApproved(false);
                  setConsistencyReviewDecision('pending');
                }
              }}
              onConsistencyReviewReasonChange={(reason) => {
                setConsistencyReviewReason(reason.slice(0, 1000));
                if (consistencyReviewDecision === 'approved') {
                  setConsistencyReviewApproved(false);
                  setConsistencyReviewDecision('pending');
                }
              }}
              onConsistencyReviewApprove={handleConsistencyReviewApprove}
              onConsistencyReviewReject={handleConsistencyReviewReject}
              onApprove={handleApprovePreflight}
              onRender={handleAutonomousGenerate}
            />
          </div>
        </div>

        <div className="mb-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
          <StoryboardTimeline
            scenes={reviewScenes}
            activeSceneId={activePreviewSceneId}
            onSelectScene={setActivePreviewSceneId}
            onCopyPrompt={handleCopyPreviewPrompt}
          />
          <PipelineTraceView
            preflight={conversationalPreflight}
            productionDecision={productionDecision}
            referenceManifest={referenceManifest}
            approvalLockRevision={approvalLockRevision}
          />
        </div>

      </section>

      <section className="mx-auto max-w-7xl px-5 pb-12 md:px-8">
        <RecentGenerations />
      </section>

      <JobResultModal
        open={showJobModal}
        jobId={jobId}
        onClose={() => setShowJobModal(false)}
        estimatedDurationS={durationHintS || 15}
        jobStartedAt={jobStartedAt}
      />
    </div>
  );

}

function CreatorJourneyBar({
  hasBrief,
  refCount,
  referenceRolesConfirmed,
  hasPlan,
  hasPreview,
  needsInput,
  loading,
  approved,
  renderSourceReady,
  qualityLabel,
  durationLabel,
  marketLabel,
}: {
  hasBrief: boolean;
  refCount: number;
  referenceRolesConfirmed: boolean;
  hasPlan: boolean;
  hasPreview: boolean;
  needsInput: boolean;
  loading: boolean;
  approved: boolean;
  renderSourceReady: boolean;
  qualityLabel: string;
  durationLabel: string;
  marketLabel: string;
}) {
  const nextAction = needsInput
    ? 'Answer the Agent question'
    : !hasBrief
      ? 'Describe the video'
      : refCount > 0 && !referenceRolesConfirmed
        ? 'Confirm reference roles'
        : loading
          ? 'Agent is drafting'
          : !hasPlan
            ? 'Send to create draft'
            : !hasPreview
              ? 'Wait for preview'
              : !approved
                ? 'Review and approve'
                : renderSourceReady
                  ? 'Ready to render'
                  : 'Locking source';

  const steps = [
    {
      label: 'Input',
      detail: refCount > 0 ? `${refCount} reference${refCount === 1 ? '' : 's'}` : 'Idea, URL or image',
      active: !hasBrief,
      done: hasBrief,
    },
    {
      label: 'Agent draft',
      detail: loading ? 'Thinking' : hasPlan ? 'Script ready' : 'Auto plan',
      active: hasBrief && !hasPlan,
      done: hasPlan,
    },
    {
      label: 'Preview',
      detail: hasPreview ? 'Scene timeline' : 'Storyboard first',
      active: hasPlan && !hasPreview,
      done: hasPreview,
    },
    {
      label: 'Approve',
      detail: approved ? 'Locked' : 'No render yet',
      active: hasPreview && !approved,
      done: approved,
    },
    {
      label: 'Render',
      detail: renderSourceReady ? 'Button unlocked' : 'Paid gated',
      active: renderSourceReady,
      done: false,
    },
  ];

  return (
    <div className="mb-5 overflow-hidden rounded-sheet border border-hairline bg-surface-1/85 shadow-card-soft">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline px-4 py-3">
        <div>
          <div className="text-sm font-extrabold text-text">Simple creator flow</div>
          <div className="mt-1 text-xs leading-relaxed text-text-muted">
            User only needs to describe the goal, add references if available, review the draft, then render.
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-semibold">
          <span className="rounded-full border border-accent-cyan/25 bg-accent-cyan/10 px-2.5 py-1 text-accent-cyan">{nextAction}</span>
          <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-text-subtle">{durationLabel}</span>
          <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-text-subtle">{qualityLabel}</span>
          <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-text-subtle">{marketLabel}</span>
        </div>
      </div>
      <div className="grid gap-px bg-hairline sm:grid-cols-5">
        {steps.map((step, index) => {
          const tone = step.done
            ? 'border-accent-cyan/20 bg-accent-cyan/10 text-accent-cyan'
            : step.active
              ? 'border-accent-magenta/25 bg-accent-magenta/10 text-accent-magenta'
              : 'border-transparent bg-surface-2 text-text-subtle';
          return (
            <div key={step.label} className={`bg-surface-1 p-3 ${tone}`}>
              <div className="flex items-center gap-2">
                <span className={`grid h-6 w-6 place-items-center rounded-full text-[10px] font-bold ${
                  step.done ? 'bg-accent-cyan text-background' : step.active ? 'bg-accent-magenta text-white' : 'bg-surface-3 text-text-subtle'
                }`}>
                  {index + 1}
                </span>
                <span className="text-xs font-bold text-text">{step.label}</span>
              </div>
              <div className="mt-1 text-[10px] leading-relaxed text-text-subtle">{step.detail}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function buildStudioPreviewScenes(
  preflight: ConversationalPreflight | null,
  refs: ReferenceAsset[],
): StudioPreviewScene[] {
  if (!preflight) return [];
  const promptContract = preflight.prompt_execution_contract_v3
    ?? preflight.production_decision?.prompt_execution_contract_v3;
  const producerV2 = preflight.creative_producer_v2
    ?? preflight.production_decision?.creative_producer_v2;
  const storyboard = preflight.storyboard ?? [];
  const script = preflight.script_outline ?? [];
  const defaultModel = promptContract?.model_plan?.primary_visual_model
    || preflight.summary?.prompt_primary_visual_model
    || preflight.production_decision?.model_route_strategy?.summary?.primary_visual_model
    || preflight.production_decision?.decision?.primary_model_route?.primary_visual_model
    || 'seedance_2_0_fast';

  const compiled = promptContract?.compiled_shots ?? [];
  if (compiled.length > 0) {
    return compiled.slice(0, SCENE_PREVIEW_MAX).map((shot, index) => {
      const frame = storyboard[index];
      const beat = script[index];
      const basePrompt = cleanPreviewText(shot.prompt || frame?.visual || beat?.script || preflight.creative_plan?.logline || '');
      const refsUsed = pickPreviewReferenceTags(basePrompt, refs);
      const prompt = withReferenceBindings(basePrompt, refsUsed, refs);
      const durationS = normalizePreviewDuration(shot.duration_s ?? beat?.duration_s);
      return {
        id: shot.shot_id || frame?.id || `compiled-${index + 1}`,
        label: shot.shot_id || frame?.frame || beat?.beat || `Scene ${index + 1}`,
        durationS,
        prompt,
        visual: cleanPreviewText(frame?.visual || beat?.script || prompt, 220),
        camera: cleanPreviewText(frame?.camera || inferCameraCue(prompt), 180),
        audio: cleanPreviewText(frame?.audio || inferAudioCue(beat?.script), 180),
        modelKey: shot.model_key || defaultModel,
        renderMode: shot.render_mode || inferRenderModeFromRefs(refsUsed),
        refs: refsUsed,
        status: preflight.status === 'approved_for_render' ? 'locked' : 'draft',
        spendUsd: estimateSceneSpendUsd(shot.model_key || defaultModel, durationS, shot.render_mode),
      };
    });
  }

  if (storyboard.length > 0) {
    return storyboard.slice(0, SCENE_PREVIEW_MAX).map((frame, index) => {
      const beat = script[index];
      const visual = cleanPreviewText(frame.visual || beat?.script || preflight.creative_plan?.logline || '');
      const refsUsed = pickPreviewReferenceTags(visual, refs);
      const durationS = normalizePreviewDuration(beat?.duration_s);
      const prompt = withReferenceBindings([
        visual,
        frame.camera ? `Camera: ${frame.camera}` : '',
        frame.audio ? `Audio: ${frame.audio}` : '',
        beat?.script ? `Script beat: ${beat.script}` : '',
      ].filter(Boolean).join('\n'), refsUsed, refs);
      return {
        id: frame.id || `storyboard-${index + 1}`,
        label: frame.frame || beat?.beat || `Scene ${index + 1}`,
        durationS,
        prompt,
        visual,
        camera: cleanPreviewText(frame.camera || inferCameraCue(prompt), 180),
        audio: cleanPreviewText(frame.audio || inferAudioCue(beat?.script), 180),
        modelKey: defaultModel,
        renderMode: inferRenderModeFromRefs(refsUsed),
        refs: refsUsed,
        status: preflight.status === 'approved_for_render' ? 'locked' : 'draft',
        spendUsd: estimateSceneSpendUsd(defaultModel, durationS, inferRenderModeFromRefs(refsUsed)),
      };
    });
  }

  const graphNodes = producerV2?.shot_graph?.nodes ?? [];
  if (graphNodes.length > 0) {
    return graphNodes.slice(0, SCENE_PREVIEW_MAX).map((node, index) => {
      const beat = script.find((item) => item.beat === node.beat_id) ?? script[index];
      const visual = cleanPreviewText(node.visual_intent || beat?.script || node.purpose || preflight.creative_plan?.logline || '');
      const refsUsed = pickPreviewReferenceTags(visual, refs);
      const durationS = normalizePreviewDuration(node.duration_s ?? beat?.duration_s);
      const route = node.model_route_hint || defaultModel;
      const prompt = withReferenceBindings([
        visual,
        node.camera_intent ? `Camera: ${node.camera_intent}` : '',
        beat?.script ? `Script beat: ${beat.script}` : '',
      ].filter(Boolean).join('\n'), refsUsed, refs);
      return {
        id: node.shot_id || `graph-${index + 1}`,
        label: node.shot_id || beat?.beat || `Scene ${index + 1}`,
        durationS,
        prompt,
        visual,
        camera: cleanPreviewText(node.camera_intent || inferCameraCue(prompt), 180),
        audio: cleanPreviewText(inferAudioCue(beat?.script), 180),
        modelKey: route,
        renderMode: inferRenderModeFromRefs(refsUsed),
        refs: refsUsed,
        status: preflight.status === 'approved_for_render' ? 'locked' : 'draft',
        spendUsd: estimateSceneSpendUsd(route, durationS, inferRenderModeFromRefs(refsUsed)),
      };
    });
  }

  if (preflight.creative_plan) {
    const visual = cleanPreviewText(
      preflight.creative_plan.logline
      || preflight.creative_plan.viewer_promise
      || preflight.creative_plan.creative_angle
      || preflight.creative_plan.title
      || 'Autonomous concept scene',
    );
    const refsUsed = pickPreviewReferenceTags(visual, refs);
    const durationS = normalizePreviewDuration(preflight.summary?.target_duration_s || DEFAULT_SCENE_DURATION_S);
    return [{
      id: 'concept-preview',
      label: preflight.creative_plan.title || 'Concept preview',
      durationS,
      prompt: withReferenceBindings(visual, refsUsed, refs),
      visual,
      camera: 'Vertical cinematic composition with a clear first frame, readable subject action, and smooth final-frame handoff.',
      audio: 'Natural voice, music or ambience according to the selected niche and platform.',
      modelKey: defaultModel,
      renderMode: inferRenderModeFromRefs(refsUsed),
      refs: refsUsed,
      status: preflight.status === 'approved_for_render' ? 'locked' : 'draft',
      spendUsd: estimateSceneSpendUsd(defaultModel, durationS, inferRenderModeFromRefs(refsUsed)),
    }];
  }

  return [];
}

function buildLongformReviewScenes(
  longformPlan: LongformPlanPreview,
  dryRunReport?: Record<string, unknown>,
): StudioPreviewScene[] {
  const shotPayloads = Array.isArray(dryRunReport?.shot_payloads)
    ? dryRunReport.shot_payloads as Array<Record<string, unknown>>
    : [];
  return (longformPlan.segments ?? []).slice(0, SCENE_PREVIEW_MAX).map((segment, index) => {
    const payload = shotPayloads[index] ?? {};
    const prompt = cleanPreviewText(String(payload.prompt || segment.objective || ''), 1200);
    const handoff = (segment.handoff_requirements ?? []).join(' | ');
    return {
      id: segment.segment_id || `longform-${index + 1}`,
      label: `Segment ${index + 1}`,
      durationS: normalizePreviewDuration(segment.duration_s),
      prompt,
      visual: cleanPreviewText(segment.objective || prompt, 260),
      camera: cleanPreviewText(`Continuity handoff: ${handoff || 'preserve identity, style, emotion, and last frame.'}`, 220),
      audio: cleanPreviewText(`Entry: ${compactPreviewState(segment.entry_state)} | Exit: ${compactPreviewState(segment.exit_state)}`, 220),
      modelKey: String((payload.payload as Record<string, unknown> | undefined)?.model_key || dryRunReport?.model || 'seedance_2_0'),
      renderMode: 'long_form_segment',
      refs: [],
      status: segment.status === 'completed' ? 'locked' : 'needs-review',
      spendUsd: estimateSceneSpendUsd(String(dryRunReport?.model || 'seedance_2_0'), normalizePreviewDuration(segment.duration_s), 'long_form_segment'),
    };
  });
}

function compactPreviewState(value?: Record<string, unknown>): string {
  if (!value) return 'none';
  const parts = Object.entries(value)
    .filter(([, item]) => item !== undefined && item !== null && item !== '')
    .map(([key, item]) => `${key}=${String(item).slice(0, 60)}`);
  return parts.length > 0 ? parts.join(', ') : 'none';
}

function summarizePreviewSpend(scenes: StudioPreviewScene[]): SpendPreview {
  const base = scenes.reduce((sum, scene) => sum + scene.spendUsd, 0);
  return {
    totalSeconds: scenes.reduce((sum, scene) => sum + scene.durationS, 0),
    lowUsd: base > 0 ? Math.max(0.01, base * 0.85) : 0,
    highUsd: base > 0 ? Math.max(0.01, base * 1.25) : 0,
  };
}

function estimateSceneSpendUsd(modelKey: string, durationS: number, renderMode?: string): number {
  const key = `${modelKey || ''} ${renderMode || ''}`.toLowerCase();
  let rate = 0.075;
  if (key.includes('fast')) rate = 0.055;
  if (key.includes('standard') || key.includes('seedance_2_0')) rate = Math.max(rate, 0.075);
  if (key.includes('reference') || key.includes('i2v') || key.includes('omni')) rate += 0.02;
  if (key.includes('pro')) rate += 0.035;
  if (durationS >= 60) rate *= 0.9;
  return Math.max(0.03, durationS * rate);
}

function isVideoModelChoice(value: unknown): value is VideoModelChoice {
  return VIDEO_MODEL_OPTIONS.some((option) => option.value === value);
}

function isAspectRatioChoice(value: unknown): value is AspectRatioChoice {
  return ASPECT_OPTIONS.some((option) => option.value === value);
}

function buildRenderBlockers({
  isGenerating,
  planning,
  approved,
  renderSourceReady,
  needsUserInput,
  preflightHasBlockedChecks,
  generationNeedsClarification,
  generationBlockedByResponsibleGate,
  hasBrief,
  referenceRolesConfirmed,
  uploadingRefs,
  hasPreview,
  selectedModelNeedsImage,
  selectedModelLabel,
  isLongform,
  hasApprovedDryRun,
  segmentReviewComplete,
  consistencyReviewRequired,
  consistencyReviewApproved,
}: {
  isGenerating: boolean;
  planning: boolean;
  approved: boolean;
  renderSourceReady: boolean;
  needsUserInput: boolean;
  preflightHasBlockedChecks: boolean;
  generationNeedsClarification: boolean;
  generationBlockedByResponsibleGate: boolean;
  hasBrief: boolean;
  referenceRolesConfirmed: boolean;
  uploadingRefs: boolean;
  hasPreview: boolean;
  selectedModelNeedsImage: boolean;
  selectedModelLabel: string;
  isLongform: boolean;
  hasApprovedDryRun: boolean;
  segmentReviewComplete: boolean;
  consistencyReviewRequired: boolean;
  consistencyReviewApproved: boolean;
}): RenderBlocker[] {
  const blockers: RenderBlocker[] = [];
  if (!hasBrief) {
    blockers.push({
      key: 'brief',
      label: 'Missing video request',
      detail: 'Type the goal in plain language so the Agent can build script, storyboard and scene prompts.',
      severity: 'hard',
    });
  }
  if (uploadingRefs) {
    blockers.push({
      key: 'uploading',
      label: 'Reference upload in progress',
      detail: 'Wait for all media files to finish uploading before approving a paid render source.',
      severity: 'hard',
    });
  }
  if (needsUserInput) {
    blockers.push({
      key: 'needs-input',
      label: 'Agent needs one answer',
      detail: 'Answer the highlighted question so the Agent does not guess a risky niche, subject or reference role.',
      severity: 'hard',
    });
  }
  if (!referenceRolesConfirmed) {
    blockers.push({
      key: 'reference-roles',
      label: 'Reference roles are not locked',
      detail: 'Confirm whether each file is product, character, style, location, motion, pacing, beat, SFX or voice timing.',
      severity: 'hard',
    });
  }
  if (selectedModelNeedsImage) {
    blockers.push({
      key: 'model-input',
      label: 'Selected model needs an image',
      detail: `${selectedModelLabel} is an image-driven route. Upload and confirm at least one image reference, or switch model back to Auto route.`,
      severity: 'hard',
    });
  }
  if (preflightHasBlockedChecks) {
    blockers.push({
      key: 'blocked-checks',
      label: 'Pre-render checklist has a blocked item',
      detail: 'Resolve blocked script, safety, continuity or reference checks before approval.',
      severity: 'hard',
    });
  }
  if (isLongform && approved && !hasApprovedDryRun) {
    blockers.push({
      key: 'longform-dry-run',
      label: 'Long-form dry-run is required',
      detail: 'Run the full segmented dry-run and review every payload before starting paid render.',
      severity: 'hard',
    });
  }
  if (isLongform && hasApprovedDryRun && !segmentReviewComplete) {
    blockers.push({
      key: 'longform-segment-review',
      label: 'Segment review is incomplete',
      detail: 'Approve or reject each segment in the long-form dry-run before paid render.',
      severity: 'hard',
    });
  }
  if (consistencyReviewRequired && !consistencyReviewApproved) {
    blockers.push({
      key: 'consistency-review',
      label: 'Consistency review required',
      detail: 'The identity or product consistency policy requires explicit review approval before paid render.',
      severity: 'hard',
    });
  }
  if (generationNeedsClarification) {
    blockers.push({
      key: 'niche-clarification',
      label: 'Niche needs clarification',
      detail: 'Clarify the primary niche or audience so the route and storytelling pattern are not mis-selected.',
      severity: 'hard',
    });
  }
  if (generationBlockedByResponsibleGate) {
    blockers.push({
      key: 'responsible-gate',
      label: 'Responsible content review required',
      detail: 'Rewrite likeness, voice, IP or sensitive content before rendering.',
      severity: 'hard',
    });
  }
  if (planning) {
    blockers.push({
      key: 'planning',
      label: 'Agent is still planning',
      detail: 'Wait for the current preflight and production decision checks to finish.',
      severity: 'hard',
    });
  }
  if (!approved) {
    blockers.push({
      key: 'approval',
      label: 'Script and storyboard not approved',
      detail: 'Review the Agent draft, then approve to lock the exact render source.',
      severity: 'hard',
    });
  } else if (!renderSourceReady) {
    blockers.push({
      key: 'source-lock',
      label: 'Render source is locking',
      detail: 'The approved input fingerprint must match the backend render source before the final button unlocks.',
      severity: 'hard',
    });
  }
  if (isGenerating) {
    blockers.push({
      key: 'rendering',
      label: 'Render job already running',
      detail: 'Wait for the current job to finish or close the job modal after review.',
      severity: 'soft',
    });
  }
  if (hasBrief && !hasPreview) {
    blockers.push({
      key: 'preview',
      label: 'Scene preview not ready yet',
      detail: 'The Agent should produce a scene timeline before you approve the final render.',
      severity: 'soft',
    });
  }
  return blockers;
}

function cleanPreviewText(value?: string, limit = 360): string {
  const text = (value || '')
    .replace(/\s+/g, ' ')
    .replace(/\\"/g, '"')
    .trim();
  if (!text) return 'Agent will compose a clear, visually specific scene.';
  return text.length > limit ? `${text.slice(0, limit - 1).trim()}...` : text;
}

function normalizePreviewDuration(value?: number | null): number {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) return DEFAULT_SCENE_DURATION_S;
  return Math.max(3, Math.min(120, Math.round(value)));
}

function inferCameraCue(prompt: string): string {
  const lower = prompt.toLowerCase();
  if (lower.includes('close')) return 'Close-up with controlled focus, clean subject separation, and no text artifacts.';
  if (lower.includes('handheld')) return 'Subtle handheld smartphone motion with stable product/character framing.';
  if (lower.includes('cinematic')) return 'Cinematic push-in with strong foreground/background depth and consistent lighting.';
  return 'Vertical 9:16 composition with a clear subject, readable motion, and smooth transition handoff.';
}

function inferAudioCue(script?: string): string {
  if (script && /(dialog|voice|speak|talk|line|thoai|noi)/i.test(script)) {
    return 'Voice-forward mix with clean dialogue timing and music underbed.';
  }
  return 'Music or ambient bed matched to the niche, with SFX only where it improves clarity.';
}

function inferRenderModeFromRefs(refTags: string[]): string {
  if (refTags.some((tag) => tag.startsWith('@video_'))) return 'reference_video';
  if (refTags.some((tag) => tag.startsWith('@image_'))) return 'reference_image';
  if (refTags.some((tag) => tag.startsWith('@audio_'))) return 'audio_guided';
  return 'text_to_video';
}

function pickPreviewReferenceTags(prompt: string, refs: ReferenceAsset[]): string[] {
  const explicit = Array.from(new Set((prompt.match(/@(image|video|audio)_\d+/gi) ?? []).map((tag) => tag.toLowerCase())));
  if (explicit.length > 0) return explicit.slice(0, 5);

  const ready = refs.filter((ref) => !ref.uploading && ref.url);
  const priority: ReferenceRole[] = [
    'product_hero',
    'character_anchor',
    'style_reference',
    'environment',
    'camera_motion',
    'motion_style',
    'shot_pacing',
    'beat_reference',
    'lip_sync_source',
  ];
  const sorted = [...ready].sort((a, b) => {
    const aIndex = priority.indexOf(a.role);
    const bIndex = priority.indexOf(b.role);
    return (aIndex === -1 ? 999 : aIndex) - (bIndex === -1 ? 999 : bIndex);
  });
  return sorted.slice(0, 4).map((ref) => getReferenceTag(ref, ready));
}

function withReferenceBindings(prompt: string, refTags: string[], refs: ReferenceAsset[]): string {
  const cleanPrompt = cleanPreviewText(prompt, 900);
  if (refTags.length === 0) return cleanPrompt;
  const ready = refs.filter((ref) => !ref.uploading && ref.url);
  const byTag = new Map(ready.map((ref) => [getReferenceTag(ref, ready), ref]));
  const bindings = refTags
    .map((tag) => {
      const ref = byTag.get(tag);
      if (!ref) return `${tag}: use only if this uploaded asset is available.`;
      return `${tag}: ${roleBindingLabel(ref.role)}`;
    })
    .join(' | ');
  return `${cleanPrompt}\nReference bindings: ${bindings}`;
}

function detectReferenceKind(file: File): ReferenceKind | null {
  const type = (file.type || '').toLowerCase();
  const name = (file.name || '').toLowerCase();
  if (type.startsWith('image/')) return 'image';
  if (type.startsWith('video/')) return 'video';
  if (type.startsWith('audio/')) return 'audio';
  if (/\.(png|jpe?g|webp|gif|bmp|avif|heic|heif|tiff?)$/i.test(name)) return 'image';
  if (/\.(mp4|mov|webm|m4v|avi|mkv)$/i.test(name)) return 'video';
  if (/\.(mp3|wav|m4a|aac|ogg|flac|opus)$/i.test(name)) return 'audio';
  return null;
}

function normalizeSeriesKey(value: string): string {
  return value
    .trimStart()
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_.-]/g, '')
    .slice(0, 80);
}

function countReferenceKinds(refs: Array<Pick<ReferenceAsset, 'kind'>>) {
  return refs.reduce(
    (acc, ref) => {
      acc[ref.kind] += 1;
      return acc;
    },
    { image: 0, video: 0, audio: 0 } satisfies Record<ReferenceKind, number>,
  );
}

function getReferenceTag(ref: Pick<ReferenceAsset, 'id' | 'kind'>, refs: Array<Pick<ReferenceAsset, 'id' | 'kind'>>): string {
  const sameKindBefore = refs
    .slice(0, Math.max(0, refs.findIndex((item) => item.id === ref.id) + 1))
    .filter((item) => item.kind === ref.kind).length;
  const prefix = ref.kind === 'image' ? 'image' : ref.kind === 'video' ? 'video' : 'audio';
  return `@${prefix}_${Math.max(1, sameKindBefore)}`;
}

function roleOptionsForKind(kind: ReferenceKind): Array<{ role: ReferenceRole; label: string; hint: string }> {
  if (kind === 'image') return [...IMAGE_REFERENCE_ROLE_OPTIONS] as Array<{ role: ReferenceRole; label: string; hint: string }>;
  if (kind === 'video') return [...VIDEO_REFERENCE_ROLE_OPTIONS] as Array<{ role: ReferenceRole; label: string; hint: string }>;
  return [...AUDIO_REFERENCE_ROLE_OPTIONS] as Array<{ role: ReferenceRole; label: string; hint: string }>;
}

function inferReferenceRole(
  file: File,
  kind: ReferenceKind,
  existingRefs: Array<Pick<ReferenceAsset, 'kind' | 'role' | 'name'>>,
): ReferenceRole {
  const name = `${file.name} ${file.type}`.toLowerCase();
  if (kind === 'audio') {
    if (/(voice|dialog|dialogue|speech|vo|lip|talk|noi|thoai)/i.test(name)) return 'lip_sync_source';
    if (/(sfx|foley|ambient|ambience|effect|sound)/i.test(name)) return 'sfx_layer';
    return 'beat_reference';
  }
  if (kind === 'video') {
    if (/(pace|edit|cut|transition|reveal)/i.test(name)) return 'shot_pacing';
    if (/(motion|action|dance|gesture|move)/i.test(name)) return 'motion_style';
    return 'camera_motion';
  }
  if (/(logo|brand|mark|typography|font)/i.test(name)) return 'brand_asset';
  if (/(room|house|home|street|cafe|store|location|place|scene|environment|background)/i.test(name)) return 'environment';
  if (/(style|mood|color|lighting|look|cinematic|film|aesthetic)/i.test(name)) return 'style_reference';
  if (/(detail|macro|texture|label|close)/i.test(name)) return 'product_detail';
  if (/(product|prod|serum|cream|bottle|pack|package|packaging|item|sku|goods|sanpham|san-pham|mypham|my-pham)/i.test(name)) return 'product_hero';
  if (/(face|person|people|portrait|model|character|actor|creator|kol|influencer|woman|man|girl|boy|nhanvat|nhan-vat)/i.test(name)) return 'character_anchor';

  const imageCount = existingRefs.filter((ref) => ref.kind === 'image').length;
  const hasProduct = existingRefs.some((ref) => ref.role === 'product_hero' || ref.role === 'product_detail');
  const hasCharacter = existingRefs.some((ref) => ref.role === 'character_anchor');
  if (imageCount === 0) return 'product_hero';
  if (!hasCharacter && hasProduct) return 'character_anchor';
  if (!hasProduct) return 'product_hero';
  return 'style_reference';
}

function buildReferenceManifest(refs: ReferenceAsset[]) {
  const ready = refs.filter((ref) => !ref.uploading && ref.url);
  const items = ready.map((ref) => {
    const tag = getReferenceTag(ref, ready);
    return {
      tag,
      kind: ref.kind,
      role: ref.role,
      role_confirmed: Boolean(ref.roleConfirmed && ref.role !== 'unknown'),
      role_source: ref.roleSource || 'auto',
      name: ref.name,
      url: ref.url,
      prompt_binding: `${tag} = ${roleBindingLabel(ref.role)}.`,
    };
  });
  return {
    schema_version: 'cinejelly.ui_reference_manifest.v1',
    confirmed: items.every((item) => item.role_confirmed),
    instruction: 'Use every @reference only for its assigned role. Never swap product, character, style, camera, motion, beat, SFX or voice responsibilities.',
    items,
    images: items.filter((item) => item.kind === 'image'),
    videos: items.filter((item) => item.kind === 'video'),
    audios: items.filter((item) => item.kind === 'audio'),
  };
}

function roleBindingLabel(role: ReferenceRole): string {
  const labels: Record<ReferenceRole, string> = {
    character_anchor: 'primary character identity: exact face, hair, outfit, body language',
    secondary_character: 'secondary character identity',
    product_hero: 'product hero: exact packaging, geometry, colors and label fidelity',
    product_detail: 'product detail: macro texture, material or close-up label fidelity',
    style_reference: 'visual style: mood, color grade, lighting and composition only',
    environment: 'environment: location, atmosphere and spatial layout',
    brand_asset: 'brand asset: logo, typography and brand colors',
    camera_motion: 'camera movement reference: dolly, pan, orbit, push-in or handheld feel',
    motion_style: 'motion style reference: subject action timing and physical rhythm',
    shot_pacing: 'edit pacing reference: cut rhythm, transition timing and reveal tempo',
    beat_reference: 'audio beat reference: music tempo, rhythm and emotional pacing',
    sfx_layer: 'sound design reference: foley texture, impact moments and ambience',
    lip_sync_source: 'voice/dialogue timing reference, not identity cloning',
    unknown: 'general reference requiring user confirmation',
  };
  return labels[role] || labels.unknown;
}

function isReferenceRole(role: unknown): role is ReferenceRole {
  return typeof role === 'string' && [
    'character_anchor',
    'secondary_character',
    'product_hero',
    'product_detail',
    'style_reference',
    'environment',
    'brand_asset',
    'camera_motion',
    'motion_style',
    'shot_pacing',
    'beat_reference',
    'sfx_layer',
    'lip_sync_source',
    'unknown',
  ].includes(role);
}

function extractFirstUrl(text: string): string {
  const match = (text || '').match(/https?:\/\/[^\s<>'")]+/i);
  return match?.[0]?.replace(/[.,]+$/, '') || '';
}

function appendUniqueBlock(current: string, block: string, limit: number): string {
  const existing = (current || '').trim();
  const next = (block || '').trim();
  if (!next) return existing.slice(0, limit);
  if (existing.includes(next.slice(0, 120))) return existing.slice(0, limit);
  return (existing ? `${existing}\n\n${next}` : next).slice(0, limit);
}

function cleanAssetName(name: string) {
  return (name || 'Autonomous reference')
    .replace(/\.[a-z0-9]{2,5}$/i, '')
    .replace(/[_-]+/g, ' ')
    .trim()
    .slice(0, 120) || 'Autonomous reference';
}
