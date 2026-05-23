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
  }, [model, resolution, duration, aspect]);

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

  // V5.2 — Magic prompt enhance
  const { enhance, isEnhancing } = useEnhanceBrief();
  const handleEnhance = useCallback(async () => {
    if (!brief.trim() || brief.trim().length < 4) return;
    try {
      const res = await enhance({ brief, duration_s: duration });
      setBrief(res.enhanced_brief);
      toast.success(`Brief enhanced (~${res.char_count} chars) — review trước khi Generate`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Enhance failed: ${msg}`);
    }
  }, [brief, duration, enhance]);

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
    await createPlan({
      product_input: { text_description: brief.slice(0, 200) },
      reference_images: referenceZones.images,
      reference_role_hints: referenceZones.roles,
      reference_videos: [],
      user_brief: brief,
      context_injection: context,
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

  // V5.2 — Approve gated by cost confirm dialog when ≥ threshold
  const handleApproveClick = () => {
    if (!plan) return;
    if (plan.cost_estimate.total_cost_usd >= COST_CONFIRM_THRESHOLD_USD) {
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
  const estimatedCostUsd = useMemo(() => {
    const videoCost = cfg.cost_per_second_usd * duration;
    const audioCost = audioMode === 'dialogue_vo' ? 0.01 : audioMode === 'asmr_macro' ? 0.10 : 0;
    return 0.04 + videoCost + audioCost;
  }, [cfg.cost_per_second_usd, duration, audioMode]);

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
