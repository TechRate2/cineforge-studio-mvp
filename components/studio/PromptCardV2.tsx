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
  ArrowUp, Loader2, Plus, Sparkles, ChevronDown, Image as ImageIcon,
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

  // Quality estimate (0-10) — shown as chip like Topview's 7.5 score
  qualityScore?: number;

  // Cost preview
  estimatedCostUsd: number;

  // Submit
  onSubmit: () => void;
  isLoading?: boolean;
  disabled?: boolean;
}

const ASPECTS: { v: AspectRatio; label: string }[] = [
  { v: '9:16', label: '9:16' },
  { v: '16:9', label: '16:9' },
  { v: '1:1', label: '1:1' },
];

const DURATION_OPTIONS_DEFAULT = [5, 8, 10, 15, 20, 30, 45, 60];
const AUDIO_LABELS: Record<AudioMode, string> = {
  silent_native: 'Silent',
  dialogue_vo: 'Voice VN',
  asmr_macro: 'ASMR',
};

export function PromptCardV2({
  brief, onBrief,
  referenceCount, onOpenReferences,
  model, onModel,
  aspect, onAspect,
  resolution, onResolution,
  duration, onDuration,
  audioMode, onAudioMode,
  qualityScore,
  estimatedCostUsd,
  onSubmit,
  isLoading, disabled,
}: Props) {
  const cfg = getModelConfig(model);
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  // Available durations — respect discrete model constraints
  const durations = cfg.duration_discrete
    ?? DURATION_OPTIONS_DEFAULT.filter((d) => d <= cfg.max_duration_s);

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

        <SettingPill icon={ChevronDown} label="aspect">
          <select
            value={aspect}
            onChange={(e) => onAspect(e.target.value as AspectRatio)}
            className="bg-transparent outline-none text-xs font-medium pr-1"
          >
            {ASPECTS.map((a) => <option key={a.v} value={a.v}>{a.label}</option>)}
          </select>
        </SettingPill>

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

        <div className="flex-1" />

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
