'use client';

import { useState, useRef } from 'react';
import {
  Plus,
  ChevronDown,
  ArrowUp,
  Infinity as InfinityIcon,
  X,
  Image as ImgIcon,
  Loader2,
  Sparkles,
  Diamond,
} from 'lucide-react';
import { MODEL_CONFIGS, getModelConfig } from '@/lib/studio/model-config';
import type { VideoModel, AspectRatio, AudioMode } from '@/lib/types/backend';
import {
  insertMentionAtCursor,
  stripAndReindexAfterRemoval,
  splitPromptSegments,
} from '@/lib/studio/parse-image-mentions';

// Resolution loose string — options dynamic per model (xem MODEL_CONFIGS[model].resolution_options)
type Resolution = string;

interface VideoAgentCardProps {
  // Input
  prompt: string;
  onPromptChange: (v: string) => void;

  // References
  referenceImages: string[];
  onReferenceImagesChange: (imgs: string[]) => void;

  // Settings
  model: VideoModel;
  onModelChange: (m: VideoModel) => void;
  aspectRatio: AspectRatio;
  onAspectRatioChange: (a: AspectRatio) => void;
  resolution: Resolution;
  onResolutionChange: (r: Resolution) => void;
  durationS: number;
  onDurationChange: (d: number) => void;
  audioMode: AudioMode;
  onAudioModeChange: (a: AudioMode) => void;
  // V3.1 — num_shots override (chỉ Seedance 2.0/Fast)
  numShots?: number | null;
  onNumShotsChange?: (n: number | null) => void;

  // Action
  costVnd: number;
  costCredits: number;
  isGenerating: boolean;
  jobProgress?: number;
  canSubmit: boolean;
  onSubmit: () => void;
}

const MODEL_OPTIONS: { value: VideoModel; label: string }[] = [
  { value: 'auto', label: '✨ Auto (AI chọn)' },
  { value: 'vidu_q3', label: 'Vidu Q3' },
  { value: 'vidu_q3_mix', label: 'Vidu Q3-Mix' },
  { value: 'wan_2_7', label: 'Wan 2.7' },
  { value: 'seedance_1_5_pro', label: 'Seedance 1.5 Pro' },
  { value: 'seedance_2_0', label: 'Seedance 2.0' },
  { value: 'seedance_2_0_fast', label: 'Seedance 2.0 Fast' },
];

const ASPECT_OPTIONS: AspectRatio[] = ['9:16', '16:9', '1:1'];
// Resolution options now dynamic — read from getModelConfig(model).resolution_options inside component

const AUDIO_OPTIONS: { value: AudioMode; label: string }[] = [
  { value: 'silent_native', label: '🔇 Câm + ASMR' },
  { value: 'dialogue_vo', label: '🎤 Lồng tiếng VN' },
  { value: 'asmr_macro', label: '🔉 ASMR Macro' },
];

// Mini dropdown reusable component
function MiniDropdown<T extends string | number>({
  value,
  options,
  onChange,
  formatLabel,
  prefix,
}: {
  value: T;
  options: T[] | { value: T; label: string }[];
  onChange: (v: T) => void;
  formatLabel?: (v: T) => string;
  prefix?: JSX.Element;
}) {
  const [open, setOpen] = useState(false);
  const opts =
    typeof options[0] === 'object' && 'value' in (options[0] as any)
      ? (options as { value: T; label: string }[])
      : (options as T[]).map((v) => ({ value: v, label: formatLabel ? formatLabel(v) : String(v) }));

  const currentLabel = opts.find((o) => o.value === value)?.label ?? String(value);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-bg-soft hover:bg-bg-hover border border-border hover:border-brand-600/50 text-xs text-text transition"
      >
        {prefix}
        <span className="font-medium">{currentLabel}</span>
        <ChevronDown className="w-3 h-3 text-text-subtle" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full mb-1 left-0 z-20 min-w-[140px] rounded-lg bg-bg-card border border-border shadow-xl overflow-hidden">
            {opts.map((o) => (
              <button
                key={String(o.value)}
                onClick={() => {
                  onChange(o.value);
                  setOpen(false);
                }}
                className={`w-full text-left px-3 py-1.5 text-xs transition ${
                  o.value === value
                    ? 'bg-brand-700/20 text-brand-200'
                    : 'text-text-muted hover:bg-bg-hover hover:text-text'
                }`}
              >
                {o.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

export function VideoAgentCard({
  prompt,
  onPromptChange,
  referenceImages,
  onReferenceImagesChange,
  model,
  onModelChange,
  aspectRatio,
  onAspectRatioChange,
  resolution,
  onResolutionChange,
  durationS,
  onDurationChange,
  audioMode,
  onAudioModeChange,
  numShots,
  onNumShotsChange,
  costVnd,
  costCredits,
  isGenerating,
  jobProgress = 0,
  canSubmit,
  onSubmit,
}: VideoAgentCardProps) {
  const config = getModelConfig(model);
  const maxRefs = Math.min(config.max_references, 5); // UI cap 5 like Topview
  const [refExpanded, setRefExpanded] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Insert [Image N] mention(s) vào prompt tại cursor — TopView V2 pattern
  const insertMentions = (firstNewIdx0: number, count: number) => {
    let curPrompt = prompt;
    let cursor = textareaRef.current?.selectionStart ?? prompt.length;
    for (let i = 0; i < count; i++) {
      const idx1 = firstNewIdx0 + i + 1;
      const r = insertMentionAtCursor(curPrompt, idx1, cursor);
      curPrompt = r.newPrompt;
      cursor = r.newCursorPos;
    }
    onPromptChange(curPrompt);
    // Restore cursor sau React re-render
    requestAnimationFrame(() => {
      const ta = textareaRef.current;
      if (ta) {
        ta.focus();
        ta.setSelectionRange(cursor, cursor);
      }
    });
  };

  const handleAddReference = () => {
    const inp = document.createElement('input');
    inp.type = 'file';
    inp.accept = 'image/*';
    inp.multiple = true;
    inp.onchange = async () => {
      const files = Array.from(inp.files || []);
      const remaining = maxRefs - referenceImages.length;
      const filesToAdd = files.slice(0, remaining);
      const dataUrls = await Promise.all(
        filesToAdd.map(
          (f) =>
            new Promise<string>((resolve) => {
              const r = new FileReader();
              r.onload = () => resolve(r.result as string);
              r.readAsDataURL(f);
            }),
        ),
      );
      const firstNewIdx0 = referenceImages.length;
      onReferenceImagesChange([...referenceImages, ...dataUrls]);
      // Auto insert [Image N] vào prompt tại cursor
      if (dataUrls.length > 0) {
        insertMentions(firstNewIdx0, dataUrls.length);
      }
    };
    inp.click();
  };

  const handleRemoveRef = (i: number) => {
    onReferenceImagesChange(referenceImages.filter((_, idx) => idx !== i));
    // Strip [Image N] khỏi prompt + re-index các mention >N
    onPromptChange(stripAndReindexAfterRemoval(prompt, i));
  };

  // Segments để render overlay chip highlight
  const segments = splitPromptSegments(prompt);
  const totalMentions = segments.filter((s) => s.type === 'mention').length;

  // Duration options based on model max
  const durationOptions = [5, 10, 15, 16].filter((d) => d <= config.max_duration_s);

  return (
    <div className="rounded-2xl bg-bg-card border border-border hover:border-brand-700/30 transition backdrop-blur-sm overflow-hidden">
      {/* Header — Sprint5 UX: rebrand to CineForge Director V3 */}
      <div className="px-4 pt-3 pb-2 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-brand-300" />
          <span className="text-text text-sm font-semibold">CineForge Director</span>
          <span className="px-1.5 py-0.5 rounded bg-brand-700/20 text-brand-200 text-[10px] font-bold">
            V3
          </span>
        </div>
        <span
          className="text-[10px] text-text-subtle hidden sm:inline"
          title="Submit sẽ mở Plan Review (Continuity Bible + Shot List) trước khi render — không gen video thẳng"
        >
          Human-in-the-Loop · Plan → Review → Render
        </span>
      </div>

      {/* V3.1 — Per-model reference hint banner */}
      {config.reference_hint_vn && (
        <div className="mx-4 mt-3 px-3 py-2 rounded-lg border border-amber-500/30 bg-amber-500/[0.04] text-[11px] text-amber-200/90 leading-relaxed">
          {config.reference_hint_vn}
        </div>
      )}

      {/* Body — Reference left + Prompt right */}
      <div className="px-4 py-4">
        <div className="flex gap-3">
          {/* Reference slot */}
          <div className="shrink-0">
            <button
              onClick={() => (referenceImages.length > 0 ? setRefExpanded(!refExpanded) : handleAddReference())}
              className="relative w-24 h-24 rounded-xl border border-border bg-bg-soft hover:bg-bg-hover hover:border-brand-600/50 transition group flex flex-col items-center justify-center text-text-subtle hover:text-text"
            >
              {referenceImages.length > 0 ? (
                <>
                  <img
                    src={referenceImages[0]}
                    alt="Ref"
                    className="absolute inset-0 w-full h-full object-cover rounded-xl"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent rounded-xl" />
                  <div className="absolute bottom-1 left-1 right-1 text-[10px] text-white/90 font-medium text-center">
                    {referenceImages.length} / {maxRefs} refs
                  </div>
                </>
              ) : (
                <>
                  <Plus className="w-5 h-5 mb-1" />
                  <span className="text-[10px] font-medium">Reference</span>
                </>
              )}
            </button>
          </div>

          {/* Prompt textarea + mention tags info banner (TopView V2 [Image N] pattern) */}
          <div className="flex-1 min-h-[96px] flex flex-col">
            <textarea
              ref={textareaRef}
              value={prompt}
              onChange={(e) => onPromptChange(e.target.value)}
              placeholder={`Mô tả ý tưởng — nhớ ĐẶT TỪ KHOÁ cạnh ảnh để AI hiểu đúng role:\n\n  ✓ "Mẹ trẻ unbox sản phẩm [Image 1], cô gái [Image 2] cười tươi"\n      → AI hiểu Image 1 = sản phẩm, Image 2 = nhân vật\n\n  ✗ "[Image 1] [Image 2]"  ← thiếu context, AI phải đoán mò\n\nTừ khoá gợi ý: "sản phẩm/blush/hộp/kem" (= product) · "cô gái/influencer/anh/she" (= nhân vật) · "phòng/café/bedroom" (= scene)`}
              rows={5}
              className="flex-1 w-full bg-transparent text-sm text-text placeholder:text-text-subtle focus:outline-none resize-none leading-relaxed"
            />
            {/* Mention chips bar — show below textarea khi có [Image N] trong prompt */}
            {totalMentions > 0 && (
              <div className="flex items-center gap-1.5 mt-1.5 flex-wrap text-[10px]">
                <span className="text-text-subtle">Mentions:</span>
                {segments
                  .filter((s) => s.type === 'mention')
                  .map((s, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-brand-700/30 border border-brand-500/40 text-brand-100 font-medium"
                    >
                      📷 Image {s.imageIndex}
                    </span>
                  ))}
              </div>
            )}
          </div>
        </div>

        {/* Reference thumbnails expanded inline */}
        {refExpanded && referenceImages.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border">
            <div className="text-[10px] text-text-subtle uppercase tracking-wider mb-2">
              References ({referenceImages.length}/{maxRefs})
            </div>
            <div className="flex gap-2 flex-wrap">
              {referenceImages.map((img, i) => (
                <div key={i} className="relative w-14 h-14 group">
                  <img src={img} alt={`Ref ${i + 1}`} className="w-full h-full object-cover rounded-md border border-border" />
                  <span className="absolute top-0.5 left-0.5 px-1 py-0 rounded bg-black/70 text-white text-[8px] font-bold">
                    Image {i + 1}
                  </span>
                  {/* Click thumbnail → insert mention vào prompt tại cursor */}
                  <button
                    onClick={() => insertMentions(i, 1)}
                    title={`Insert [Image ${i + 1}] vào prompt`}
                    className="absolute inset-0 rounded-md hover:bg-brand-500/20 hover:border-brand-400 transition"
                  />
                  <button
                    onClick={() => handleRemoveRef(i)}
                    className="absolute top-0.5 right-0.5 w-4 h-4 rounded-full bg-black/70 text-white opacity-0 group-hover:opacity-100 hover:bg-red-500 transition flex items-center justify-center z-10"
                  >
                    <X className="w-2 h-2" />
                  </button>
                </div>
              ))}
              {referenceImages.length < maxRefs && (
                <button
                  onClick={handleAddReference}
                  className="w-14 h-14 rounded-md border-2 border-dashed border-border hover:border-brand-600/50 hover:bg-bg-soft transition flex items-center justify-center text-text-subtle hover:text-text"
                >
                  <Plus className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Try Unlimited (top right floating) */}
      <div className="absolute top-3 right-4 z-10 hidden lg:block">
        {/* Empty placeholder - we'll add inline below */}
      </div>

      {/* Bottom row — Dropdowns + Cost + Submit */}
      <div className="px-4 py-3 border-t border-border flex items-center gap-1.5 flex-wrap">
        {/* Model — Sprint5 UX: tooltip explains Auto picker rule */}
        <div
          title={
            model === 'auto'
              ? 'Auto: AI tự chọn model tối ưu dựa trên kịch bản (số shots, dialogue lip-sync, số refs, budget tier). Xem rule chi tiết trong backend agent/model_picker.py'
              : 'Chọn model render — Auto khuyến nghị nếu không chắc'
          }
        >
          <MiniDropdown<VideoModel>
            value={model}
            options={MODEL_OPTIONS}
            onChange={onModelChange}
          />
        </div>

        {/* Aspect Ratio */}
        <MiniDropdown<AspectRatio>
          value={aspectRatio}
          options={ASPECT_OPTIONS}
          onChange={onAspectRatioChange}
          prefix={<span className="text-white/50 text-[10px]">▭</span>}
        />

        {/* Resolution — dynamic per model (vd vidu_q3 chỉ có 540p/720p/1080p) */}
        <MiniDropdown<Resolution>
          value={resolution}
          options={getModelConfig(model).resolution_options}
          onChange={onResolutionChange}
        />

        {/* Duration */}
        <MiniDropdown<number>
          value={durationS}
          options={durationOptions}
          formatLabel={(v) => `${v}s`}
          onChange={onDurationChange}
          prefix={<span className="text-white/50 text-[10px]">⏱</span>}
        />

        {/* Audio Mode */}
        <MiniDropdown<AudioMode>
          value={audioMode}
          options={AUDIO_OPTIONS}
          onChange={onAudioModeChange}
        />

        {/* V3.1 — num_shots dropdown (chỉ Seedance 2.0/Fast support) */}
        {getModelConfig(model).supports_num_shots_override && onNumShotsChange && (
          <MiniDropdown<number>
            value={numShots ?? 0}
            options={(() => {
              const range = getModelConfig(model).num_shots_range ?? [2, 5];
              const [min, max] = range;
              const opts = [0];  // 0 = Auto
              for (let i = min; i <= max; i++) opts.push(i);
              return opts;
            })()}
            formatLabel={(v) => (v === 0 ? '🎬 Auto shots' : `🎬 ${v} shots`)}
            onChange={(v) => onNumShotsChange(v === 0 ? null : v)}
          />
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Try Unlimited link */}
        <a
          href="/pricing"
          className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-xs transition"
        >
          <InfinityIcon className="w-3 h-3" />
          <span className="font-medium">Try Unlimited</span>
        </a>

        {/* Cost + Submit */}
        <div className="flex items-center gap-2 ml-1">
          <div className="flex items-center gap-1 text-xs text-text-muted">
            <Diamond className="w-3 h-3 text-brand-300" />
            <span className="font-bold text-text">{costCredits.toFixed(1)}</span>
          </div>
          <button
            onClick={onSubmit}
            disabled={!canSubmit || isGenerating}
            title={
              isGenerating
                ? 'Đang render...'
                : !canSubmit
                  ? 'Nhập brief hoặc upload sản phẩm để tiếp tục'
                  : 'Tạo kế hoạch video — mở Plan Review (Continuity Bible + Shot List) trước khi render'
            }
            className="w-8 h-8 rounded-lg bg-brand-600 hover:bg-brand-500 disabled:opacity-40 disabled:cursor-not-allowed text-white flex items-center justify-center transition shadow-md shadow-brand-600/40 hover:scale-105 disabled:hover:scale-100"
          >
            {isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowUp className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Progress bar khi generating */}
      {isGenerating && (
        <div className="h-1 bg-bg-soft">
          <div
            className="h-full bg-gradient-to-r from-brand-500 to-fuchsia-500 transition-all duration-500"
            style={{ width: `${jobProgress}%` }}
          />
        </div>
      )}

      {/* Footer info — cost VND realtime + duration */}
      <div className="px-4 py-2 border-t border-border flex items-center justify-between text-[10px] text-text-subtle">
        <span>
          {config.name_vn} · Max {config.max_references} refs · {config.syntax_style.slice(0, 50)}
          {config.syntax_style.length > 50 ? '...' : ''}
        </span>
        <span className="text-brand-300 font-medium">
          ~{costVnd.toLocaleString('vi-VN')}đ · ~2-4 phút
        </span>
      </div>
    </div>
  );
}
