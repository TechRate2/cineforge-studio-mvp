'use client';
import { Modal } from '@/components/ui/Modal';
import { AlertTriangle, Coins, Sparkles, X } from 'lucide-react';

interface Props {
  open: boolean;
  estimatedCostUsd: number;
  estimatedDurationS: number;
  shotCount: number;
  modelName: string;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

/** V5.2 — Show before approving any render > $1.50 so users see a concrete
 *  number and click confirm. Below threshold the modal is skipped (anti-friction). */
export const COST_CONFIRM_THRESHOLD_USD = 1.5;

export function CostConfirmDialog({
  open, estimatedCostUsd, estimatedDurationS, shotCount, modelName,
  onConfirm, onCancel, isLoading,
}: Props) {
  const isExpensive = estimatedCostUsd >= 3.0;
  return (
    <Modal open={open} onClose={onCancel} maxWidth="max-w-md" showClose={false}>
      <div className="p-6">
        <div className={`w-12 h-12 rounded-card grid place-items-center mb-4
                        ${isExpensive ? 'bg-accent-orange/15' : 'bg-accent-yellow/15'}`}>
          {isExpensive
            ? <AlertTriangle size={22} className="text-accent-orange" />
            : <Coins size={22} className="text-accent-yellow" />}
        </div>

        <h2 className="text-xl font-bold tracking-tight mb-2">
          Confirm chi phí render
        </h2>
        <p className="text-sm text-text-muted leading-relaxed mb-5">
          Render này sẽ tiêu tốn <b className="text-accent-magenta">${estimatedCostUsd.toFixed(2)}</b>{' '}
          (≈ {Math.round(estimatedCostUsd * 24500).toLocaleString('vi-VN')}đ) từ wallet AtlasCloud của anh.
          Cancel giữa chừng vẫn bị charge phần vendor đã render.
        </p>

        <div className="surface-2 rounded-card p-4 space-y-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-text-muted">Model</span>
            <span className="font-mono text-xs">{modelName}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-text-muted">Duration</span>
            <span>{estimatedDurationS}s · {shotCount} shot{shotCount > 1 ? 's' : ''}</span>
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-hairline">
            <span className="text-text-muted">Total</span>
            <span className="text-lg font-bold text-accent-magenta">
              ${estimatedCostUsd.toFixed(2)}
            </span>
          </div>
        </div>

        <div className="mt-6 flex gap-2 justify-end">
          <button onClick={onCancel} disabled={isLoading} className="btn-outline">
            <X size={14} /> Quay lại
          </button>
          <button onClick={onConfirm} disabled={isLoading} className="btn-cta">
            <Sparkles size={14} />
            Xác nhận render · ${estimatedCostUsd.toFixed(2)}
          </button>
        </div>
      </div>
    </Modal>
  );
}
