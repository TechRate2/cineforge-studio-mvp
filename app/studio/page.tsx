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
import { AlertCircle, Loader2, ChevronDown, Sparkles, Zap } from 'lucide-react';

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

  // V6.1 — Autonomous mode state (1-click full video, no manual director plan)
  const [isAutonomousLoading, setIsAutonomousLoading] = useState(false);
  const [autonomousPreview, setAutonomousPreview] = useState<{
    caption_vn?: string;
    hashtags_vn?: string[];
    hook_first_3s?: string;
    niche?: string;
    n_shots?: number;
    estimated_cost_usd?: number;
  } | null>(null);
  // V6.2 — Manual mode collapsed by default. Autonomous IS the primary flow.
  const [manualMode, setManualMode] = useState(false);

  /** V6.1 — 1-click autonomous flow.
   * POST /director/autonomous → backend chain 5 skills → spawn render →
   * return job_id + editor_preview + hook_preview. FE shows preview ngay,
   * job render chạy background, JobResultModal poll status như flow cũ.
   */
  const handleAutonomousGenerate = async () => {
    if (!brief.trim()) {
      toast.error('Hãy nhập ý tưởng video trước (≥5 ký tự)');
      return;
    }
    setIsAutonomousLoading(true);
    setAutonomousPreview(null);
    try {
      const res = await fetch('/api/v1/director/autonomous', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_idea: brief,
          reference_image_urls: referenceZones.images,
          reference_video_urls: [],
          reference_audio_urls: [],
          target_platform: aspect === '9:16' ? 'tiktok' : aspect === '16:9' ? 'youtube_long' : 'universal',
          duration_hint_s: duration,
          user_model: model === 'auto' ? 'auto' : model,
          resolution,
          use_vision_llm_for_tagging: referenceZones.images.length > 0,
        }),
      });
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`${res.status}: ${errText.slice(0, 200)}`);
      }
      const data = await res.json();
      setAutonomousPreview({
        caption_vn: data.editor_preview?.caption_vn,
        hashtags_vn: data.editor_preview?.hashtags_vn,
        hook_first_3s: data.hook_preview?.first_3s,
        niche: data.hook_preview?.niche,
        n_shots: data.n_shots,
        estimated_cost_usd: data.estimated_cost_usd,
      });
      setJobId(data.job_id);
      setShowJobModal(true);
      toast.success(
        `🎬 Autonomous mode: ${data.n_shots} shots, ${data.estimated_duration_s}s, ` +
        `$${data.estimated_cost_usd?.toFixed(2) ?? '?'} • ${data.resolved_model}`,
        { duration: 6000 }
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Autonomous failed: ${msg}`, { duration: 8000 });
      console.error(e);
    } finally {
      setIsAutonomousLoading(false);
    }
  };

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

  // V6.2 — Estimated cost cho Autonomous flow (đơn giản: rate × duration + $0.05 plan)
  const autonomousCostUsd = useMemo(() => {
    const rate =
      model === 'wan_2_7' ? 0.10 :
      model === 'seedance_2_0' ? 0.096 :
      0.076;  // seedance_2_0_fast / auto default
    return 0.05 + rate * duration;
  }, [model, duration]);

  return (
    <div className="min-h-full">
      {/* V6.2 — Autonomous-first hero */}
      <section className="px-5 md:px-10 pt-12 md:pt-16 pb-6 max-w-container mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full mb-5 border border-accent-magenta/30 bg-accent-magenta/10">
          <Zap size={12} className="text-accent-magenta" />
          <span className="text-[10px] font-bold tracking-widest uppercase text-accent-magenta">
            Autonomous Agent · 1-Click Magic
          </span>
        </div>
        <h1 className="text-4xl md:text-5xl lg:text-[56px] font-extrabold tracking-tight leading-tight">
          Tell Your Idea · Get Your <span className="text-gradient">Video</span>
        </h1>
        <p className="text-sm md:text-base text-text-muted mt-4 max-w-2xl mx-auto leading-relaxed">
          1 ý tưởng + references → Agent tự <b className="text-text">planner</b> · <b className="text-text">storyboard</b> · <b className="text-text">director</b> · <b className="text-text">render</b> · <b className="text-text">caption viral</b>.
          Không cần plan tay.
        </p>
      </section>

      {/* ═══════════════════════════════════════════════════════
          PRIMARY: Autonomous Studio Card
          ═══════════════════════════════════════════════════════ */}
      <section className="px-5 md:px-10 pb-6 max-w-3xl mx-auto">
        <div className="surface-2 rounded-card border border-hairline-strong overflow-hidden shadow-2xl shadow-accent-magenta/5">
          {/* Top gradient accent line */}
          <div className="h-0.5 bg-gradient-to-r from-accent-magenta via-accent-cyan to-accent-magenta" />

          <div className="p-5 md:p-6 space-y-5">
            {/* Brief textarea — primary input */}
            <div>
              <label className="flex items-center justify-between mb-2">
                <span className="text-[11px] uppercase tracking-wider text-text-subtle font-semibold">
                  Your idea
                </span>
                <span className="text-[10px] text-text-subtle/70 font-mono">{brief.length}/800</span>
              </label>
              <textarea
                value={brief}
                onChange={(e) => { setBrief(e.target.value); setActivePresetId(undefined); }}
                placeholder="Vd: Cô gái Việt unbox son môi cao cấp ở quán cafe Sài Gòn, ánh nắng vàng chiều tà, camera handheld iPhone style…"
                rows={3}
                maxLength={800}
                className="w-full bg-surface-3 border border-hairline rounded-card p-3.5 text-sm text-text placeholder:text-text-subtle/60 resize-none focus:outline-none focus:border-accent-magenta/60 focus:ring-1 focus:ring-accent-magenta/20 transition"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && !isAutonomousLoading && brief.trim()) {
                    void handleAutonomousGenerate();
                  }
                }}
              />
              <div className="text-[10px] text-text-subtle/70 mt-1.5">
                Càng cụ thể càng tốt — agent đọc và tự quyết niche, hook 3s, mood, camera, audio
              </div>
            </div>

            {/* Quick platform presets */}
            <div>
              <label className="text-[11px] uppercase tracking-wider text-text-subtle font-semibold">
                Platform preset
              </label>
              <div className="grid grid-cols-3 gap-2 mt-2">
                {([
                  { id: 'tiktok',   label: 'TikTok / Reels',  dur: 15, ar: '9:16' as AspectRatio, icon: '📱' },
                  { id: 'short',    label: 'YouTube Short',   dur: 30, ar: '9:16' as AspectRatio, icon: '🎬' },
                  { id: 'longform', label: 'YouTube Long',    dur: 60, ar: '16:9' as AspectRatio, icon: '🎥' },
                ]).map((p) => {
                  const active = duration === p.dur && aspect === p.ar;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => { setDuration(p.dur); setAspect(p.ar); }}
                      className={`p-3 rounded-card border text-left transition ${
                        active
                          ? 'border-accent-magenta/60 bg-accent-magenta/10 shadow-sm shadow-accent-magenta/10'
                          : 'border-hairline bg-surface-3 hover:border-hairline-strong'
                      }`}
                    >
                      <div className="text-lg leading-none">{p.icon}</div>
                      <div className="text-[11px] font-bold mt-1.5">{p.label}</div>
                      <div className="text-[10px] text-text-subtle mt-0.5">{p.dur}s · {p.ar}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Inline controls row: refs + audio + cost */}
            <div className="flex items-center gap-2 flex-wrap">
              <button
                type="button"
                onClick={() => setShowRefDrawer(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface-3 border border-hairline hover:border-hairline-strong text-[11px] font-medium transition"
              >
                <span>📎</span>
                <span>References</span>
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-mono ${
                  referenceZones.images.length > 0 ? 'bg-accent-magenta/20 text-accent-magenta' : 'bg-surface-2 text-text-subtle'
                }`}>
                  {referenceZones.images.length}
                </span>
              </button>

              <select
                value={audioMode}
                onChange={(e) => setAudioMode(e.target.value as AudioMode)}
                className="px-3 py-1.5 rounded-full bg-surface-3 border border-hairline text-[11px] font-medium focus:outline-none focus:border-hairline-strong cursor-pointer"
              >
                <option value="silent_native">🔇 Silent (model gen)</option>
                <option value="dialogue_vo">🎤 Dialogue VN (TTS)</option>
                <option value="asmr_macro">✨ ASMR / SFX</option>
              </select>

              <div className="ml-auto text-[11px] text-text-subtle font-mono">
                ~${autonomousCostUsd.toFixed(2)}
              </div>
            </div>

            {/* BIG CTA */}
            <button
              onClick={handleAutonomousGenerate}
              disabled={isAutonomousLoading || isRendering || !brief.trim()}
              className="w-full py-4 rounded-card bg-gradient-to-r from-accent-magenta to-accent-cyan text-white font-bold text-base flex items-center justify-center gap-2 hover:opacity-95 active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed transition shadow-lg shadow-accent-magenta/30"
            >
              {isAutonomousLoading ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Agent đang dựng kế hoạch + render…
                </>
              ) : (
                <>
                  <Zap size={18} />
                  Generate Full Video (Autonomous)
                </>
              )}
            </button>
            <div className="text-center text-[10px] text-text-subtle/70 -mt-1">
              Tip: <kbd className="px-1.5 py-0.5 rounded bg-surface-3 border border-hairline text-[9px] font-mono">Cmd/Ctrl + Enter</kbd> để gen nhanh
            </div>
          </div>

          {/* Preview area — appears after first generate */}
          {autonomousPreview && (
            <div className="border-t border-hairline px-5 md:px-6 py-4 bg-surface-3/40 animate-fade-in space-y-3">
              <div className="text-[10px] uppercase tracking-wider text-text-subtle font-semibold flex items-center gap-1.5">
                <Sparkles size={11} className="text-accent-cyan" /> Agent's plan
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                {autonomousPreview.niche && (
                  <div>
                    <div className="text-[10px] text-text-subtle">Niche</div>
                    <div className="text-text font-semibold capitalize mt-0.5">{autonomousPreview.niche}</div>
                  </div>
                )}
                {autonomousPreview.n_shots && (
                  <div>
                    <div className="text-[10px] text-text-subtle">Shots planned</div>
                    <div className="text-text font-semibold mt-0.5">{autonomousPreview.n_shots} shots</div>
                  </div>
                )}
              </div>
              {autonomousPreview.hook_first_3s && (
                <div>
                  <div className="text-[10px] text-text-subtle">Hook 3s (scroll-stop)</div>
                  <div className="text-xs text-text leading-snug mt-0.5">{autonomousPreview.hook_first_3s}</div>
                </div>
              )}
              {autonomousPreview.caption_vn && (
                <div>
                  <div className="text-[10px] text-text-subtle">Caption viral (VN)</div>
                  <div className="text-xs text-text leading-snug mt-0.5">{autonomousPreview.caption_vn}</div>
                </div>
              )}
              {autonomousPreview.hashtags_vn && autonomousPreview.hashtags_vn.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {autonomousPreview.hashtags_vn.slice(0, 10).map((t) => (
                    <span key={t} className="px-2 py-0.5 rounded-full bg-surface-2 border border-hairline text-[10px]">#{t}</span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Switch to manual mode — subtle toggle */}
        <div className="text-center mt-4">
          <button
            type="button"
            onClick={() => setManualMode((m) => !m)}
            className="inline-flex items-center gap-1.5 text-[11px] text-text-subtle hover:text-text-muted transition"
          >
            <ChevronDown size={11} className={`transition ${manualMode ? 'rotate-180' : ''}`} />
            {manualMode ? 'Hide advanced manual mode' : 'Need fine-grained control? Open Advanced Manual Mode'}
          </button>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════
          ADVANCED — Manual Director (collapsed by default, power-user)
          ═══════════════════════════════════════════════════════ */}
      {manualMode && (
        <section className="px-5 md:px-10 pb-6 max-w-3xl mx-auto animate-fade-in">
          <div className="surface-2 rounded-card border border-hairline p-4 md:p-5">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-1.5 h-5 rounded-full bg-accent-cyan" />
              <div className="text-[11px] uppercase tracking-wider text-text-subtle font-semibold">
                Advanced · Manual Director
              </div>
              <div className="ml-auto text-[10px] text-text-subtle/70">
                Quyết shot/camera/audio/master-board từng bước. Hook flow Director Plan Modal.
              </div>
            </div>

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
          </div>

          <div className="mt-4">
            <h3 className="text-[11px] uppercase tracking-wider text-text-subtle mb-3 px-1">Pick a tier (manual)</h3>
            <ModelShowcase onPick={setModel} />
          </div>

          <div className="mt-4">
            <ContextInjection value={context} onChange={setContext} />
          </div>
        </section>
      )}

      {/* Recent generations — always visible (both modes share render history) */}
      <section className="px-5 md:px-10 pb-12 max-w-container mx-auto">
        <RecentGenerations />
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
