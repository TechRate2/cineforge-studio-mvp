'use client';
import { Modal } from '@/components/ui/Modal';
import { Download, AlertTriangle, Loader2, Sparkles, RotateCcw } from 'lucide-react';
import { useDirectorJobPoll } from '@/lib/studio/use-director-job-poll';

interface Props {
  open: boolean;
  jobId: string | null;
  onClose: () => void;
  onRetry?: () => void;
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

export function JobResultModal({ open, jobId, onClose, onRetry }: Props) {
  const { job, error } = useDirectorJobPoll(jobId);
  const status = job?.status ?? 'pending';
  const progress = job?.progress ?? 0;
  const isDone = status === 'done';
  const isFailed = status === 'failed' || status === 'cancelled';
  const isWorking = !isDone && !isFailed;
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
              <div className="ml-auto text-xs text-text-muted">{progress}%</div>
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
