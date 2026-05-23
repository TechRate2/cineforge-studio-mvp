'use client';
import { useState, useMemo } from 'react';
import { Diamond, FolderArchive, Eye, Link2, Image as ImgIcon, History, Settings, Sparkles } from 'lucide-react';
import { GenerateFormats, type FormatCard } from './GenerateFormats';
import { JobResultModal } from './JobResultModal';
import { VideoAgentCard } from './VideoAgentCard';
import { ContextInjection } from './ContextInjection';
import { AdvancedPanel } from './AdvancedPanel';
import { DirectorPlanModal, useDirectorJobPoll } from './DirectorPlanModal';
import { ReferenceZones, type ReferenceZonesValue } from './ReferenceZones';
import { ProjectHistoryDrawer } from './ProjectHistoryDrawer';
import { AssetLibrary } from './AssetLibrary';
import type { DirectorPlan } from '@/lib/studio/use-director-plan';
// V3 Director-only context-injection types (kept locally to avoid the removed use-propose-job hook)
type ContextInjectionType = {
  pain_points?: string;
  real_reviews?: string;
  usps?: string;
  forbidden_to_say?: string;
  mood_hint?: string;
};
type NicheHint = string;
import { getModelConfig } from '@/lib/studio/model-config';
import type { VideoModel, AspectRatio, AudioMode } from '@/lib/types/backend';
import PRESETS from '@/lib/studio-presets.json';

const INSPIRATION_CARDS: FormatCard[] = (PRESETS as any[]).map((p) => ({
  id: p.id,
  label: p.name || p.label,
  video: p.video,
  cost: 60.5,
  chips: [],
  headerLabel: '',
  body: p.prompt?.slice(0, 200) || '',
  productImg: p.productImg,
  avatarImg: p.avatarImgs?.[0]?.img || null,
}));

// Resolution loose string — per-model options từ model_config.resolution_options
// (KHÔNG hardcode Literal vì mỗi model AtlasCloud có set khác: vidu_q3 dùng 540p/720p/1080p,
//  wan_2_7 dùng 720P/1080P uppercase, seedance_2_0 có 720p-SR/1080p-SR variants)
type Resolution = string;

export function StudioMain() {
  // ============ STATE — Compact like Topview ============
  // Product input (link/text/img)
  const [productUrl, setProductUrl] = useState('');
  const [productImg, setProductImg] = useState<string | null>(null);

  // Main prompt textarea (idea + product description)
  const [prompt, setPrompt] = useState('');

  // References (1-12 depend on model, UI cap 5)
  // V3 §5: split into 3 zones (character / product / storyboard) for clearer
  // role tagging — the Director Agent gets pre-classified refs instead of
  // having to guess via a vision pass.
  const [referenceZones, setReferenceZones] = useState<ReferenceZonesValue>({
    images: [],
    roles: [],
    storyboardImages: [],
  });
  // Compatibility: VideoAgentCard still expects a flat string[] for the
  // existing `@Image N` mention UI. We mirror the zone state into a flat list.
  const referenceImages = referenceZones.images;
  const setReferenceImages = (next: string[]) => {
    // Manual edit from VideoAgentCard removes images by URL — preserve roles
    const nextRoles = next.map((url) => {
      const idx = referenceZones.images.indexOf(url);
      return idx >= 0 ? referenceZones.roles[idx] : null;
    });
    const nextStoryboard = referenceZones.storyboardImages.filter((u) => next.includes(u));
    setReferenceZones({ images: next, roles: nextRoles, storyboardImages: nextStoryboard });
  };

  // Settings — init resolution theo default của model
  const [model, setModel] = useState<VideoModel>('seedance_2_0');
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>('16:9');
  const [resolution, setResolution] = useState<Resolution>(
    getModelConfig('seedance_2_0').resolution_default,
  );
  const [durationS, setDurationS] = useState(15);
  const [audioMode, setAudioMode] = useState<AudioMode>('silent_native');
  // V3.1 — num_shots override (null = Director tự quyết, 1-5 = user ép)
  const [numShots, setNumShots] = useState<number | null>(null);

  // Director Agent V3 (Continuity Bible + Shot List + Reference Chaining)
  const [context, setContext] = useState<ContextInjectionType>({});
  const [referenceVideos, setReferenceVideos] = useState<string[]>([]);
  const [nicheHint, setNicheHint] = useState<NicheHint>('auto');
  const [planRequest, setPlanRequest] = useState<Parameters<typeof DirectorPlanModal>[0]['initialRequest']>(null);
  const [showPlanModal, setShowPlanModal] = useState(false);

  // V3 render job state (server-side dispatched in /api/v1/director/generate)
  const [directorJobId, setDirectorJobId] = useState<string | null>(null);
  const directorJob = useDirectorJobPoll(directorJobId);
  const [showResultModal, setShowResultModal] = useState(false);
  const isGenerating = Boolean(directorJobId) && (directorJob?.status as string) !== 'done' && (directorJob?.status as string) !== 'failed';

  // Project History drawer
  const [showHistory, setShowHistory] = useState(false);
  const [forkedPlan, setForkedPlan] = useState<DirectorPlan | null>(null);

  // Sprint5 UX — Asset Library modal opened from header button (standalone
  // access in addition to ReferenceZones' inline picker). Picked assets are
  // pushed into the corresponding ReferenceZone.
  const [showAssetLibrary, setShowAssetLibrary] = useState(false);

  // Sprint5 UX — 3-step progress indicator (Input → Plan Review → Render)
  const flowStep: 1 | 2 | 3 = showResultModal || isGenerating ? 3 : showPlanModal ? 2 : 1;

  // Computed
  const modelConfig = getModelConfig(model);
  const { costVnd, costCredits } = useMemo(() => {
    const videoCostUsd = modelConfig.cost_per_second_usd * durationS;
    const claudeCostUsd = 0.087;
    const audioCostUsd = audioMode === 'dialogue_vo' ? 0.01 : 0.1;
    const totalUsd = videoCostUsd + claudeCostUsd + audioCostUsd;
    return {
      costVnd: Math.round(totalUsd * 24500),
      costCredits: parseFloat((totalUsd * 5).toFixed(1)), // 1 USD ≈ 5 credits
    };
  }, [modelConfig, durationS, audioMode]);

  const canSubmit = !!(prompt.trim() || productUrl || productImg);

  // Model change → auto adjust limits + reset resolution nếu không hợp lệ
  const handleModelChange = (newModel: VideoModel) => {
    setModel(newModel);
    const newConfig = getModelConfig(newModel);
    if (durationS > newConfig.max_duration_s) {
      setDurationS(newConfig.max_duration_s);
    }
    if (referenceImages.length > newConfig.max_references) {
      setReferenceImages(referenceImages.slice(0, newConfig.max_references));
    }
    // Auto-reset resolution nếu giá trị hiện tại không có trong options model mới
    if (!newConfig.resolution_options.includes(resolution)) {
      setResolution(newConfig.resolution_default);
    }
  };

  // V3 — Submit → Director Agent V3 plan modal (Continuity Bible review)
  const handleSubmit = () => {
    if (!canSubmit) return;
    setPlanRequest({
      product_input: {
        url: productUrl || undefined,
        text_description: prompt || undefined,
        image_urls: productImg ? [productImg] : [],
      },
      reference_images: referenceImages,
      // V3 §5: pre-tagged roles from ReferenceZones — Director skips vision
      // pass for these refs and goes straight to apply_to_shots binding.
      reference_role_hints: referenceZones.roles,
      reference_videos: referenceVideos,
      user_brief: prompt,
      context_injection: context,
      settings: {
        audio_mode: audioMode,
        model,
        duration_s: durationS,
        aspect_ratio: aspectRatio,
        resolution,
        num_shots: numShots ?? undefined,
      },
      niche_hint: nicheHint,
    });
    setShowPlanModal(true);
  };

  const handlePlanModalClose = () => {
    setShowPlanModal(false);
    setPlanRequest(null);
  };

  const handleJobStarted = (jobId: string) => {
    setDirectorJobId(jobId);
    setShowResultModal(true);
  };

  const handleCloseModal = () => {
    setShowResultModal(false);
    const s = (directorJob?.status as string | undefined);
    if (s === 'done' || s === 'failed' || s === 'cancelled') {
      setDirectorJobId(null);
    }
  };

  const handleUploadProduct = () => {
    const inp = document.createElement('input');
    inp.type = 'file';
    inp.accept = 'image/*';
    inp.onchange = () => {
      const f = inp.files?.[0];
      if (!f) return;
      const r = new FileReader();
      r.onload = () => setProductImg(r.result as string);
      r.readAsDataURL(f);
    };
    inp.click();
  };

  return (
    <main className="flex-1 overflow-y-auto relative">
      {/* Background — đồng bộ homepage palette */}
      <div className="absolute inset-0 bg-gradient-to-b from-bg via-bg-soft to-bg pointer-events-none" />
      <div
        className="absolute inset-0 pointer-events-none opacity-25"
        style={{
          backgroundImage:
            'linear-gradient(rgba(124,77,255,0.10) 1px, transparent 1px), linear-gradient(90deg, rgba(124,77,255,0.10) 1px, transparent 1px)',
          backgroundSize: '60px 60px',
          maskImage: 'radial-gradient(ellipse at center top, rgba(0,0,0,1) 0%, rgba(0,0,0,0.4) 60%, transparent 100%)',
          WebkitMaskImage: 'radial-gradient(ellipse at center top, rgba(0,0,0,1) 0%, rgba(0,0,0,0.4) 60%, transparent 100%)',
        }}
      />
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-brand-600/20 rounded-full blur-[150px] pointer-events-none" />
      <div className="absolute top-32 right-1/4 w-[400px] h-[400px] bg-rose-500/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Top right */}
      <div className="absolute top-4 right-6 z-20 flex items-center gap-2">
        <a
          href="/pricing"
          className="relative flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-card hover:bg-bg-hover backdrop-blur border border-border text-text text-sm transition"
        >
          <Diamond className="w-3.5 h-3.5 text-brand-300" /> Pricing
          <span className="absolute -top-2 -right-2 px-1.5 py-0.5 rounded-md bg-gradient-to-r from-amber-500 to-rose-500 text-white text-[9px] font-bold">
            30% OFF
          </span>
        </a>
        <a
          href="/admin"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-card hover:bg-bg-hover backdrop-blur border border-border text-text text-sm transition"
        >
          <Settings className="w-3.5 h-3.5 text-brand-300" /> Admin
        </a>
        <a
          href="/studio-v5"
          title="Thử giao diện V5 — LumeFlow-inspired layout (cùng pipeline V3)"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-fuchsia-500/15 to-purple-500/15 hover:from-fuchsia-500/25 hover:to-purple-500/25 backdrop-blur border border-fuchsia-400/30 text-fuchsia-100 text-sm transition"
        >
          <Sparkles className="w-3.5 h-3.5" /> Thử UI V5
        </a>
        <button
          onClick={() => setShowHistory(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-card hover:bg-bg-hover backdrop-blur border border-border text-text text-sm transition"
        >
          <History className="w-3.5 h-3.5 text-fuchsia-300" /> History
        </button>
        <button
          onClick={() => setShowAssetLibrary(true)}
          title="Mở thư viện Character / Product / Storyboard đã lưu — tái sử dụng giữa các dự án"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-card hover:bg-bg-hover backdrop-blur border border-border text-text text-sm transition"
        >
          <FolderArchive className="w-3.5 h-3.5 text-emerald-300" /> Assets
        </button>
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-brand-400 to-fuchsia-500 border-2 border-border" />
      </div>

      <div className="relative px-6 lg:px-12 pt-16 pb-12 max-w-4xl mx-auto">
        {/* HERO — Sprint5 UX: rebrand to CineForge Director V3 */}
        <div className="text-center mb-8">
          <div className="text-amber-400 text-[11px] uppercase tracking-[0.3em] font-medium mb-3 flex items-center justify-center gap-2">
            <span className="relative flex w-1.5 h-1.5">
              <span className="absolute inset-0 rounded-full bg-amber-400 animate-ping opacity-75" />
              <span className="relative w-1.5 h-1.5 rounded-full bg-amber-400" />
            </span>
            CineForge Director V3 · Marketing Studio
          </div>
          <h1 className="text-3xl lg:text-5xl font-bold tracking-tight leading-[1.1]">
            Biến mọi sản phẩm thành{' '}
            <span className="bg-gradient-to-r from-brand-300 via-fuchsia-400 to-amber-300 bg-clip-text text-transparent animate-gradient-shift inline-block">
              video ad
            </span>
          </h1>
        </div>

        {/* Sprint5 UX — 3-step flow indicator: Input → Plan Review → Render */}
        <div className="flex items-center justify-center gap-1.5 mb-6 text-[11px]">
          {([
            { n: 1, label: 'Input', desc: 'Nhập brief + upload references' },
            { n: 2, label: 'Plan Review', desc: 'Xem Continuity Bible + Shot List, sửa nếu cần' },
            { n: 3, label: 'Render', desc: 'AI render từng shot + assemble MP4' },
          ] as const).map((s, i, arr) => (
            <div key={s.n} className="flex items-center gap-1.5" title={s.desc}>
              <div
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border transition ${
                  flowStep === s.n
                    ? 'bg-brand-700/20 border-brand-500/50 text-brand-100'
                    : flowStep > s.n
                      ? 'bg-emerald-700/15 border-emerald-500/30 text-emerald-200/80'
                      : 'bg-bg-card border-border text-text-subtle'
                }`}
              >
                <span
                  className={`w-4 h-4 rounded-full text-[10px] font-bold flex items-center justify-center ${
                    flowStep === s.n
                      ? 'bg-brand-500 text-white'
                      : flowStep > s.n
                        ? 'bg-emerald-500 text-white'
                        : 'bg-bg-hover text-text-subtle'
                  }`}
                >
                  {flowStep > s.n ? '✓' : s.n}
                </span>
                <span className="font-medium">{s.label}</span>
              </div>
              {i < arr.length - 1 && <span className="text-text-subtle">→</span>}
            </div>
          ))}
        </div>

        {/* ADVANCED PANEL — compact 2-col grid (gọn hơn — TopView V2 style) */}
        {/* Default ẨN. User click "Advanced ▼" để expand. Layout 2-col cho desktop, 1-col mobile */}
        <AdvancedPanel
          filledCount={
            (productUrl ? 1 : 0) +
            (productImg ? 1 : 0) +
            (nicheHint !== 'auto' ? 1 : 0) +
            (referenceVideos.length > 0 ? 1 : 0) +
            (context.pain_points || context.real_reviews || context.usps ? 1 : 0)
          }
        >
          {/* Row 1 — 2-col: Niche dropdown | Reference video URL */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
            <label className="flex items-center gap-2">
              <span className="text-text-muted shrink-0 w-16">🎯 Niche</span>
              <select
                value={nicheHint}
                onChange={(e) => setNicheHint(e.target.value as NicheHint)}
                className="flex-1 bg-bg-soft border border-border rounded-md px-2 py-1.5 text-xs text-text hover:border-brand-500 focus:outline-none focus:border-brand-500 cursor-pointer"
              >
                <option value="auto">🤖 Auto-detect</option>
                <option value="beauty_skincare">💄 Beauty & Skincare</option>
                <option value="shopee_general">🛒 Shopee General</option>
                <option value="supplement_health">💊 Supplement & Health</option>
                <option value="tech_gadget">⚡ Tech & Gadget</option>
                <option value="fashion_apparel">👗 Fashion & Apparel</option>
                <option value="food_beverage">🍜 Food & Beverage</option>
                <option value="custom">🎨 Custom</option>
              </select>
            </label>

            <label className="flex items-center gap-2">
              <span className="text-text-muted shrink-0 w-16">🎬 Clone</span>
              <input
                type="text"
                value={referenceVideos[0] || ''}
                onChange={(e) => setReferenceVideos(e.target.value ? [e.target.value] : [])}
                placeholder="URL TikTok/Reel viral (optional)"
                className="flex-1 bg-bg-soft border border-border rounded-md px-2 py-1.5 text-xs text-text hover:border-brand-500 focus:outline-none focus:border-brand-500 placeholder:text-text-subtle"
              />
            </label>
          </div>

          {/* Row 2 — Product link + image upload (compact) */}
          <div className="flex items-center gap-2 text-xs">
            <span className="text-text-muted shrink-0 w-16">🔗 Sản phẩm</span>
            <div className="relative flex-1">
              <Link2 className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-text-subtle" />
              <input
                value={productUrl}
                onChange={(e) => setProductUrl(e.target.value)}
                placeholder="URL Shopee / Lazada / Tiki (optional)"
                className="w-full pl-7 pr-2 py-1.5 text-xs bg-bg-soft border border-border rounded-md text-text hover:border-brand-500 focus:outline-none focus:border-brand-500 placeholder:text-text-subtle"
              />
            </div>
            <button
              onClick={handleUploadProduct}
              className="shrink-0 w-8 h-8 rounded-md border border-border bg-bg-soft hover:bg-bg-hover hover:border-brand-600/50 transition flex items-center justify-center text-text-subtle hover:text-text"
              title="Upload ảnh sản phẩm"
            >
              {productImg ? (
                <img src={productImg} alt="" className="w-full h-full object-cover rounded-md" />
              ) : (
                <ImgIcon className="w-3.5 h-3.5" />
              )}
            </button>
          </div>

          {/* Row 3 — Context Injection (giữ collapse riêng vì 5 field dài) */}
          <ContextInjection value={context} onChange={setContext} />

          {/* Row 4 — Reference Pack: 3 zones (Character / Product / Storyboard) */}
          <ReferenceZones value={referenceZones} onChange={setReferenceZones} />
        </AdvancedPanel>

        {/* ===== MAIN INPUT CARD — CineForge Director V3 entry point ===== */}
        <VideoAgentCard
          prompt={prompt}
          onPromptChange={setPrompt}
          referenceImages={referenceImages}
          onReferenceImagesChange={setReferenceImages}
          model={model}
          onModelChange={handleModelChange}
          aspectRatio={aspectRatio}
          onAspectRatioChange={setAspectRatio}
          resolution={resolution}
          onResolutionChange={setResolution}
          durationS={durationS}
          onDurationChange={setDurationS}
          audioMode={audioMode}
          onAudioModeChange={setAudioMode}
          numShots={numShots}
          onNumShotsChange={setNumShots}
          costVnd={costVnd}
          costCredits={costCredits}
          isGenerating={isGenerating}
          jobProgress={typeof directorJob?.progress === 'number' ? directorJob.progress : undefined}
          canSubmit={canSubmit}
          onSubmit={handleSubmit}
        />

        {/* ===== INSPIRATION GALLERY ===== */}
        <div className="mt-16 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-[11px] uppercase tracking-widest text-text-subtle font-medium mb-1 flex items-center gap-1.5">
                <Eye className="w-3 h-3" /> Cảm hứng từ video mẫu
              </div>
              <div className="text-lg font-bold text-text">Xem demo phong cách</div>
            </div>
            <div className="text-[11px] text-text-subtle">{INSPIRATION_CARDS.length} video tham khảo</div>
          </div>
          <GenerateFormats cards={INSPIRATION_CARDS} />
        </div>
      </div>

      {/* MODAL — Director Plan V3 (Continuity Bible + Shot List review) */}
      <DirectorPlanModal
        open={showPlanModal}
        initialRequest={planRequest}
        referenceImages={referenceImages}
        settings={{
          audio_mode: audioMode,
          model,
          duration_s: durationS,
          aspect_ratio: aspectRatio,
          resolution,
        }}
        onClose={handlePlanModalClose}
        onJobStarted={handleJobStarted}
      />

      {/* MODAL — Render Result (V3 — polls /api/v1/director/jobs/{jobId}) */}
      {showResultModal && (
        <JobResultModal
          status={directorJob as any}
          error={(directorJob?.error_message as string | undefined) ?? null}
          onClose={handleCloseModal}
          onCancel={() => {
            if (directorJobId) {
              fetch(`/api/v1/director/jobs/${directorJobId}/cancel`, { method: 'POST' }).catch(() => {});
            }
            handleCloseModal();
          }}
        />
      )}

      {/* DRAWER — Project History (V3) */}
      <ProjectHistoryDrawer
        open={showHistory}
        onClose={() => setShowHistory(false)}
        onFork={(plan) => {
          // Fork — preload state from history plan
          const cb = plan.continuity_bible;
          setPrompt(cb.logline || cb.title);
          setDurationS(cb.duration_s);
          setAspectRatio((cb.aspect_ratio as AspectRatio) || '9:16');
          setForkedPlan(plan);
          // Seed reference zones từ bible.reference_assets (with role tags)
          if (Array.isArray(cb.reference_assets) && cb.reference_assets.length > 0) {
            setReferenceZones({
              images: cb.reference_assets.map((r) => r.url),
              roles: cb.reference_assets.map((r) => {
                const map: Record<string, ReferenceZonesValue['roles'][number]> = {
                  character_anchor: 'primary_subject',
                  secondary_character: 'secondary_subject',
                  product_hero: 'product_hero',
                  product_detail: 'product_detail',
                  style_reference: 'style_reference',
                  environment: 'environment',
                  brand_asset: 'brand_asset',
                };
                return map[r.role] ?? null;
              }),
              storyboardImages: cb.reference_assets
                .filter((r) => r.role === 'style_reference')
                .map((r) => r.url),
            });
          }
        }}
      />

      {/* Sprint5 UX — Asset Library modal (header button entry point).
          ReferenceZones has its own inline picker; this surface is for
          browsing/curating across projects without opening Advanced first. */}
      <AssetLibrary
        open={showAssetLibrary}
        onClose={() => setShowAssetLibrary(false)}
        onPick={(picked) => {
          // Push picked URLs into images zone with role preserved
          const newImages = [...referenceZones.images];
          const newRoles = [...referenceZones.roles];
          for (const a of picked) {
            if (!newImages.includes(a.image_url)) {
              newImages.push(a.image_url);
              // Map AssetType → ReferenceZonesValue role
              const roleMap: Record<string, ReferenceZonesValue['roles'][number]> = {
                character: 'primary_subject',
                product: 'product_hero',
                storyboard: 'style_reference',
              };
              newRoles.push(roleMap[a.type] ?? null);
            }
          }
          const newStoryboard = [...referenceZones.storyboardImages];
          for (const a of picked) {
            if (a.type === 'storyboard' && !newStoryboard.includes(a.image_url)) {
              newStoryboard.push(a.image_url);
            }
          }
          setReferenceZones({
            images: newImages,
            roles: newRoles,
            storyboardImages: newStoryboard,
          });
        }}
      />
    </main>
  );
}
