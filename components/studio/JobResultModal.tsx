'use client';

import { X, Download, Loader2, AlertCircle, CheckCircle2, Sparkles } from 'lucide-react';
import type { JobStatus } from '@/lib/types/backend';

interface JobResultModalProps {
  status: JobStatus | null;
  error: string | null;
  onClose: () => void;
  onCancel: () => void;
}

const STEP_LABELS_VN: Record<string, string> = {
  pending: 'Đang khởi tạo...',
  scraping: 'Đang đọc thông tin sản phẩm...',
  analyzing: 'AI đang phân tích sản phẩm + nhân vật...',
  generating: 'AI viết kịch bản + prompt video...',
  rendering: 'Đang render video (mất 1-3 phút)...',
  voicing: 'Đang lồng tiếng Việt...',
  sfx: 'Đang tạo hiệu ứng âm thanh ASMR...',
  assembling: 'Đang ghép video + audio + caption...',
  uploading: 'Đang upload kết quả...',
  done: 'Hoàn tất!',
  failed: 'Đã xảy ra lỗi',
};

export function JobResultModal({ status, error, onClose, onCancel }: JobResultModalProps) {
  if (!status && !error) return null;

  const isDone = status?.status === 'done';
  const isFailed = status?.status === 'failed' || error;
  const isWorking = !isDone && !isFailed;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur p-4">
      <div className="relative w-full max-w-md rounded-2xl bg-gradient-to-br from-[#1a0610] to-[#0a0507] border border-rose-900/40 shadow-2xl shadow-rose-900/30 overflow-hidden">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-10 p-1.5 rounded-md text-white/40 hover:text-white hover:bg-white/10 transition"
          aria-label="Đóng"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Header */}
        <div className="px-6 pt-6 pb-4 border-b border-white/5">
          <div className="flex items-center gap-3">
            {isWorking && (
              <div className="w-10 h-10 rounded-full bg-rose-500/20 flex items-center justify-center">
                <Loader2 className="w-5 h-5 text-rose-300 animate-spin" />
              </div>
            )}
            {isDone && (
              <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5 text-emerald-300" />
              </div>
            )}
            {isFailed && (
              <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center">
                <AlertCircle className="w-5 h-5 text-red-300" />
              </div>
            )}
            <div>
              <div className="text-xs uppercase tracking-widest text-rose-300/70 font-medium">
                {isDone ? 'Video sẵn sàng' : isFailed ? 'Lỗi' : 'Đang tạo video UGC'}
              </div>
              <div className="text-sm text-white/90 font-medium mt-0.5">
                {error || STEP_LABELS_VN[status?.status || 'pending'] || status?.current_step}
              </div>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-5">
          {isWorking && status && (
            <>
              {/* Progress bar */}
              <div className="mb-4">
                <div className="flex justify-between items-center mb-1.5">
                  <span className="text-[11px] text-white/50">Tiến độ</span>
                  <span className="text-[11px] text-rose-300 font-bold">{status.progress}%</span>
                </div>
                <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-rose-500 to-pink-500 transition-all duration-500"
                    style={{ width: `${status.progress}%` }}
                  />
                </div>
              </div>

              {/* Time remaining */}
              {status.estimated_remaining_s && (
                <div className="text-[12px] text-white/60 mb-4">
                  Thời gian còn lại: ~{Math.ceil(status.estimated_remaining_s / 60)} phút
                </div>
              )}

              {/* Cancel button */}
              <button
                onClick={onCancel}
                className="w-full px-4 py-2.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white/70 text-sm font-medium transition"
              >
                Huỷ
              </button>
            </>
          )}

          {isDone && status?.output_url && (
            <>
              {/* Video preview */}
              <div className="aspect-[9/16] mb-4 rounded-xl overflow-hidden bg-black border border-white/10">
                <video src={status.output_url} controls className="w-full h-full" />
              </div>

              {/* Info */}
              <div className="flex justify-between text-[12px] text-white/60 mb-4">
                <span>Thời lượng: {status.duration_s}s</span>
                <span>
                  Chi phí: {((status.cost_actual_usd || 0) * 24500).toLocaleString('vi-VN')}đ
                </span>
              </div>

              {/* Action buttons */}
              <div className="flex gap-2">
                <a
                  href={status.output_url}
                  download={`ugc-${status.job_id}.mp4`}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-gradient-to-br from-rose-500 to-pink-600 hover:from-rose-400 hover:to-pink-500 text-white text-sm font-semibold transition shadow-lg shadow-rose-600/40"
                >
                  <Download className="w-4 h-4" /> Tải xuống MP4
                </a>
                <button
                  onClick={onClose}
                  className="px-4 py-2.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white/70 text-sm font-medium transition flex items-center gap-1.5"
                >
                  <Sparkles className="w-4 h-4" /> Tạo video khác
                </button>
              </div>
            </>
          )}

          {isFailed && (
            <>
              <div className="text-[13px] text-red-300/80 mb-4 leading-relaxed">
                {error || status?.error_message || 'Không xác định lỗi. Vui lòng thử lại.'}
              </div>
              <button
                onClick={onClose}
                className="w-full px-4 py-2.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white/80 text-sm font-medium transition"
              >
                Đóng
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
