'use client';
/**
 * PromptCardV2 — Topview-style "Video Agent" compact input.
 *
 * Layout:
 *   [+ Reference button] [BIG TEXTAREA with @mention placeholder]
 *   [Model ▾] [Aspect ▾] [Resolution ▾] [Duration ▾] [Quality chip] [Submit →]
 *
 * All settings live INSIDE the input card — no sticky sidebar. Matches the
 * "Plan any-length videos with AI assistant and references" UX from Topview.
 */
import { useRef } from 'react';
import {
  ArrowUp, Loader2, Plus, Sparkles, ChevronDown, Image as ImageIcon, Wand2,
} from 'lucide-react';
import { MODEL_CONFIGS, getModelConfig } from '@/lib/studio/model-config';
import type { VideoModel, AspectRatio, AudioMode } from '@/lib/types/backend';

interface Props {
  // Input
  brief: string;
  onBrief: (v: string) => void;

  // Reference (collapsed access — caller wires drawer)
  referenceCount: number;
  onOpenReferences: () => void;

  // Settings
  model: VideoModel;
  onModel: (m: VideoModel) => void;
  aspect: AspectRatio;
  onAspect: (a: AspectRatio) => void;
  resolution: string;
  onResolution: (r: string) => void;
  duration: number;
  onDuration: (d: number) => void;
  audioMode: AudioMode;
  onAudioMode: (a: AudioMode) => void;

  // V5.16 #2 — Number of shots picker (Auto = let Director decide, 1-5 = override)
  numShots: number | null;
  onNumShots: (n: number | null) => void;

  // V5.16 #1 — Master Storyboard Board toggle (auto $0.04 identity anchor)
  masterBoardEnabled: boolean;
  onMasterBoardEnabled: (v: boolean) => void;

  // Quality estimate (0-10) — shown as chip like Topview's 7.5 score
  qualityScore?: number;

  // Cost preview
  estimatedCostUsd: number;

  // Submit
  onSubmit: () => void;
  isLoading?: boolean;
  disabled?: boolean;

  // V5.2 — Magic enhance ✨
  onEnhance?: () => void;
  isEnhancing?: boolean;
}

// V5.7 — aspect dropdown now built dynamically per model from cfg.aspect_ratio_options
// (was: hardcoded to 3 values, hiding 40% of BE-supported aspects).

const DURATION_OPTIONS_DEFAULT = [5, 8, 10, 15, 20, 30, 45, 60];
const AUDIO_LABELS: Record<AudioMode, string> = {
  silent_native: 'Silent',
  dialogue_vo: 'Voice VN',
  asmr_macro: 'ASMR',
};

// V5.16 — Models eligible for Master Storyboard Board ($0.04 9-panel anchor).
// Synced with backend scene_generation_agent.py `is_seedance_ref_for_board` check
// and DirectorPlanModal's auto-trigger condition.
const MASTER_BOARD_MODELS = new Set<VideoModel>(['auto', 'seedance_2_0', 'seedance_2_0_fast']);

// V5.16 — Max shots per model (vendor hard limit). Used by numShots picker.
// auto/seedance_2_0/seedance_2_0_fast → 6 (Strategy A cap), seedance_1_5_pro → 4
// (Strategy B cap), vidu_q3/vidu_q3_mix/wan_2_7 → 5 (per-shot chain practical cap).
const MAX_SHOTS_PER_MODEL: Record<VideoModel, number> = {
  auto: 6,
  seedance_2_0: 6,
  seedance_2_0_fast: 6,
  seedance_1_5_pro: 4,
  vidu_q3: 5,
  vidu_q3_mix: 5,
  wan_2_7: 5,
};

export function PromptCardV2({
  brief, onBrief,
  referenceCount, onOpenReferences,
  model, onModel,
  aspect, onAspect,
  resolution, onResolution,
  duration, onDuration,
  audioMode, onAudioMode,
  numShots, onNumShots,
  masterBoardEnabled, onMasterBoardEnabled,
  qualityScore,
  estimatedCostUsd,
  onSubmit,
  isLoading, disabled,
  onEnhance, isEnhancing,
}: Props) {
  const cfg = getModelConfig(model);
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  // Available durations — respect discrete model constraints
  const durations = cfg.duration_discrete
    ?? DURATION_OPTIONS_DEFAULT.filter((d) => d <= cfg.max_duration_s);

  // V5.7 — dynamic aspect dropdown from current model. Wan 2.7 i2v returns [].
  const aspectOptions = cfg.aspect_ratio_options ?? ['9:16', '16:9', '1:1'];

  // V5.16 — derived: is current model eligible for Master Board?
  const masterBoardEligible = MASTER_BOARD_MODELS.has(model);
  const maxShots = MAX_SHOTS_PER_MODEL[model] ?? 5;
  const numShotsOptions = Array.from({ length: maxShots }, (_, i) => i + 1);

  // V5.1 — Vidu Q3 has a vendor-side prompt cap (~1000 chars) and the backend
  // silently truncates anything past it. Warn the user in the brief area when
  // they're getting close so they don't lose intent.
  const isViduModel = model === 'vidu_q3' || model === 'vidu_q3_mix';
  const PROMPT_SOFT_LIMIT = 1000;
  const briefLength = brief.length;
  const briefOverLimit = isViduModel && briefLength > PROMPT_SOFT_LIMIT;
  const briefNearLimit = isViduModel && briefLength > PROMPT_SOFT_LIMIT * 0.85;

  return (
    // AUDIT FIX: overflow-hidden + backdrop-blur creates a stacking context
    // that clips native <select> dropdown popup on some Chromium combos.
    // Use overflow-visible — glass-card border-radius still clips children
    // visually but lets dropdowns escape.
    <div className="glass-card p-0 overflow-visible">
      {/* Tab strip header (Topview "Video Agent V2") */}
      <div className="px-5 pt-4 pb-2 flex items-center justify-between border-b border-hairline">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold">Video Agent</span>
          <span className="chip text-[10px]">V2</span>
        </div>
        <div className="flex items-center gap-2">
          {typeof qualityScore === 'number' && (
            <span className={`chip text-[10px] ${
              qualityScore >= 8 ? 'border-accent-green/40 text-accent-green'
              : qualityScore >= 6 ? 'border-accent-yellow/40 text-accent-yellow'
              : 'border-accent-orange/40 text-accent-orange'
            }`}>
              <Sparkles size={10} /> {qualityScore.toFixed(1)}
            </span>
          )}
          <span className="text-[11px] text-text-subtle">
            ~${estimatedCostUsd.toFixed(2)}
          </span>
        </div>
      </div>

      {/* Reference button + main textarea row */}
      <div className="px-4 py-4 flex items-start gap-3">
        <button
          onClick={onOpenReferences}
          className="shrink-0 w-16 h-16 rounded-card border border-dashed border-hairline-strong
                     hover:border-accent-magenta/60 hover:bg-surface-3
                     flex flex-col items-center justify-center transition group"
          title="Add references"
        >
          {referenceCount > 0 ? (
            <>
              <ImageIcon size={16} className="text-accent-magenta" />
              <span className="text-[10px] font-semibold text-text mt-0.5">
                {referenceCount}
              </span>
            </>
          ) : (
            <>
              <Plus size={18} className="text-text-muted group-hover:text-text" />
              <span className="text-[10px] text-text-subtle mt-0.5 group-hover:text-text">
                Reference
              </span>
            </>
          )}
        </button>

        <div className="flex-1 flex flex-col min-w-0">
          <textarea
            ref={taRef}
            value={brief}
            onChange={(e) => onBrief(e.target.value)}
            rows={3}
            disabled={disabled}
            className="field-bare resize-none flex-1 text-[14px] leading-relaxed min-h-[68px]"
            placeholder={
              'Plan any-length videos with AI assistant and references.\n'
              + 'Upload 1-12 reference images or videos and @mention to create interactions. '
              + 'Example: Use @Image 1 as the first frame, @Image 2 as the last frame, and have them dance like the moves in @Video 1.'
            }
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && !disabled) onSubmit();
            }}
          />
          {/* V5.1 — Vidu Q3 / Q3-Mix prompt cap warning */}
          {isViduModel && briefNearLimit && (
            <div className={`mt-1.5 text-[11px] flex items-center gap-1 ${
              briefOverLimit ? 'text-accent-orange' : 'text-accent-yellow'
            }`}>
              <span className="font-mono">{briefLength}/{PROMPT_SOFT_LIMIT}</span>
              <span>
                {briefOverLimit
                  ? `· Vidu sẽ truncate brief — rút gọn dưới ${PROMPT_SOFT_LIMIT} chars`
                  : `· Gần Vidu prompt limit ${PROMPT_SOFT_LIMIT} chars`}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Settings inline footer (Topview pattern) */}
      <div className="px-4 pb-4 flex items-center gap-2 flex-wrap">
        <SettingPill icon={ChevronDown}>
          <select
            value={model}
            onChange={(e) => onModel(e.target.value as VideoModel)}
            className="bg-transparent outline-none text-xs font-medium pr-1"
          >
            {Object.values(MODEL_CONFIGS).map((m) => (
              <option key={m.id} value={m.id}>
                {m.name_short} · ${m.cost_per_second_usd}/s
              </option>
            ))}
          </select>
        </SettingPill>

        {aspectOptions.length > 0 && (
          <SettingPill icon={ChevronDown} label="aspect">
            <select
              value={aspectOptions.includes(aspect) ? aspect : aspectOptions[0]}
              onChange={(e) => onAspect(e.target.value as AspectRatio)}
              className="bg-transparent outline-none text-xs font-medium pr-1"
            >
              {aspectOptions.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </SettingPill>
        )}

        <SettingPill icon={ChevronDown} label="res">
          <select
            value={resolution}
            onChange={(e) => onResolution(e.target.value)}
            className="bg-transparent outline-none text-xs font-medium pr-1"
          >
            {cfg.resolution_options.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </SettingPill>

        <SettingPill icon={ChevronDown} label="duration">
          <select
            value={duration}
            onChange={(e) => onDuration(Number(e.target.value))}
            className="bg-transparent outline-none text-xs font-medium pr-1"
          >
            {durations.map((d) => <option key={d} value={d}>{d}s</option>)}
          </select>
        </SettingPill>

        <SettingPill icon={ChevronDown} label="audio">
          <select
            value={audioMode}
            onChange={(e) => onAudioMode(e.target.value as AudioMode)}
            className="bg-transparent outline-none text-xs font-medium pr-1"
          >
            {(Object.keys(AUDIO_LABELS) as AudioMode[]).map((m) => (
              <option key={m} value={m}>{AUDIO_LABELS[m]}</option>
            ))}
          </select>
        </SettingPill>

        {/* V5.16 #2 — Number of shots picker. Auto = let Director decide. */}
        <SettingPill icon={ChevronDown} label="shots">
          <select
            value={numShots ?? ''}
            onChange={(e) => onNumShots(e.target.value ? Number(e.target.value) : null)}
            className="bg-transparent outline-none text-xs font-medium pr-1"
            title="Số cảnh trong video. Auto = AI tự quyết. Max cap theo model."
          >
            <option value="">Auto</option>
            {numShotsOptions.map((n) => (
              <option key={n} value={n}>{n} cảnh</option>
            ))}
          </select>
        </SettingPill>

        {/* V5.16 #1 — Master Storyboard Board toggle. Disabled for models that
            don't support multi-ref (Wan i2v, Seedance 1.5 Pro). $0.04 surcharge. */}
        <button
          onClick={() => masterBoardEligible && onMasterBoardEnabled(!masterBoardEnabled)}
          disabled={!masterBoardEligible}
          title={
            masterBoardEligible
              ? `${masterBoardEnabled ? 'Tắt' : 'Bật'} Master Board (identity anchor $0.04). Lock nhân vật giữa các cảnh.`
              : `${model} chỉ nhận 1 ảnh ref — Master Board không apply.`
          }
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-pill border text-xs font-medium transition ${
            !masterBoardEligible
              ? 'border-hairline bg-surface-2/30 text-text-subtle/50 cursor-not-allowed'
              : masterBoardEnabled
                ? 'border-accent-magenta/40 bg-accent-magenta/10 text-accent-magenta'
                : 'border-hairline bg-surface-2/60 hover:bg-surface-3 text-text-muted'
          }`}
        >
          <span className="text-[10px] text-text-subtle">board</span>
          <span>{masterBoardEnabled && masterBoardEligible ? '✓ ON' : 'OFF'}</span>
          <span className="text-[10px] text-text-subtle">+$0.04</span>
        </button>

        <div className="flex-1" />

        {/* V5.2 — Magic prompt enhance */}
        {onEnhance && (
          <button
            onClick={onEnhance}
            disabled={disabled || isEnhancing || isLoading || !brief.trim() || brief.trim().length < 4}
            title="✨ Magic enhance — viết lại brief giàu chi tiết hơn (~$0.001)"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-pill
                       border border-accent-magenta/30 bg-accent-magenta/8
                       text-accent-magenta hover:bg-accent-magenta/15 transition
                       text-xs font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isEnhancing ? (
              <><Loader2 size={12} className="animate-spin" /> Enhancing…</>
            ) : (
              <><Wand2 size={12} /> Enhance</>
            )}
          </button>
        )}

        <button
          onClick={onSubmit}
          disabled={disabled || isLoading || !brief.trim()}
          className="ml-auto w-10 h-10 rounded-full bg-cta-gradient grid place-items-center
                     text-white transition hover:brightness-110 active:brightness-95
                     disabled:opacity-50 disabled:cursor-not-allowed shadow-cta-glow"
          title={isLoading ? 'Planning…' : 'Generate plan (⌘/Ctrl + ↵)'}
        >
          {isLoading ? <Loader2 size={16} className="animate-spin" /> : <ArrowUp size={16} />}
        </button>
      </div>
    </div>
  );
}

function SettingPill({ icon: Icon, label, children }: {
  icon?: typeof ChevronDown;
  label?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="inline-flex items-center gap-1 px-3 py-1.5 rounded-pill
                    border border-hairline bg-surface-2/60 hover:bg-surface-3 transition
                    text-xs text-text-muted hover:text-text">
      {label && <span className="text-[10px] text-text-subtle">{label}</span>}
      {children}
      {Icon && <Icon size={11} className="text-text-subtle" />}
    </div>
  );
}
