'use client';
import { useEffect, useMemo, useState } from 'react';
import { PromptCard } from '@/components/studio/PromptCard';
import { ReferenceZones, type ReferenceZonesValue } from '@/components/studio/ReferenceZones';
import { ContextInjection, type ContextValue } from '@/components/studio/ContextInjection';
import { SettingsPanel } from '@/components/studio/SettingsPanel';
import { DirectorPlanModal } from '@/components/studio/DirectorPlanModal';
import { JobResultModal } from '@/components/studio/JobResultModal';
import { ModelShowcase } from '@/components/studio/ModelShowcase';
import { useDirectorPlan, generateFromPlan, DIRECTOR_STAGE_LABELS_VN } from '@/lib/studio/use-director-plan';
import { getModelConfig } from '@/lib/studio/model-config';
import type { VideoModel, AspectRatio, AudioMode } from '@/lib/types/backend';
import { Sparkles, AlertCircle, Loader2 } from 'lucide-react';

const SUGGESTION_CHIPS = [
  { label: '🛒 Review sản phẩm Shopee 30s', value: 'Video review sản phẩm 30s phong cách UGC TikTok, nữ Gen Z, golden hour, bàn make-up.' },
  { label: '💄 Beauty unboxing 15s', value: 'Unboxing son lì matte 89k, close-up texture, vibe Gen Z confident, anamorphic 35mm.' },
  { label: '📱 Tech demo 20s', value: 'Demo tính năng app trên iPhone 16 Pro, B-roll tay swipe, voice-over VN nam.' },
  { label: '🍜 Food viral hook', value: 'Phở Việt Nam, slow-mo lift the noodles, steam, ASMR slurp, hook 2s đầu cực mạnh.' },
];

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
  const { createPlan, plan, progress, isLoading, error, storytellingIssues, reset } = useDirectorPlan();
  const [showPlanModal, setShowPlanModal] = useState(false);

  // Open modal when plan ready
  useEffect(() => {
    if (plan) setShowPlanModal(true);
  }, [plan]);

  // Render job flow
  const [jobId, setJobId] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(false);
  const [showJobModal, setShowJobModal] = useState(false);

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

  return (
    <div className="min-h-full">
      {/* Hero strip */}
      <section className="px-5 md:px-10 pt-8 md:pt-10 pb-5 max-w-container mx-auto">
        <div className="flex flex-col items-start gap-2">
          <span className="chip">
            <Sparkles size={11} className="text-accent-magenta" />
            Director Agent V3 · Continuity Bible
          </span>
          <h1 className="h-section">
            What do you want to <span className="text-gradient">create</span> today?
          </h1>
          <p className="text-sm text-text-muted">
            Mô tả ý tưởng → AI dựng kế hoạch shot-by-shot → bạn duyệt → render thật.
          </p>
        </div>
      </section>

      {/* Featured models strip */}
      <section className="px-5 md:px-10 pb-6 max-w-container mx-auto">
        <ModelShowcase onPick={setModel} />
      </section>

      {/* Main canvas */}
      <section className="px-5 md:px-10 pb-12 max-w-container mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-5">
          {/* LEFT — input flow */}
          <div className="space-y-4 min-w-0">
            <PromptCard
              value={brief}
              onChange={setBrief}
              onSubmit={handleGeneratePlan}
              isLoading={isLoading}
              chips={SUGGESTION_CHIPS}
            />

            {/* Live progress */}
            {progress && isLoading && (
              <div className="surface-2 rounded-card p-4 flex items-center gap-3">
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
              <div className="surface-2 rounded-card p-4 flex items-start gap-3 border-accent-orange/40">
                <AlertCircle size={16} className="text-accent-orange shrink-0 mt-0.5" />
                <div>
                  <div className="text-sm font-semibold text-accent-orange">Plan failed</div>
                  <div className="text-xs text-text-muted mt-1 font-mono">{error}</div>
                  <button onClick={reset} className="btn-ghost mt-2">Reset</button>
                </div>
              </div>
            )}

            {/* References */}
            <div>
              <div className="flex items-center justify-between mb-2 px-1">
                <h3 className="text-[11px] uppercase tracking-wider text-text-subtle font-semibold">References</h3>
                <span className="text-[11px] text-text-subtle">
                  {referenceZones.images.length} / {cfg.max_references}
                </span>
              </div>
              <ReferenceZones
                value={referenceZones}
                onChange={setReferenceZones}
                maxRefs={cfg.max_references}
              />
            </div>

            {/* Context Injection */}
            <ContextInjection value={context} onChange={setContext} />
          </div>

          {/* RIGHT — sticky settings */}
          <div className="lg:sticky lg:top-4 self-start">
            <SettingsPanel
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
            />
          </div>
        </div>
      </section>

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
      />
      <JobResultModal
        open={showJobModal}
        jobId={jobId}
        onClose={() => setShowJobModal(false)}
      />
    </div>
  );
}
