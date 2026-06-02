'use client';

import { AlertTriangle, BadgeCheck, DollarSign, Loader2, Play, ShieldCheck } from 'lucide-react';

export interface RenderReviewSpend {
  totalSeconds?: number;
  lowUsd?: number;
  highUsd?: number;
}

export interface RenderReviewScene {
  id: string;
  label?: string;
  prompt?: string;
}

export interface RenderReviewBlocker {
  key: string;
  label: string;
  detail?: string;
  severity?: string;
}

export interface RenderReviewPanelProps {
  approved: boolean;
  renderSourceReady: boolean;
  loading?: boolean;
  planning?: boolean;
  renderDisabled?: boolean;
  referencesConfirmed?: boolean;
  approvalLockRevision?: number;
  spendPreview?: RenderReviewSpend | null;
  scenes: readonly RenderReviewScene[];
  blockers: readonly RenderReviewBlocker[];
  dryRunReport?: Record<string, unknown> | null;
  onApprove: () => void | Promise<void>;
  onRender: () => void | Promise<void>;
}

function costRange(spend?: RenderReviewSpend | null) {
  if (!spend) return 'Pending';
  return `$${(spend.lowUsd ?? 0).toFixed(2)} - $${(spend.highUsd ?? 0).toFixed(2)}`;
}

export function RenderReviewPanel({
  approved,
  renderSourceReady,
  loading = false,
  planning = false,
  renderDisabled = false,
  referencesConfirmed = false,
  approvalLockRevision = 0,
  spendPreview,
  scenes,
  blockers,
  dryRunReport,
  onApprove,
  onRender,
}: RenderReviewPanelProps) {
  const hardBlockers = blockers.filter((blocker) => blocker.severity !== 'warning');
  const approveLabel = approved ? 'Plan approved' : 'Approve plan';
  const renderLabel = loading ? 'Rendering video' : planning ? 'Planning' : renderSourceReady ? 'Generate full video' : 'Lock plan first';

  return (
    <section className="rounded-sheet border border-hairline bg-surface-1 p-4 shadow-card-soft">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-bold uppercase tracking-normal text-accent-cyan">
            Render review
          </div>
          <h2 className="mt-1 text-lg font-extrabold text-text">Approve before spend</h2>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${
          renderSourceReady
            ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
            : 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange'
        }`}>
          <ShieldCheck size={12} />
          {renderSourceReady ? 'ApprovalLock enforced' : `ApprovalLock v${approvalLockRevision}`}
        </span>
      </div>

      <div className="grid gap-3">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-card border border-hairline bg-surface-2 px-3 py-3">
            <div className="mb-1 flex items-center gap-1.5 text-[10px] font-bold uppercase text-text-subtle">
              <DollarSign size={12} />
              Cost estimate
            </div>
            <div className="text-sm font-extrabold text-text">{costRange(spendPreview)}</div>
          </div>
          <div className="rounded-card border border-hairline bg-surface-2 px-3 py-3">
            <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">Runtime</div>
            <div className="text-sm font-extrabold text-text">
              {spendPreview?.totalSeconds ? `${spendPreview.totalSeconds}s` : 'Pending'}
            </div>
          </div>
          <div className="rounded-card border border-hairline bg-surface-2 px-3 py-3">
            <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">Prompts</div>
            <div className="text-sm font-extrabold text-text">
              {scenes.filter((scene) => scene.prompt?.trim()).length}/{scenes.length}
            </div>
          </div>
        </div>

        {blockers.length > 0 && (
          <div className="rounded-card border border-accent-orange/25 bg-accent-orange/10 p-3">
            <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase text-accent-orange">
              <AlertTriangle size={14} />
              Render blockers
            </div>
            <div className="grid gap-2">
              {blockers.map((blocker) => (
                <div key={blocker.key} className="rounded-card border border-accent-orange/20 bg-surface-1/70 px-3 py-2">
                  <div className="text-xs font-bold text-text">{blocker.label}</div>
                  {blocker.detail && <p className="mt-1 text-xs leading-relaxed text-text-muted">{blocker.detail}</p>}
                </div>
              ))}
            </div>
          </div>
        )}

        {dryRunReport && (
          <div className="rounded-card border border-hairline bg-surface-2 px-3 py-3">
            <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">Dry-run</div>
            <p className="text-xs leading-relaxed text-text-muted">
              Payload preview is available. Confirm prompts, references, model, duration, and cost before render.
            </p>
          </div>
        )}

        <div className="grid gap-2 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => void onApprove()}
            disabled={planning || loading || (approved && renderSourceReady) || !referencesConfirmed}
            className="btn-outline justify-center px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-50"
          >
            {approved ? <BadgeCheck size={16} /> : <ShieldCheck size={16} />}
            {approveLabel}
          </button>
          <button
            type="button"
            onClick={() => void onRender()}
            disabled={renderDisabled || hardBlockers.length > 0}
            className="inline-flex items-center justify-center gap-2 rounded-card bg-cta-gradient px-4 py-3 text-sm font-bold text-white shadow-cta-glow transition hover:brightness-110 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-45"
          >
            {loading || planning ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} fill="currentColor" />}
            {renderLabel}
          </button>
        </div>
      </div>
    </section>
  );
}
