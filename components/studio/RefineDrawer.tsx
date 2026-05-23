'use client';

/**
 * RefineDrawer — Modal mini cho việc re-render 1 shot riêng.
 *
 * Mở từ Shot card hoặc từ Evaluation suggestion. User chỉnh các field
 * trọng yếu (action / dialogue / duration / refs) rồi click "Refine" →
 * spawn job qua `/api/v1/director/refine` → poll → show clip kết quả.
 *
 * Không cho phép edit Bible từ đây — refine là per-shot, Bible global đã
 * lock sau khi user approve render đầu tiên.
 */

import { useEffect, useMemo, useState } from 'react';
import { X, Wand2, Loader2, CheckCircle2, AlertTriangle, Play } from 'lucide-react';
import type { DirectorPlan, Shot } from '@/lib/studio/use-director-plan';
import type { VideoSettings } from '@/lib/types/backend';
import { useRefineShot } from '@/lib/studio/use-refine-shot';

interface Props {
  open: boolean;
  plan: DirectorPlan;
  shotId: string;
  referenceImages: string[];
  settings: VideoSettings;
  /** Previous shot's last frame URL — passed so refine chains identity continuity */
  previousLastFrameUrl?: string | null;
  onClose: () => void;
  /** Optional: caller updates its local timeline when a refine completes */
  onRefined?: (shotId: string, outputUrl: string) => void;
}

export function RefineDrawer({
  open, plan, shotId, referenceImages, settings,
  previousLastFrameUrl, onClose, onRefined,
}: Props) {
  const shot = useMemo<Shot | undefined>(
    () => plan.shot_list.find((s) => s.shot_id === shotId),
    [plan, shotId],
  );

  // Local form state, seeded from the shot. Submitting builds a sparse
  // `shot_overrides` containing ONLY fields the user changed (so the backend
  // shallow-merge stays minimal).
  const [action, setAction] = useState('');
  const [dialogue, setDialogue] = useState('');
  const [duration, setDuration] = useState(5);
  const [refs, setRefs] = useState<number[]>([]);

  useEffect(() => {
    if (shot && open) {
      setAction(shot.visual.action ?? '');
      setDialogue(shot.audio.dialogue_vn ?? '');
      setDuration(shot.duration_s);
      setRefs([...shot.continuity.reference_indices]);
    }
  }, [shot, open]);

  const { state, refine, reset } = useRefineShot();

  // Auto-notify parent when refine completes successfully
  useEffect(() => {
    if (state.status === 'done' && state.outputUrl && onRefined) {
      onRefined(shotId, state.outputUrl);
    }
  }, [state.status, state.outputUrl, shotId, onRefined]);

  if (!open || !shot) return null;

  const buildOverrides = () => {
    const ov: NonNullable<Parameters<typeof refine>[0]['shot_overrides']> = {};
    if (duration !== shot.duration_s) ov.duration_s = duration;
    if (action.trim() !== (shot.visual.action ?? '').trim()) {
      ov.visual = { ...(ov.visual || {}), action: action.trim() };
    }
    const dialogueNorm = dialogue.trim() || null;
    const origDialogueNorm = (shot.audio.dialogue_vn ?? '').trim() || null;
    if (dialogueNorm !== origDialogueNorm) {
      ov.audio = { dialogue_vn: dialogueNorm };
    }
    if (JSON.stringify(refs) !== JSON.stringify(shot.continuity.reference_indices)) {
      ov.continuity = { reference_indices: refs };
    }
    return Object.keys(ov).length > 0 ? ov : undefined;
  };

  const handleSubmit = () => {
    refine({
      plan,
      shot_id: shotId,
      reference_images: referenceImages,
      settings,
      previous_last_frame_url: previousLastFrameUrl ?? null,
      shot_overrides: buildOverrides(),
    });
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const isBusy =
    state.status === 'submitting' ||
    state.status === 'rendering' ||
    state.status === 'uploading';

  return (
    <div className="fixed inset-0 z-[60] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-bg-card border border-border rounded-2xl shadow-2xl w-full max-w-xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-amber-300 font-medium">Refine Shot</div>
            <div className="text-sm font-semibold text-text">
              Re-render <span className="font-mono text-brand-300">{shotId}</span> với điều chỉnh
            </div>
          </div>
          <button onClick={handleClose} className="p-1.5 rounded-md hover:bg-bg-hover text-text-muted hover:text-text">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-3 max-h-[60vh] overflow-y-auto">
          {state.status === 'idle' || state.status === 'failed' ? (
            <>
              <div className="text-xs text-text-subtle">
                {shot.purpose} · {shot.visual.camera_shot} {shot.visual.camera_movement}
                {previousLastFrameUrl && (
                  <span className="ml-2 px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 text-[10px]">
                    chain anchored
                  </span>
                )}
              </div>

              <FormRow label="Action">
                <textarea
                  rows={2}
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                  className="w-full bg-bg-soft border border-border rounded px-2 py-1.5 text-xs text-text focus:outline-none focus:border-brand-500 resize-y"
                  placeholder="Mô tả động tác trong shot"
                />
              </FormRow>

              <FormRow label="Dialogue VN">
                <input
                  type="text"
                  value={dialogue}
                  onChange={(e) => setDialogue(e.target.value)}
                  className="w-full bg-bg-soft border border-border rounded px-2 py-1.5 text-xs text-text focus:outline-none focus:border-brand-500"
                  placeholder="(không có dialogue)"
                />
              </FormRow>

              <FormRow label="Duration (s)">
                <input
                  type="number"
                  min={2}
                  max={20}
                  value={duration}
                  onChange={(e) => setDuration(Math.max(2, Math.min(20, parseInt(e.target.value, 10) || 5)))}
                  className="w-24 bg-bg-soft border border-border rounded px-2 py-1.5 text-xs text-text font-mono focus:outline-none focus:border-brand-500"
                />
              </FormRow>

              {referenceImages.length > 0 && (
                <FormRow label="Reference indices">
                  <div className="flex flex-wrap gap-1">
                    {referenceImages.map((_, i) => {
                      const on = refs.includes(i);
                      return (
                        <button
                          key={i}
                          onClick={() => setRefs(on ? refs.filter((x) => x !== i) : [...refs, i].sort((a, b) => a - b))}
                          className={`w-7 h-7 rounded text-[10px] font-mono transition ${
                            on
                              ? 'bg-brand-500/30 border border-brand-500/50 text-brand-200'
                              : 'bg-bg-soft border border-border text-text-subtle hover:border-brand-500/30'
                          }`}
                        >
                          {i}
                        </button>
                      );
                    })}
                  </div>
                </FormRow>
              )}

              {state.status === 'failed' && state.error && (
                <div className="px-3 py-2 rounded bg-rose-500/10 border border-rose-500/30 text-rose-200 text-xs">
                  <AlertTriangle className="inline w-3.5 h-3.5 mr-1" /> {state.error}
                </div>
              )}
            </>
          ) : state.status === 'done' ? (
            <div className="space-y-3">
              <div className="px-3 py-2 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-200 text-xs flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0 mt-px" />
                <div>
                  <div className="font-medium">Refine xong</div>
                  <div className="text-emerald-300/80 mt-0.5">Clip mới sẵn sàng. Replace vào timeline bằng FFmpeg concat (out of scope: timeline editor).</div>
                </div>
              </div>
              {(state.outputUrl || state.videoUrl) && (
                <video
                  controls
                  src={state.outputUrl || state.videoUrl}
                  className="w-full rounded border border-border bg-black"
                />
              )}
              {state.outputUrl && (
                <a
                  href={state.outputUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-xs text-brand-300 hover:underline font-mono break-all"
                >
                  {state.outputUrl}
                </a>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center gap-3 py-8">
              <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
              <div className="text-text-muted text-sm capitalize">{state.status}</div>
              {state.currentStep && (
                <div className="text-text-subtle text-xs font-mono">{state.currentStep}</div>
              )}
              <div className="w-48 h-1.5 rounded-full bg-bg-soft overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-brand-500 to-fuchsia-500 transition-all"
                  style={{ width: `${state.progress}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-border px-5 py-3 flex items-center justify-between gap-3">
          <div className="text-xs text-text-subtle">
            Job: {state.jobId ? <span className="font-mono">{state.jobId}</span> : '—'}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleClose}
              className="px-3 py-2 text-xs rounded-md border border-border bg-bg-soft hover:bg-bg-hover text-text-muted"
            >
              {state.status === 'done' ? 'Đóng' : 'Huỷ'}
            </button>
            {(state.status === 'idle' || state.status === 'failed') && (
              <button
                onClick={handleSubmit}
                disabled={isBusy}
                className="px-4 py-2 text-xs font-medium rounded-md bg-gradient-to-r from-amber-500 to-rose-500 hover:opacity-90 disabled:opacity-40 text-white inline-flex items-center gap-1.5"
              >
                <Wand2 className="w-3.5 h-3.5" /> Refine · Re-render
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function FormRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1 text-xs">
      <span className="text-text-subtle">{label}</span>
      {children}
    </div>
  );
}
