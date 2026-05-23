'use client';

/**
 * InspirationPanelV5 — LumeFlow-style right column with tab toggle.
 *
 * Two tabs:
 *   - "Lịch sử" — Project History (jobs đã render)
 *   - "Cảm hứng" — Inspiration gallery (preset cards)
 *
 * Re-uses original `use-project-history` hook + `studio-presets.json` data
 * so no new backend wiring is needed.
 */

import { useState } from 'react';
import { Clock, Sparkles, Flame, Play } from 'lucide-react';
import PRESETS from '@/lib/studio-presets.json';
import { useProjectHistory, type HistoryItem } from '@/lib/studio/use-project-history';

type TabKey = 'history' | 'inspiration';

interface Preset {
  id: string;
  name?: string;
  label?: string;
  prompt?: string;
  video?: string;
  productImg?: string;
  avatarImgs?: Array<{ img: string }>;
}

interface Props {
  onOpenHistoryItem?: (item: HistoryItem) => void;
  onUsePreset?: (preset: Preset) => void;
}

export function InspirationPanelV5({ onOpenHistoryItem, onUsePreset }: Props) {
  const [tab, setTab] = useState<TabKey>('inspiration');
  const history = useProjectHistory();

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Tab bar — LumeFlow style: pill toggle */}
      <div className="flex items-center gap-1 p-1 mb-4 rounded-xl bg-white/[0.03] border border-white/5 self-start">
        <button
          onClick={() => setTab('history')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm font-medium transition ${
            tab === 'history'
              ? 'bg-white/10 text-white shadow-sm'
              : 'text-white/60 hover:text-white/90'
          }`}
        >
          <Clock className="w-3.5 h-3.5" /> Lịch sử
        </button>
        <button
          onClick={() => setTab('inspiration')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-sm font-medium transition ${
            tab === 'inspiration'
              ? 'bg-white/10 text-white shadow-sm'
              : 'text-white/60 hover:text-white/90'
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" /> Cảm hứng
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 min-h-0 overflow-y-auto pr-1 custom-scrollbar">
        {tab === 'inspiration' ? (
          <InspirationGrid presets={PRESETS as Preset[]} onUse={onUsePreset} />
        ) : (
          <HistoryList items={history.items} loading={history.loading} onOpen={onOpenHistoryItem} />
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────

function InspirationGrid({ presets, onUse }: { presets: Preset[]; onUse?: (p: Preset) => void }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
      {presets.map((p) => {
        const cover = p.productImg || p.avatarImgs?.[0]?.img || null;
        const heat = 1500 + Math.floor(Math.random() * 6000); // visual fire counter (deterministic seed could be added)
        return (
          <button
            key={p.id}
            onClick={() => onUse?.(p)}
            className="group relative rounded-2xl overflow-hidden bg-white/[0.04] border border-white/5 hover:border-fuchsia-400/40 hover:shadow-lg hover:shadow-fuchsia-500/10 transition-all aspect-[3/4]"
          >
            {cover ? (
              <img
                src={cover}
                alt={p.name || p.label || 'preset'}
                className="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
              />
            ) : (
              <div className="absolute inset-0 bg-gradient-to-br from-fuchsia-500/20 via-purple-500/10 to-transparent" />
            )}

            {/* Bottom gradient overlay + label */}
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black via-black/70 to-transparent pt-12 pb-3 px-3 flex items-end justify-between gap-2">
              <span className="text-white text-sm font-medium truncate" title={p.name || p.label}>
                {p.name || p.label}
              </span>
              <span className="shrink-0 flex items-center gap-0.5 text-white/90 text-xs">
                <Flame className="w-3 h-3 text-orange-400" />
                {heat.toLocaleString('vi-VN')}
              </span>
            </div>

            {/* Hover play indicator (for video presets) */}
            {p.video && (
              <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <div className="w-7 h-7 rounded-full bg-black/60 backdrop-blur flex items-center justify-center">
                  <Play className="w-3 h-3 text-white fill-white" />
                </div>
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}

function HistoryList({
  items,
  loading,
  onOpen,
}: {
  items: HistoryItem[];
  loading: boolean;
  onOpen?: (item: HistoryItem) => void;
}) {
  if (loading) {
    return <div className="text-white/40 text-sm py-8 text-center">Đang tải lịch sử…</div>;
  }
  if (items.length === 0) {
    return (
      <div className="text-white/40 text-sm py-12 text-center">
        Chưa có job nào. Bấm "Tạo kế hoạch video" để bắt đầu.
      </div>
    );
  }
  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
      {items.map((item) => (
        <button
          key={item.job_id}
          onClick={() => onOpen?.(item)}
          className="group relative rounded-2xl overflow-hidden bg-white/[0.04] border border-white/5 hover:border-fuchsia-400/40 transition-all aspect-[3/4] text-left"
        >
          {item.output_url ? (
            <video
              src={item.output_url}
              muted
              loop
              playsInline
              className="absolute inset-0 w-full h-full object-cover"
              onMouseEnter={(e) => (e.currentTarget as HTMLVideoElement).play().catch(() => {})}
              onMouseLeave={(e) => {
                const v = e.currentTarget as HTMLVideoElement;
                v.pause();
                v.currentTime = 0;
              }}
            />
          ) : (
            <div className="absolute inset-0 bg-gradient-to-br from-fuchsia-500/10 via-purple-500/5 to-transparent" />
          )}
          <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black via-black/70 to-transparent pt-10 pb-3 px-3">
            <div className="text-white text-sm font-medium truncate">{item.title || 'Untitled'}</div>
            <div className="text-white/50 text-[11px] flex items-center gap-1.5 mt-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${item.status === 'done' ? 'bg-emerald-400' : item.status === 'failed' ? 'bg-rose-400' : 'bg-amber-400'}`} />
              {item.status} · {item.duration_s}s
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}
