'use client';
import { Coins } from 'lucide-react';
import { MODEL_CONFIGS, getModelConfig } from '@/lib/studio/model-config';
import type { VideoModel, AspectRatio, AudioMode } from '@/lib/types/backend';

interface Props {
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
  numShots: number | null;
  onNumShots: (n: number | null) => void;
}

const ASPECTS: { v: AspectRatio; label: string }[] = [
  { v: '9:16', label: '9:16' },
  { v: '16:9', label: '16:9' },
  { v: '1:1', label: '1:1' },
];

const AUDIO_MODES: { v: AudioMode; label: string; hint: string }[] = [
  { v: 'silent_native', label: 'Silent', hint: 'Không thoại / nhạc nền post' },
  { v: 'dialogue_vo', label: 'Dialogue VO', hint: 'TTS giọng Việt (GenMax)' },
  { v: 'asmr_macro', label: 'ASMR', hint: 'SFX nổi bật, dialogue tối thiểu' },
];

export function SettingsPanel({
  model, onModel, aspect, onAspect, resolution, onResolution,
  duration, onDuration, audioMode, onAudioMode, numShots, onNumShots,
}: Props) {
  const cfg = getModelConfig(model);
  const isDiscrete = cfg.duration_discrete && cfg.duration_discrete.length > 0;
  const videoCost = cfg.cost_per_second_usd * duration;
  const audioCost = audioMode === 'dialogue_vo' ? 0.01 : 0;
  const planCost = 0.04;
  const totalUsd = videoCost + audioCost + planCost;

  return (
    <aside className="space-y-3">
      {/* MODEL */}
      <section className="surface-2 rounded-card p-4">
        <div className="text-[11px] uppercase tracking-wider text-text-subtle mb-2">Model</div>
        <select
          value={model}
          onChange={(e) => onModel(e.target.value as VideoModel)}
          className="field text-sm"
        >
          {Object.values(MODEL_CONFIGS).map((m) => (
            <option key={m.id} value={m.id}>
              {m.name_vn} · ${m.cost_per_second_usd}/s
            </option>
          ))}
        </select>
        <p className="text-[11px] text-text-subtle mt-2 leading-relaxed">{cfg.description}</p>
        {cfg.reference_hint_vn && (
          <p className="text-[11px] text-accent-yellow/80 mt-2 leading-relaxed">{cfg.reference_hint_vn}</p>
        )}
      </section>

      {/* TECH CONFIG */}
      <section className="surface-2 rounded-card p-4 space-y-4">
        {/* Aspect */}
        <div>
          <div className="text-[11px] uppercase tracking-wider text-text-subtle mb-2">Aspect Ratio</div>
          <div className="grid grid-cols-3 gap-1.5">
            {ASPECTS.map((a) => (
              <button
                key={a.v}
                onClick={() => onAspect(a.v)}
                className={`py-2 text-xs rounded-md border transition
                            ${aspect === a.v
                              ? 'border-accent-magenta/60 bg-accent-magenta/10 text-text'
                              : 'border-hairline text-text-muted hover:text-text hover:border-hairline-strong'}`}
              >
                {a.label}
              </button>
            ))}
          </div>
        </div>

        {/* Resolution */}
        <div>
          <div className="text-[11px] uppercase tracking-wider text-text-subtle mb-2">Resolution</div>
          <div className="flex flex-wrap gap-1.5">
            {cfg.resolution_options.map((r) => (
              <button
                key={r}
                onClick={() => onResolution(r)}
                className={`px-2.5 py-1.5 text-xs rounded-md border transition
                            ${resolution === r
                              ? 'border-accent-magenta/60 bg-accent-magenta/10 text-text'
                              : 'border-hairline text-text-muted hover:text-text hover:border-hairline-strong'}`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        {/* Duration */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] uppercase tracking-wider text-text-subtle">Duration</span>
            <span className="text-xs font-semibold text-text">{duration}s</span>
          </div>
          {isDiscrete ? (
            <div className="flex gap-1.5">
              {cfg.duration_discrete!.map((d) => (
                <button
                  key={d}
                  onClick={() => onDuration(d)}
                  className={`flex-1 py-2 text-xs rounded-md border transition
                              ${duration === d
                                ? 'border-accent-magenta/60 bg-accent-magenta/10 text-text'
                                : 'border-hairline text-text-muted hover:text-text'}`}
                >
                  {d}s
                </button>
              ))}
            </div>
          ) : (
            <input
              type="range"
              min={3}
              max={cfg.max_duration_s}
              value={duration}
              onChange={(e) => onDuration(Number(e.target.value))}
              className="w-full accent-accent-magenta"
            />
          )}
        </div>

        {/* Num shots override (if supported) */}
        {cfg.supports_num_shots_override && (
          <div>
            <div className="text-[11px] uppercase tracking-wider text-text-subtle mb-2">Số shot</div>
            <select
              value={numShots ?? 'auto'}
              onChange={(e) => onNumShots(e.target.value === 'auto' ? null : Number(e.target.value))}
              className="field text-sm"
            >
              <option value="auto">Auto (Director quyết)</option>
              {(() => {
                const [min, max] = cfg.num_shots_range ?? [2, 5];
                return Array.from({ length: max - min + 1 }, (_, i) => min + i).map((n) => (
                  <option key={n} value={n}>{n} shot</option>
                ));
              })()}
            </select>
          </div>
        )}

        {/* Audio mode */}
        <div>
          <div className="text-[11px] uppercase tracking-wider text-text-subtle mb-2">Audio</div>
          <div className="space-y-1">
            {AUDIO_MODES.map((a) => (
              <button
                key={a.v}
                onClick={() => onAudioMode(a.v)}
                className={`w-full text-left px-3 py-2 rounded-md border transition
                            ${audioMode === a.v
                              ? 'border-accent-magenta/60 bg-accent-magenta/10'
                              : 'border-hairline hover:border-hairline-strong'}`}
              >
                <div className="text-xs font-semibold text-text">{a.label}</div>
                <div className="text-[10px] text-text-subtle mt-0.5">{a.hint}</div>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* COST */}
      <section className="rounded-card p-4 bg-gradient-to-br from-accent-magenta/12 via-surface-2 to-accent-orange/12 border border-hairline-strong">
        <div className="flex items-center gap-2 mb-3">
          <Coins size={14} className="text-accent-magenta" />
          <span className="text-[11px] uppercase tracking-wider text-text">Cost estimate</span>
        </div>
        <div className="space-y-1 text-xs text-text-muted">
          <Line label="Director plan" usd={planCost} />
          <Line label={`Video (${duration}s × ${cfg.name_short})`} usd={videoCost} />
          {audioCost > 0 && <Line label="TTS dialogue VN" usd={audioCost} />}
        </div>
        <div className="border-t border-hairline-strong mt-3 pt-3 flex items-center justify-between">
          <span className="text-xs text-text-muted">Total</span>
          <div className="text-right">
            <div className="text-base font-bold text-text">${totalUsd.toFixed(2)}</div>
            <div className="text-[10px] text-text-subtle">≈ {Math.round(totalUsd * 24500).toLocaleString('vi-VN')}₫</div>
          </div>
        </div>
      </section>
    </aside>
  );
}

function Line({ label, usd }: { label: string; usd: number }) {
  return (
    <div className="flex justify-between">
      <span>{label}</span>
      <span className="text-text">${usd.toFixed(3)}</span>
    </div>
  );
}
