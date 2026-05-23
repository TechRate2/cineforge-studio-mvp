'use client';
import { useEffect, useMemo, useState } from 'react';
import { PromptCardV2 } from '@/components/studio/PromptCardV2';
import { ReferenceZones, type ReferenceZonesValue } from '@/components/studio/ReferenceZones';
import { ContextInjection, type ContextValue } from '@/components/studio/ContextInjection';
import { DirectorPlanModal } from '@/components/studio/DirectorPlanModal';
import { JobResultModal } from '@/components/studio/JobResultModal';
import { ModelShowcase } from '@/components/studio/ModelShowcase';
import { Drawer } from '@/components/ui/Modal';
import { useDirectorPlan, generateFromPlan, DIRECTOR_STAGE_LABELS_VN } from '@/lib/studio/use-director-plan';
import { getModelConfig } from '@/lib/studio/model-config';
import type { VideoModel, AspectRatio, AudioMode } from '@/lib/types/backend';
import { AlertCircle, Loader2 } from 'lucide-react';

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

  // Sync resolution to model on change
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
  }, [model, resolution, duration]);

  // Director plan flow
  const { createPlan, plan, setPlan, progress, isLoading, error, storytellingIssues, reset } = useDirectorPlan();
  const [showPlanModal, setShowPlanModal] = useState(false);

  // Open modal when plan ready
  useEffect(() => {
    if (plan) setShowPlanModal(true);
  }, [plan]);

  // Render job flow
  const [jobId, setJobId] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(false);
  const [showJobModal, setShowJobModal] = useState(false);
  // V4 Sprint1 Task #7 — master board URL (set when user gens master board in PlanModal)
  const [masterBoardUrl, setMasterBoardUrl] = useState<string | null>(null);
  // Topview-style: references live in a drawer instead of always-visible 3-zone
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

  const handleApproveAndRender = async () => {
    if (!plan) return;
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
    } catch (e) {
      // surface error via existing error state from hook? simplest: alert
      // For demo, log:
      console.error(e);
    } finally {
      setIsRendering(false);
    }
  };

  const cfg = useMemo(() => getModelConfig(model), [model]);

  // Cost estimate — videos × duration + plan + audio
  const estimatedCostUsd = useMemo(() => {
    const videoCost = cfg.cost_per_second_usd * duration;
    const audioCost = audioMode === 'dialogue_vo' ? 0.01 : audioMode === 'asmr_macro' ? 0.10 : 0;
    return 0.04 + videoCost + audioCost;
  }, [cfg.cost_per_second_usd, duration, audioMode]);

  return (
    <div className="min-h-full">
      {/* Hero — Topview style: tighter, bold one-line */}
      <section className="px-5 md:px-10 pt-12 md:pt-16 pb-8 max-w-container mx-auto text-center">
        <h1 className="text-4xl md:text-5xl lg:text-[56px] font-extrabold tracking-tight leading-tight">
          Create Any Video, Just Tell Your <span className="text-gradient">Agent</span>
        </h1>
        <p className="text-sm text-text-muted mt-3 max-w-2xl mx-auto">
          Mô tả ý tưởng → AI dựng kế hoạch shot-by-shot → render thật. Niche-agnostic, identity-locked, audio sync.
        </p>
      </section>

      {/* Main compact input card — Topview Video Agent V2 style */}
      <section className="px-5 md:px-10 pb-6 max-w-3xl mx-auto">
        <PromptCardV2
          brief={brief}
          onBrief={setBrief}
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
        />

        {/* Live progress / error directly under input */}
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
      </section>

      {/* Featured models showcase — below input as inspiration */}
      <section className="px-5 md:px-10 pb-8 max-w-container mx-auto">
        <h3 className="text-[11px] uppercase tracking-wider text-text-subtle mb-3 px-1">Pick a tier</h3>
        <ModelShowcase onPick={setModel} />
      </section>

      {/* Context injection — optional, collapsed */}
      <section className="px-5 md:px-10 pb-12 max-w-3xl mx-auto">
        <ContextInjection value={context} onChange={setContext} />
      </section>

      {/* References drawer — opens from "+ Reference" button */}
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

      {/* Modals */}
      <DirectorPlanModal
        open={showPlanModal}
        onClose={() => setShowPlanModal(false)}
        plan={plan}
        onApprove={handleApproveAndRender}
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
      <JobResultModal
        open={showJobModal}
        jobId={jobId}
        onClose={() => setShowJobModal(false)}
      />
    </div>
  );
}
