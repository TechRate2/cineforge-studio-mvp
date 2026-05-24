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
  /** V5.15.1 Sprint 1A — Master Board cost included in total; shown as separate
   *  line item when > 0 so user understands the +$0.04 surcharge buys 2-layer
   *  identity lock (vision LLM + ultra-wide pixel canvas anchor). */
  masterBoardCostUsd?: number;
}

/** V5.2 — Show before approving any render > $1.50 so users see a concrete
 *  number and click confirm. Below threshold the modal is skipped (anti-friction). */
export const COST_CONFIRM_THRESHOLD_USD = 1.5;

export function CostConfirmDialog({
  open, estimatedCostUsd, estimatedDurationS, shotCount, modelName,
  onConfirm, onCancel, isLoading, masterBoardCostUsd = 0,
}: Props) {
  // V5.15.2 C2 — Grand total includes Master Board cost so what user sees in
  // header/Total/button matches the actual wallet deduction. Master board is
  // billed out-of-band via /storyboard/master, so plan.cost_estimate doesn't
  // include it — we add it here for accurate disclosure.
  const grandTotalUsd = estimatedCostUsd + masterBoardCostUsd;
  const isExpensive = grandTotalUsd >= 3.0;
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
          Render này sẽ tiêu tốn <b className="text-accent-magenta">${grandTotalUsd.toFixed(2)}</b>{' '}
          (≈ {Math.round(grandTotalUsd * 24500).toLocaleString('vi-VN')}đ) từ wallet AtlasCloud của anh.
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
          {masterBoardCostUsd > 0 && (
            <>
              <div className="flex items-center justify-between">
                <span className="text-text-muted">Render</span>
                <span className="text-xs">${estimatedCostUsd.toFixed(2)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-text-muted flex items-center gap-1.5">
                  Master Board
                  <span className="text-[10px] text-text-subtle">(identity lock)</span>
                </span>
                <span className="text-xs">${masterBoardCostUsd.toFixed(2)}</span>
              </div>
            </>
          )}
          <div className="flex items-center justify-between pt-2 border-t border-hairline">
            <span className="text-text-muted">Total</span>
            <span className="text-lg font-bold text-accent-magenta">
              ${grandTotalUsd.toFixed(2)}
            </span>
          </div>
        </div>

        <div className="mt-6 flex gap-2 justify-end">
          <button onClick={onCancel} disabled={isLoading} className="btn-outline">
            <X size={14} /> Quay lại
          </button>
          <button onClick={onConfirm} disabled={isLoading} className="btn-cta">
            <Sparkles size={14} />
            Xác nhận render · ${grandTotalUsd.toFixed(2)}
          </button>
        </div>
      </div>
    </Modal>
  );
}
