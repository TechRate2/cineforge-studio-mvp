'use client';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import { Download, AlertTriangle, Loader2, Sparkles, RotateCcw, X, Clock } from 'lucide-react';
import { useDirectorJobPoll } from '@/lib/studio/use-director-job-poll';
import { useJobCancel } from '@/lib/studio/use-job-cancel';

interface Props {
  open: boolean;
  jobId: string | null;
  onClose: () => void;
  onRetry?: () => void;
  /** V5.2 — total expected render duration (s) for ETA computation. */
  estimatedDurationS?: number;
  /** V5.3 — stable job start timestamp (from usePersistedJob). Required for
   *  accurate ETA across modal close/reopen — was: reset every remount. */
  jobStartedAt?: number | null;
}

function formatEta(secondsLeft: number): string {
  if (secondsLeft <= 0) return 'sắp xong';
  if (secondsLeft < 60) return `~${Math.ceil(secondsLeft)}s còn lại`;
  return `~${Math.ceil(secondsLeft / 60)} phút còn lại`;
}

const STAGE_LABELS_VN: Record<string, string> = {
  pending: 'Đang vào hàng đợi...',
  planning: 'Build prompt từ Continuity Bible...',
  rendering: 'Đang gen từng shot trên AtlasCloud...',
  assembling: 'FFmpeg ghép clip + dán audio...',
  uploading: 'Upload lên storage...',
  done: 'Hoàn tất',
  failed: 'Lỗi',
  cancelled: 'Đã huỷ',
};

export function JobResultModal({ open, jobId, onClose, onRetry, estimatedDurationS, jobStartedAt }: Props) {
  const { job, error, timedOut } = useDirectorJobPoll(jobId);
  const { cancel, isCancelling } = useJobCancel();
  const [cancelConfirm, setCancelConfirm] = useState(false);
  const status = job?.status ?? 'pending';
  const progress = job?.progress ?? 0;
  const isDone = status === 'done';
  const isFailed = status === 'failed' || status === 'cancelled';
  const isWorking = !isDone && !isFailed && !timedOut;

  // V5.3 — ETA uses stable job start time from parent (persisted in localStorage)
  // instead of mountedAt which reset on every modal remount → wild ETA jumps.
  // Skip ETA entirely when progress < 10% (too noisy — projection inflates 10×).
  const totalExpectedS = (estimatedDurationS ?? 15) * 5 + 60;  // +60s plan/upload overhead
  const anchorTime = jobStartedAt ?? Date.now();
  const elapsedS = Math.max(0, (Date.now() - anchorTime) / 1000);
  // V5.3 — math fix: when progress=0%, don't divide by 0.05 (inflates 20×).
  // Only project when we have meaningful progress signal.
  const showEta = isWorking && progress >= 10 && progress < 95;
  const fractionDone = Math.max(0.10, Math.min(0.95, progress / 100));
  const projectedTotalS = elapsedS / fractionDone;
  const secondsLeft = showEta
    ? Math.max(0, Math.min(projectedTotalS, totalExpectedS) - elapsedS)
    : 0;

  // V5.1 — toast on terminal status changes (visible even when modal minimized)
  useEffect(() => {
    if (isDone) toast.success(`Render hoàn tất ${job?.elapsed_s ? `· ${Math.round(job.elapsed_s)}s` : ''}`);
  }, [isDone, job?.elapsed_s]);
  useEffect(() => {
    if (status === 'failed') toast.error(`Render failed: ${job?.error_message ?? 'unknown'}`, { duration: 10000 });
    if (status === 'cancelled') toast.info('Job đã hủy');
  }, [status, job?.error_message]);

  const handleCancel = async () => {
    if (!jobId) return;
    if (!cancelConfirm) {
      setCancelConfirm(true);
      setTimeout(() => setCancelConfirm(false), 4000);
      return;
    }
    try {
      const res = await cancel(jobId);
      toast.success(
        `Đã hủy job — vendor predictions killed ${res.vendor_cancelled_count ?? 0}/${res.vendor_total_predictions ?? 0}`
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Cancel failed: ${msg}`);
    }
    setCancelConfirm(false);
  };
  const videoUrl = (job?.output_url || job?.output_path || '') as string;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isDone ? 'Render hoàn tất' : 'Đang render video'}
      subtitle={jobId ? `Job ${jobId}` : undefined}
      maxWidth="max-w-3xl"
    >
      <div className="p-6 md:p-8 space-y-6">
        {/* Status section */}
        {isWorking && (
          <div className="surface-2 rounded-card p-5">
            <div className="flex items-center gap-3 mb-4">
              <Loader2 size={18} className="text-accent-magenta animate-spin" />
              <div>
                <div className="text-sm font-semibold">{STAGE_LABELS_VN[status] || status}</div>
                {job?.current_step && (
                  <div className="text-xs text-text-subtle mt-0.5">{job.current_step}</div>
                )}
              </div>
              <div className="ml-auto flex items-center gap-2 text-xs">
                {showEta && (
                  <span className="text-accent-cyan flex items-center gap-1">
                    <Clock size={11} /> {formatEta(secondsLeft)}
                  </span>
                )}
                <span className="text-text-muted">{progress}%</span>
              </div>
            </div>
            <div className="h-1.5 rounded-full bg-surface-3 overflow-hidden">
              <div
                className="h-full bg-cta-gradient transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-[11px] text-text-subtle mt-3 leading-relaxed">
              Render thật ~2-5 phút cho 15s video. Anh có thể đóng modal, job vẫn chạy nền —
              vào tab History xem kết quả khi xong.
            </p>
            {/* Cancel button — 2-click confirm to prevent accidental cancel */}
            <div className="mt-4 flex items-center justify-between">
              <span className="text-[11px] text-text-subtle">
                Cost dự kiến vẫn tính dù bạn hủy giữa chừng (vendor đã charge phần đã gen)
              </span>
              <button
                onClick={handleCancel}
                disabled={isCancelling}
                className={`btn-outline text-xs px-3 py-1.5 ${
                  cancelConfirm ? 'border-accent-orange/60 text-accent-orange bg-accent-orange/10' : ''
                }`}
              >
                {isCancelling ? (
                  <><Loader2 size={12} className="animate-spin" /> Đang hủy...</>
                ) : cancelConfirm ? (
                  <><X size={12} /> Xác nhận hủy job</>
                ) : (
                  <><X size={12} /> Hủy render</>
                )}
              </button>
            </div>
          </div>
        )}

        {/* V5.1 — Stuck timeout */}
        {timedOut && !isFailed && !isDone && (
          <div className="surface-2 rounded-card p-5 border-accent-yellow/40">
            <div className="flex items-start gap-3">
              <Clock size={18} className="text-accent-yellow shrink-0 mt-0.5" />
              <div className="flex-1">
                <div className="text-sm font-semibold text-accent-yellow">
                  Job có vẻ stuck — đã chạy quá 15 phút
                </div>
                <p className="text-xs text-text-muted mt-2 leading-relaxed">
                  Render thường mất 2-5 phút. Quá lâu có thể vendor đang queue cao hoặc server bị treo.
                  Anh có thể: (1) Hủy job để dừng và tránh bị charge thêm, (2) Đóng modal, vào tab History sau 30 phút check lại.
                </p>
                <div className="mt-4 flex gap-2">
                  <button onClick={handleCancel} disabled={isCancelling} className="btn-outline">
                    {isCancelling ? (
                      <><Loader2 size={12} className="animate-spin" /> Đang hủy...</>
                    ) : cancelConfirm ? (
                      <><X size={12} /> Xác nhận hủy</>
                    ) : (
                      <><X size={12} /> Hủy job</>
                    )}
                  </button>
                  <button onClick={onClose} className="btn-ghost">Đóng (giữ job chạy nền)</button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Error */}
        {isFailed && (
          <div className="surface-2 rounded-card p-5 border-accent-orange/40">
            <div className="flex items-start gap-3">
              <AlertTriangle size={18} className="text-accent-orange shrink-0 mt-0.5" />
              <div className="flex-1">
                <div className="text-sm font-semibold text-accent-orange">
                  {STAGE_LABELS_VN[status]}
                </div>
                {job?.error_message && (
                  <p className="text-xs text-text-muted mt-2 leading-relaxed font-mono">
                    {job.error_message}
                  </p>
                )}
                {error && (
                  <p className="text-xs text-text-subtle mt-2">{error}</p>
                )}
                {onRetry && (
                  <button onClick={onRetry} className="btn-outline mt-4">
                    <RotateCcw size={14} /> Thử lại
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Done — video player */}
        {isDone && videoUrl && (
          <>
            <div className="relative rounded-card overflow-hidden bg-black aspect-video">
              <video
                src={videoUrl}
                controls
                className="w-full h-full"
                playsInline
              />
            </div>
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs text-text-muted">
                {job?.elapsed_s && <span>Render time: {Math.round(job.elapsed_s)}s</span>}
                {job?.cost_actual_usd !== undefined && (
                  <span> · Cost: ${job.cost_actual_usd.toFixed(2)}</span>
                )}
              </div>
              <div className="flex gap-2">
                <a
                  href={videoUrl}
                  download
                  className="btn-outline"
                >
                  <Download size={14} /> Download MP4
                </a>
                <button onClick={onClose} className="btn-cta">
                  <Sparkles size={14} /> Tạo video khác
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
