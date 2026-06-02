'use client';

import { type RefObject, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  ArrowRight,
  AlertTriangle,
  BadgeCheck,
  CheckCircle2,
  Clapperboard,
  Clock,
  Copy,
  Eye,
  FileAudio,
  Film,
  Globe2,
  ImagePlus,
  Layers,
  ListChecks,
  Loader2,
  Pin,
  Play,
  Plus,
  RotateCcw,
  Sparkles,
  Upload,
  Wand2,
  X,
} from 'lucide-react';
import { JobResultModal } from '@/components/studio/JobResultModal';
import { RecentGenerations } from '@/components/studio/RecentGenerations';
import { usePersistedJob } from '@/lib/studio/use-persisted-job';
import { uploadMediaToR2 } from '@/lib/studio/upload-media';

const DRAFT_STORAGE_KEY = 'cineforge:autonomous_draft_v1';
const AUTONOMOUS_MAX_IMAGES = 9;
const AUTONOMOUS_MAX_VIDEOS = 3;
const AUTONOMOUS_MAX_AUDIO = 3;
const AUTONOMOUS_MAX_TOTAL_REFS = 12;
const CHAT_HISTORY_LIMIT = 12;
const BRIEF_MAX_CHARS = 3000;
const CHAT_INPUT_MAX_CHARS = 1000;
const SCENE_PREVIEW_MAX = 12;
const DEFAULT_SCENE_DURATION_S = 8;

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
  { value: 30, label: '30s', hint: 'short' },
  { value: 180, label: '3m', hint: 'micro film' },
  { value: 300, label: '5m', hint: 'short film' },
  { value: 1800, label: '30m', hint: 'episode' },
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
  '5-minute founder story for a Vietnamese cafe, emotional but premium',
  'Short drama episode about betrayal, one twist, cinematic vertical style',
  'Product demo for a SaaS tool, global market, fast social ad pacing',
] as const;

const MEMORY_ROLE_OPTIONS = [
  { role: 'character_anchor', label: 'Character', assetType: 'character', tags: 'character,anchor' },
  { role: 'product_hero', label: 'Product', assetType: 'product', tags: 'product,hero' },
  { role: 'style_reference', label: 'Style', assetType: 'storyboard', tags: 'style,reference' },
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
type MemoryRoleOption = (typeof MEMORY_ROLE_OPTIONS)[number];
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

interface AutonomousAssetPin {
  id: string;
  asset_id: string;
  role: string;
  target_market: string;
  niche: string;
  series_key: string;
  priority: number;
  status: string;
  notes?: string;
  asset?: {
    id?: string;
    type?: string;
    name?: string;
    image_url?: string;
    tags?: string;
  } | null;
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
  const [chatInput, setChatInput] = useState('');
  const [revisionInput, setRevisionInput] = useState('');
  const [revisionNotes, setRevisionNotes] = useState('');
  const [planVersion, setPlanVersion] = useState(1);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => [...INITIAL_CHAT_MESSAGES]);
  const [conversationalPreflight, setConversationalPreflight] = useState<ConversationalPreflight | null>(null);
  const [conversationalPreflightLoading, setConversationalPreflightLoading] = useState(false);
  const [preflightApproved, setPreflightApproved] = useState(false);
  const [approvedInputKey, setApprovedInputKey] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [autonomousPreview, setAutonomousPreview] = useState<AutonomousPreview | null>(null);
  const [productionDecision, setProductionDecision] = useState<ProductionDecision | null>(null);
  const [productionDecisionLoading, setProductionDecisionLoading] = useState(false);
  const [productIntelligence, setProductIntelligence] = useState<ProductIntelligence | null>(null);
  const [productIntelligenceLoading, setProductIntelligenceLoading] = useState(false);
  const [deepPreflight, setDeepPreflight] = useState<DeepPreflightBrain | null>(null);
  const [deepPreflightLoading, setDeepPreflightLoading] = useState(false);
  const [assetPins, setAssetPins] = useState<AutonomousAssetPin[]>([]);
  const [selectedPinIds, setSelectedPinIds] = useState<string[]>([]);
  const [pinRefreshNonce, setPinRefreshNonce] = useState(0);
  const [approvingMemoryKey, setApprovingMemoryKey] = useState<string | null>(null);
  const [showJobModal, setShowJobModal] = useState(false);
  const [activePreviewSceneId, setActivePreviewSceneId] = useState<string | null>(null);
  const [sceneDraftsInserted, setSceneDraftsInserted] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatInputRef = useRef<HTMLTextAreaElement | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
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
  }, [aspectRatioChoice, brief, durationHintS, planVersion, qualityPreset, revisionNotes, seriesKey, targetMarket, videoModelChoice]);

  useEffect(() => {
    if (jobId && !showJobModal) {
      setShowJobModal(true);
      toast.info('Resuming the previous render job', { duration: 3500 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ limit: '12', status: 'active' });
    if (targetMarket !== 'auto') params.set('target_market', targetMarket);
    if (seriesKey.trim()) params.set('series_key', seriesKey.trim());
    fetch(`/api/v1/assets/autonomous-pins?${params.toString()}`, { cache: 'no-store' })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled) return;
        const items = Array.isArray(data?.items) ? data.items : [];
        setAssetPins(items);
        setSelectedPinIds((prev) => prev.filter((id) => items.some((pin: AutonomousAssetPin) => pin.id === id)));
      })
      .catch(() => {
        if (!cancelled) setAssetPins([]);
      });
    return () => {
      cancelled = true;
    };
  }, [seriesKey, targetMarket, pinRefreshNonce]);

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
  const selectedPinIdsKey = useMemo(
    () => [...selectedPinIds].sort().join('|'),
    [selectedPinIds],
  );
  const targetPlatform = durationHintS >= 180 ? 'youtube_long' : 'tiktok';
  const targetPlatformLabel = durationHintS >= 180 ? 'Long-form story' : 'Short-form vertical';
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
      revisionNotes.trim(),
      referenceStateKey,
      selectedPinIdsKey,
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
      selectedResolution,
      selectedPinIdsKey,
      targetMarket,
      targetPlatform,
      videoModelChoice,
    ],
  );
  const readyImageRefs = useMemo(
    () => readyRefs.filter((r) => r.kind === 'image'),
    [readyRefs],
  );
  const previewScenes = useMemo(
    () => buildStudioPreviewScenes(conversationalPreflight, readyRefs),
    [conversationalPreflight, readyRefs],
  );
  const activePreviewScene = useMemo(
    () => previewScenes.find((scene) => scene.id === activePreviewSceneId) ?? previewScenes[0] ?? null,
    [activePreviewSceneId, previewScenes],
  );
  const spendPreview = useMemo(
    () => summarizePreviewSpend(previewScenes),
    [previewScenes],
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
      planning: productionDecisionLoading || conversationalPreflightLoading,
      approved: preflightApproved,
      renderSourceReady,
      needsUserInput: conversationalPreflight?.status === 'needs_user_input',
      preflightHasBlockedChecks,
      generationNeedsClarification,
      generationBlockedByResponsibleGate,
      hasBrief: Boolean(brief.trim()),
      referenceRolesConfirmed,
      uploadingRefs: refs.some((r) => r.uploading),
      hasPreview: previewScenes.length > 0,
      selectedModelNeedsImage,
      selectedModelLabel: selectedVideoModel.label,
    }),
    [
      brief,
      conversationalPreflight?.status,
      conversationalPreflightLoading,
      generationBlockedByResponsibleGate,
      generationNeedsClarification,
      isGenerating,
      preflightApproved,
      preflightHasBlockedChecks,
      previewScenes.length,
      productionDecisionLoading,
      referenceRolesConfirmed,
      referenceImageUrls.length,
      refs,
      renderSourceReady,
      selectedModelNeedsImage,
      selectedVideoModel.label,
    ],
  );
  const workflowSteps = useMemo(() => buildWorkflowSteps({
    hasBrief: Boolean(brief.trim()),
    hasPlan: Boolean(conversationalPreflight?.creative_plan),
    hasPreview: previewScenes.length > 0,
    previewInserted: sceneDraftsInserted,
    needsInput: conversationalPreflight?.status === 'needs_user_input',
    hasRevision: Boolean(revisionNotes.trim()),
    approved: preflightApproved,
    rendering: isGenerating,
    renderStarted: Boolean(autonomousPreview),
  }), [
    autonomousPreview,
    brief,
    conversationalPreflight?.creative_plan,
    conversationalPreflight?.status,
    isGenerating,
    preflightApproved,
    previewScenes.length,
    revisionNotes,
    sceneDraftsInserted,
  ]);
  const generateDisabled = (
    isGenerating
    || productionDecisionLoading
    || conversationalPreflightLoading
    || !preflightApproved
    || !renderSourceReady
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
    if (previewScenes.length === 0) {
      if (activePreviewSceneId) setActivePreviewSceneId(null);
      return;
    }
    if (!previewScenes.some((scene) => scene.id === activePreviewSceneId)) {
      setActivePreviewSceneId(previewScenes[0]?.id ?? null);
    }
  }, [activePreviewSceneId, previewScenes]);

  useEffect(() => {
    setSceneDraftsInserted(false);
  }, [currentInputKey]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ block: 'end', behavior: 'smooth' });
  }, [chatMessages.length, conversationalPreflightLoading, suggestedReplies.length]);

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
            pinned_assets: selectedPinIds.length,
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
  }, [preflightBrief, durationHintS, readyRefs, referenceAudioUrls, referenceImageUrls, referenceManifest, referenceStateKey, referenceVideoUrls, refs, renderAspectRatio, selectedPinIds.length, selectedPinIdsKey, targetMarket, targetPlatform]);

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
            pinned_assets: selectedPinIds.length,
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
  }, [preflightBrief, conversationHistoryKey, durationHintS, preflightApproved, readyRefs, referenceAudioUrls, referenceImageUrls, referenceManifest, referenceStateKey, referenceVideoUrls, refs, renderAspectRatio, revisionNotes, selectedPinIds.length, selectedPinIdsKey, targetMarket, targetPlatform]);

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
    setSceneDraftsInserted(false);
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
            pinned_assets: selectedPinIds.length,
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
    selectedPinIds.length,
    targetMarket,
    targetPlatform,
  ]);

  const handleApprovePreflight = useCallback(() => {
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
    setPreflightApproved(true);
    setApprovedInputKey(currentInputKey);
    toast.success('Plan approved. Locking render source.');
  }, [conversationalPreflight, currentInputKey, referenceRolesConfirmed]);

  const handleInsertPreviewOnly = useCallback(() => {
    if (previewScenes.length === 0) {
      toast.info('Send one clear idea first so the Agent can draft scenes.');
      return;
    }
    setSceneDraftsInserted(true);
    setActivePreviewSceneId((current) => (
      current && previewScenes.some((scene) => scene.id === current)
        ? current
        : previewScenes[0]?.id ?? null
    ));
    toast.success('Scene timeline inserted for review. No paid render started.');
  }, [previewScenes]);

  const handleInsertAndUnlockRender = useCallback(() => {
    if (previewScenes.length === 0) {
      toast.info('Send one clear idea first so the Agent can draft scenes.');
      return;
    }
    setSceneDraftsInserted(true);
    setActivePreviewSceneId((current) => (
      current && previewScenes.some((scene) => scene.id === current)
        ? current
        : previewScenes[0]?.id ?? null
    ));
    handleApprovePreflight();
  }, [handleApprovePreflight, previewScenes]);

  const handleAddSceneRequest = useCallback(() => {
    if (!conversationalPreflight?.creative_plan) {
      toast.info('Create the first agent plan before adding more scenes.');
      return;
    }
    const instruction = 'Add one extra high-value scene that improves pacing, preserves character/product continuity, and uses only the confirmed reference roles.';
    setRevisionNotes((prev) => appendUniqueBlock(prev, instruction, 1200));
    setPlanVersion((version) => version + 1);
    setPreflightApproved(false);
    setSceneDraftsInserted(false);
    toast.info('Agent queued one more scene and will refresh the storyboard.');
  }, [conversationalPreflight?.creative_plan]);

  const handlePolishAllScenes = useCallback(() => {
    if (!conversationalPreflight?.creative_plan) {
      toast.info('Create the first agent plan before polishing scene prompts.');
      return;
    }
    const instruction = 'Improve every scene prompt with stronger camera language, exact reference binding, visible continuity handoff, no text artifacts, and a cleaner first-frame/last-frame transition.';
    setRevisionNotes((prev) => appendUniqueBlock(prev, instruction, 1200));
    setPlanVersion((version) => version + 1);
    setPreflightApproved(false);
    setSceneDraftsInserted(false);
    toast.info('Agent will refresh all scene prompts for a cleaner preview.');
  }, [conversationalPreflight?.creative_plan]);

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
    setAutonomousPreview(null);
    setProductionDecision(null);
    setProductionDecisionLoading(false);
    setProductIntelligence(null);
    setProductIntelligenceLoading(false);
    setDeepPreflight(null);
    setDeepPreflightLoading(false);
    setActivePreviewSceneId(null);
    setSceneDraftsInserted(false);
    setSelectedPinIds([]);
    setApprovingMemoryKey(null);
    lastAssistantPreflightRef.current = '';
    if (typeof window !== 'undefined') {
      localStorage.removeItem(DRAFT_STORAGE_KEY);
    }
    toast.success('New autonomous project started.');
  }, []);

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
  }, [refs]);

  const removeReference = useCallback((id: string) => {
    setRefs((prev) => {
      const removed = prev.find((r) => r.id === id);
      if (removed) revokeReferencePreview(removed);
      return prev.filter((r) => r.id !== id);
    });
  }, []);

  const updateReferenceRole = useCallback((id: string, role: ReferenceRole) => {
    setRefs((prev) => prev.map((item) => (
      item.id === id ? { ...item, role, roleConfirmed: true, roleSource: 'user' } : item
    )));
    setPreflightApproved(false);
  }, []);

  const confirmAllReferenceRoles = useCallback(() => {
    setRefs((prev) => prev.map((item) => (
      item.uploading || !item.url
        ? item
        : { ...item, roleConfirmed: item.role !== 'unknown', roleSource: item.roleSource || 'user' }
    )));
    setPreflightApproved(false);
    toast.success('Reference manifest confirmed.');
  }, []);

  const approveReferenceAsMemory = useCallback(async (
    ref: ReferenceAsset,
    option: MemoryRoleOption,
  ) => {
    if (ref.kind !== 'image' || !ref.url || ref.uploading) return;
    const key = `${ref.id}:${option.role}`;
    setApprovingMemoryKey(key);
    try {
      const assetRes = await fetch('/api/v1/assets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: option.assetType,
          name: cleanAssetName(ref.name),
          image_url: ref.url,
          payload: {
            source: 'studio_autonomous_reference',
            original_name: ref.name,
          },
          tags: `${option.tags},autonomous`,
        }),
      });
      if (!assetRes.ok) {
        const errText = await assetRes.text();
        throw new Error(`asset ${assetRes.status}: ${errText.slice(0, 160)}`);
      }
      const asset = await assetRes.json();
      const pinRes = await fetch('/api/v1/assets/autonomous-pins', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_id: asset.id,
          role: option.role,
          target_market: targetMarket,
          niche: 'any',
          series_key: seriesKey.trim(),
          priority: option.role === 'character_anchor' ? 90 : option.role === 'product_hero' ? 85 : 70,
          status: 'active',
          notes: `Approved from /studio reference: ${ref.name}`,
          metadata: {
            source: 'studio_autonomous_reference',
            reference_url: ref.url,
          },
        }),
      });
      if (!pinRes.ok) {
        const errText = await pinRes.text();
        throw new Error(`pin ${pinRes.status}: ${errText.slice(0, 160)}`);
      }
      const pin = await pinRes.json();
      setSelectedPinIds((prev) => (prev.includes(pin.id) ? prev : [...prev, pin.id]));
      setPinRefreshNonce((n) => n + 1);
      toast.success(`Approved ${option.label.toLowerCase()} memory`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Approve memory failed: ${msg}`, { duration: 7000 });
      console.error(e);
    } finally {
      setApprovingMemoryKey(null);
    }
  }, [seriesKey, targetMarket]);

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
          reference_image_urls: referenceImageUrls,
          reference_video_urls: referenceVideoUrls,
          reference_audio_urls: referenceAudioUrls,
          pinned_asset_ids: selectedPinIds,
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
  }, [brief, conversationalPreflight, conversationalPreflightLoading, durationHintS, preflightApproved, productionDecision, productionDecisionLoading, referenceAudioUrls, referenceImageUrls, referenceManifest, referenceVideoUrls, refs, renderAspectRatio, renderSourceReady, selectedPinIds, selectedResolution, seriesKey, setJobId, targetMarket, targetPlatform, videoModelChoice]);

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
          hasPreview={previewScenes.length > 0}
          needsInput={conversationalPreflight?.status === 'needs_user_input'}
          loading={conversationalPreflightLoading || productionDecisionLoading}
          approved={preflightApproved}
          renderSourceReady={renderSourceReady}
          qualityLabel={`${selectedQuality.label} ${selectedResolution}`}
          durationLabel={durationHintS ? `${durationHintS}s` : 'Auto'}
          marketLabel={targetMarket === 'auto' ? 'Auto market' : `${targetMarket.toUpperCase()} market`}
        />

        <UnifiedCommandTable
          brief={brief}
          chatInput={chatInput}
          chatRevisionMode={chatRevisionMode}
          refs={refs}
          readyRefs={readyRefs}
          refCounts={refCounts}
          targetMarket={targetMarket}
          durationHintS={durationHintS}
          qualityPreset={qualityPreset}
          selectedResolution={selectedResolution}
          videoModelChoice={videoModelChoice}
          aspectRatioChoice={aspectRatioChoice}
          loading={conversationalPreflightLoading || productionDecisionLoading}
          suggestedReplies={suggestedReplies}
          showStarterPrompts={showStarterPrompts}
          productIntelligenceLoading={productIntelligenceLoading}
          deepPreflightLoading={deepPreflightLoading}
          referenceRolesConfirmed={referenceRolesConfirmed}
          onChatInputChange={setChatInput}
          onSubmit={handleChatSubmit}
          onStarterPrompt={handleStarterPrompt}
          onExtractProductUrl={handleExtractProductUrl}
          onDeepAnalyze={handleDeepAnalyze}
          onAddReference={() => fileInputRef.current?.click()}
          onFilesSelected={uploadReferences}
          fileInputRef={fileInputRef}
          onRemoveReference={removeReference}
          onConfirmReferenceRoles={confirmAllReferenceRoles}
          onReferenceRoleChange={updateReferenceRole}
          onTargetMarketChange={setTargetMarket}
          onDurationChange={setDurationHintS}
          onQualityChange={(value) => {
            setQualityPreset(value);
            setPreflightApproved(false);
          }}
          onVideoModelChange={(value) => {
            setVideoModelChoice(value);
            setPreflightApproved(false);
          }}
          onAspectRatioChange={(value) => {
            setAspectRatioChoice(value);
            setPreflightApproved(false);
          }}
          inputRef={chatInputRef}
          onFocusComposer={() => chatInputRef.current?.focus()}
        />

        <ScenePreviewWorkbench
          scenes={previewScenes}
          activeScene={activePreviewScene}
          activeSceneId={activePreviewSceneId}
          refs={readyRefs}
          loading={conversationalPreflightLoading}
          inserted={sceneDraftsInserted}
          approved={preflightApproved}
          renderSourceReady={renderSourceReady}
          renderBlockers={renderBlockers}
          spendPreview={spendPreview}
          onActiveSceneChange={setActivePreviewSceneId}
          onInsertOnly={handleInsertPreviewOnly}
          onInsertAndUnlock={handleInsertAndUnlockRender}
          onAddScene={handleAddSceneRequest}
          onPolishAll={handlePolishAllScenes}
          onCopyPrompt={handleCopyPreviewPrompt}
          onAddReference={() => fileInputRef.current?.click()}
        />

        <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_390px]">
          <SimplePlanReviewPanel
            preflight={conversationalPreflight}
            loading={conversationalPreflightLoading}
            approved={preflightApproved}
            planVersion={planVersion}
            revisionNotes={revisionNotes}
            renderSourceReady={renderSourceReady}
            onApprove={handleApprovePreflight}
          />

          <aside className="space-y-4">
            <RenderBlockerPanel blockers={renderBlockers} renderSourceReady={renderSourceReady} />
            <button
              onClick={handleAutonomousGenerate}
              disabled={generateDisabled}
              className="flex w-full items-center justify-center gap-2 rounded-card bg-cta-gradient px-5 py-4 text-base font-bold text-white shadow-cta-glow transition hover:brightness-110 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-45"
            >
              {isGenerating ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Rendering video
                </>
              ) : conversationalPreflightLoading || productionDecisionLoading ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Planning
                </>
              ) : !preflightApproved ? (
                <>
                  <BadgeCheck size={18} />
                  Approve plan first
                </>
              ) : !referenceRolesConfirmed ? (
                <>
                  <BadgeCheck size={18} />
                  Confirm reference roles
                </>
              ) : !renderSourceReady ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Locking plan
                </>
              ) : (
                <>
                  <Play size={18} fill="currentColor" />
                  Generate Full Video (Autonomous)
                  <ArrowRight size={17} />
                </>
              )}
            </button>
            {autonomousPreview && (
              <div className="rounded-card border border-hairline bg-surface-1 p-4">
                <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase text-text-subtle">
                  <Sparkles size={12} className="text-accent-cyan" />
                  Render started
                </div>
                <div className="grid gap-2">
                  {autonomousPreview.hook_first_3s && <PreviewBlock label="Hook 3s" value={autonomousPreview.hook_first_3s} />}
                  {autonomousPreview.caption_vn && <PreviewBlock label="Caption" value={autonomousPreview.caption_vn} />}
                </div>
              </div>
            )}
          </aside>
        </div>

        <div className="hidden">
          <div className="overflow-hidden rounded-sheet border border-hairline-strong bg-surface-1 shadow-2xl shadow-black/20">
            <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
              <div className="flex items-center gap-2">
                <div className="grid h-8 w-8 place-items-center rounded-full bg-cta-gradient text-white">
                  <Sparkles size={15} />
                </div>
                <div>
                  <div className="text-sm font-bold text-text">Conversational Preflight Agent</div>
                  <div className="text-[10px] text-text-subtle">Ask, plan, approve, render</div>
                </div>
              </div>
              <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${
                conversationalPreflight?.status === 'approved_for_render'
                  ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
                  : conversationalPreflight?.status === 'needs_user_input'
                    ? 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange'
                    : 'border-hairline bg-surface-3 text-text-subtle'
              }`}>
                {(conversationalPreflight?.status || 'waiting').replace(/_/g, ' ')}
              </span>
            </div>

            <div className="grid min-h-[560px] gap-px bg-hairline md:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
              <div className="flex min-h-[560px] flex-col bg-surface-1">
                <div className="flex-1 space-y-3 overflow-y-auto p-4">
                  {chatMessages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div className={`max-w-[88%] rounded-2xl border px-3 py-2 text-sm leading-relaxed ${
                        message.role === 'user'
                          ? 'border-accent-magenta/30 bg-accent-magenta/15 text-text'
                          : 'border-hairline bg-surface-2 text-text-muted'
                      }`}>
                        {message.text}
                      </div>
                    </div>
                  ))}

                  {showStarterPrompts && (
                    <div className="grid gap-2 pt-1">
                      {STARTER_PROMPTS.map((prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          onClick={() => handleStarterPrompt(prompt)}
                          className="w-full rounded-card border border-hairline bg-surface-2 px-3 py-2 text-left text-xs leading-relaxed text-text-muted transition hover:border-accent-cyan/35 hover:bg-surface-3 hover:text-text"
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  )}

                  {conversationalPreflightLoading && (
                    <div className="inline-flex items-center gap-2 rounded-full border border-hairline bg-surface-2 px-3 py-1.5 text-xs text-text-subtle">
                      <Loader2 size={13} className="animate-spin" />
                      Agent is drafting
                    </div>
                  )}
                  <div ref={chatEndRef} aria-hidden="true" />
                </div>

                <div className="border-t border-hairline p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div>
                      <div className="text-[10px] font-bold uppercase text-accent-cyan">Tell CineJelly what to make</div>
                      <div className="mt-0.5 text-[10px] text-text-subtle">
                        Plain language is enough. Add the product, audience, style, length, or a URL if you have one.
                      </div>
                    </div>
                    <span className="hidden rounded-full border border-hairline bg-surface-3 px-2 py-0.5 text-[9px] font-semibold uppercase text-text-subtle sm:inline-flex">
                      Ctrl+Enter
                    </span>
                  </div>
                  {suggestedReplies.length > 0 && conversationalPreflight?.status === 'needs_user_input' && (
                    <div className="mb-3 rounded-card border border-accent-orange/20 bg-accent-orange/10 p-2">
                      <div className="mb-1.5 text-[10px] font-bold uppercase text-accent-orange">
                        Quick replies
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {suggestedReplies.map((reply) => (
                          <button
                            key={reply}
                            type="button"
                            onClick={() => {
                              setChatInput(reply);
                              window.requestAnimationFrame(() => chatInputRef.current?.focus());
                            }}
                            className="rounded-full border border-accent-orange/25 bg-surface-2 px-2.5 py-1 text-[10px] font-semibold text-text-muted transition hover:border-accent-orange/45 hover:text-text"
                          >
                            {reply}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  <textarea
                    value={chatInput}
                    onChange={(event) => setChatInput(event.target.value.slice(0, CHAT_INPUT_MAX_CHARS))}
                    placeholder={chatRevisionMode
                      ? 'Ask for a stronger hook, different ending, new tone, simpler shots, or more emotional story...'
                      : 'Tell the agent your video idea, product, audience, story twist, voice or market...'}
                    rows={3}
                    className="w-full resize-none rounded-card border border-hairline bg-surface-2 p-3 text-sm leading-relaxed text-text outline-none transition placeholder:text-text-subtle/60 focus:border-accent-cyan/50 focus:ring-2 focus:ring-accent-cyan/10"
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
                        event.preventDefault();
                        handleChatSubmit();
                      }
                    }}
                  />
                  <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {chatRevisionMode && (
                        <span className="rounded-full border border-accent-cyan/25 bg-accent-cyan/10 px-2.5 py-1 text-[10px] font-semibold text-accent-cyan">
                          Revising blueprint
                        </span>
                      )}
                      <button
                        type="button"
                        onClick={handleExtractProductUrl}
                        disabled={productIntelligenceLoading || !(chatInput || brief).match(/https?:\/\//i)}
                        className="inline-flex items-center gap-1 rounded-full border border-accent-cyan/25 bg-accent-cyan/10 px-2.5 py-1 text-[10px] font-semibold text-accent-cyan transition hover:bg-accent-cyan/15 disabled:cursor-not-allowed disabled:opacity-45"
                        title="Fetch public URL metadata without LLM or video render."
                      >
                        {productIntelligenceLoading ? <Loader2 size={11} className="animate-spin" /> : <Globe2 size={11} />}
                        Extract URL
                      </button>
                      <button
                        type="button"
                        onClick={handleDeepAnalyze}
                        disabled={deepPreflightLoading || (!preflightBrief && !chatInput.trim()) || refs.some((ref) => ref.uploading)}
                        className="inline-flex items-center gap-1 rounded-full border border-accent-magenta/30 bg-accent-magenta/10 px-2.5 py-1 text-[10px] font-semibold text-accent-magenta transition hover:bg-accent-magenta/15 disabled:cursor-not-allowed disabled:opacity-45"
                        title="Opt-in Flash/Qwen analysis after confirmation. This does not start paid video render."
                      >
                        {deepPreflightLoading ? <Loader2 size={11} className="animate-spin" /> : <Sparkles size={11} />}
                        Deep analyze (Flash/Qwen)
                      </button>
                      {DURATION_OPTIONS.map((option) => (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => setDurationHintS(option.value)}
                          className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold transition ${
                            durationHintS === option.value
                              ? 'border-accent-magenta/60 bg-accent-magenta/15 text-text'
                              : 'border-hairline bg-surface-3 text-text-subtle hover:text-text'
                          }`}
                        >
                          {option.label}
                        </button>
                      ))}
                      {QUALITY_OPTIONS.map((option) => (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => {
                            setQualityPreset(option.value);
                            setPreflightApproved(false);
                          }}
                          title={option.hint}
                          className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold transition ${
                            qualityPreset === option.value
                              ? 'border-accent-cyan/60 bg-accent-cyan/15 text-accent-cyan'
                              : 'border-hairline bg-surface-3 text-text-subtle hover:text-text'
                          }`}
                        >
                          {option.label} {option.resolution}
                        </button>
                      ))}
                    </div>
                    <button
                      type="button"
                      onClick={handleChatSubmit}
                      disabled={!chatInput.trim()}
                      className="inline-flex items-center gap-2 rounded-full bg-cta-gradient px-4 py-2 text-xs font-bold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-45"
                    >
                      Send <ArrowRight size={13} />
                    </button>
                  </div>
                </div>
              </div>

              <div className="bg-surface-2 p-4">
                <div className="rounded-card border border-hairline bg-surface-1 p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div>
                      <div className="text-[10px] font-bold uppercase text-text-subtle">Agent understanding</div>
                      <div className="mt-0.5 text-[10px] leading-relaxed text-text-subtle">
                        Read-only summary of what the Agent will plan from. To change it, chat normally.
                      </div>
                    </div>
                    <span className="rounded-full border border-hairline bg-surface-3 px-2 py-0.5 font-mono text-[9px] text-text-subtle">
                      {brief.length}/{BRIEF_MAX_CHARS}
                    </span>
                  </div>
                  <div className={`min-h-[118px] rounded-card border border-hairline bg-surface-2 p-3 text-sm leading-relaxed ${
                    brief.trim() ? 'text-text' : 'text-text-subtle'
                  }`}>
                    {brief.trim() || 'Type one command in the chat box, for example: "Lam video TikTok 30s cho san pham trong anh, tu viet hook, script, shot list, viral cho thi truong Viet Nam."'}
                  </div>
                </div>

                {(productIntelligence || deepPreflight) && (
                  <div className="mt-3 grid gap-2">
                    {productIntelligence && (
                      <div className="rounded-card border border-accent-cyan/20 bg-accent-cyan/10 p-3">
                        <div className="mb-1 flex items-center justify-between gap-2">
                          <div className="text-[10px] font-bold uppercase text-accent-cyan">URL intelligence</div>
                          <span className="rounded-full border border-accent-cyan/25 px-2 py-0.5 text-[9px] font-semibold text-accent-cyan">
                            {productIntelligence.status || 'ready'}
                          </span>
                        </div>
                        <div className="text-xs leading-relaxed text-text-muted">
                          {productIntelligence.title || productIntelligence.source_url || 'Product context added.'}
                        </div>
                        {productIntelligence.primary_image_url && (
                          <div className="mt-1 text-[10px] text-text-subtle">
                            Product image imported as unconfirmed reference.
                          </div>
                        )}
                      </div>
                    )}
                    {deepPreflight && (
                      <div className="rounded-card border border-accent-magenta/20 bg-accent-magenta/10 p-3">
                        <div className="mb-1 flex items-center justify-between gap-2">
                          <div className="text-[10px] font-bold uppercase text-accent-magenta">Deep intelligence</div>
                          <span className="rounded-full border border-accent-magenta/25 px-2 py-0.5 text-[9px] font-semibold text-accent-magenta">
                            {deepPreflight.vendor_calls_performed ? 'LLM used' : 'no vendor'}
                          </span>
                        </div>
                        <div className="text-xs leading-relaxed text-text-muted">
                          {deepPreflight.deep_brief?.one_sentence_goal || deepPreflight.user_message || 'Deep preflight completed.'}
                        </div>
                        <div className="mt-1 text-[10px] text-text-subtle">
                          Route: {deepPreflight.route_source_of_truth?.primary_visual_model || productionDecision?.decision?.primary_model_route?.primary_visual_model || 'pending'} · Text brain: {compactModelName(deepPreflight.cost_guard?.text_model)}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <div className="rounded-card border border-hairline bg-surface-1 p-3">
                    <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-text-muted">
                      <Globe2 size={13} className="text-accent-cyan" />
                      Market
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {TARGET_MARKET_OPTIONS.map((option) => (
                        <button
                          key={option.value}
                          type="button"
                          onClick={() => setTargetMarket(option.value)}
                          className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold transition ${
                            targetMarket === option.value
                              ? 'border-accent-cyan/60 bg-accent-cyan/15 text-accent-cyan'
                              : 'border-hairline bg-surface-3 text-text-subtle hover:text-text'
                          }`}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-card border border-hairline bg-surface-1 p-3">
                    <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-text-muted">
                      <Pin size={13} className="text-accent-magenta" />
                      Series memory
                    </div>
                    <input
                      value={seriesKey}
                      onChange={(event) => setSeriesKey(normalizeSeriesKey(event.target.value))}
                      placeholder="campaign or brand"
                      className="w-full rounded-full border border-hairline bg-surface-3 px-3 py-1.5 text-xs text-text outline-none placeholder:text-text-faint focus:border-accent-magenta/45"
                    />
                  </div>
                </div>

                <div className="mt-3 rounded-card border border-hairline bg-surface-1 p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 text-xs font-semibold text-text-muted">
                      <ImagePlus size={13} className="text-accent-cyan" />
                      References
                    </div>
                    <div className="flex gap-1.5">
                      <MediaCount icon="image" label="Images" value={refCounts.image} max={AUTONOMOUS_MAX_IMAGES} />
                      <MediaCount icon="video" label="Video" value={refCounts.video} max={AUTONOMOUS_MAX_VIDEOS} />
                      <MediaCount icon="audio" label="Audio" value={refCounts.audio} max={AUTONOMOUS_MAX_AUDIO} />
                    </div>
                  </div>
                  <div className="mb-2 text-[10px] leading-relaxed text-text-subtle">
                    Add only what you have. CineJelly will ask if a reference role could affect paid output quality.
                  </div>
                  <input
                    type="file"
                    accept="image/*,video/*,audio/*"
                    multiple
                    className="hidden"
                    onChange={(event) => {
                      if (event.target.files) void uploadReferences(event.target.files);
                      event.currentTarget.value = '';
                    }}
                  />
                  {refs.length > 0 ? (
                    <div className="grid grid-cols-6 gap-2">
                      {refs.slice(0, 12).map((ref) => (
                        <div key={ref.id} className="group relative aspect-square overflow-hidden rounded-md border border-hairline bg-surface-3">
                          {ref.uploading ? (
                            <div className="absolute inset-0 grid place-items-center">
                              <Loader2 size={15} className="animate-spin text-text-subtle" />
                            </div>
                          ) : ref.kind === 'image' ? (
                            <img src={getReferencePreviewUrl(ref)} alt={ref.name} className="absolute inset-0 h-full w-full object-cover" />
                          ) : (
                            <div className="absolute inset-0 grid place-items-center">
                              {ref.kind === 'video' ? <Film size={17} className="text-accent-magenta" /> : <FileAudio size={17} className="text-accent-cyan" />}
                            </div>
                          )}
                          <button
                            type="button"
                            onClick={() => removeReference(ref.id)}
                            className="absolute right-1 top-1 grid h-5 w-5 place-items-center rounded-full bg-black/70 text-white opacity-0 transition group-hover:opacity-100"
                            aria-label="Remove reference"
                          >
                            <X size={11} />
                          </button>
                          <div className="absolute bottom-1 left-1 rounded-full bg-black/70 px-1.5 py-0.5 font-mono text-[9px] text-white">
                            {getReferenceTag(ref, refs)}
                          </div>
                          {!ref.uploading && (
                            <div className={`absolute left-1 top-1 rounded-full px-1.5 py-0.5 text-[8px] font-bold uppercase ${
                              ref.roleConfirmed ? 'bg-accent-cyan/90 text-black' : 'bg-accent-orange/90 text-black'
                            }`}>
                              {ref.roleConfirmed ? 'locked' : 'review'}
                            </div>
                          )}
                        </div>
                      ))}
                      {refs.length < AUTONOMOUS_MAX_TOTAL_REFS && (
                        <button
                          type="button"
                          onClick={() => fileInputRef.current?.click()}
                          className="group relative aspect-square overflow-hidden rounded-md border border-dashed border-hairline bg-surface-2 text-text-subtle transition hover:border-accent-cyan/45 hover:bg-surface-3 hover:text-text"
                          aria-label="Add more references"
                        >
                          <div className="absolute inset-0 grid place-items-center">
                            <div className="grid gap-1 text-center">
                              <ImagePlus size={17} className="mx-auto text-accent-cyan" />
                              <span className="text-[9px] font-bold uppercase">Add more</span>
                            </div>
                          </div>
                        </button>
                      )}
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="grid w-full place-items-center rounded-card border border-dashed border-hairline bg-surface-2 px-4 py-6 text-xs text-text-subtle transition hover:border-accent-cyan/35 hover:text-text"
                    >
                      Drop in product, character, location, motion or voice references
                    </button>
                  )}
                  {readyRefs.length > 0 && (
                    <div className="mt-3 rounded-card border border-hairline bg-surface-2 p-2">
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <div>
                          <div className="text-[10px] font-bold uppercase text-text-muted">Reference manifest</div>
                          <div className="mt-0.5 text-[10px] leading-relaxed text-text-subtle">
                            Confirm roles before approval so Seedance uses each @reference for one exact job.
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={confirmAllReferenceRoles}
                          disabled={readyRefs.length === 0 || referenceRolesConfirmed}
                          className="rounded-full border border-accent-cyan/30 bg-accent-cyan/10 px-2.5 py-1 text-[10px] font-bold text-accent-cyan transition hover:bg-accent-cyan/15 disabled:cursor-not-allowed disabled:opacity-45"
                        >
                          {referenceRolesConfirmed ? 'Confirmed' : 'Confirm roles'}
                        </button>
                      </div>
                      <div className="grid gap-2">
                        {readyRefs.map((ref) => (
                          <div key={`manifest:${ref.id}`} className="rounded-md border border-hairline bg-surface-1 p-2">
                            <div className="mb-1.5 flex items-center justify-between gap-2">
                              <div className="min-w-0">
                                <div className="font-mono text-[10px] font-bold text-accent-cyan">{getReferenceTag(ref, readyRefs)}</div>
                                <div className="truncate text-[10px] text-text-subtle">{ref.name}</div>
                                <div className="mt-0.5 truncate text-[9px] text-text-faint">
                                  {roleBindingLabel(ref.role)}
                                  {typeof ref.roleConfidence === 'number' ? ` · confidence ${Math.round(ref.roleConfidence * 100)}%` : ''}
                                </div>
                              </div>
                              <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase ${
                                ref.roleConfirmed ? 'bg-accent-cyan/10 text-accent-cyan' : 'bg-accent-orange/10 text-accent-orange'
                              }`}>
                                {ref.roleConfirmed ? 'locked' : 'needs confirm'}
                              </span>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                              {roleOptionsForKind(ref.kind).map((option) => (
                                <button
                                  key={`${ref.id}:${option.role}`}
                                  type="button"
                                  title={option.hint}
                                  onClick={() => updateReferenceRole(ref.id, option.role)}
                                  className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold transition ${
                                    ref.role === option.role
                                      ? 'border-accent-magenta/50 bg-accent-magenta/15 text-text'
                                      : 'border-hairline bg-surface-2 text-text-subtle hover:text-text'
                                  }`}
                                >
                                  {option.label}
                                </button>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {readyImageRefs.length > 0 && (
                  <ReferenceMemoryPromoter
                    refs={readyImageRefs}
                    approvingKey={approvingMemoryKey}
                    onApprove={approveReferenceAsMemory}
                  />
                )}
              </div>
            </div>
          </div>

          <aside className="space-y-4">
            <SimplePlanReviewPanel
              preflight={conversationalPreflight}
              loading={conversationalPreflightLoading}
              approved={preflightApproved}
              planVersion={planVersion}
              revisionNotes={revisionNotes}
              renderSourceReady={renderSourceReady}
              onApprove={handleApprovePreflight}
            />

            <RenderBlockerPanel blockers={renderBlockers} renderSourceReady={renderSourceReady} />

            <button
              onClick={handleAutonomousGenerate}
              disabled={generateDisabled}
              className="flex w-full items-center justify-center gap-2 rounded-card bg-cta-gradient px-5 py-4 text-base font-bold text-white shadow-cta-glow transition hover:brightness-110 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-45"
            >
              {isGenerating ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Rendering video
                </>
              ) : conversationalPreflightLoading || productionDecisionLoading ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Planning
                </>
              ) : !preflightApproved ? (
                <>
                  <BadgeCheck size={18} />
                  Approve plan first
                </>
              ) : !referenceRolesConfirmed ? (
                <>
                  <BadgeCheck size={18} />
                  Confirm reference roles
                </>
              ) : !renderSourceReady ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Locking plan
                </>
              ) : (
                <>
                  <Play size={18} fill="currentColor" />
                  Generate Full Video (Autonomous)
                  <ArrowRight size={17} />
                </>
              )}
            </button>

            {autonomousPreview && (
              <div className="rounded-card border border-hairline bg-surface-1 p-4">
                <div className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase text-text-subtle">
                  <Sparkles size={12} className="text-accent-cyan" />
                  Render started
                </div>
                <div className="grid gap-2">
                  {autonomousPreview.hook_first_3s && <PreviewBlock label="Hook 3s" value={autonomousPreview.hook_first_3s} />}
                  {autonomousPreview.caption_vn && <PreviewBlock label="Caption" value={autonomousPreview.caption_vn} />}
                </div>
              </div>
            )}
          </aside>
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

function PreviewBlock({
  label,
  value,
  className = '',
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className={`rounded-card border border-hairline bg-surface-3/70 p-3 ${className}`}>
      <div className="text-[10px] font-semibold uppercase text-text-subtle">
        {label}
      </div>
      <div className="mt-1 text-sm leading-relaxed text-text">{value}</div>
    </div>
  );
}

function UnifiedCommandTable({
  brief,
  chatInput,
  chatRevisionMode,
  refs,
  readyRefs,
  refCounts,
  targetMarket,
  durationHintS,
  qualityPreset,
  selectedResolution,
  videoModelChoice,
  aspectRatioChoice,
  loading,
  suggestedReplies,
  showStarterPrompts,
  productIntelligenceLoading,
  deepPreflightLoading,
  referenceRolesConfirmed,
  inputRef,
  onChatInputChange,
  onSubmit,
  onStarterPrompt,
  onExtractProductUrl,
  onDeepAnalyze,
  onAddReference,
  onFilesSelected,
  fileInputRef,
  onRemoveReference,
  onConfirmReferenceRoles,
  onReferenceRoleChange,
  onTargetMarketChange,
  onDurationChange,
  onQualityChange,
  onVideoModelChange,
  onAspectRatioChange,
  onFocusComposer,
}: {
  brief: string;
  chatInput: string;
  chatRevisionMode: boolean;
  refs: ReferenceAsset[];
  readyRefs: ReferenceAsset[];
  refCounts: Record<ReferenceKind, number>;
  targetMarket: string;
  durationHintS: number;
  qualityPreset: QualityPreset;
  selectedResolution: string;
  videoModelChoice: VideoModelChoice;
  aspectRatioChoice: AspectRatioChoice;
  loading: boolean;
  suggestedReplies: string[];
  showStarterPrompts: boolean;
  productIntelligenceLoading: boolean;
  deepPreflightLoading: boolean;
  referenceRolesConfirmed: boolean;
  inputRef: RefObject<HTMLTextAreaElement>;
  onChatInputChange: (value: string) => void;
  onSubmit: () => void;
  onStarterPrompt: (value: string) => void;
  onExtractProductUrl: () => void;
  onDeepAnalyze: () => void;
  onAddReference: () => void;
  onFilesSelected: (files: FileList | File[]) => void;
  fileInputRef: RefObject<HTMLInputElement>;
  onRemoveReference: (id: string) => void;
  onConfirmReferenceRoles: () => void;
  onReferenceRoleChange: (id: string, role: ReferenceRole) => void;
  onTargetMarketChange: (value: string) => void;
  onDurationChange: (value: number) => void;
  onQualityChange: (value: QualityPreset) => void;
  onVideoModelChange: (value: VideoModelChoice) => void;
  onAspectRatioChange: (value: AspectRatioChoice) => void;
  onFocusComposer: () => void;
}) {
  const uploading = refs.some((ref) => ref.uploading);
  const selectedModel = VIDEO_MODEL_OPTIONS.find((option) => option.value === videoModelChoice) ?? VIDEO_MODEL_OPTIONS[0];
  const selectedAspect = ASPECT_OPTIONS.find((option) => option.value === aspectRatioChoice) ?? ASPECT_OPTIONS[1];

  return (
    <div className="mb-5 overflow-hidden rounded-sheet border border-hairline-strong bg-surface-1 shadow-2xl shadow-black/20">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,video/*,audio/*"
        multiple
        className="hidden"
        onChange={(event) => {
          if (event.target.files) void onFilesSelected(event.target.files);
          event.currentTarget.value = '';
        }}
      />
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline p-4">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-accent-cyan/25 bg-accent-cyan/10 px-3 py-1 text-[10px] font-bold uppercase text-accent-cyan">
            <Sparkles size={12} />
            One command table
          </div>
          <div className="mt-2 text-xl font-extrabold text-text">Describe once, set video options, review before render</div>
          <div className="mt-1 max-w-3xl text-xs leading-relaxed text-text-muted">
            Upload references if you have them, choose duration/model quality/aspect, then write one request. The Agent uses this table as the source of truth.
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-semibold">
          <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-text-subtle">
            {selectedModel.label}
          </span>
          <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-text-subtle">
            {selectedAspect.label}
          </span>
          <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-text-subtle">
            {selectedResolution}
          </span>
          <span className="rounded-full border border-accent-orange/25 bg-accent-orange/10 px-2.5 py-1 text-accent-orange">
            No render until approval
          </span>
        </div>
      </div>

      <div className="grid gap-px bg-hairline lg:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
        <div className="bg-surface-1 p-4">
          {brief.trim() && (
            <div className="mb-3 rounded-card border border-accent-cyan/20 bg-accent-cyan/10 p-3">
              <div className="mb-1 text-[10px] font-bold uppercase text-accent-cyan">
                Current mission
              </div>
              <div className="line-clamp-3 text-xs leading-relaxed text-text-muted">
                {brief.trim()}
              </div>
            </div>
          )}

          {suggestedReplies.length > 0 && (
            <div className="mb-3 rounded-card border border-accent-orange/20 bg-accent-orange/10 p-2">
              <div className="mb-1.5 text-[10px] font-bold uppercase text-accent-orange">
                Agent needs one answer
              </div>
              <div className="flex flex-wrap gap-1.5">
                {suggestedReplies.map((reply) => (
                  <button
                    key={reply}
                    type="button"
                    onClick={() => {
                      onChatInputChange(reply);
                      window.requestAnimationFrame(onFocusComposer);
                    }}
                    className="rounded-full border border-accent-orange/25 bg-surface-2 px-2.5 py-1 text-[10px] font-semibold text-text-muted transition hover:border-accent-orange/45 hover:text-text"
                  >
                    {reply}
                  </button>
                ))}
              </div>
            </div>
          )}

          <textarea
            ref={inputRef}
            value={chatInput}
            onChange={(event) => onChatInputChange(event.target.value.slice(0, CHAT_INPUT_MAX_CHARS))}
            placeholder={chatRevisionMode
              ? 'Use this same box to revise: make the hook stronger, add one scene, change tone, make it more premium...'
              : 'Example: Make a 30s TikTok video for the product in my image, VN market, premium UGC style, write hook/script/storyboard and make it viral...'}
            rows={5}
            className="w-full resize-none rounded-card border border-hairline bg-surface-2 p-4 text-base leading-relaxed text-text outline-none transition placeholder:text-text-subtle/65 focus:border-accent-cyan/50 focus:ring-2 focus:ring-accent-cyan/10"
            onKeyDown={(event) => {
              if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
                event.preventDefault();
                onSubmit();
              }
            }}
          />

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <button
                type="button"
                onClick={onAddReference}
                className="inline-flex items-center gap-1 rounded-full border border-hairline bg-surface-3 px-3 py-1.5 text-[10px] font-bold text-text-muted transition hover:border-accent-cyan/35 hover:text-text"
              >
                <Upload size={12} />
                Add references
              </button>
              <button
                type="button"
                onClick={onExtractProductUrl}
                disabled={productIntelligenceLoading || !(chatInput || brief).match(/https?:\/\//i)}
                className="inline-flex items-center gap-1 rounded-full border border-accent-cyan/25 bg-accent-cyan/10 px-3 py-1.5 text-[10px] font-bold text-accent-cyan transition hover:bg-accent-cyan/15 disabled:cursor-not-allowed disabled:opacity-45"
              >
                {productIntelligenceLoading ? <Loader2 size={12} className="animate-spin" /> : <Globe2 size={12} />}
                Read URL
              </button>
              <button
                type="button"
                onClick={onDeepAnalyze}
                disabled={deepPreflightLoading || (!brief.trim() && !chatInput.trim()) || uploading}
                className="inline-flex items-center gap-1 rounded-full border border-accent-magenta/30 bg-accent-magenta/10 px-3 py-1.5 text-[10px] font-bold text-accent-magenta transition hover:bg-accent-magenta/15 disabled:cursor-not-allowed disabled:opacity-45"
              >
                {deepPreflightLoading ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                Deep analyze
              </button>
            </div>
            <button
              type="button"
              onClick={onSubmit}
              disabled={!chatInput.trim()}
              className="inline-flex items-center gap-2 rounded-full bg-cta-gradient px-5 py-2.5 text-sm font-bold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-45"
            >
              {loading ? <Loader2 size={15} className="animate-spin" /> : <ArrowRight size={15} />}
              {chatRevisionMode ? 'Send revision' : 'Send to Agent'}
            </button>
          </div>

          {showStarterPrompts && (
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {STARTER_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => onStarterPrompt(prompt)}
                  className="rounded-card border border-hairline bg-surface-2 px-3 py-2 text-left text-xs leading-relaxed text-text-muted transition hover:border-accent-cyan/35 hover:bg-surface-3 hover:text-text"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="bg-surface-2 p-4">
          <div className="rounded-card border border-hairline bg-surface-1 p-3">
            <div className="mb-2 flex items-center gap-2 text-xs font-bold text-text">
              <ListChecks size={14} className="text-accent-cyan" />
              Video settings
            </div>
            <div className="grid gap-3">
              <div>
                <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">Duration</div>
                <div className="flex flex-wrap gap-1.5">
                  {DURATION_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => onDurationChange(option.value)}
                      title={option.hint}
                      className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold transition ${
                        durationHintS === option.value
                          ? 'border-accent-magenta/60 bg-accent-magenta/15 text-text'
                          : 'border-hairline bg-surface-3 text-text-subtle hover:text-text'
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">Quality</div>
                <div className="flex flex-wrap gap-1.5">
                  {QUALITY_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => onQualityChange(option.value)}
                      title={option.hint}
                      className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold transition ${
                        qualityPreset === option.value
                          ? 'border-accent-cyan/60 bg-accent-cyan/15 text-accent-cyan'
                          : 'border-hairline bg-surface-3 text-text-subtle hover:text-text'
                      }`}
                    >
                      {option.label} {option.resolution}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">Market</div>
                <div className="flex flex-wrap gap-1.5">
                  {TARGET_MARKET_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => onTargetMarketChange(option.value)}
                      title={option.hint}
                      className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold transition ${
                        targetMarket === option.value
                          ? 'border-accent-cyan/60 bg-accent-cyan/15 text-accent-cyan'
                          : 'border-hairline bg-surface-3 text-text-subtle hover:text-text'
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">Model / frame</div>
                <div className="grid gap-2">
                  <div className="flex flex-wrap gap-1.5">
                    {VIDEO_MODEL_OPTIONS.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => onVideoModelChange(option.value)}
                        title={option.hint}
                        className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold transition ${
                          videoModelChoice === option.value
                            ? 'border-accent-magenta/60 bg-accent-magenta/15 text-text'
                            : 'border-hairline bg-surface-3 text-text-subtle hover:text-text'
                        }`}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {ASPECT_OPTIONS.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => onAspectRatioChange(option.value)}
                        title={option.hint}
                        className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold transition ${
                          aspectRatioChoice === option.value
                            ? 'border-accent-cyan/60 bg-accent-cyan/15 text-accent-cyan'
                            : 'border-hairline bg-surface-3 text-text-subtle hover:text-text'
                        }`}
                      >
                        {option.label}
                      </button>
                    ))}
                    <span className="rounded-full border border-hairline bg-surface-3 px-2.5 py-1 text-[10px] font-semibold text-text-subtle">
                      {selectedResolution}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-3 rounded-card border border-hairline bg-surface-1 p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-xs font-bold text-text">
                <ImagePlus size={14} className="text-accent-cyan" />
                References
              </div>
              <div className="flex gap-1.5">
                <MediaCount icon="image" label="Images" value={refCounts.image} max={AUTONOMOUS_MAX_IMAGES} />
                <MediaCount icon="video" label="Video" value={refCounts.video} max={AUTONOMOUS_MAX_VIDEOS} />
                <MediaCount icon="audio" label="Audio" value={refCounts.audio} max={AUTONOMOUS_MAX_AUDIO} />
              </div>
            </div>
            {refs.length === 0 ? (
              <button
                type="button"
                onClick={onAddReference}
                className="grid w-full place-items-center rounded-card border border-dashed border-hairline bg-surface-2 px-4 py-6 text-xs text-text-subtle transition hover:border-accent-cyan/35 hover:text-text"
              >
                Upload product, character, style, motion or voice references
              </button>
            ) : (
              <div className="grid grid-cols-4 gap-2">
                {refs.slice(0, 8).map((ref) => (
                  <div key={`command-ref:${ref.id}`} className="group relative aspect-square overflow-hidden rounded-md border border-hairline bg-surface-3">
                    {ref.uploading ? (
                      <div className="absolute inset-0 grid place-items-center">
                        <Loader2 size={15} className="animate-spin text-text-subtle" />
                      </div>
                    ) : ref.kind === 'image' ? (
                      <img src={getReferencePreviewUrl(ref)} alt={ref.name} className="absolute inset-0 h-full w-full object-cover" />
                    ) : (
                      <div className="absolute inset-0 grid place-items-center">
                        {ref.kind === 'video' ? <Film size={17} className="text-accent-magenta" /> : <FileAudio size={17} className="text-accent-cyan" />}
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => onRemoveReference(ref.id)}
                      className="absolute right-1 top-1 grid h-5 w-5 place-items-center rounded-full bg-black/70 text-white opacity-0 transition group-hover:opacity-100"
                      aria-label="Remove reference"
                    >
                      <X size={11} />
                    </button>
                    <div className="absolute bottom-1 left-1 rounded-full bg-black/70 px-1.5 py-0.5 font-mono text-[9px] text-white">
                      {getReferenceTag(ref, refs)}
                    </div>
                    {!ref.uploading && (
                      <div className={`absolute left-1 top-1 rounded-full px-1.5 py-0.5 text-[8px] font-bold uppercase ${
                        ref.roleConfirmed ? 'bg-accent-cyan/90 text-black' : 'bg-accent-orange/90 text-black'
                      }`}>
                        {ref.roleConfirmed ? 'locked' : 'review'}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {readyRefs.length > 0 && (
              <details className="mt-3 rounded-card border border-hairline bg-surface-2 p-2">
                <summary className="cursor-pointer list-none text-[10px] font-bold uppercase text-text-subtle">
                  Reference roles {referenceRolesConfirmed ? '(confirmed)' : '(review needed)'}
                </summary>
                <div className="mt-2 grid gap-2">
                  <button
                    type="button"
                    onClick={onConfirmReferenceRoles}
                    disabled={readyRefs.length === 0 || referenceRolesConfirmed}
                    className="rounded-full border border-accent-cyan/30 bg-accent-cyan/10 px-2.5 py-1 text-[10px] font-bold text-accent-cyan transition hover:bg-accent-cyan/15 disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    {referenceRolesConfirmed ? 'Roles confirmed' : 'Confirm all roles'}
                  </button>
                  {readyRefs.map((ref) => (
                    <div key={`command-manifest:${ref.id}`} className="rounded-md border border-hairline bg-surface-1 p-2">
                      <div className="mb-1.5 flex items-center justify-between gap-2">
                        <div className="min-w-0">
                          <div className="font-mono text-[10px] font-bold text-accent-cyan">{getReferenceTag(ref, readyRefs)}</div>
                          <div className="truncate text-[10px] text-text-subtle">{ref.name}</div>
                        </div>
                        <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase ${
                          ref.roleConfirmed ? 'bg-accent-cyan/10 text-accent-cyan' : 'bg-accent-orange/10 text-accent-orange'
                        }`}>
                          {ref.roleConfirmed ? 'locked' : 'needs confirm'}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {roleOptionsForKind(ref.kind).map((option) => (
                          <button
                            key={`${ref.id}:command:${option.role}`}
                            type="button"
                            title={option.hint}
                            onClick={() => onReferenceRoleChange(ref.id, option.role)}
                            className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold transition ${
                              ref.role === option.role
                                ? 'border-accent-magenta/50 bg-accent-magenta/15 text-text'
                                : 'border-hairline bg-surface-2 text-text-subtle hover:text-text'
                            }`}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        </div>
      </div>
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

function CreatorIntakeGuide({
  hasBrief,
  refCount,
  referenceRolesConfirmed,
  hasPlan,
  needsInput,
  approved,
  renderSourceReady,
  productIntelligence,
  deepPreflight,
}: {
  hasBrief: boolean;
  refCount: number;
  referenceRolesConfirmed: boolean;
  hasPlan: boolean;
  needsInput: boolean;
  approved: boolean;
  renderSourceReady: boolean;
  productIntelligence: ProductIntelligence | null;
  deepPreflight: DeepPreflightBrain | null;
}) {
  const nextAction = needsInput
    ? 'Answer the Agent question before approval.'
    : !hasBrief
      ? 'Describe the video in plain language.'
      : refCount > 0 && !referenceRolesConfirmed
        ? 'Confirm what each reference should do.'
        : !hasPlan
          ? 'Send the command so the Agent drafts the plan.'
          : !approved
            ? 'Review and approve the script and storyboard.'
            : renderSourceReady
              ? 'Render is unlocked.'
              : 'Locking the approved render source.';

  const cards = [
    {
      title: '1. Say the goal',
      body: hasBrief
        ? 'Mission captured. You can still ask for revisions in normal language.'
        : 'Type like: “Make a 30s TikTok ad for this serum, VN market, premium UGC.”',
      status: hasBrief ? 'done' : 'next',
      icon: Sparkles,
    },
    {
      title: '2. Add proof',
      body: refCount
        ? `${refCount} reference${refCount > 1 ? 's' : ''} added${referenceRolesConfirmed ? ' and locked' : '; roles need review'}.`
        : 'Optional: upload product, character, location, motion, voice, or paste a product URL.',
      status: refCount === 0 ? 'optional' : referenceRolesConfirmed ? 'done' : 'next',
      icon: ImagePlus,
    },
    {
      title: '3. Let Agent think',
      body: deepPreflight?.vendor_calls_performed
        ? 'Deep analysis used Flash/Qwen. No video render was started.'
        : productIntelligence
          ? 'URL context added. Deep analysis is optional before approval.'
          : 'Use Send for free planning, or Deep analyze for opt-in Flash/Qwen reasoning.',
      status: deepPreflight ? 'done' : 'optional',
      icon: Globe2,
    },
    {
      title: '4. Approve then render',
      body: renderSourceReady
        ? 'The paid render button is unlocked from a locked plan.'
        : approved
          ? 'Approval is set; waiting for server lock.'
          : 'Paid generation stays disabled until you approve the script and storyboard.',
      status: renderSourceReady ? 'done' : approved ? 'next' : 'locked',
      icon: BadgeCheck,
    },
  ] as const;

  return (
    <div className="mb-5 overflow-hidden rounded-sheet border border-hairline bg-surface-1/85 shadow-card-soft">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline px-4 py-3">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wide text-accent-cyan">Creator intake</div>
          <div className="mt-1 text-sm font-bold text-text">What the Agent needs next</div>
        </div>
        <span className="rounded-full border border-hairline bg-surface-2 px-3 py-1 text-xs font-semibold text-text-muted">
          {nextAction}
        </span>
      </div>
      <div className="grid gap-px bg-hairline sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => {
          const Icon = card.icon;
          const tone = card.status === 'done'
            ? 'text-accent-cyan border-accent-cyan/20 bg-accent-cyan/10'
            : card.status === 'next'
              ? 'text-accent-magenta border-accent-magenta/20 bg-accent-magenta/10'
              : card.status === 'locked'
                ? 'text-accent-orange border-accent-orange/20 bg-accent-orange/10'
                : 'text-text-subtle border-hairline bg-surface-2';
          return (
            <div key={card.title} className="bg-surface-1 p-4">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className={`grid h-8 w-8 place-items-center rounded-full border ${tone}`}>
                  <Icon size={14} />
                </div>
                <span className={`rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase ${tone}`}>
                  {card.status}
                </span>
              </div>
              <div className="text-sm font-bold text-text">{card.title}</div>
              <div className="mt-1 text-xs leading-relaxed text-text-muted">{card.body}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

type WorkflowStepTone = 'done' | 'active' | 'waiting';

interface WorkflowStep {
  label: string;
  detail: string;
  tone: WorkflowStepTone;
}

function WorkflowStepper({ steps }: { steps: WorkflowStep[] }) {
  return (
    <div className="mb-5 grid auto-cols-[148px] grid-flow-col gap-2 overflow-x-auto rounded-sheet border border-hairline bg-surface-1/80 p-2 shadow-lg shadow-black/10 md:grid-flow-row md:grid-cols-5">
      {steps.map((step, index) => (
        <div
          key={step.label}
          className={`min-w-[148px] rounded-card border px-3 py-2 transition md:min-w-0 ${
            step.tone === 'done'
              ? 'border-accent-cyan/25 bg-accent-cyan/10'
              : step.tone === 'active'
                ? 'border-accent-magenta/35 bg-accent-magenta/10'
                : 'border-hairline bg-surface-2/70'
          }`}
        >
          <div className="flex items-center gap-2">
            <span className={`grid h-5 w-5 place-items-center rounded-full text-[10px] font-bold ${
              step.tone === 'done'
                ? 'bg-accent-cyan text-background'
                : step.tone === 'active'
                  ? 'bg-accent-magenta text-white'
                  : 'bg-surface-3 text-text-subtle'
            }`}>
              {index + 1}
            </span>
            <span className="text-xs font-bold text-text">{step.label}</span>
          </div>
          <div className="mt-1 hidden text-[10px] leading-relaxed text-text-subtle sm:line-clamp-2 sm:block">{step.detail}</div>
        </div>
      ))}
    </div>
  );
}

function buildWorkflowSteps({
  hasBrief,
  hasPlan,
  hasPreview,
  previewInserted,
  needsInput,
  hasRevision,
  approved,
  rendering,
  renderStarted,
}: {
  hasBrief: boolean;
  hasPlan: boolean;
  hasPreview: boolean;
  previewInserted: boolean;
  needsInput: boolean;
  hasRevision: boolean;
  approved: boolean;
  rendering: boolean;
  renderStarted: boolean;
}): WorkflowStep[] {
  return [
    {
      label: 'Idea',
      detail: hasBrief ? 'Brief captured from chat' : 'Start with one strong idea',
      tone: hasBrief ? 'done' : 'active',
    },
    {
      label: 'Plan',
      detail: needsInput ? 'Agent needs one answer' : hasPlan ? 'Script and storyboard ready' : 'Agent drafts the plan',
      tone: needsInput || (hasBrief && !hasPlan) ? 'active' : hasPlan ? 'done' : 'waiting',
    },
    {
      label: 'Preview',
      detail: previewInserted ? 'Timeline inserted for review' : hasPreview ? 'Preview scenes are ready' : 'No paid render yet',
      tone: previewInserted ? 'done' : hasPreview ? 'active' : 'waiting',
    },
    {
      label: 'Approve',
      detail: approved ? 'Render unlocked' : hasRevision ? 'Revision notes applied' : 'User approval required',
      tone: approved ? 'done' : hasPlan && !needsInput ? 'active' : 'waiting',
    },
    {
      label: 'Render',
      detail: rendering ? 'Rendering in progress' : renderStarted ? 'Job started' : 'One click after approval',
      tone: rendering || renderStarted ? 'active' : approved ? 'active' : 'waiting',
    },
  ];
}

function SimplePlanReviewPanel({
  preflight,
  loading,
  approved,
  planVersion,
  revisionNotes,
  renderSourceReady,
  onApprove,
}: {
  preflight: ConversationalPreflight | null;
  loading: boolean;
  approved: boolean;
  planVersion: number;
  revisionNotes: string;
  renderSourceReady: boolean;
  onApprove: () => void;
}) {
  const needsInput = preflight?.status === 'needs_user_input';
  const questions = preflight?.blocking_questions ?? [];
  const checklist = preflight?.approval_checklist ?? [];
  const hasBlockedChecks = checklist.some((item) => item.status === 'blocked');
  const plan = preflight?.creative_plan;
  const script = preflight?.script_outline ?? [];
  const storyboard = preflight?.storyboard ?? [];
  const distribution = preflight?.distribution_preview;
  const summary = preflight?.summary;
  const promptContract = preflight?.prompt_execution_contract_v3
    ?? preflight?.production_decision?.prompt_execution_contract_v3;
  const promptModelPlan = promptContract?.model_plan;
  const outputQaRetry = preflight?.output_qa_retry_brain
    ?? preflight?.production_decision?.output_qa_retry_brain;
  const renderSourceLength = preflight?.approved_plan?.source_length ?? preflight?.approved_brief?.length ?? 0;
  const statusText = renderSourceReady
    ? 'Ready to render'
    : approved
      ? 'Locking source'
      : needsInput
        ? 'Needs answer'
        : preflight
          ? 'Review draft'
          : loading
            ? 'Drafting'
            : 'Waiting';

  return (
    <div className="overflow-hidden rounded-sheet border border-hairline-strong bg-surface-1 shadow-xl shadow-black/15">
      <div className="border-b border-hairline p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm font-bold text-text">
            <BadgeCheck size={15} className={renderSourceReady ? 'text-accent-cyan' : 'text-text-subtle'} />
            Draft review v{planVersion}
          </div>
          <span className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase ${
            renderSourceReady
              ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
              : needsInput
                ? 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange'
                : 'border-hairline bg-surface-3 text-text-subtle'
          }`}>
            {statusText}
          </span>
        </div>
        <p className="text-xs leading-relaxed text-text-muted">
          {loading
            ? 'Agent is building the script, storyboard and render-safe scene prompts.'
            : preflight?.assistant_message || 'Send an idea. The Agent will draft a reviewable plan before paid render.'}
        </p>
      </div>

      {questions.length > 0 && (
        <div className="border-b border-hairline bg-accent-orange/10 p-4">
          <div className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase text-accent-orange">
            <AlertTriangle size={12} />
            Answer before render
          </div>
          {questions.slice(0, 2).map((item) => (
            <div key={item.id || item.question} className="mb-2 rounded-md border border-accent-orange/25 bg-surface-2 p-2 last:mb-0">
              <div className="text-xs font-semibold text-text">{item.question}</div>
              {item.why && <div className="mt-1 text-[10px] leading-relaxed text-text-subtle">{item.why}</div>}
            </div>
          ))}
        </div>
      )}

      <div className="border-b border-hairline p-4">
        <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">What will be made</div>
        <div className="text-sm font-extrabold text-text">{plan?.title || plan?.creative_angle || 'No draft yet'}</div>
        <div className="mt-2 text-xs leading-relaxed text-text-muted">
          {plan?.logline || plan?.viewer_promise || 'The draft appears here after the Agent analyzes the request.'}
        </div>
        {distribution?.hook_first_3s && (
          <div className="mt-3 rounded-card border border-accent-cyan/20 bg-accent-cyan/10 p-3 text-xs leading-relaxed text-text-muted">
            <span className="font-bold text-accent-cyan">Hook: </span>{distribution.hook_first_3s}
          </div>
        )}
      </div>

      {(script.length > 0 || storyboard.length > 0) && (
        <div className="border-b border-hairline p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-[10px] font-bold uppercase text-text-subtle">Preview script and storyboard</div>
            <span className="rounded-full border border-hairline bg-surface-2 px-2 py-0.5 text-[9px] text-text-subtle">
              {script.length} beats / {storyboard.length} frames
            </span>
          </div>
          <div className="grid gap-2">
            {script.slice(0, 3).map((beat, index) => (
              <div key={`${beat.beat}:${index}`} className="rounded-md border border-hairline bg-surface-2 p-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-xs font-semibold text-text">{beat.beat || `Beat ${index + 1}`}</span>
                  {typeof beat.duration_s === 'number' && <span className="font-mono text-[9px] text-text-subtle">{beat.duration_s}s</span>}
                </div>
                <div className="mt-1 line-clamp-2 text-[10px] leading-relaxed text-text-subtle">
                  {beat.script}
                </div>
              </div>
            ))}
            {storyboard.slice(0, 2).map((frame, index) => (
              <div key={frame.id || index} className="rounded-md border border-hairline bg-surface-2 p-2">
                <div className="text-xs font-semibold text-text">{frame.frame || `Frame ${index + 1}`}</div>
                <div className="mt-1 line-clamp-2 text-[10px] leading-relaxed text-text-subtle">{frame.visual}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {preflight && !needsInput && (
        <div className="border-b border-hairline p-4">
          <div className="mb-2 text-[10px] font-bold uppercase text-text-subtle">Revise before render</div>
          {revisionNotes.trim() && (
            <div className="mb-2 rounded-md border border-accent-magenta/20 bg-accent-magenta/10 p-2 text-[10px] leading-relaxed text-text-muted">
              {revisionNotes.trim()}
            </div>
          )}
          <div className="rounded-card border border-hairline bg-surface-2 p-3 text-xs leading-relaxed text-text-muted">
            Use the main command table above to ask for changes, for example: make the hook stronger, add one scene, simplify the shots, or change the tone. The approval lock resets automatically after any revision.
          </div>
        </div>
      )}

      <details className="border-b border-hairline bg-surface-2/60">
        <summary className="cursor-pointer list-none px-4 py-3 text-[10px] font-bold uppercase text-text-subtle">
          Advanced checks: model route, prompt readiness, QA
        </summary>
        <div className="grid gap-2 px-4 pb-4 text-[10px] leading-relaxed text-text-subtle">
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-md border border-hairline bg-surface-1 p-2">
              <div className="font-semibold uppercase text-text-subtle">Niche</div>
              <div className="mt-1 truncate text-xs font-bold text-text">{(summary?.niche || 'auto').replace(/_/g, ' ')}</div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-1 p-2">
              <div className="font-semibold uppercase text-text-subtle">Video engine</div>
              <div className="mt-1 truncate text-xs font-bold text-text">
                {compactModelName(promptModelPlan?.primary_visual_model || summary?.prompt_primary_visual_model)}
              </div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-1 p-2">
              <div className="font-semibold uppercase text-text-subtle">Compiled shots</div>
              <div className="mt-1 text-xs font-bold text-text">
                {promptContract?.readiness?.compiled_shot_count ?? summary?.compiled_shot_count ?? 0}
              </div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-1 p-2">
              <div className="font-semibold uppercase text-text-subtle">QA score</div>
              <div className="mt-1 text-xs font-bold text-text">
                {outputQaRetry?.readiness?.qa_confidence_score ?? summary?.qa_confidence_score ?? 0}%
              </div>
            </div>
          </div>
          {checklist.length > 0 && (
            <div className="rounded-md border border-hairline bg-surface-1 p-2">
              <div className="mb-1 font-semibold uppercase text-text-subtle">Pre-render checks</div>
              {checklist.slice(0, 5).map((item) => (
                <div key={item.key || item.label} className="flex items-start gap-2 py-1">
                  <CheckCircle2 size={12} className={item.status === 'blocked' ? 'mt-0.5 text-accent-orange' : 'mt-0.5 text-accent-cyan'} />
                  <div>
                    <div className="font-semibold text-text">{item.label || 'Check'} - {item.status || 'ready'}</div>
                    {item.detail && <div className="text-text-subtle">{item.detail}</div>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </details>

      <div className="p-4">
        {approved && (
          <div className={`mb-3 rounded-md border p-2 text-[10px] leading-relaxed text-text-muted ${
            renderSourceReady
              ? 'border-accent-cyan/20 bg-accent-cyan/10'
              : 'border-accent-yellow/25 bg-accent-yellow/10'
          }`}>
            {renderSourceReady
              ? `Render source locked from approved script and storyboard (${renderSourceLength}/2000 chars).`
              : 'Waiting for the server to lock the approved render source.'}
          </div>
        )}
        <button
          type="button"
          onClick={onApprove}
          disabled={!preflight || loading || needsInput || hasBlockedChecks}
          className="flex w-full items-center justify-center gap-2 rounded-card border border-accent-cyan/30 bg-accent-cyan/10 px-4 py-3 text-sm font-bold text-accent-cyan transition hover:bg-accent-cyan/15 disabled:cursor-not-allowed disabled:opacity-45"
        >
          <BadgeCheck size={15} />
          {hasBlockedChecks ? 'Resolve blocked checks first' : approved ? 'Plan approved' : 'Approve script and storyboard'}
        </button>
      </div>
    </div>
  );
}

function ConversationalPlanPanel({
  preflight,
  loading,
  approved,
  planVersion,
  revisionInput,
  revisionNotes,
  renderSourceReady,
  onApprove,
  onRevisionInputChange,
  onRequestRevision,
}: {
  preflight: ConversationalPreflight | null;
  loading: boolean;
  approved: boolean;
  planVersion: number;
  revisionInput: string;
  revisionNotes: string;
  renderSourceReady: boolean;
  onApprove: () => void;
  onRevisionInputChange: (value: string) => void;
  onRequestRevision: () => void;
}) {
  const questions = preflight?.blocking_questions ?? [];
  const script = preflight?.script_outline ?? [];
  const storyboard = preflight?.storyboard ?? [];
  const suggestions = preflight?.input_suggestions ?? [];
  const checklist = preflight?.approval_checklist ?? [];
  const summary = preflight?.summary;
  const plan = preflight?.creative_plan;
  const distribution = preflight?.distribution_preview;
  const planningTrace = preflight?.planning_trace;
  const brainRoute = summary?.llm_brain_route
    ?? preflight?.production_decision?.decision?.llm_brain_route
    ?? preflight?.production_decision?.llm_brain_policy?.route_summary;
  const briefContract = preflight?.creative_brief_contract
    ?? preflight?.production_decision?.creative_brief_contract;
  const briefParsed = briefContract?.parsed;
  const briefReadiness = briefContract?.readiness;
  const briefCompletenessScore = briefReadiness?.completeness_score ?? 0;
  const briefDurationS = briefParsed?.duration?.requested_s;
  const missingBriefFields = briefContract?.missing_fields ?? [];
  const producerV2 = preflight?.creative_producer_v2
    ?? preflight?.production_decision?.creative_producer_v2;
  const producerAngle = producerV2?.selected_angle;
  const producerShotGraph = producerV2?.shot_graph;
  const promptContract = preflight?.prompt_execution_contract_v3
    ?? preflight?.production_decision?.prompt_execution_contract_v3;
  const promptContractReadiness = promptContract?.readiness;
  const promptModelPlan = promptContract?.model_plan;
  const promptModeCounts = promptModelPlan?.render_mode_counts ?? {};
  const promptModeSummary = Object.entries(promptModeCounts)
    .slice(0, 3)
    .map(([mode, count]) => `${mode.replace(/_/g, ' ')} ${count}`)
    .join(', ');
  const viralBrain = preflight?.viral_creative_brain
    ?? preflight?.production_decision?.viral_creative_brain;
  const viralReadiness = viralBrain?.readiness;
  const viralPattern = viralBrain?.selected_viral_pattern;
  const viralHook = viralBrain?.hook_variants?.[0];
  const viralPackage = viralBrain?.platform_package;
  const outputQaRetry = preflight?.output_qa_retry_brain
    ?? preflight?.production_decision?.output_qa_retry_brain;
  const outputQaReadiness = outputQaRetry?.readiness;
  const outputQaWarnings = outputQaRetry?.warnings ?? [];
  const needsInput = preflight?.status === 'needs_user_input';
  const approvedPlan = preflight?.approved_plan;
  const renderSourceLength = approvedPlan?.source_length ?? preflight?.approved_brief?.length ?? 0;
  const hasBlockedChecks = checklist.some((item) => item.status === 'blocked');
  const hasDistributionPreview = Boolean(
    distribution?.caption_draft
    || distribution?.hook_first_3s
    || distribution?.title_hint
    || distribution?.cover_frame_cue
    || (distribution?.hashtags?.length ?? 0) > 0,
  );

  return (
    <div className="overflow-hidden rounded-sheet border border-hairline-strong bg-surface-1 shadow-xl shadow-black/15">
      <div className="border-b border-hairline p-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm font-bold text-text">
            <BadgeCheck size={15} className={renderSourceReady ? 'text-accent-cyan' : 'text-text-subtle'} />
            Agent plan v{planVersion}
          </div>
          <span className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase ${
            renderSourceReady
              ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
              : needsInput
                ? 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange'
                : 'border-hairline bg-surface-3 text-text-subtle'
          }`}>
            {renderSourceReady ? 'locked' : approved ? 'locking' : needsInput ? 'needs answer' : 'review'}
          </span>
        </div>
        {planningTrace && (
          <div className="mb-2 flex flex-wrap items-center gap-2 text-[10px]">
            <span className="rounded-full border border-accent-cyan/25 bg-accent-cyan/10 px-2 py-0.5 font-bold uppercase text-accent-cyan">
              {planningTrace.engine_mode?.replace(/_/g, ' ') || 'preflight'}
            </span>
            <span className="rounded-full border border-hairline bg-surface-2 px-2 py-0.5 font-semibold text-text-subtle">
              Live AI: {planningTrace.llm_calls_performed ? 'used' : 'not used'}
            </span>
            <span className="rounded-full border border-hairline bg-surface-2 px-2 py-0.5 font-semibold text-text-subtle">
              Paid render: {planningTrace.paid_video_vendor_calls_allowed ? 'allowed' : 'locked'}
            </span>
          </div>
        )}
        <p className="text-xs leading-relaxed text-text-muted">
          {loading
            ? 'Drafting script and storyboard...'
            : preflight?.assistant_message || 'Start with an idea and the agent will draft the plan.'}
        </p>
        {planningTrace?.why_response_is_fast && (
          <p className="mt-2 text-[10px] leading-relaxed text-text-subtle">
            {planningTrace.why_response_is_fast}
          </p>
        )}
      </div>

      {summary && (
        <div className="grid grid-cols-3 gap-px bg-hairline">
          <div className="bg-surface-2 p-3">
            <div className="text-[9px] font-semibold uppercase text-text-subtle">Niche</div>
            <div className="mt-1 truncate text-xs font-semibold text-text">{(summary.niche || 'auto').replace(/_/g, ' ')}</div>
          </div>
          <div className="bg-surface-2 p-3">
            <div className="text-[9px] font-semibold uppercase text-text-subtle">Runtime</div>
            <div className="mt-1 truncate text-xs font-semibold text-text">{(summary.runtime_class || 'auto').replace(/_/g, ' ')} / {summary.target_duration_s ?? 'auto'}s</div>
          </div>
          <div className="bg-surface-2 p-3">
            <div className="text-[9px] font-semibold uppercase text-text-subtle">Format</div>
            <div className="mt-1 truncate text-xs font-semibold text-text">{(summary.target_platform || 'auto').replace(/_/g, ' ')}</div>
          </div>
        </div>
      )}

      {brainRoute && (
        <div className="border-b border-hairline bg-surface-2/70 p-4">
          <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">AI brain plan</div>
          <div className="mb-2 text-[10px] leading-relaxed text-text-subtle">
            Planned thinking models for the approved render chain. This review panel does not execute those live calls.
          </div>
          <div className="grid grid-cols-2 gap-2 text-[10px] leading-relaxed text-text-subtle sm:grid-cols-4">
            <div className="rounded-md border border-hairline bg-surface-1 p-2">
              <div className="font-semibold uppercase text-text-subtle">Writer</div>
              <div className="mt-1 truncate text-xs font-bold text-text">{compactModelName(brainRoute.primary_text_model)}</div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-1 p-2">
              <div className="font-semibold uppercase text-text-subtle">Image brain</div>
              <div className="mt-1 truncate text-xs font-bold text-text">{compactModelName(brainRoute.vision_model)}</div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-1 p-2">
              <div className="font-semibold uppercase text-text-subtle">Complexity</div>
              <div className="mt-1 truncate text-xs font-bold text-text">
                {brainRoute.complexity_band || 'simple'}{typeof brainRoute.complexity_score === 'number' ? ` / ${brainRoute.complexity_score}` : ''}
              </div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-1 p-2">
              <div className="font-semibold uppercase text-text-subtle">Pro</div>
              <div className={`mt-1 truncate text-xs font-bold ${
                brainRoute.pro_selected
                  ? 'text-accent-cyan'
                  : brainRoute.pro_candidate
                    ? 'text-accent-yellow'
                    : 'text-text'
              }`}>
                {brainRoute.pro_selected ? 'approved' : brainRoute.pro_candidate ? 'gated' : 'off'}
              </div>
            </div>
          </div>
        </div>
      )}

      {briefContract && (
        <div className="border-b border-hairline p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-[10px] font-bold uppercase text-text-subtle">Request understanding</div>
            <span className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase ${
              briefCompletenessScore >= 75
                ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
                : 'border-accent-yellow/25 bg-accent-yellow/10 text-accent-yellow'
            }`}>
              {briefCompletenessScore}% complete
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[10px] leading-relaxed text-text-subtle sm:grid-cols-4">
            <div className="rounded-md border border-hairline bg-surface-2 p-2">
              <div className="font-semibold uppercase text-text-subtle">Intent</div>
              <div className="mt-1 truncate text-xs font-bold text-text">{(briefParsed?.output_intent || 'general_video').replace(/_/g, ' ')}</div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-2 p-2">
              <div className="font-semibold uppercase text-text-subtle">Subject</div>
              <div className="mt-1 truncate text-xs font-bold text-text">{briefParsed?.subject?.summary || briefParsed?.subject?.status || 'missing'}</div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-2 p-2">
              <div className="font-semibold uppercase text-text-subtle">Duration</div>
              <div className="mt-1 truncate text-xs font-bold text-text">{briefDurationS ? `${briefDurationS}s` : 'auto'}</div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-2 p-2">
              <div className="font-semibold uppercase text-text-subtle">Platform</div>
              <div className="mt-1 truncate text-xs font-bold text-text">{(briefParsed?.target_platform || 'auto').replace(/_/g, ' ')}</div>
            </div>
          </div>
          {missingBriefFields.length > 0 && (
            <div className="mt-2 rounded-md border border-accent-yellow/20 bg-accent-yellow/10 p-2 text-[10px] leading-relaxed text-text-muted">
              Missing: {missingBriefFields.slice(0, 3).map((item) => item.key || item.question).join(', ')}
            </div>
          )}
        </div>
      )}

      {producerV2 && (
        <div className="border-b border-hairline p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-[10px] font-bold uppercase text-text-subtle">Producer plan</div>
            <span className="rounded-full border border-accent-cyan/25 bg-accent-cyan/10 px-2 py-0.5 text-[9px] font-semibold uppercase text-accent-cyan">
              {producerShotGraph?.node_count ?? 0} shots
            </span>
          </div>
          <div className="text-sm font-bold text-text">{producerAngle?.label || summary?.producer_angle || 'Selected producer angle'}</div>
          {producerAngle?.story_engine && (
            <div className="mt-1 text-xs leading-relaxed text-text-muted">{producerAngle.story_engine}</div>
          )}
          <div className="mt-2 grid grid-cols-3 gap-2 text-[10px] leading-relaxed text-text-subtle">
            <div className="rounded-md border border-hairline bg-surface-2 p-2">
              <div className="font-semibold uppercase text-text-subtle">Score</div>
              <div className="mt-1 text-xs font-bold text-text">{producerAngle?.score ?? 'auto'}</div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-2 p-2">
              <div className="font-semibold uppercase text-text-subtle">Risk</div>
              <div className="mt-1 text-xs font-bold text-text">{producerAngle?.risk_level || 'review'}</div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-2 p-2">
              <div className="font-semibold uppercase text-text-subtle">Beats</div>
              <div className="mt-1 text-xs font-bold text-text">{producerV2.script_beats?.length ?? summary?.script_beat_count ?? 0}</div>
            </div>
          </div>
        </div>
      )}

      {viralBrain && (
        <div className="border-b border-hairline p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-[10px] font-bold uppercase text-text-subtle">Hook and retention</div>
            <span className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase ${
              (viralReadiness?.creative_score ?? summary?.viral_creative_score ?? 0) >= 80
                ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
                : 'border-accent-yellow/25 bg-accent-yellow/10 text-accent-yellow'
            }`}>
              {viralReadiness?.creative_score ?? summary?.viral_creative_score ?? 0}% creative
            </span>
          </div>
          <div className="text-sm font-bold text-text">
            {viralPattern?.label || summary?.viral_pattern || 'Selected viral pattern'}
          </div>
          {(viralPattern?.hook_formula || viralHook?.first_3s_line) && (
            <div className="mt-1 text-xs leading-relaxed text-text-muted">
              {viralPattern?.hook_formula || viralHook?.first_3s_line}
            </div>
          )}
          <div className="mt-2 grid grid-cols-3 gap-2 text-[10px] leading-relaxed text-text-subtle">
            <div className="rounded-md border border-hairline bg-surface-2 p-2">
              <div className="font-semibold uppercase text-text-subtle">Hooks</div>
              <div className="mt-1 text-xs font-bold text-text">{viralReadiness?.hook_variant_count ?? summary?.viral_hook_count ?? 0}</div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-2 p-2">
              <div className="font-semibold uppercase text-text-subtle">Risk</div>
              <div className="mt-1 text-xs font-bold text-text">{viralPattern?.risk_level || 'review'}</div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-2 p-2">
              <div className="font-semibold uppercase text-text-subtle">Variants</div>
              <div className="mt-1 text-xs font-bold text-text">{viralReadiness?.variant_count ?? 0}</div>
            </div>
          </div>
          {viralHook?.first_3s_line && (
            <div className="mt-2 rounded-md border border-hairline bg-surface-2 p-2 text-[10px] leading-relaxed text-text-muted">
              Hook: {viralHook.first_3s_line}
            </div>
          )}
          {viralPackage?.cta && (
            <div className="mt-2 rounded-md border border-hairline bg-surface-2 p-2 text-[10px] leading-relaxed text-text-muted">
              CTA: {viralPackage.cta}
            </div>
          )}
        </div>
      )}

      {promptContract && (
        <div className="border-b border-hairline bg-surface-2/60 p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-[10px] font-bold uppercase text-text-subtle">Render readiness</div>
            <span className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase ${
              (promptContractReadiness?.warning_count ?? 0) > 0
                ? 'border-accent-yellow/25 bg-accent-yellow/10 text-accent-yellow'
                : 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
            }`}>
              {promptContractReadiness?.compiled_shot_count ?? summary?.compiled_shot_count ?? 0} compiled
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[10px] leading-relaxed text-text-subtle sm:grid-cols-4">
            <div className="rounded-md border border-hairline bg-surface-1 p-2">
              <div className="font-semibold uppercase text-text-subtle">Video engine</div>
              <div className="mt-1 truncate text-xs font-bold text-text">
                {compactModelName(promptModelPlan?.primary_visual_model || summary?.prompt_primary_visual_model)}
              </div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-1 p-2">
              <div className="font-semibold uppercase text-text-subtle">Status</div>
              <div className="mt-1 truncate text-xs font-bold text-text">
                {(promptContractReadiness?.status || summary?.prompt_contract_status || 'review').replace(/_/g, ' ')}
              </div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-1 p-2">
              <div className="font-semibold uppercase text-text-subtle">Warnings</div>
              <div className="mt-1 text-xs font-bold text-text">
                {promptContractReadiness?.warning_count ?? summary?.prompt_contract_warning_count ?? 0}
              </div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-1 p-2">
              <div className="font-semibold uppercase text-text-subtle">Shot types</div>
              <div className="mt-1 truncate text-xs font-bold text-text">{promptModeSummary || 'auto'}</div>
            </div>
          </div>
        </div>
      )}

      {outputQaRetry && (
        <div className="border-b border-hairline p-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="text-[10px] font-bold uppercase text-text-subtle">Quality and retry plan</div>
            <span className={`rounded-full border px-2 py-0.5 text-[9px] font-semibold uppercase ${
              (outputQaReadiness?.qa_confidence_score ?? summary?.qa_confidence_score ?? 0) >= 80
                ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
                : 'border-accent-yellow/25 bg-accent-yellow/10 text-accent-yellow'
            }`}>
              {outputQaReadiness?.qa_confidence_score ?? summary?.qa_confidence_score ?? 0}% QA
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[10px] leading-relaxed text-text-subtle sm:grid-cols-4">
            <div className="rounded-md border border-hairline bg-surface-2 p-2">
              <div className="font-semibold uppercase text-text-subtle">Status</div>
              <div className="mt-1 truncate text-xs font-bold text-text">
                {(outputQaReadiness?.status || summary?.output_qa_status || 'review').replace(/_/g, ' ')}
              </div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-2 p-2">
              <div className="font-semibold uppercase text-text-subtle">QA nodes</div>
              <div className="mt-1 text-xs font-bold text-text">{outputQaReadiness?.qa_node_count ?? summary?.qa_node_count ?? 0}</div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-2 p-2">
              <div className="font-semibold uppercase text-text-subtle">Retry recipes</div>
              <div className="mt-1 text-xs font-bold text-text">{outputQaReadiness?.retry_recipe_count ?? summary?.retry_recipe_count ?? 0}</div>
            </div>
            <div className="rounded-md border border-hairline bg-surface-2 p-2">
              <div className="font-semibold uppercase text-text-subtle">Warnings</div>
              <div className="mt-1 text-xs font-bold text-text">{outputQaReadiness?.warning_count ?? summary?.qa_warning_count ?? 0}</div>
            </div>
          </div>
          {outputQaRetry.acceptance_gate && (
            <div className="mt-2 rounded-md border border-hairline bg-surface-2 p-2 text-[10px] leading-relaxed text-text-muted">
              Gate: shot &gt;= {outputQaRetry.acceptance_gate.minimum_shot_score ?? 78}, sequence &gt;= {outputQaRetry.acceptance_gate.minimum_sequence_score ?? 78}; hard failures block delivery.
            </div>
          )}
          {outputQaWarnings.length > 0 && (
            <div className="mt-2 rounded-md border border-accent-yellow/20 bg-accent-yellow/10 p-2 text-[10px] leading-relaxed text-text-muted">
              QA warning: {outputQaWarnings[0]?.risk?.replace(/_/g, ' ') || 'review QA contract'}
            </div>
          )}
        </div>
      )}

      {questions.length > 0 && (
        <div className="border-b border-hairline bg-accent-orange/10 p-4">
          <div className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase text-accent-orange">
            <AlertTriangle size={12} />
            Needed before render
          </div>
          <div className="space-y-2">
            {questions.map((item) => (
              <div key={item.id || item.question} className="rounded-md border border-accent-orange/25 bg-surface-2 p-2">
                <div className="text-xs font-semibold text-text">{item.question}</div>
                {item.why && <div className="mt-1 text-[10px] leading-relaxed text-text-subtle">{item.why}</div>}
              </div>
            ))}
          </div>
        </div>
      )}

      {plan && (
        <div className="border-b border-hairline p-4">
          <div className="text-[10px] font-bold uppercase text-text-subtle">Creative treatment</div>
          <div className="mt-1 text-sm font-bold text-text">{plan.title || plan.creative_angle || 'Autonomous concept'}</div>
          <div className="mt-2 text-xs leading-relaxed text-text-muted">{plan.logline || plan.viewer_promise}</div>
          {plan.viewer_promise && (
            <div className="mt-2 rounded-md border border-hairline bg-surface-2 p-2 text-[10px] leading-relaxed text-text-subtle">
              {plan.viewer_promise}
            </div>
          )}
        </div>
      )}

      {hasDistributionPreview && (
        <div className="border-b border-hairline p-4">
          <div className="mb-2 text-[10px] font-bold uppercase text-text-subtle">Publishing preview</div>
          <div className="grid gap-2 text-xs leading-relaxed text-text-muted">
            {distribution?.hook_first_3s && (
              <div>
                <span className="font-semibold text-text">Hook: </span>
                {distribution.hook_first_3s}
              </div>
            )}
            {distribution?.caption_draft && (
              <div>
                <span className="font-semibold text-text">Caption: </span>
                {distribution.caption_draft}
              </div>
            )}
            {distribution?.title_hint && (
              <div>
                <span className="font-semibold text-text">Title: </span>
                {distribution.title_hint}
              </div>
            )}
            {distribution?.cover_frame_cue && (
              <div>
                <span className="font-semibold text-text">Cover: </span>
                {distribution.cover_frame_cue}
              </div>
            )}
          </div>
          {distribution?.hashtags && distribution.hashtags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {distribution.hashtags.slice(0, 8).map((tag) => (
                <span key={tag} className="rounded-full border border-hairline bg-surface-2 px-2 py-0.5 text-[10px] text-text-subtle">
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {checklist.length > 0 && (
        <div className="border-b border-hairline p-4">
          <div className="mb-2 text-[10px] font-bold uppercase text-text-subtle">Pre-render checks</div>
          <div className="grid gap-2">
            {checklist.slice(0, 6).map((item) => (
              <div key={item.key || item.label} className="flex gap-2 rounded-md border border-hairline bg-surface-2 p-2">
                <CheckCircle2
                  size={13}
                  className={`mt-0.5 shrink-0 ${
                    item.status === 'blocked'
                      ? 'text-accent-orange'
                      : item.status === 'recommended'
                        ? 'text-accent-yellow'
                        : 'text-accent-cyan'
                  }`}
                />
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-xs font-semibold text-text">{item.label || 'Check'}</span>
                    <span className="rounded-full border border-hairline bg-surface-3 px-1.5 py-0.5 text-[9px] text-text-subtle">
                      {item.status || 'ready'}
                    </span>
                  </div>
                  {item.detail && (
                    <div className="mt-1 line-clamp-2 text-[10px] leading-relaxed text-text-subtle">{item.detail}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {script.length > 0 && (
        <div className="border-b border-hairline p-4">
          <div className="mb-2 text-[10px] font-bold uppercase text-text-subtle">Script beats</div>
          <div className="space-y-2">
            {script.slice(0, 5).map((beat, index) => (
              <div key={`${beat.beat}:${index}`} className="rounded-md border border-hairline bg-surface-2 p-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-xs font-semibold text-text">{beat.beat || `Beat ${index + 1}`}</span>
                  {typeof beat.duration_s === 'number' && <span className="font-mono text-[9px] text-text-subtle">{beat.duration_s}s</span>}
                </div>
                <div className="mt-1 line-clamp-2 text-[10px] leading-relaxed text-text-subtle">{beat.script}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {storyboard.length > 0 && (
        <div className="border-b border-hairline p-4">
          <div className="mb-2 text-[10px] font-bold uppercase text-text-subtle">Storyboard</div>
          <div className="grid gap-2">
            {storyboard.slice(0, 4).map((frame, index) => (
              <div key={frame.id || index} className="rounded-md border border-hairline bg-surface-2 p-2">
                <div className="text-xs font-semibold text-text">{frame.frame || `Frame ${index + 1}`}</div>
                <div className="mt-1 line-clamp-2 text-[10px] leading-relaxed text-text-subtle">{frame.visual}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {suggestions.length > 0 && !approved && (
        <div className="border-b border-hairline p-4">
          <div className="mb-2 text-[10px] font-bold uppercase text-text-subtle">Quality suggestions</div>
          <div className="flex flex-wrap gap-1.5">
            {suggestions.slice(0, 4).map((item) => (
              <span key={`${item.priority}:${item.action}`} className="rounded-full border border-hairline bg-surface-2 px-2 py-0.5 text-[10px] text-text-subtle">
                {item.action}
              </span>
            ))}
          </div>
        </div>
      )}

      {preflight && !needsInput && (
        <div className="border-b border-hairline p-4">
          <div className="mb-2 text-[10px] font-bold uppercase text-text-subtle">Revise before render</div>
          {revisionNotes.trim() && (
            <div className="mb-2 rounded-md border border-accent-magenta/20 bg-accent-magenta/10 p-2 text-[10px] leading-relaxed text-text-muted">
              {revisionNotes.trim()}
            </div>
          )}
          <textarea
            value={revisionInput}
            onChange={(event) => onRevisionInputChange(event.target.value.slice(0, 500))}
            rows={3}
            placeholder="Ask the agent to strengthen the hook, change tone, add a twist, simplify shots, or adjust the ending..."
            className="w-full resize-none rounded-card border border-hairline bg-surface-2 p-3 text-xs leading-relaxed text-text outline-none transition placeholder:text-text-subtle/60 focus:border-accent-magenta/50 focus:ring-2 focus:ring-accent-magenta/10"
          />
          <button
            type="button"
            onClick={onRequestRevision}
            disabled={loading || !revisionInput.trim()}
            className="mt-2 inline-flex w-full items-center justify-center gap-2 rounded-card border border-accent-magenta/30 bg-accent-magenta/10 px-4 py-2.5 text-xs font-bold text-accent-magenta transition hover:bg-accent-magenta/15 disabled:cursor-not-allowed disabled:opacity-45"
          >
            <RotateCcw size={14} />
            Revise plan
          </button>
        </div>
      )}

      <div className="p-4">
        {approved && (
          <div className={`mb-3 rounded-md border p-2 text-[10px] leading-relaxed text-text-muted ${
            renderSourceReady
              ? 'border-accent-cyan/20 bg-accent-cyan/10'
              : 'border-accent-yellow/25 bg-accent-yellow/10'
          }`}>
            {renderSourceReady
              ? `Render source locked from approved treatment, script beats and storyboard (${renderSourceLength}/2000 chars).`
              : 'Waiting for the server to lock the approved render source.'}
          </div>
        )}
        <button
          type="button"
          onClick={onApprove}
          disabled={!preflight || loading || needsInput || hasBlockedChecks}
          className="flex w-full items-center justify-center gap-2 rounded-card border border-accent-cyan/30 bg-accent-cyan/10 px-4 py-3 text-sm font-bold text-accent-cyan transition hover:bg-accent-cyan/15 disabled:cursor-not-allowed disabled:opacity-45"
        >
          <BadgeCheck size={15} />
          {hasBlockedChecks ? 'Resolve blocked checks first' : approved ? 'Plan approved' : 'Approve script and storyboard'}
        </button>
      </div>
    </div>
  );
}

function ScenePreviewWorkbench({
  scenes,
  activeScene,
  activeSceneId,
  refs,
  loading,
  inserted,
  approved,
  renderSourceReady,
  renderBlockers,
  spendPreview,
  onActiveSceneChange,
  onInsertOnly,
  onInsertAndUnlock,
  onAddScene,
  onPolishAll,
  onCopyPrompt,
  onAddReference,
}: {
  scenes: StudioPreviewScene[];
  activeScene: StudioPreviewScene | null;
  activeSceneId: string | null;
  refs: ReferenceAsset[];
  loading: boolean;
  inserted: boolean;
  approved: boolean;
  renderSourceReady: boolean;
  renderBlockers: RenderBlocker[];
  spendPreview: SpendPreview;
  onActiveSceneChange: (id: string | null) => void;
  onInsertOnly: () => void;
  onInsertAndUnlock: () => void;
  onAddScene: () => void;
  onPolishAll: () => void;
  onCopyPrompt: (prompt: string) => void;
  onAddReference: () => void;
}) {
  const taggedRefs = refs.map((ref) => ({ ref, tag: getReferenceTag(ref, refs) }));
  const referenceByTag = new Map(taggedRefs.map((item) => [item.tag, item.ref]));
  const activeImageRef = activeScene?.refs
    .map((tag) => referenceByTag.get(tag))
    .find((ref): ref is ReferenceAsset => Boolean(ref && ref.kind === 'image'));
  const hardBlockers = renderBlockers.filter((blocker) => blocker.severity === 'hard');
  const softBlockers = renderBlockers.filter((blocker) => blocker.severity === 'soft');
  const statusLabel = renderSourceReady
    ? 'Locked for render'
    : approved
      ? 'Approval saved'
      : inserted
        ? 'Inserted for review'
        : scenes.length > 0
          ? 'Draft ready'
          : loading
            ? 'Agent drafting'
            : 'Waiting for idea';

  return (
    <div className="mb-5 overflow-hidden rounded-sheet border border-hairline-strong bg-surface-1 shadow-2xl shadow-black/20">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline p-4">
        <div className="min-w-0">
          <div className="mb-1 inline-flex items-center gap-2 rounded-full border border-accent-cyan/25 bg-accent-cyan/10 px-2.5 py-1 text-[10px] font-bold uppercase text-accent-cyan">
            <Clapperboard size={12} />
            Video draft preview
          </div>
          <div className="text-lg font-extrabold text-text">Review the video before final render</div>
          <div className="mt-1 max-w-3xl text-xs leading-relaxed text-text-muted">
            The Agent shows scenes, reference usage and a timeline first. Nothing is rendered until the final Generate Full Video button is clicked.
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[10px]">
          <span className={`rounded-full border px-2.5 py-1 font-bold uppercase ${
            renderSourceReady
              ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
              : hardBlockers.length > 0
                ? 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange'
                : 'border-hairline bg-surface-2 text-text-subtle'
          }`}>
            {statusLabel}
          </span>
          <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 font-semibold text-text-subtle">
            {spendPreview.totalSeconds || 0}s preview
          </span>
          {scenes.length > 0 && (
            <span className="rounded-full border border-accent-magenta/25 bg-accent-magenta/10 px-2.5 py-1 font-semibold text-accent-magenta">
              No render cost yet
            </span>
          )}
        </div>
      </div>

      <div className="grid gap-px bg-hairline lg:grid-cols-[230px_minmax(0,1fr)_360px]">
        <div className="bg-surface-2 p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div>
              <div className="text-[10px] font-bold uppercase text-text-subtle">Assets</div>
              <div className="mt-0.5 text-xs text-text-muted">{refs.length} ready reference{refs.length === 1 ? '' : 's'}</div>
            </div>
            <button
              type="button"
              onClick={onAddReference}
              className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-hairline bg-surface-3 text-text-subtle transition hover:border-accent-cyan/35 hover:text-text"
              aria-label="Add reference"
            >
              <Plus size={14} />
            </button>
          </div>
          {taggedRefs.length > 0 ? (
            <div className="grid gap-2">
              {taggedRefs.slice(0, 8).map(({ ref, tag }) => (
                <div key={ref.id} className="flex min-w-0 gap-2 rounded-card border border-hairline bg-surface-1 p-2">
                  <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-md border border-hairline bg-surface-3">
                    {ref.kind === 'image' ? (
                      <img src={getReferencePreviewUrl(ref)} alt={ref.name} className="h-full w-full object-cover" />
                    ) : (
                      <div className="grid h-full w-full place-items-center">
                        {ref.kind === 'video' ? <Film size={17} className="text-accent-magenta" /> : <FileAudio size={17} className="text-accent-cyan" />}
                      </div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-[10px] font-bold text-accent-cyan">{tag}</span>
                      <span className={`rounded-full px-1.5 py-0.5 text-[8px] font-bold uppercase ${
                        ref.roleConfirmed ? 'bg-accent-cyan/10 text-accent-cyan' : 'bg-accent-orange/10 text-accent-orange'
                      }`}>
                        {ref.roleConfirmed ? 'locked' : 'review'}
                      </span>
                    </div>
                    <div className="mt-0.5 truncate text-xs font-semibold text-text">{ref.name}</div>
                    <div className="mt-0.5 truncate text-[10px] text-text-subtle">{roleBindingLabel(ref.role)}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <button
              type="button"
              onClick={onAddReference}
              className="grid min-h-[150px] w-full place-items-center rounded-card border border-dashed border-hairline bg-surface-1 p-4 text-center text-xs leading-relaxed text-text-subtle transition hover:border-accent-cyan/35 hover:text-text"
            >
              Upload product, character, location, motion or voice references if you have them.
            </button>
          )}
        </div>

        <div className="bg-background/80 p-4">
          <div className="relative min-h-[340px] overflow-hidden rounded-card border border-hairline bg-[radial-gradient(circle_at_30%_20%,rgba(34,211,238,0.16),transparent_34%),linear-gradient(135deg,rgba(255,255,255,0.05),rgba(255,255,255,0.01))]">
            {activeImageRef && (
              <img
                src={getReferencePreviewUrl(activeImageRef)}
                alt={activeImageRef.name}
                className="absolute inset-0 h-full w-full object-cover opacity-35 blur-[1px]"
              />
            )}
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/35 to-black/20" />
            <div className="relative flex min-h-[340px] flex-col justify-between p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/35 px-3 py-1 text-[10px] font-bold uppercase text-white/80">
                  <Eye size={12} />
                  Storyboard preview
                </div>
                {activeScene && (
                  <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/35 px-3 py-1 font-mono text-[10px] text-white/70">
                    <Clock size={12} />
                    {activeScene.durationS}s
                  </div>
                )}
              </div>

              {activeScene ? (
                <div className="max-w-3xl">
                  <div className="mb-2 text-[10px] font-bold uppercase tracking-wide text-accent-cyan">{activeScene.label}</div>
                  <div className="text-2xl font-extrabold leading-tight text-white md:text-3xl">
                    {activeScene.visual}
                  </div>
                  <div className="mt-3 grid gap-2 text-xs leading-relaxed text-white/75 md:grid-cols-2">
                    <div className="rounded-card border border-white/10 bg-black/35 p-3">
                      <div className="mb-1 font-bold uppercase text-white/50">Camera</div>
                      {activeScene.camera}
                    </div>
                    <div className="rounded-card border border-white/10 bg-black/35 p-3">
                      <div className="mb-1 font-bold uppercase text-white/50">Audio</div>
                      {activeScene.audio}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="grid place-items-center py-16 text-center">
                  <div className="max-w-sm">
                    <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-full border border-white/10 bg-white/5 text-white/70">
                      {loading ? <Loader2 size={18} className="animate-spin" /> : <Clapperboard size={18} />}
                    </div>
                    <div className="text-lg font-bold text-white">Timeline is empty</div>
                    <div className="mt-2 text-sm leading-relaxed text-white/55">
                      Send a plain-language request. The Agent will draft scenes here before any video render.
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="mt-3 overflow-x-auto rounded-card border border-hairline bg-surface-1 p-3">
            {scenes.length > 0 ? (
              <div className="flex min-w-max gap-2">
                {scenes.map((scene, index) => (
                  <button
                    key={scene.id}
                    type="button"
                    onClick={() => onActiveSceneChange(scene.id)}
                    className={`w-48 rounded-card border p-3 text-left transition ${
                      scene.id === activeSceneId
                        ? 'border-accent-cyan/50 bg-accent-cyan/10'
                        : 'border-hairline bg-surface-2 hover:border-accent-cyan/25 hover:bg-surface-3'
                    }`}
                  >
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <span className="font-mono text-[10px] font-bold text-accent-cyan">S{String(index + 1).padStart(2, '0')}</span>
                      <span className="rounded-full border border-hairline bg-surface-3 px-1.5 py-0.5 text-[9px] text-text-subtle">{scene.durationS}s</span>
                    </div>
                    <div className="line-clamp-2 text-xs font-semibold leading-relaxed text-text">{scene.visual}</div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {scene.refs.slice(0, 3).map((tag) => (
                        <span key={`${scene.id}:${tag}`} className="rounded-full border border-accent-magenta/25 bg-accent-magenta/10 px-1.5 py-0.5 font-mono text-[9px] text-accent-magenta">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="flex min-h-[72px] items-center justify-center text-xs text-text-subtle">
                Scene cards appear here after the Agent drafts the plan.
              </div>
            )}
          </div>
        </div>

        <div className="bg-surface-2 p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <div>
              <div className="text-[10px] font-bold uppercase text-text-subtle">Draft actions</div>
              <div className="mt-0.5 text-xs text-text-muted">{scenes.length} scene{scenes.length === 1 ? '' : 's'} prepared</div>
            </div>
            <span className="rounded-full border border-hairline bg-surface-3 px-2 py-1 text-[10px] font-semibold text-text-subtle">
              {inserted ? 'Inserted' : 'Review'}
            </span>
          </div>

          {activeScene ? (
            <div className="space-y-3">
              <details className="rounded-card border border-hairline bg-surface-1 p-3">
                <summary className="cursor-pointer list-none text-[10px] font-bold uppercase text-text-subtle">
                  Advanced scene prompt and model route
                </summary>
                <div className="mt-3 mb-2 flex items-center justify-end">
                  <button
                    type="button"
                    onClick={() => onCopyPrompt(activeScene.prompt)}
                    className="inline-flex items-center gap-1 rounded-full border border-hairline bg-surface-3 px-2 py-0.5 text-[10px] font-semibold text-text-subtle transition hover:text-text"
                  >
                    <Copy size={10} />
                    Copy
                  </button>
                </div>
                <div className="max-h-44 overflow-y-auto rounded-md border border-hairline bg-surface-2 p-3 text-xs leading-relaxed text-text-muted">
                  {activeScene.prompt}
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-[10px]">
                  <div className="rounded-md border border-hairline bg-surface-2 p-2">
                    <div className="font-bold uppercase text-text-subtle">Model route</div>
                    <div className="mt-1 truncate text-xs font-semibold text-text">{compactModelName(activeScene.modelKey)}</div>
                  </div>
                  <div className="rounded-md border border-hairline bg-surface-2 p-2">
                    <div className="font-bold uppercase text-text-subtle">Mode</div>
                    <div className="mt-1 truncate text-xs font-semibold text-text">{activeScene.renderMode.replace(/_/g, ' ')}</div>
                  </div>
                </div>
              </details>

              {activeScene.refs.length > 0 && (
                <div className="rounded-card border border-hairline bg-surface-1 p-3">
                  <div className="mb-2 text-[10px] font-bold uppercase text-text-subtle">Referenced assets</div>
                  <div className="flex flex-wrap gap-1.5">
                    {activeScene.refs.map((tag) => {
                      const ref = referenceByTag.get(tag);
                      return (
                        <span key={`${activeScene.id}:active:${tag}`} className="rounded-full border border-accent-cyan/25 bg-accent-cyan/10 px-2 py-1 text-[10px] font-semibold text-accent-cyan">
                          {tag}{ref?.role ? ` - ${roleOptionsForKind(ref.kind).find((option) => option.role === ref.role)?.label || ref.kind}` : ''}
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-card border border-hairline bg-surface-1 p-4 text-xs leading-relaxed text-text-muted">
              No draft yet. Type the user request in the main command box; the Agent will create script beats, storyboard frames and prompt-ready shots.
            </div>
          )}

          <div className="mt-4 grid gap-2">
            <button
              type="button"
              onClick={onInsertOnly}
              disabled={loading || scenes.length === 0}
              className="inline-flex w-full items-center justify-center gap-2 rounded-card border border-hairline bg-surface-3 px-4 py-2.5 text-xs font-bold text-text transition hover:border-accent-cyan/35 hover:bg-surface-1 disabled:cursor-not-allowed disabled:opacity-45"
            >
              <Layers size={14} />
              Save draft only
            </button>
            <button
              type="button"
              onClick={onInsertAndUnlock}
              disabled={loading || scenes.length === 0}
              className="inline-flex w-full items-center justify-center gap-2 rounded-card border border-accent-cyan/30 bg-accent-cyan/10 px-4 py-2.5 text-xs font-bold text-accent-cyan transition hover:bg-accent-cyan/15 disabled:cursor-not-allowed disabled:opacity-45"
            >
              <BadgeCheck size={14} />
              Approve draft (no render yet)
            </button>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={onAddScene}
                disabled={loading}
                className="inline-flex items-center justify-center gap-2 rounded-card border border-hairline bg-surface-1 px-3 py-2 text-[10px] font-bold text-text-muted transition hover:border-accent-magenta/35 hover:text-text disabled:cursor-not-allowed disabled:opacity-45"
              >
                <Plus size={12} />
                Add scene
              </button>
              <button
                type="button"
                onClick={onPolishAll}
                disabled={loading}
                className="inline-flex items-center justify-center gap-2 rounded-card border border-hairline bg-surface-1 px-3 py-2 text-[10px] font-bold text-text-muted transition hover:border-accent-magenta/35 hover:text-text disabled:cursor-not-allowed disabled:opacity-45"
              >
                <Wand2 size={12} />
                Improve all
              </button>
            </div>
          </div>

          {(hardBlockers.length > 0 || softBlockers.length > 0) && (
            <div className="mt-4 rounded-card border border-hairline bg-surface-1 p-3">
              <div className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase text-text-subtle">
                <ListChecks size={12} />
                Before render
              </div>
              <div className="grid gap-1.5">
                {[...hardBlockers, ...softBlockers].slice(0, 5).map((blocker) => (
                  <div key={blocker.key} className={`rounded-md border p-2 text-[10px] leading-relaxed ${
                    blocker.severity === 'hard'
                      ? 'border-accent-orange/25 bg-accent-orange/10 text-text-muted'
                      : 'border-accent-yellow/25 bg-accent-yellow/10 text-text-muted'
                  }`}>
                    <div className="font-bold text-text">{blocker.label}</div>
                    <div className="mt-0.5 text-text-subtle">{blocker.detail}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function RenderBlockerPanel({
  blockers,
  renderSourceReady,
}: {
  blockers: RenderBlocker[];
  renderSourceReady: boolean;
}) {
  if (blockers.length === 0) {
    return (
      <div className="rounded-card border border-accent-cyan/20 bg-accent-cyan/10 p-3">
        <div className="mb-1 flex items-center gap-2 text-[10px] font-bold uppercase text-accent-cyan">
          <CheckCircle2 size={12} />
          Render gate clear
        </div>
        <div className="text-xs leading-relaxed text-text-muted">
          {renderSourceReady
            ? 'The approved source is locked. Final render starts only when you click Generate Full Video.'
            : 'The plan is ready for approval. Final render remains locked until the source is approved.'}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-card border border-hairline bg-surface-1 p-3">
      <div className="mb-2 flex items-center gap-2 text-[10px] font-bold uppercase text-text-subtle">
        <ListChecks size={12} className="text-accent-orange" />
        Render gate blockers
      </div>
      <div className="grid gap-2">
        {blockers.slice(0, 6).map((blocker) => (
          <div key={blocker.key} className={`rounded-md border p-2 text-[10px] leading-relaxed ${
            blocker.severity === 'hard'
              ? 'border-accent-orange/25 bg-accent-orange/10'
              : 'border-accent-yellow/25 bg-accent-yellow/10'
          }`}>
            <div className="font-bold text-text">{blocker.label}</div>
            <div className="mt-0.5 text-text-subtle">{blocker.detail}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MediaCount({
  icon,
  label,
  value,
  max,
}: {
  icon: ReferenceKind;
  label: string;
  value: number;
  max: number;
}) {
  const Icon = icon === 'image' ? ImagePlus : icon === 'video' ? Film : FileAudio;
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-hairline bg-surface-3 px-2 py-0.5 text-[10px] text-text-subtle">
      <Icon size={10} />
      {label} {value}/{max}
    </span>
  );
}

function ReferenceMemoryPromoter({
  refs,
  approvingKey,
  onApprove,
}: {
  refs: ReferenceAsset[];
  approvingKey: string | null;
  onApprove: (ref: ReferenceAsset, option: MemoryRoleOption) => void;
}) {
  return (
    <div className="mt-4 border-t border-hairline pt-3">
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-text-muted">
        <BadgeCheck size={14} className="text-accent-cyan" />
        Approve references as memory
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {refs.slice(0, 6).map((ref) => (
          <div
            key={ref.id}
            className="flex min-w-0 items-center gap-2 rounded-card border border-hairline bg-surface-3 p-2"
          >
            <img
              src={getReferencePreviewUrl(ref)}
              alt={ref.name}
              className="h-10 w-10 shrink-0 rounded-md object-cover"
            />
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-semibold text-text">{ref.name}</div>
              <div className="mt-1 flex flex-wrap gap-1">
                {MEMORY_ROLE_OPTIONS.map((option) => {
                  const key = `${ref.id}:${option.role}`;
                  const loading = approvingKey === key;
                  return (
                    <button
                      key={option.role}
                      type="button"
                      onClick={() => onApprove(ref, option)}
                      disabled={Boolean(approvingKey)}
                      className="rounded-full border border-hairline bg-surface-2 px-2 py-0.5 text-[9px] font-semibold text-text-subtle transition hover:border-accent-cyan/40 hover:text-text disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {loading ? 'Saving' : option.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        ))}
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
