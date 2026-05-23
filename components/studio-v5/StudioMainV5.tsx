'use client';

/**
 * StudioMainV5 — LumeFlow-inspired visual redesign of Director V3 studio.
 *
 * Reuses ALL business logic from the original StudioMain:
 *   - State shape (productUrl/Img, prompt, referenceZones, model, settings,
 *     planRequest, directorJobId, ...)
 *   - Handlers (handleSubmit → DirectorPlanModal, handleJobStarted,
 *     handleUploadProduct, history fork, ...)
 *   - Downstream modals (DirectorPlanModal, JobResultModal,
 *     ProjectHistoryDrawer, AssetLibrary, AdvancedPanel, ReferenceZones,
 *     ContextInjection) — imported from `../studio/*` unchanged
 *   - Hooks (useDirectorJobPoll, useDirectorPlan, ...)
 *
 * Only the OUTER LAYOUT + visual tokens are LumeFlow-styled:
 *   - Pure black bg + purple/fuchsia accents
 *   - Top header bar with logo + page title + credits + lang + avatar
 *   - 2-column main: Left = input card | Right = Lịch sử/Cảm hứng gallery
 *   - Large gradient "Tạo kế hoạch video" button
 *   - Inline upload zone + dotted border + suggested avatars row
 *
 * Old `/studio` route stays intact for side-by-side comparison.
 */

import { useState, useMemo } from 'react';
import {
  Database, Globe, RefreshCw, Image as ImgIcon, Video, Sparkles, ArrowUp, Loader2,
  FolderArchive, Settings, Plus, ChevronDown, Link2,
} from 'lucide-react';
import { JobResultModal } from '../studio/JobResultModal';
import { AdvancedPanel } from '../studio/AdvancedPanel';
import { ContextInjection } from '../studio/ContextInjection';
import { DirectorPlanModal, useDirectorJobPoll } from '../studio/DirectorPlanModal';
import { ReferenceZones, type ReferenceZonesValue } from '../studio/ReferenceZones';
import { ProjectHistoryDrawer } from '../studio/ProjectHistoryDrawer';
import { AssetLibrary } from '../studio/AssetLibrary';
import { InspirationPanelV5 } from './InspirationPanelV5';
import { getModelConfig, MODEL_CONFIGS } from '@/lib/studio/model-config';
import type { VideoModel, AspectRatio, AudioMode } from '@/lib/types/backend';
import type { DirectorPlan } from '@/lib/studio/use-director-plan';

type ContextInjectionType = {
  pain_points?: string;
  real_reviews?: string;
  usps?: string;
  forbidden_to_say?: string;
  mood_hint?: string;
};
type Resolution = string;

const MODEL_OPTIONS: { value: VideoModel; label: string; desc: string }[] = [
  { value: 'auto', label: 'Auto', desc: 'AI tự chọn model tối ưu cho kịch bản' },
  { value: 'seedance_2_0', label: 'Seedance 2.0', desc: 'Multi-shot + @image_N + native audio' },
  { value: 'seedance_2_0_fast', label: 'Seedance 2.0 Fast', desc: 'Rẻ hơn 20%, chất lượng tương đương' },
  { value: 'seedance_1_5_pro', label: 'Seedance 1.5 Pro', desc: 'Time-coded prompt, ổn định identity' },
  { value: 'vidu_q3', label: 'Vidu Q3', desc: 'Reference-to-video, 1 ref' },
  { value: 'vidu_q3_mix', label: 'Vidu Q3-Mix', desc: 'Multi-ref positional, 1080p premium' },
  { value: 'wan_2_7', label: 'Wan 2.7', desc: 'Lip-sync VN driven audio (TTS)' },
];

export function StudioMainV5() {
  // ============ STATE — mirrors original StudioMain ============
  const [productUrl, setProductUrl] = useState('');
  const [productImg, setProductImg] = useState<string | null>(null);
  const [prompt, setPrompt] = useState('');

  const [referenceZones, setReferenceZones] = useState<ReferenceZonesValue>({
    images: [],
    roles: [],
    storyboardImages: [],
  });
  const referenceImages = referenceZones.images;
  const setReferenceImages = (next: string[]) => {
    const nextRoles = next.map((url) => {
      const idx = referenceZones.images.indexOf(url);
      return idx >= 0 ? referenceZones.roles[idx] : null;
    });
    const nextStoryboard = referenceZones.storyboardImages.filter((u) => next.includes(u));
    setReferenceZones({ images: next, roles: nextRoles, storyboardImages: nextStoryboard });
  };

  const [model, setModel] = useState<VideoModel>('seedance_2_0');
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>('9:16');
  const [resolution, setResolution] = useState<Resolution>(
    getModelConfig('seedance_2_0').resolution_default,
  );
  const [durationS, setDurationS] = useState(15);
  const [audioMode, setAudioMode] = useState<AudioMode>('silent_native');
  const [numShots, setNumShots] = useState<number | null>(null);

  const [context, setContext] = useState<ContextInjectionType>({});
  const [referenceVideos, setReferenceVideos] = useState<string[]>([]);
  const [nicheHint, setNicheHint] = useState<string>('auto');
  const [planRequest, setPlanRequest] = useState<Parameters<typeof DirectorPlanModal>[0]['initialRequest']>(null);
  const [showPlanModal, setShowPlanModal] = useState(false);

  const [directorJobId, setDirectorJobId] = useState<string | null>(null);
  const directorJob = useDirectorJobPoll(directorJobId);
  const [showResultModal, setShowResultModal] = useState(false);
  const isGenerating = Boolean(directorJobId) && (directorJob?.status as string) !== 'done' && (directorJob?.status as string) !== 'failed';

  const [showHistory, setShowHistory] = useState(false);
  const [showAssetLibrary, setShowAssetLibrary] = useState(false);
  const [, setForkedPlan] = useState<DirectorPlan | null>(null);
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);

  const modelConfig = getModelConfig(model);
  const modelMeta = MODEL_OPTIONS.find((o) => o.value === model);

  const { costCredits } = useMemo(() => {
    const videoCostUsd = modelConfig.cost_per_second_usd * durationS;
    const claudeCostUsd = 0.087;
    const audioCostUsd = audioMode === 'dialogue_vo' ? 0.01 : 0.1;
    const totalUsd = videoCostUsd + claudeCostUsd + audioCostUsd;
    return {
      costCredits: parseFloat((totalUsd * 5).toFixed(1)),
    };
  }, [modelConfig, durationS, audioMode]);

  const canSubmit = !!(prompt.trim() || productUrl || productImg);

  const handleModelChange = (newModel: VideoModel) => {
    setModel(newModel);
    const newConfig = getModelConfig(newModel);
    if (durationS > newConfig.max_duration_s) setDurationS(newConfig.max_duration_s);
    if (referenceImages.length > newConfig.max_references) {
      setReferenceImages(referenceImages.slice(0, newConfig.max_references));
    }
    if (!newConfig.resolution_options.includes(resolution)) {
      setResolution(newConfig.resolution_default);
    }
  };

  const handleSubmit = () => {
    if (!canSubmit) return;
    setPlanRequest({
      product_input: {
        url: productUrl || undefined,
        text_description: prompt || undefined,
        image_urls: productImg ? [productImg] : [],
      },
      reference_images: referenceImages,
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

  const handleAddReferences = () => {
    const inp = document.createElement('input');
    inp.type = 'file';
    inp.accept = 'image/*,video/*';
    inp.multiple = true;
    inp.onchange = async () => {
      const files = Array.from(inp.files || []);
      if (!files.length) return;
      const room = 3 - referenceImages.length;
      const accept = files.slice(0, Math.max(0, room));
      const dataUrls = await Promise.all(
        accept.map(
          (f) =>
            new Promise<string>((resolve) => {
              const r = new FileReader();
              r.onload = () => resolve(r.result as string);
              r.readAsDataURL(f);
            }),
        ),
      );
      setReferenceZones({
        images: [...referenceImages, ...dataUrls],
        roles: [...referenceZones.roles, ...new Array(dataUrls.length).fill(null)],
        storyboardImages: referenceZones.storyboardImages,
      });
    };
    inp.click();
  };

  return (
    <main className="flex-1 overflow-hidden relative bg-[#0a0a0c]">
      {/* Background — subtle purple radial like LumeFlow */}
      <div className="absolute top-0 left-1/3 w-[600px] h-[400px] bg-fuchsia-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute top-32 right-1/4 w-[400px] h-[400px] bg-purple-500/10 rounded-full blur-[120px] pointer-events-none" />

      {/* ============ TOP HEADER BAR ============ */}
      <header className="relative z-20 flex items-center justify-between px-6 py-3 border-b border-white/5 bg-black/40 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-fuchsia-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm">
            C
          </div>
          <h1 className="text-white text-base font-semibold">
            <span className="bg-gradient-to-r from-fuchsia-300 to-purple-400 bg-clip-text text-transparent">
              CineForge
            </span>
            <span className="text-white/40 mx-2">·</span>
            <span>Tạo video thành kịch bản, kịch bản thành video</span>
          </h1>
        </div>
        <div className="flex items-center gap-2">
          {/* Credit badge */}
          <a
            href="/pricing"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-purple-500/15 hover:bg-purple-500/25 border border-purple-400/30 transition text-sm"
          >
            <Database className="w-3.5 h-3.5 text-purple-300" />
            <span className="text-white font-medium">{costCredits.toFixed(1)}</span>
            <span className="text-purple-200/80 text-xs">|</span>
            <span className="text-purple-200 text-xs font-medium">nâng cấp</span>
            <RefreshCw className="w-3.5 h-3.5 text-purple-300/60" />
          </a>
          {/* Lang */}
          <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 transition text-sm text-white/80">
            <Globe className="w-3.5 h-3.5" /> Tiếng Việt
            <ChevronDown className="w-3 h-3 text-white/50" />
          </button>
          {/* Assets quick access */}
          <button
            onClick={() => setShowAssetLibrary(true)}
            title="Thư viện asset đã lưu (Character / Product / Storyboard)"
            className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 flex items-center justify-center text-white/70 transition"
          >
            <FolderArchive className="w-4 h-4" />
          </button>
          {/* History quick access */}
          <button
            onClick={() => setShowHistory(true)}
            title="Lịch sử dự án"
            className="w-9 h-9 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 flex items-center justify-center text-white/70 transition"
          >
            <Settings className="w-4 h-4" />
          </button>
          {/* Switch back to V3 */}
          <a
            href="/studio"
            title="Về giao diện gốc (V3)"
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 transition text-xs text-white/70"
          >
            V3
          </a>
          {/* Avatar */}
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-fuchsia-400 to-purple-600 flex items-center justify-center text-white font-bold text-sm">
            T
          </div>
        </div>
      </header>

      {/* ============ MAIN 2-COL ============ */}
      <div className="relative z-10 h-[calc(100%-3.5rem)] grid grid-cols-1 lg:grid-cols-[minmax(380px,440px)_1fr] gap-5 p-5 overflow-hidden">
        {/* ============ LEFT — INPUT CARD ============ */}
        <div className="overflow-y-auto pr-1 space-y-4 custom-scrollbar">
          {/* Model section */}
          <section>
            <div className="text-white/90 text-sm font-semibold mb-2">Model</div>
            <div className="relative">
              <button
                onClick={() => setModelDropdownOpen((v) => !v)}
                className="w-full flex items-start gap-3 p-3.5 rounded-2xl bg-white/[0.04] hover:bg-white/[0.06] border border-white/5 hover:border-fuchsia-400/30 transition text-left"
              >
                <div className="w-9 h-9 shrink-0 rounded-xl bg-gradient-to-br from-fuchsia-500/30 to-purple-600/30 border border-fuchsia-400/30 flex items-center justify-center">
                  <Sparkles className="w-4 h-4 text-fuchsia-300" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-white font-medium text-sm">{modelMeta?.label || model}</div>
                  <div className="text-white/50 text-xs leading-relaxed truncate">{modelMeta?.desc}</div>
                </div>
                <ChevronDown className={`w-4 h-4 text-white/40 shrink-0 mt-1 transition ${modelDropdownOpen ? 'rotate-180' : ''}`} />
              </button>
              {modelDropdownOpen && (
                <>
                  <div className="fixed inset-0 z-30" onClick={() => setModelDropdownOpen(false)} />
                  <div className="absolute top-full mt-1 left-0 right-0 z-40 rounded-2xl bg-[#15151a] border border-white/10 shadow-2xl shadow-fuchsia-500/10 overflow-hidden">
                    {MODEL_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => {
                          handleModelChange(opt.value);
                          setModelDropdownOpen(false);
                        }}
                        className={`w-full text-left px-3.5 py-2.5 transition ${
                          opt.value === model
                            ? 'bg-fuchsia-500/15'
                            : 'hover:bg-white/[0.04]'
                        }`}
                      >
                        <div className="text-white text-sm font-medium">{opt.label}</div>
                        <div className="text-white/50 text-xs">{opt.desc}</div>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          </section>

          {/* Upload zone */}
          <section>
            <div className="flex items-center justify-between mb-2">
              <div className="text-white/90 text-sm font-semibold">Tải hình ảnh / video lên</div>
              <div className="text-white/50 text-xs">{referenceImages.length} / 3</div>
            </div>
            <button
              onClick={handleAddReferences}
              className="w-full rounded-2xl bg-white/[0.03] hover:bg-white/[0.05] border-2 border-dashed border-white/15 hover:border-fuchsia-400/40 transition p-6 flex flex-col items-center justify-center gap-2 group"
            >
              <div className="w-10 h-10 rounded-xl bg-white/5 group-hover:bg-fuchsia-500/15 border border-white/10 group-hover:border-fuchsia-400/30 flex items-center justify-center transition">
                <ImgIcon className="w-5 h-5 text-white/60 group-hover:text-fuchsia-300" />
              </div>
              <div className="text-white/80 text-sm font-medium">Nhấn vào đây để tải lên</div>
              <div className="text-white/40 text-xs text-center leading-relaxed">
                Hỗ trợ JPG, PNG, WEBP, MP4 · ≤10 MB · kích thước tối thiểu 300×300
              </div>
            </button>

            {/* Suggested refs row (placeholder for asset library quick pick) */}
            {referenceImages.length === 0 && (
              <div className="mt-3 flex items-center gap-2">
                <span className="text-white/40 text-xs shrink-0">gợi ý:</span>
                <div className="flex-1 flex items-center gap-1.5 overflow-x-auto">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <button
                      key={i}
                      onClick={() => setShowAssetLibrary(true)}
                      className="w-10 h-10 shrink-0 rounded-lg bg-gradient-to-br from-white/5 to-white/[0.02] border border-white/10 hover:border-fuchsia-400/30 transition flex items-center justify-center text-white/30 text-xs"
                      title="Mở Asset Library"
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => setShowAssetLibrary(true)}
                  title="Mở Asset Library"
                  className="w-7 h-7 shrink-0 rounded-md bg-white/5 hover:bg-white/10 border border-white/10 flex items-center justify-center text-white/60"
                >
                  <RefreshCw className="w-3 h-3" />
                </button>
              </div>
            )}

            {/* Active refs thumbnails */}
            {referenceImages.length > 0 && (
              <div className="mt-3 grid grid-cols-3 gap-2">
                {referenceImages.slice(0, 3).map((url, i) => (
                  <div key={i} className="relative aspect-square rounded-lg overflow-hidden bg-black border border-white/10 group">
                    <img src={url} alt={`ref ${i + 1}`} className="absolute inset-0 w-full h-full object-cover" />
                    <button
                      onClick={() => setReferenceImages(referenceImages.filter((_, k) => k !== i))}
                      className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/70 text-white text-xs opacity-0 group-hover:opacity-100 transition"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Advanced panel — reuse from /studio */}
          <AdvancedPanel
            filledCount={
              (productUrl ? 1 : 0) +
              (productImg ? 1 : 0) +
              (nicheHint !== 'auto' ? 1 : 0) +
              (referenceVideos.length > 0 ? 1 : 0) +
              (context.pain_points || context.real_reviews || context.usps ? 1 : 0)
            }
          >
            <div className="space-y-2 text-xs text-white/80">
              <label className="flex items-center gap-2">
                <span className="text-white/50 w-16">Niche</span>
                <select
                  value={nicheHint}
                  onChange={(e) => setNicheHint(e.target.value)}
                  className="flex-1 bg-white/5 border border-white/10 rounded-md px-2 py-1.5"
                >
                  <option value="auto">Auto-detect</option>
                  <option value="beauty_skincare">Beauty & Skincare</option>
                  <option value="shopee_general">Shopee General</option>
                  <option value="supplement_health">Supplement</option>
                  <option value="tech_gadget">Tech & Gadget</option>
                  <option value="fashion_apparel">Fashion</option>
                  <option value="food_beverage">Food & Beverage</option>
                </select>
              </label>
              <label className="flex items-center gap-2">
                <span className="text-white/50 w-16">Clone</span>
                <input
                  value={referenceVideos[0] || ''}
                  onChange={(e) => setReferenceVideos(e.target.value ? [e.target.value] : [])}
                  placeholder="URL TikTok/Reel viral (optional)"
                  className="flex-1 bg-white/5 border border-white/10 rounded-md px-2 py-1.5 placeholder:text-white/30"
                />
              </label>
              <label className="flex items-center gap-2">
                <span className="text-white/50 w-16">Sản phẩm</span>
                <div className="relative flex-1">
                  <Link2 className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-white/40" />
                  <input
                    value={productUrl}
                    onChange={(e) => setProductUrl(e.target.value)}
                    placeholder="URL Shopee/Lazada/Tiki"
                    className="w-full pl-6 pr-2 py-1.5 bg-white/5 border border-white/10 rounded-md placeholder:text-white/30"
                  />
                </div>
              </label>
              <ContextInjection value={context} onChange={setContext} />
              <ReferenceZones value={referenceZones} onChange={setReferenceZones} />
            </div>
          </AdvancedPanel>

          {/* Prompt — LumeFlow style "Lời nhắc" */}
          <section>
            <div className="text-white/90 text-sm font-semibold mb-2">Lời nhắc</div>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Mô tả video bạn muốn tạo (idea + sản phẩm + tone)…"
              rows={4}
              className="w-full bg-white/[0.04] hover:bg-white/[0.05] focus:bg-white/[0.06] border border-white/10 hover:border-white/20 focus:border-fuchsia-400/40 rounded-2xl px-4 py-3 text-sm text-white placeholder:text-white/30 resize-none outline-none transition"
            />
          </section>

          {/* Credit & unlock */}
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1.5 text-white/60">
              <Sparkles className="w-3 h-3 text-fuchsia-300" />
              Yêu cầu tín chỉ: <span className="text-white font-bold">{costCredits.toFixed(1)}</span>
            </div>
            <a href="/pricing" className="flex items-center gap-1 text-amber-300 hover:text-amber-200 font-medium">
              Mở khóa tạo không giới hạn
              <ArrowUp className="w-3 h-3 rotate-45" />
            </a>
          </div>

          {/* PRIMARY CTA — Tạo kế hoạch video */}
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || isGenerating}
            title={
              isGenerating
                ? 'Đang render...'
                : !canSubmit
                  ? 'Nhập lời nhắc hoặc upload sản phẩm để tiếp tục'
                  : 'Mở Plan Review (Continuity Bible + Shot List) trước khi render'
            }
            className="w-full py-3.5 rounded-2xl bg-gradient-to-r from-fuchsia-500 via-purple-500 to-purple-600 hover:from-fuchsia-400 hover:via-purple-400 hover:to-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold text-base shadow-xl shadow-fuchsia-500/20 hover:shadow-fuchsia-500/40 transition-all hover:scale-[1.01] disabled:hover:scale-100 flex items-center justify-center gap-2"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Đang xử lý…
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" /> Tạo kế hoạch video
              </>
            )}
          </button>

          {/* Bottom info bar */}
          <div className="text-[11px] text-white/40 text-center">
            {modelConfig.name_vn} · {durationS}s · {aspectRatio} · {resolution}
          </div>
        </div>

        {/* ============ RIGHT — INSPIRATION / HISTORY ============ */}
        <div className="overflow-hidden">
          <InspirationPanelV5 />
        </div>
      </div>

      {/* ============ MODALS (reused from V3) ============ */}
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
        onClose={() => {
          setShowPlanModal(false);
          setPlanRequest(null);
        }}
        onJobStarted={(jobId) => {
          setDirectorJobId(jobId);
          setShowResultModal(true);
        }}
      />

      {showResultModal && (
        <JobResultModal
          status={directorJob as any}
          error={(directorJob?.error_message as string | undefined) ?? null}
          onClose={() => {
            setShowResultModal(false);
            const s = directorJob?.status as string | undefined;
            if (s === 'done' || s === 'failed' || s === 'cancelled') setDirectorJobId(null);
          }}
          onCancel={() => {
            if (directorJobId) {
              fetch(`/api/v1/director/jobs/${directorJobId}/cancel`, { method: 'POST' }).catch(() => {});
            }
            setShowResultModal(false);
          }}
        />
      )}

      <ProjectHistoryDrawer
        open={showHistory}
        onClose={() => setShowHistory(false)}
        onFork={(plan) => {
          const cb = plan.continuity_bible;
          setPrompt(cb.logline || cb.title);
          setDurationS(cb.duration_s);
          setAspectRatio((cb.aspect_ratio as AspectRatio) || '9:16');
          setForkedPlan(plan);
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

      <AssetLibrary
        open={showAssetLibrary}
        onClose={() => setShowAssetLibrary(false)}
        onPick={(picked) => {
          const newImages = [...referenceZones.images];
          const newRoles = [...referenceZones.roles];
          for (const a of picked) {
            if (!newImages.includes(a.image_url)) {
              newImages.push(a.image_url);
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
