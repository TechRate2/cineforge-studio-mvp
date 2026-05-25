'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { PromptCardV2 } from '@/components/studio/PromptCardV2';
import { ReferenceZones, type ReferenceZonesValue } from '@/components/studio/ReferenceZones';
import { ContextInjection, type ContextValue } from '@/components/studio/ContextInjection';
import { DirectorPlanModal } from '@/components/studio/DirectorPlanModal';
import { JobResultModal } from '@/components/studio/JobResultModal';
import { ModelShowcase } from '@/components/studio/ModelShowcase';
import { StylePresets } from '@/components/studio/StylePresets';
import { RecentGenerations } from '@/components/studio/RecentGenerations';
import { CostConfirmDialog, COST_CONFIRM_THRESHOLD_USD } from '@/components/studio/CostConfirmDialog';
import { isMasterBoardEligible, MASTER_BOARD_COST_USD } from '@/lib/studio/master-board-config';
import { Drawer } from '@/components/ui/Modal';
import { useDirectorPlan, generateFromPlan, DIRECTOR_STAGE_LABELS_VN } from '@/lib/studio/use-director-plan';
import { usePersistedJob } from '@/lib/studio/use-persisted-job';
import { useEnhanceBrief } from '@/lib/studio/use-enhance-brief';
import { getModelConfig, MODEL_CONFIGS } from '@/lib/studio/model-config';
import { type StylePreset } from '@/lib/studio/style-presets';
import type { VideoModel, AspectRatio, AudioMode } from '@/lib/types/backend';
import { AlertCircle, Loader2, ChevronDown, Sparkles } from 'lucide-react';

/** V5.2 — auto-save key for draft brief + settings */
const DRAFT_STORAGE_KEY = 'cineforge:draft_v1';

interface DraftState {
  brief: string;
  model: VideoModel;
  aspect: AspectRatio;
  resolution: string;
  duration: number;
  audioMode: AudioMode;
  context: ContextValue;
  saved_at: number;
}

export default function StudioPage() {
  // Form state
  const [brief, setBrief] = useState('');
  const [referenceZones, setReferenceZones] = useState<ReferenceZonesValue>({
    images: [], roles: [], storyboardImages: [],
  });
  const [context, setContext] = useState<ContextValue>({});

  // Settings
  const [model, setModel] = useState<VideoModel>('seedance_2_0');
  const [aspect, setAspect] = useState<AspectRatio>('9:16');
  const [resolution, setResolution] = useState<string>(getModelConfig('seedance_2_0').resolution_default);
  const [duration, setDuration] = useState(15);
  const [audioMode, setAudioMode] = useState<AudioMode>('silent_native');
  const [numShots, setNumShots] = useState<number | null>(null);
  // V5.16 #1 — Master Board toggle. Default ON for eligible models, OFF otherwise.
  // User can override via UI pill. DirectorPlanModal reads this instead of hardcode.
  const [masterBoardEnabled, setMasterBoardEnabled] = useState<boolean>(true);
  const [activePresetId, setActivePresetId] = useState<string | undefined>();
  const [showPresets, setShowPresets] = useState(false);

  // V5.2 — hydrate draft on mount (24h TTL)
  const hydratedRef = useRef(false);
  useEffect(() => {
    if (hydratedRef.current || typeof window === 'undefined') return;
    hydratedRef.current = true;
    try {
      const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
      if (!raw) return;
      const d = JSON.parse(raw) as DraftState;
      if (Date.now() - d.saved_at > 24 * 60 * 60 * 1000) {
        localStorage.removeItem(DRAFT_STORAGE_KEY);
        return;
      }
      if (d.brief) setBrief(d.brief);
      if (d.model) setModel(d.model);
      if (d.aspect) setAspect(d.aspect);
      if (d.resolution) setResolution(d.resolution);
      if (d.duration) setDuration(d.duration);
      if (d.audioMode) setAudioMode(d.audioMode);
      if (d.context) setContext(d.context);
      if (d.brief) toast.info('Đã restore draft brief từ session trước', { duration: 3000 });
    } catch {
      localStorage.removeItem(DRAFT_STORAGE_KEY);
    }
  }, []);

  // V5.2 — persist draft on any change (debounced 800ms)
  useEffect(() => {
    if (!hydratedRef.current) return;
    const t = setTimeout(() => {
      try {
        const draft: DraftState = {
          brief, model, aspect, resolution, duration, audioMode, context,
          saved_at: Date.now(),
        };
        localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));
      } catch {}
    }, 800);
    return () => clearTimeout(t);
  }, [brief, model, aspect, resolution, duration, audioMode, context]);

  // Sync resolution + aspect + duration to model on change
  useEffect(() => {
    const cfg = getModelConfig(model);
    if (!cfg.resolution_options.includes(resolution)) {
      setResolution(cfg.resolution_default);
    }
    if (cfg.duration_discrete && !cfg.duration_discrete.includes(duration)) {
      setDuration(cfg.duration_discrete[0]);
    } else if (duration > cfg.max_duration_s) {
      setDuration(cfg.max_duration_s);
    }
    // V5.7 — snap aspect to a valid option for the picked model (Wan 2.7 has [])
    if (cfg.aspect_ratio_options.length > 0 && !cfg.aspect_ratio_options.includes(aspect)) {
      setAspect(cfg.aspect_ratio_options[0]);
    }
    // V6 — clamp numShots to model's max. Seedance 2.0 family supports
    // single-call multi-shot ≤6; Wan 2.7 is i2v only (single shot).
    const maxShotsByModel: Record<string, number> = {
      auto: 6, seedance_2_0: 6, seedance_2_0_fast: 6, wan_2_7: 1,
    };
    const maxShots = maxShotsByModel[model] ?? 6;
    if (numShots !== null && numShots > maxShots) {
      setNumShots(maxShots);
    }
  }, [model, resolution, duration, aspect, numShots]);

  // V5.2 — Style preset one-click apply
  const handlePickPreset = useCallback((preset: StylePreset) => {
    setBrief(preset.brief_template);
    setModel(preset.settings.model);
    setAspect(preset.settings.aspect_ratio);
    setResolution(getModelConfig(preset.settings.model).resolution_default);
    setDuration(preset.settings.duration_s);
    setAudioMode(preset.settings.audio_mode);
    setActivePresetId(preset.id);
    toast.success(`Đã áp preset ${preset.label_vn} — edit brief tiếp hoặc Generate ngay`);
  }, []);

  // V5.17 — Smart Enhance cache: stores vision_notes + suggested fields so
  // Director Agent can reuse vision_notes via context_injection (skip its own
  // vision pass = save ~$0.0004 per /plan call). Cleared when brief or refs
  // change so stale notes don't leak into a different plan.
  const [smartEnhance, setSmartEnhance] = useState<{
    vision_notes?: Record<string, unknown> | null;
    suggested_niche?: string | null;
    suggested_mood?: string | null;
    suggested_hook_pattern?: string | null;
  } | null>(null);

  // V5.2 — Magic prompt enhance / V5.17 — Smart Enhance auto-apply settings
  const { enhance, isEnhancing } = useEnhanceBrief();
  const handleEnhance = useCallback(async () => {
    if (!brief.trim() || brief.trim().length < 4) return;
    try {
      const res = await enhance({
        brief,
        duration_s: duration,
        // V5.12 — pass refs so vision LLM can ground brief in actual images
        reference_image_urls: [
          ...referenceZones.images,
          ...referenceZones.storyboardImages,
        ].filter((u) => u && u.startsWith('http')),
      });
      setBrief(res.enhanced_brief);

      // V5.17 — auto-apply Smart Enhance suggestions (user can override after).
      // Each setter is independent so partial suggestions still take effect.
      const applied: string[] = [];
      if (res.suggested_model && res.suggested_model !== model) {
        // Cast — server already whitelisted to VideoModel-compatible strings
        setModel(res.suggested_model as VideoModel);
        applied.push(`model=${res.suggested_model}`);
      }
      if (res.suggested_num_shots && res.suggested_num_shots !== numShots) {
        setNumShots(res.suggested_num_shots);
        applied.push(`shots=${res.suggested_num_shots}`);
      }
      if (res.suggested_audio_mode && res.suggested_audio_mode !== audioMode) {
        setAudioMode(res.suggested_audio_mode as AudioMode);
        applied.push(`audio=${res.suggested_audio_mode}`);
      }

      // V5.17 — cache vision_notes + suggestions for Director Agent reuse
      setSmartEnhance({
        vision_notes: res.vision_notes ?? null,
        suggested_niche: res.suggested_niche ?? null,
        suggested_mood: res.suggested_mood ?? null,
        suggested_hook_pattern: res.suggested_hook_pattern ?? null,
      });

      const modeLabel = res.mode === 'vision'
        ? `vision (đọc ${res.refs_seen} ảnh)`
        : 'text-only';
      const settingsLabel = applied.length > 0 ? ` · auto-set: ${applied.join(', ')}` : '';
      toast.success(`Brief enhanced · ${modeLabel}${settingsLabel}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Enhance failed: ${msg}`);
    }
  }, [brief, duration, enhance, referenceZones.images, referenceZones.storyboardImages,
      model, numShots, audioMode]);

  // V5.17 — clear smart enhance cache when brief OR refs change (stale notes)
  useEffect(() => {
    if (smartEnhance !== null) setSmartEnhance(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [brief, referenceZones.images.join('|')]);

  // Director plan flow
  const { createPlan, plan, setPlan, progress, isLoading, error, storytellingIssues, reset } = useDirectorPlan();
  const [showPlanModal, setShowPlanModal] = useState(false);

  useEffect(() => {
    if (plan) {
      setShowPlanModal(true);
      toast.success(`Plan ready — ${plan.shot_list.length} shots, điểm ${plan.evaluation.overall_score.toFixed(1)}/10`);
    }
  }, [plan]);

  useEffect(() => {
    if (error) toast.error(`Plan failed: ${error}`, { duration: 8000 });
  }, [error]);

  // Render job flow — V5.1 persist jobId across refresh + V5.3 startedAt for stable ETA
  const { jobId, startedAt: jobStartedAt, setJobId } = usePersistedJob();
  const [isRendering, setIsRendering] = useState(false);
  const [showJobModal, setShowJobModal] = useState(false);
  const [showCostConfirm, setShowCostConfirm] = useState(false);

  useEffect(() => {
    if (jobId && !showJobModal) {
      setShowJobModal(true);
      toast.info('Đang resume job đã render từ session trước', { duration: 4000 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [masterBoardUrl, setMasterBoardUrl] = useState<string | null>(null);
  const [showRefDrawer, setShowRefDrawer] = useState(false);

  const handleGeneratePlan = async () => {
    if (!brief.trim()) return;
    setShowPlanModal(false);
    // V5.17 — inject Smart Enhance cache into context_injection so Director
    // Agent can reuse vision_notes (skip its vision pass) + bias plan toward
    // suggested hook_pattern / niche / mood. Server-side schema is permissive
    // (ContextInjection is dict-shaped) so extra fields pass through.
    const ctxWithEnhance = smartEnhance ? {
      ...context,
      vision_notes: smartEnhance.vision_notes ?? undefined,
      suggested_niche: smartEnhance.suggested_niche ?? undefined,
      suggested_mood: smartEnhance.suggested_mood ?? undefined,
      suggested_hook_pattern: smartEnhance.suggested_hook_pattern ?? undefined,
    } : context;
    await createPlan({
      product_input: { text_description: brief.slice(0, 200) },
      reference_images: referenceZones.images,
      reference_role_hints: referenceZones.roles,
      reference_videos: [],
      user_brief: brief,
      context_injection: ctxWithEnhance,
      settings: {
        audio_mode: audioMode,
        model,
        duration_s: duration,
        aspect_ratio: aspect,
        resolution,
        num_shots: numShots,
      },
      niche_hint: 'auto',
    });
  };

  // V5.2 — Approve gated by cost confirm dialog when ≥ threshold.
  // V5.15.2 M2 — include Master Board $0.04 so threshold comparison reflects
  // the actual wallet deduction (prevents skip-dialog on $1.47+$0.04=$1.51).
  const handleApproveClick = () => {
    if (!plan) return;
    const masterBoardCost = masterBoardUrl ? MASTER_BOARD_COST_USD : 0;
    const grandTotal = plan.cost_estimate.total_cost_usd + masterBoardCost;
    if (grandTotal >= COST_CONFIRM_THRESHOLD_USD) {
      setShowCostConfirm(true);
    } else {
      void handleApproveAndRender();
    }
  };

  const handleApproveAndRender = async () => {
    if (!plan) return;
    setShowCostConfirm(false);
    setIsRendering(true);
    try {
      const res = await generateFromPlan({
        plan,
        reference_images: referenceZones.images,
        settings: {
          audio_mode: audioMode, model, duration_s: duration,
          aspect_ratio: aspect, resolution, num_shots: numShots,
        },
        use_llm_scene_gen: true,
        master_board_url: masterBoardUrl,
      });
      setJobId(res.job_id);
      setShowPlanModal(false);
      setShowJobModal(true);
      toast.success(`Job đã queue — ước tính $${res.estimated_cost_usd?.toFixed(2) ?? '?'}, ${res.estimated_duration_s}s render`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Render failed: ${msg}`, { duration: 8000 });
      console.error(e);
    } finally {
      setIsRendering(false);
    }
  };

  const cfg = useMemo(() => getModelConfig(model), [model]);
  // V5.16.2 — Pre-plan cost estimate shown in PromptCardV2 chip + cost gate.
  // Includes:
  //   $0.04 Director Plan LLM call (analyzer + generator + evaluation)
  //   $videoCost = per-sec rate × duration (vendor render)
  //   $audioCost = 0.01 (TTS) or 0.10 (ASMR SFX) or 0 (silent)
  //   $0.04 Master Board (only when toggle ON AND model in eligible set)
  // Note: actual /generate may differ slightly after BE auto-pick + snap.
  const estimatedCostUsd = useMemo(() => {
    const videoCost = cfg.cost_per_second_usd * duration;
    const audioCost = audioMode === 'dialogue_vo' ? 0.01 : audioMode === 'asmr_macro' ? 0.10 : 0;
    const masterBoardCost = (
      masterBoardEnabled && isMasterBoardEligible(model) ? MASTER_BOARD_COST_USD : 0
    );
    return 0.04 + videoCost + audioCost + masterBoardCost;
  }, [cfg.cost_per_second_usd, duration, audioMode, masterBoardEnabled, model]);

  return (
    <div className="min-h-full">
      <section className="px-5 md:px-10 pt-12 md:pt-16 pb-8 max-w-container mx-auto text-center">
        <h1 className="text-4xl md:text-5xl lg:text-[56px] font-extrabold tracking-tight leading-tight">
          Create Any Video, Just Tell Your <span className="text-gradient">Agent</span>
        </h1>
        <p className="text-sm text-text-muted mt-3 max-w-2xl mx-auto">
          Mô tả ý tưởng → AI dựng kế hoạch shot-by-shot → render thật. Niche-agnostic, identity-locked, audio sync.
        </p>
      </section>

      {/* Main compact input card */}
      <section className="px-5 md:px-10 pb-6 max-w-3xl mx-auto">
        <PromptCardV2
          brief={brief}
          onBrief={(v) => { setBrief(v); setActivePresetId(undefined); }}
          referenceCount={referenceZones.images.length}
          onOpenReferences={() => setShowRefDrawer(true)}
          model={model}
          onModel={setModel}
          aspect={aspect}
          onAspect={setAspect}
          resolution={resolution}
          onResolution={setResolution}
          duration={duration}
          onDuration={setDuration}
          audioMode={audioMode}
          onAudioMode={setAudioMode}
          numShots={numShots}
          onNumShots={setNumShots}
          masterBoardEnabled={masterBoardEnabled}
          onMasterBoardEnabled={setMasterBoardEnabled}
          qualityScore={plan?.evaluation?.overall_score}
          estimatedCostUsd={estimatedCostUsd}
          onSubmit={handleGeneratePlan}
          isLoading={isLoading}
          onEnhance={handleEnhance}
          isEnhancing={isEnhancing}
        />

        {progress && isLoading && (
          <div className="surface-2 rounded-card p-4 mt-4 flex items-center gap-3">
            <Loader2 size={16} className="text-accent-magenta animate-spin shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-text">
                {DIRECTOR_STAGE_LABELS_VN[progress.stage] || progress.stage}
              </div>
              {progress.message && (
                <div className="text-xs text-text-subtle mt-0.5">{progress.message}</div>
              )}
            </div>
            <span className="chip">{progress.status}</span>
          </div>
        )}
        {error && (
          <div className="surface-2 rounded-card p-4 mt-4 flex items-start gap-3 border-accent-orange/40">
            <AlertCircle size={16} className="text-accent-orange shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="text-sm font-semibold text-accent-orange">Plan failed</div>
              <div className="text-xs text-text-muted mt-1 font-mono">{error}</div>
              <button onClick={reset} className="btn-ghost mt-2">Reset</button>
            </div>
          </div>
        )}

        {/* V5.4 — Optional preset suggestions. Default collapsed — Director Agent
            tự hiểu từ brief, không bắt buộc preset (Topview/Higgsfield UX). */}
        <div className="mt-4">
          <button
            onClick={() => setShowPresets((s) => !s)}
            className="inline-flex items-center gap-1.5 text-[11px] text-text-subtle hover:text-text-muted transition"
          >
            <Sparkles size={11} />
            {showPresets ? 'Ẩn template' : 'Bí ý tưởng? Xem 6 template gợi ý'}
            <ChevronDown size={11} className={`transition ${showPresets ? 'rotate-180' : ''}`} />
          </button>
          {showPresets && (
            <div className="mt-3 animate-fade-in">
              <StylePresets onPick={(p) => { handlePickPreset(p); setShowPresets(false); }} activeId={activePresetId} />
            </div>
          )}
        </div>
      </section>

      {/* V5.2 — Recent generations carousel */}
      <section className="px-5 md:px-10 pb-8 max-w-container mx-auto">
        <RecentGenerations />
      </section>

      <section className="px-5 md:px-10 pb-8 max-w-container mx-auto">
        <h3 className="text-[11px] uppercase tracking-wider text-text-subtle mb-3 px-1">Pick a tier</h3>
        <ModelShowcase onPick={setModel} />
      </section>

      <section className="px-5 md:px-10 pb-12 max-w-3xl mx-auto">
        <ContextInjection value={context} onChange={setContext} />
      </section>

      <Drawer
        open={showRefDrawer}
        onClose={() => setShowRefDrawer(false)}
        title="References · Character / Product / Storyboard"
        width="w-[min(95vw,720px)]"
      >
        <div className="p-5">
          <p className="text-xs text-text-muted mb-4">
            Upload 1-{cfg.max_references} ảnh. Phân vùng theo role — Director Agent dùng để khoá identity character + product + style xuyên shot.
            {cfg.reference_hint_vn && (
              <span className="block mt-2 text-accent-yellow/80">{cfg.reference_hint_vn}</span>
            )}
          </p>
          <ReferenceZones
            value={referenceZones}
            onChange={setReferenceZones}
            maxRefs={cfg.max_references}
          />
          <div className="mt-5 flex justify-end">
            <button onClick={() => setShowRefDrawer(false)} className="btn-cta">
              Done · {referenceZones.images.length} refs
            </button>
          </div>
        </div>
      </Drawer>

      <DirectorPlanModal
        open={showPlanModal}
        onClose={() => setShowPlanModal(false)}
        plan={plan}
        onApprove={handleApproveClick}
        isRendering={isRendering}
        storytellingIssues={storytellingIssues}
        referenceImages={referenceZones.images}
        settings={{
          audio_mode: audioMode, model, duration_s: duration,
          aspect_ratio: aspect, resolution, num_shots: numShots,
        }}
        masterBoardEnabled={masterBoardEnabled}
        onRefineJobStarted={(rid) => {
          setJobId(rid);
          setShowPlanModal(false);
          setShowJobModal(true);
        }}
        onMasterBoardChange={setMasterBoardUrl}
        onPlanRevised={setPlan}
      />

      {/* V5.2 — Cost confirmation gate before high-cost renders */}
      {plan && (
        <CostConfirmDialog
          open={showCostConfirm}
          estimatedCostUsd={plan.cost_estimate.total_cost_usd}
          estimatedDurationS={plan.continuity_bible.duration_s}
          shotCount={plan.shot_list.length}
          modelName={MODEL_CONFIGS[model]?.name_short ?? model}
          onConfirm={handleApproveAndRender}
          onCancel={() => setShowCostConfirm(false)}
          isLoading={isRendering}
          masterBoardCostUsd={masterBoardUrl ? MASTER_BOARD_COST_USD : 0}
        />
      )}

      <JobResultModal
        open={showJobModal}
        jobId={jobId}
        onClose={() => setShowJobModal(false)}
        estimatedDurationS={plan?.continuity_bible.duration_s ?? duration}
        jobStartedAt={jobStartedAt}
      />
    </div>
  );
}
