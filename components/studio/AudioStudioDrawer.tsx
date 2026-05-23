'use client';

/**
 * AudioStudioDrawer — Voice picker + per-shot TTS preview.
 *
 * Critical cho Wan 2.7 lip-sync: sau Bug #1 fix, Wan model cần audio URL truyền
 * vào field `audio`. Drawer này pre-render TTS từng shot có dialogue → lưu URL
 * map vào `audio_plan.driven_audio_urls[shot_id]` → khi user approve render,
 * video_worker tự pipe vào AtlasCloud Wan.
 *
 * Workflow:
 *   1. Mở từ DirectorPlanModal hoặc button "Audio Studio" trên top bar
 *   2. Pick voice preset (12 voice VN — 6 ElevenLabs premium + 6 MiniMax budget)
 *   3. Loop qua shots có dialogue_vn — preview cost → gen → save URL
 *   4. Apply → trả về Record<shot_id, audio_url> cho caller
 */

import { useEffect, useMemo, useState } from 'react';
import { X, Mic, Play, Loader2, Check, AlertTriangle, RotateCw } from 'lucide-react';
import type { DirectorPlan } from '@/lib/studio/use-director-plan';
import { useGenmaxTts, type VoicePreset } from '@/lib/studio/use-genmax-tts';

interface Props {
  open: boolean;
  plan: DirectorPlan;
  /** Pre-existing URL map (e.g. user re-opens after generating earlier). */
  initialUrls?: Record<string, string>;
  onClose: () => void;
  /** Applied = user clicks "Áp dụng" — pass URL map back to caller. */
  onApply: (drivenAudioUrls: Record<string, string>) => void;
}

interface ShotGenState {
  status: 'idle' | 'generating' | 'done' | 'failed';
  url?: string;
  duration?: number;
  cost?: { credits: number; vnd: number };
  error?: string;
}

export function AudioStudioDrawer({
  open, plan, initialUrls, onClose, onApply,
}: Props) {
  const tts = useGenmaxTts();
  const [voiceAlias, setVoiceAlias] = useState<string>('mai');
  const [tierFilter, setTierFilter] = useState<'all' | 'premium' | 'budget'>('all');

  // Shots that actually need TTS = those with dialogue_vn
  const shotsWithDialogue = useMemo(
    () => plan.shot_list.filter((s) => s.audio.dialogue_vn && s.audio.dialogue_vn.trim()),
    [plan],
  );

  const [genState, setGenState] = useState<Record<string, ShotGenState>>(() => {
    const init: Record<string, ShotGenState> = {};
    shotsWithDialogue.forEach((s) => {
      init[s.shot_id] = initialUrls?.[s.shot_id]
        ? { status: 'done', url: initialUrls[s.shot_id] }
        : { status: 'idle' };
    });
    return init;
  });

  // Reset gen state when drawer reopens with new plan
  useEffect(() => {
    if (open) {
      setGenState((prev) => {
        const next: Record<string, ShotGenState> = {};
        shotsWithDialogue.forEach((s) => {
          next[s.shot_id] = prev[s.shot_id] ?? (
            initialUrls?.[s.shot_id]
              ? { status: 'done', url: initialUrls[s.shot_id] }
              : { status: 'idle' }
          );
        });
        return next;
      });
    }
  }, [open, plan.plan_id, shotsWithDialogue, initialUrls]);

  if (!open) return null;

  const filteredVoices = tts.voices.filter((v) =>
    tierFilter === 'all' ? true : v.tier === tierFilter,
  );
  const selectedVoice = tts.voices.find((v) => v.alias === voiceAlias);

  const generateForShot = async (shotId: string, text: string) => {
    setGenState((prev) => ({ ...prev, [shotId]: { status: 'generating' } }));
    try {
      const cost = await tts.previewCost(text, voiceAlias);
      const result = await tts.generate(text, voiceAlias);
      setGenState((prev) => ({
        ...prev,
        [shotId]: {
          status: 'done',
          url: result.audio_url,
          duration: result.duration_s,
          cost: { credits: cost.estimated_credits, vnd: cost.estimated_vnd },
        },
      }));
    } catch (e) {
      setGenState((prev) => ({
        ...prev,
        [shotId]: { status: 'failed', error: e instanceof Error ? e.message : String(e) },
      }));
    }
  };

  const generateAll = async () => {
    for (const s of shotsWithDialogue) {
      if (genState[s.shot_id]?.status !== 'done') {
        await generateForShot(s.shot_id, s.audio.dialogue_vn!);
      }
    }
  };

  const applyAll = () => {
    const urls: Record<string, string> = {};
    for (const [shotId, st] of Object.entries(genState)) {
      if (st.status === 'done' && st.url) urls[shotId] = st.url;
    }
    onApply(urls);
    onClose();
  };

  const totalCost = Object.values(genState).reduce(
    (acc, st) => acc + (st.cost?.vnd ?? 0), 0,
  );
  const doneCount = Object.values(genState).filter((s) => s.status === 'done').length;

  return (
    <div className="fixed inset-0 z-[58] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-bg-card border border-border rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <Mic className="w-4 h-4 text-brand-300" />
            <div>
              <div className="text-[10px] uppercase tracking-widest text-brand-300 font-medium">Audio Studio</div>
              <div className="text-sm font-semibold text-text">
                Voice picker + per-shot TTS preview
              </div>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-bg-hover text-text-muted hover:text-text">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Voice picker */}
        <div className="px-5 py-3 border-b border-border bg-bg-soft/30">
          <div className="flex items-center justify-between mb-2">
            <div className="text-[11px] uppercase tracking-widest text-text-subtle font-medium">Voice</div>
            <div className="flex items-center gap-1 text-[10px]">
              <FilterChip active={tierFilter === 'all'} onClick={() => setTierFilter('all')}>All ({tts.voices.length})</FilterChip>
              <FilterChip active={tierFilter === 'premium'} onClick={() => setTierFilter('premium')}>Premium</FilterChip>
              <FilterChip active={tierFilter === 'budget'} onClick={() => setTierFilter('budget')}>Budget</FilterChip>
            </div>
          </div>
          {tts.voicesLoading ? (
            <div className="text-xs text-text-subtle">Đang tải voices…</div>
          ) : tts.voicesError ? (
            <div className="text-xs text-rose-300">Lỗi: {tts.voicesError}</div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
              {filteredVoices.map((v) => (
                <VoiceCard
                  key={v.alias}
                  voice={v}
                  selected={v.alias === voiceAlias}
                  onClick={() => setVoiceAlias(v.alias)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Per-shot list */}
        <div className="flex-1 overflow-y-auto px-5 py-3 space-y-2">
          <div className="flex items-center justify-between mb-1">
            <div className="text-[11px] uppercase tracking-widest text-text-subtle font-medium">
              Shots có dialogue ({shotsWithDialogue.length})
            </div>
            {shotsWithDialogue.length > 0 && (
              <button
                onClick={generateAll}
                className="text-xs px-3 py-1.5 rounded-md bg-brand-500/15 border border-brand-500/30 text-brand-200 hover:bg-brand-500/25 inline-flex items-center gap-1.5"
              >
                <RotateCw className="w-3 h-3" /> Generate tất cả
              </button>
            )}
          </div>
          {shotsWithDialogue.length === 0 ? (
            <div className="text-center py-8 text-text-subtle text-sm">
              Plan chưa có shot nào dialogue. Vào Shot List tab → điền field 💬 Dialogue VN.
            </div>
          ) : (
            shotsWithDialogue.map((s) => {
              const st = genState[s.shot_id] ?? { status: 'idle' };
              return (
                <div key={s.shot_id} className="rounded-md border border-border bg-bg-soft px-3 py-2">
                  <div className="flex items-center justify-between text-xs mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-brand-300">{s.shot_id}</span>
                      <span className="text-text-subtle">{s.duration_s}s · {s.purpose}</span>
                      {st.status === 'done' && (
                        <span className="text-emerald-300 text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 inline-flex items-center gap-1">
                          <Check className="w-2.5 h-2.5" /> done
                        </span>
                      )}
                      {st.status === 'failed' && (
                        <span className="text-rose-300 text-[10px] px-1.5 py-0.5 rounded bg-rose-500/10 inline-flex items-center gap-1">
                          <AlertTriangle className="w-2.5 h-2.5" /> fail
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {st.cost && (
                        <span className="text-[10px] text-text-subtle">
                          {st.cost.credits.toFixed(1)} cr · {st.cost.vnd.toLocaleString('vi-VN')}đ
                        </span>
                      )}
                      <button
                        onClick={() => generateForShot(s.shot_id, s.audio.dialogue_vn!)}
                        disabled={st.status === 'generating'}
                        className="text-xs px-2 py-1 rounded bg-bg-card border border-border text-text-muted hover:text-brand-300 hover:border-brand-500/30 disabled:opacity-50 inline-flex items-center gap-1"
                      >
                        {st.status === 'generating' ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : st.status === 'done' ? (
                          <RotateCw className="w-3 h-3" />
                        ) : (
                          <Play className="w-3 h-3" />
                        )}
                        {st.status === 'done' ? 'Re-gen' : 'Gen'}
                      </button>
                    </div>
                  </div>
                  <div className="text-xs text-text leading-relaxed italic">
                    "{s.audio.dialogue_vn}"
                  </div>
                  {st.status === 'done' && st.url && (
                    <audio
                      controls
                      src={st.url}
                      className="w-full mt-2 h-8"
                      style={{ colorScheme: 'dark' }}
                    />
                  )}
                  {st.error && (
                    <div className="mt-1 text-[10px] text-rose-300">{st.error}</div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-border px-5 py-3 flex items-center justify-between gap-3">
          <div className="text-xs text-text-subtle">
            {doneCount}/{shotsWithDialogue.length} shots · est. {totalCost.toLocaleString('vi-VN')}đ
            {selectedVoice && (
              <span className="ml-3">Voice: <span className="text-text">{selectedVoice.label_vn}</span></span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onClose} className="px-3 py-2 text-xs rounded-md border border-border bg-bg-soft hover:bg-bg-hover text-text-muted">
              Huỷ
            </button>
            <button
              onClick={applyAll}
              disabled={doneCount === 0}
              className="px-4 py-2 text-xs font-medium rounded-md bg-gradient-to-r from-brand-500 to-fuchsia-500 hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed text-white inline-flex items-center gap-1.5"
            >
              <Check className="w-3.5 h-3.5" /> Áp dụng vào plan ({doneCount})
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Sub: voice card
// ============================================================
function VoiceCard({
  voice, selected, onClick,
}: { voice: VoicePreset; selected: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`text-left rounded-md border px-2.5 py-2 transition ${
        selected
          ? 'border-brand-500 bg-brand-500/10 ring-1 ring-brand-500/30'
          : 'border-border bg-bg-soft hover:border-brand-500/40'
      }`}
    >
      <div className="flex items-center justify-between text-[10px] mb-0.5">
        <span className={voice.gender === 'female' ? 'text-fuchsia-300' : 'text-blue-300'}>
          {voice.gender === 'female' ? '♀' : '♂'}
        </span>
        <span className={`text-[9px] uppercase tracking-wider ${
          voice.tier === 'premium' ? 'text-amber-300' : 'text-text-subtle'
        }`}>
          {voice.tier}
        </span>
      </div>
      <div className="text-xs text-text font-medium truncate" title={voice.label_vn}>{voice.label_vn}</div>
      <div className="text-[10px] text-text-subtle font-mono">{voice.provider}</div>
    </button>
  );
}

function FilterChip({
  active, onClick, children,
}: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-2 py-0.5 rounded text-[10px] ${
        active
          ? 'bg-brand-500/20 text-brand-200 border border-brand-500/30'
          : 'text-text-subtle hover:text-text border border-transparent'
      }`}
    >
      {children}
    </button>
  );
}
