'use client';

/**
 * TimelineEditor — V3 §4.3 post-render clip arrangement.
 *
 * Open từ ProjectHistoryDrawer ("Open Timeline" trên job done). Cho user:
 *   - Reorder shots (drag handle ↑↓)
 *   - Swap clip với refined URL (paste URL or click "Use refined")
 *   - Remove clip khỏi timeline
 *   - Preview <video> mỗi clip + audio strip (per-shot TTS nếu có)
 *   - Submit → POST /director/reassemble → poll → final MP4 URL mới
 *
 * KHÔNG re-render từ AtlasCloud — chỉ FFmpeg concat + color pass + R2 upload.
 * Cost ~$0, fast iteration.
 */

import { useState } from 'react';
import {
  X, Film, ArrowUp, ArrowDown, Trash2, Wand2, RotateCw, Play, Loader2,
  CheckCircle2, AlertTriangle, GitMerge,
} from 'lucide-react';
import { useTimeline } from '@/lib/studio/use-timeline';

interface Props {
  open: boolean;
  historyJobId: string | null;
  onClose: () => void;
}

export function TimelineEditor({ open, historyJobId, onClose }: Props) {
  const tl = useTimeline(historyJobId);
  const [swapping, setSwapping] = useState<string | null>(null);
  const [swapUrl, setSwapUrl] = useState('');

  if (!open) return null;

  const handleSwap = (shotId: string) => {
    if (!swapUrl.trim()) {
      setSwapping(null);
      return;
    }
    tl.swapClipUrl(shotId, swapUrl.trim());
    setSwapping(null);
    setSwapUrl('');
  };

  const totalDuration = tl.clips.reduce((s, c) => s + c.duration_s, 0);
  const isBusy =
    tl.reassembleState.status === 'submitting' ||
    tl.reassembleState.status === 'downloading' ||
    tl.reassembleState.status === 'assembling' ||
    tl.reassembleState.status === 'grading' ||
    tl.reassembleState.status === 'uploading';

  return (
    <div className="fixed inset-0 z-[56] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-bg-card border border-border rounded-2xl shadow-2xl w-full max-w-5xl max-h-[92vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <Film className="w-4 h-4 text-brand-300" />
            <div>
              <div className="text-[10px] uppercase tracking-widest text-brand-300 font-medium">Timeline Editor</div>
              <div className="text-sm font-semibold text-text">
                {tl.detail?.title ?? '—'}
                {tl.isDirty && (
                  <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">
                    ● dirty
                  </span>
                )}
              </div>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-bg-hover text-text-muted hover:text-text">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {tl.loading ? (
            <div className="text-center py-12 text-text-subtle text-sm">Đang tải timeline…</div>
          ) : tl.error ? (
            <div className="text-center py-12 text-rose-300 text-sm">Lỗi: {tl.error}</div>
          ) : tl.clips.length === 0 ? (
            <div className="text-center py-12 text-text-subtle text-sm">
              Job này không có chain meta — có thể được render trước khi history tracking enable.
            </div>
          ) : (
            <div className="space-y-2">
              {/* Track summary bar */}
              <div className="flex items-center justify-between text-[11px] text-text-subtle px-1">
                <span>{tl.clips.length} clips · {totalDuration}s total</span>
                <span>Drag ↑↓ để đổi thứ tự</span>
              </div>

              {/* Clip rows */}
              {tl.clips.map((c, idx) => {
                const isOverridden = c.refined_url && c.refined_url !== c.original_url;
                return (
                  <div
                    key={c.shot_id}
                    className={`rounded-md border bg-bg-soft px-3 py-2 flex items-stretch gap-3 ${
                      isOverridden ? 'border-emerald-500/40' : 'border-border'
                    }`}
                  >
                    {/* Move buttons */}
                    <div className="flex flex-col justify-center gap-0.5">
                      <button
                        onClick={() => tl.moveClip(idx, idx - 1)}
                        disabled={idx === 0}
                        className="p-0.5 rounded text-text-subtle hover:text-brand-300 disabled:opacity-30"
                        title="Lên trên"
                      >
                        <ArrowUp className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => tl.moveClip(idx, idx + 1)}
                        disabled={idx === tl.clips.length - 1}
                        className="p-0.5 rounded text-text-subtle hover:text-brand-300 disabled:opacity-30"
                        title="Xuống dưới"
                      >
                        <ArrowDown className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    {/* Preview */}
                    <div className="w-32 shrink-0">
                      {c.video_url ? (
                        <video
                          src={c.video_url}
                          className="w-full rounded bg-black aspect-video object-cover"
                          muted
                          onMouseEnter={(e) => (e.currentTarget as HTMLVideoElement).play().catch(() => {})}
                          onMouseLeave={(e) => {
                            const v = e.currentTarget as HTMLVideoElement;
                            v.pause();
                            v.currentTime = 0;
                          }}
                        />
                      ) : (
                        <div className="w-full aspect-video rounded bg-bg-card border border-border flex items-center justify-center text-text-subtle">
                          <Play className="w-4 h-4" />
                        </div>
                      )}
                    </div>

                    {/* Meta */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-brand-300 text-[11px]">#{idx + 1} · {c.shot_id}</span>
                          <span className="text-text-subtle">{c.duration_s}s</span>
                          <span className="text-[10px] text-text-subtle">{c.render_mode}</span>
                          {isOverridden && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                              ✓ refined
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-1">
                          {swapping === c.shot_id ? (
                            <>
                              <input
                                type="text"
                                value={swapUrl}
                                onChange={(e) => setSwapUrl(e.target.value)}
                                placeholder="Paste refined URL"
                                className="text-[10px] px-2 py-1 rounded bg-bg-card border border-border text-text w-48 focus:outline-none focus:border-brand-500"
                                autoFocus
                              />
                              <button
                                onClick={() => handleSwap(c.shot_id)}
                                className="text-[10px] px-2 py-1 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-200"
                              >
                                OK
                              </button>
                              <button
                                onClick={() => { setSwapping(null); setSwapUrl(''); }}
                                className="text-[10px] px-2 py-1 rounded text-text-subtle"
                              >
                                Hủy
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                onClick={() => { setSwapping(c.shot_id); setSwapUrl(c.refined_url ?? ''); }}
                                className="p-1 rounded text-text-subtle hover:text-amber-300"
                                title="Swap với refined clip URL"
                              >
                                <Wand2 className="w-3.5 h-3.5" />
                              </button>
                              {isOverridden && (
                                <button
                                  onClick={() => tl.revertClip(c.shot_id)}
                                  className="p-1 rounded text-text-subtle hover:text-text"
                                  title="Khôi phục clip gốc"
                                >
                                  <RotateCw className="w-3.5 h-3.5" />
                                </button>
                              )}
                              <button
                                onClick={() => tl.removeClip(c.shot_id)}
                                className="p-1 rounded text-text-subtle hover:text-rose-400"
                                title="Xoá clip khỏi timeline"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                      <div className="text-[10px] text-text-subtle font-mono truncate" title={c.video_url ?? ''}>
                        {c.video_url ?? '(no clip URL)'}
                      </div>
                    </div>
                  </div>
                );
              })}

              {/* Reassemble status */}
              {tl.reassembleState.status !== 'idle' && (
                <div className="mt-4 px-3 py-3 rounded-md border border-brand-500/30 bg-brand-500/5">
                  {isBusy && (
                    <div className="flex items-center gap-2 text-xs text-text">
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-300" />
                      <span>FFmpeg đang re-concat… {tl.reassembleState.currentStep ?? ''} ({tl.reassembleState.progress}%)</span>
                    </div>
                  )}
                  {tl.reassembleState.status === 'done' && tl.reassembleState.outputUrl && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-xs text-emerald-200">
                        <CheckCircle2 className="w-4 h-4" />
                        Timeline edit xong — MP4 mới sẵn sàng
                      </div>
                      <video
                        src={tl.reassembleState.outputUrl}
                        controls
                        className="w-full rounded border border-border bg-black"
                      />
                      <a
                        href={tl.reassembleState.outputUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block text-[10px] text-brand-300 hover:underline font-mono break-all"
                      >
                        {tl.reassembleState.outputUrl}
                      </a>
                    </div>
                  )}
                  {tl.reassembleState.status === 'failed' && (
                    <div className="text-xs text-rose-200 flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span>Reassemble lỗi: {tl.reassembleState.error}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-border px-5 py-3 flex items-center justify-between gap-3">
          <div className="text-xs text-text-subtle">
            {tl.clips.length} clip · {totalDuration}s · cost ~$0 (FFmpeg only)
          </div>
          <div className="flex items-center gap-2">
            <button onClick={onClose} className="px-3 py-2 text-xs rounded-md border border-border bg-bg-soft hover:bg-bg-hover text-text-muted">
              Đóng
            </button>
            <button
              onClick={tl.submitReassemble}
              disabled={tl.clips.length === 0 || isBusy}
              className="px-4 py-2 text-xs font-medium rounded-md bg-gradient-to-r from-brand-500 to-fuchsia-500 hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed text-white inline-flex items-center gap-1.5"
            >
              <GitMerge className="w-3.5 h-3.5" /> Re-assemble MP4
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
