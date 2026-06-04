'use client';

import { AlertTriangle, BadgeCheck, DollarSign, Loader2, Play, ShieldCheck, XCircle } from 'lucide-react';

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

export interface LongformReviewSegment {
  segment_id?: string;
  index?: number;
  start_s?: number;
  duration_s?: number;
  objective?: string;
  entry_state?: Record<string, unknown>;
  exit_state?: Record<string, unknown>;
  handoff_requirements?: string[];
  status?: string;
}

export interface LongformReviewPlan {
  longform_plan_id?: string;
  total_duration_s?: number;
  continuity_pressure?: string;
  segments?: LongformReviewSegment[];
  warnings?: string[];
}

export interface ConsistencyReviewPolicy {
  action?: string;
  reasons?: string[];
  review_approved?: boolean;
  review_decision?: string;
  review_reason?: string;
  reviewed_segment_ids?: string[];
}

export interface ConsistencyReviewHistoryItem {
  decision: 'approved' | 'rejected';
  reason: string;
  segmentIds: string[];
  createdAt: string;
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
  longformPlan?: LongformReviewPlan | null;
  consistencyPolicy?: ConsistencyReviewPolicy | null;
  consistencyReviewApproved?: boolean;
  consistencyReviewReason?: string;
  consistencyReviewDecision?: 'pending' | 'approved' | 'rejected';
  consistencyReviewHistory?: readonly ConsistencyReviewHistoryItem[];
  approvedSegmentIds?: readonly string[];
  onToggleSegmentApproval?: (segmentId: string) => void;
  onApproveAllSegments?: () => void;
  onConsistencyReviewReasonChange?: (reason: string) => void;
  onConsistencyReviewApprove?: () => void;
  onConsistencyReviewReject?: () => void;
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
  longformPlan,
  consistencyPolicy,
  consistencyReviewApproved = false,
  consistencyReviewReason = '',
  consistencyReviewDecision = 'pending',
  consistencyReviewHistory = [],
  approvedSegmentIds = [],
  onToggleSegmentApproval,
  onApproveAllSegments,
  onConsistencyReviewReasonChange,
  onConsistencyReviewApprove,
  onConsistencyReviewReject,
  onApprove,
  onRender,
}: RenderReviewPanelProps) {
  const hardBlockers = blockers.filter((blocker) => blocker.severity !== 'warning');
  const approveLabel = approved ? 'Plan approved' : 'Approve plan';
  const longformSegments = longformPlan?.segments ?? [];
  const segmentReviewComplete = longformSegments.length === 0
    || longformSegments.every((segment) => segment.segment_id && approvedSegmentIds.includes(segment.segment_id));
  const needsConsistencyReview = consistencyPolicy?.action === 'requires_review';
  const renderLabel = loading ? 'Rendering video' : planning ? 'Planning' : renderSourceReady ? 'Generate full video' : 'Run dry-run first';

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

        {longformSegments.length > 0 && (
          <div className="rounded-card border border-hairline bg-surface-2 p-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-[10px] font-bold uppercase text-text-subtle">Long-form segments</div>
                <div className="mt-1 text-xs text-text-muted">
                  {longformPlan?.total_duration_s ?? '-'}s / {longformSegments.length} segments / continuity {longformPlan?.continuity_pressure || 'medium'}
                </div>
              </div>
              {onApproveAllSegments && (
                <button type="button" onClick={onApproveAllSegments} className="btn-outline px-3 py-1.5 text-xs">
                  <BadgeCheck size={13} />
                  Approve all
                </button>
              )}
            </div>
            <div className="grid gap-2">
              {longformSegments.map((segment, index) => {
                const id = segment.segment_id || `segment-${index + 1}`;
                const approvedSegment = approvedSegmentIds.includes(id);
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => onToggleSegmentApproval?.(id)}
                    className={`rounded-card border px-3 py-2 text-left transition ${
                      approvedSegment
                        ? 'border-accent-cyan/35 bg-accent-cyan/10'
                        : 'border-accent-orange/30 bg-accent-orange/10'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold text-text">
                        Segment {index + 1} · {segment.duration_s ?? '-'}s
                      </span>
                      <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${
                        approvedSegment
                          ? 'border-accent-cyan/25 text-accent-cyan'
                          : 'border-accent-orange/25 text-accent-orange'
                      }`}>
                        {approvedSegment ? 'Approved' : 'Needs review'}
                      </span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-text-muted">
                      {segment.objective || 'Segment objective pending'}
                    </p>
                  </button>
                );
              })}
            </div>
            {!segmentReviewComplete && (
              <p className="mt-2 text-xs text-accent-orange">
                Every segment must be approved before paid long-form render.
              </p>
            )}
          </div>
        )}

        {needsConsistencyReview && (
          <div className="rounded-card border border-accent-orange/25 bg-accent-orange/10 p-3">
            <div className="mb-1 flex items-center gap-2 text-xs font-bold uppercase text-accent-orange">
              <AlertTriangle size={14} />
              Consistency review
            </div>
            <p className="text-xs leading-relaxed text-text-muted">
              The consistency policy requires manual approval before paid render.
              {(consistencyPolicy?.reasons ?? []).length > 0 ? ` Reasons: ${(consistencyPolicy?.reasons ?? []).join(', ')}.` : ''}
            </p>
            <div className="mt-3 grid gap-2">
              <textarea
                value={consistencyReviewReason}
                onChange={(event) => onConsistencyReviewReasonChange?.(event.target.value)}
                rows={3}
                placeholder="Review note: why this consistency risk is acceptable, or what must be fixed before render."
                className="min-h-20 w-full rounded-card border border-hairline bg-surface-1/80 px-3 py-2 text-xs text-text outline-none placeholder:text-text-subtle focus:border-accent-cyan/50"
              />
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={onConsistencyReviewApprove}
                  disabled={consistencyReviewApproved || consistencyReviewReason.trim().length < 3}
                  className="btn-outline px-3 py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {consistencyReviewApproved ? <BadgeCheck size={13} /> : <ShieldCheck size={13} />}
                  {consistencyReviewApproved ? 'Consistency approved' : 'Approve with note'}
                </button>
                <button
                  type="button"
                  onClick={onConsistencyReviewReject}
                  disabled={consistencyReviewReason.trim().length < 3}
                  className="btn-outline border-accent-orange/30 px-3 py-1.5 text-xs text-accent-orange disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <XCircle size={13} />
                  Reject with reason
                </button>
              </div>
              <div className="text-[11px] text-text-muted">
                Decision: <span className="font-semibold text-text">{consistencyReviewDecision}</span>
              </div>
              {consistencyReviewHistory.length > 0 && (
                <div className="rounded-card border border-hairline bg-surface-1/60 p-2">
                  <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">Review history</div>
                  <div className="grid gap-1">
                    {consistencyReviewHistory.slice(-3).map((item) => (
                      <div key={`${item.createdAt}-${item.decision}`} className="text-[11px] leading-relaxed text-text-muted">
                        <span className="font-semibold text-text">{item.decision}</span>
                        {' '}({item.segmentIds.length} segments): {item.reason}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
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
