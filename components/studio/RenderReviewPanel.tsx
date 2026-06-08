'use client';

import type { ReactNode } from 'react';
import {
  AlertTriangle,
  BadgeCheck,
  ClipboardCheck,
  DollarSign,
  GitBranch,
  Layers3,
  Loader2,
  Play,
  ShieldCheck,
  Sparkles,
  XCircle,
} from 'lucide-react';

export interface RenderReviewSpend {
  totalSeconds?: number;
  lowUsd?: number;
  highUsd?: number;
}

export interface RenderReviewScene {
  id: string;
  label?: string;
  prompt?: string;
  durationS?: number;
  modelKey?: string;
  renderMode?: string;
  refs?: string[];
  status?: string;
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
  last_frame_anchor?: Record<string, unknown>;
  handoff_requirements?: string[];
  status?: string;
}

export interface LongformReviewPlan {
  longform_plan_id?: string;
  total_duration_s?: number;
  continuity_pressure?: string;
  segment_graph_hash?: string;
  continuity_bible_hash?: string;
  segments?: LongformReviewSegment[];
  handoffs?: Array<Record<string, unknown>>;
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

interface DryRunSummary {
  status: string;
  renderPath?: string;
  exactPayloads?: number;
  payloadSource?: string;
  costUsd?: number;
  warnings: string[];
  blockers: string[];
}

interface ReferenceInsightSummary {
  assetId: string;
  kind: string;
  tag?: string;
  role: string;
  readiness: string;
  roleConfidence?: number;
  roleLocked: boolean;
  bestUse?: string;
  warnings: string[];
  missingConfirmations: string[];
}

interface ReferenceIntelligenceSummary {
  status: string;
  assetCount: number;
  imageCount: number;
  videoCount: number;
  audioCount: number;
  missingRequiredRoles: string[];
  warnings: string[];
  blockers: string[];
  insights: ReferenceInsightSummary[];
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
  const hardBlockers = blockers.filter((blocker) => blocker.severity !== 'soft' && blocker.severity !== 'warning');
  const dryRunSummary = summarizeDryRunReport(dryRunReport);
  const referenceSummary = summarizeReferenceIntelligence(dryRunReport);
  const longformSegments = longformPlan?.segments ?? [];
  const approvedSegmentCount = longformSegments.filter((segment, index) => (
    approvedSegmentIds.includes(segment.segment_id || `segment-${index + 1}`)
  )).length;
  const segmentReviewComplete = longformSegments.length === 0 || approvedSegmentCount === longformSegments.length;
  const needsConsistencyReview = consistencyPolicy?.action === 'requires_review';
  const consistencyComplete = !needsConsistencyReview || consistencyReviewApproved;
  const readinessStatus = readinessLabel({
    approved,
    renderSourceReady,
    referencesConfirmed,
    segmentReviewComplete,
    consistencyComplete,
    hardBlockerCount: hardBlockers.length,
  });
  const approveLabel = approved ? 'Dry-run locked' : longformSegments.length > 0 ? 'Refresh dry-run' : 'Approve plan';
  const renderLabel = loading ? 'Rendering video' : planning ? 'Planning' : renderSourceReady ? 'Generate full video' : 'Run dry-run first';

  return (
    <section className="rounded-sheet border border-hairline bg-surface-1 p-4 shadow-card-soft">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-bold uppercase tracking-normal text-accent-cyan">
            Render review
          </div>
          <h2 className="mt-1 text-lg font-extrabold text-text">Lock the exact render plan</h2>
          <p className="mt-1 max-w-xl text-xs leading-relaxed text-text-muted">
            Dry-run first, inspect segment continuity, approve any consistency risk, then start the paid Seedance render.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${
            renderSourceReady
              ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
              : 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange'
          }`}>
            <ShieldCheck size={12} />
            {renderSourceReady ? 'ApprovalLock enforced' : `ApprovalLock v${approvalLockRevision}`}
          </span>
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${
            readinessStatus.tone === 'cyan'
              ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
              : 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange'
          }`}>
            <ClipboardCheck size={12} />
            {readinessStatus.label}
          </span>
        </div>
      </div>

      <div className="grid gap-3">
        <div className="grid gap-3 sm:grid-cols-4">
          <StatTile icon={<DollarSign size={12} />} label="Cost estimate" value={costRange(spendPreview)} />
          <StatTile label="Runtime" value={spendPreview?.totalSeconds ? `${spendPreview.totalSeconds}s` : 'Pending'} />
          <StatTile label="Prompts" value={`${scenes.filter((scene) => scene.prompt?.trim()).length}/${scenes.length}`} />
          <StatTile
            label="Review gates"
            value={longformSegments.length > 0 ? `${approvedSegmentCount}/${longformSegments.length} segments` : consistencyComplete ? 'Ready' : 'Needs note'}
          />
        </div>

        {blockers.length > 0 && <BlockerPanel blockers={blockers} />}

        {(dryRunReport || longformSegments.length > 0) && (
          <DryRunReadinessPanel
            summary={dryRunSummary}
            sceneCount={scenes.length}
            longformSegmentCount={longformSegments.length}
            approved={approved}
            renderSourceReady={renderSourceReady}
          />
        )}

        {referenceSummary && <ReferenceIntelligencePanel summary={referenceSummary} />}

        {longformSegments.length > 0 && (
          <LongformReviewFlow
            plan={longformPlan}
            approvedSegmentIds={approvedSegmentIds}
            onToggleSegmentApproval={onToggleSegmentApproval}
            onApproveAllSegments={onApproveAllSegments}
          />
        )}

        {needsConsistencyReview && (
          <ConsistencyReviewBox
            policy={consistencyPolicy}
            approved={consistencyReviewApproved}
            decision={consistencyReviewDecision}
            reason={consistencyReviewReason}
            history={consistencyReviewHistory}
            onReasonChange={onConsistencyReviewReasonChange}
            onApprove={onConsistencyReviewApprove}
            onReject={onConsistencyReviewReject}
          />
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

function StatTile({
  icon,
  label,
  value,
}: {
  icon?: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-card border border-hairline bg-surface-2 px-3 py-3">
      <div className="mb-1 flex items-center gap-1.5 text-[10px] font-bold uppercase text-text-subtle">
        {icon}
        {label}
      </div>
      <div className="truncate text-sm font-extrabold text-text">{value}</div>
    </div>
  );
}

function BlockerPanel({ blockers }: { blockers: readonly RenderReviewBlocker[] }) {
  return (
    <div className="rounded-card border border-accent-orange/25 bg-accent-orange/10 p-3">
      <div className="mb-2 flex items-center gap-2 text-xs font-bold uppercase text-accent-orange">
        <AlertTriangle size={14} />
        Render blockers
      </div>
      <div className="grid gap-2">
        {blockers.map((blocker) => (
          <div key={blocker.key} className="rounded-card border border-accent-orange/20 bg-surface-1/70 px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-xs font-bold text-text">{blocker.label}</div>
              <span className="rounded-full border border-accent-orange/25 px-2 py-0.5 text-[10px] font-semibold uppercase text-accent-orange">
                {blocker.severity || 'hard'}
              </span>
            </div>
            {blocker.detail && <p className="mt-1 text-xs leading-relaxed text-text-muted">{blocker.detail}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

function DryRunReadinessPanel({
  summary,
  sceneCount,
  longformSegmentCount,
  approved,
  renderSourceReady,
}: {
  summary: DryRunSummary | null;
  sceneCount: number;
  longformSegmentCount: number;
  approved: boolean;
  renderSourceReady: boolean;
}) {
  const warningCount = (summary?.warnings.length ?? 0) + (summary?.blockers.length ?? 0);
  return (
    <div className="rounded-card border border-hairline bg-surface-2 p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-start gap-2">
          <Sparkles size={15} className="mt-0.5 text-accent-cyan" />
          <div>
            <div className="text-[10px] font-bold uppercase text-text-subtle">Dry-run readiness</div>
            <p className="mt-1 text-xs leading-relaxed text-text-muted">
              {longformSegmentCount > 0
                ? 'Long-form uses a saved dry-run snapshot. Paid render must reuse the exact locked plan.'
                : 'Short-form plan is locked before paid render so model, refs, prompt and cost cannot drift.'}
            </p>
          </div>
        </div>
        <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${
          renderSourceReady
            ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
            : 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange'
        }`}>
          {renderSourceReady ? 'source locked' : approved ? 'dry-run ready' : 'pending'}
        </span>
      </div>
      <div className="grid gap-2 md:grid-cols-4">
        <InfoPill label="Status" value={summary?.status || (approved ? 'approved' : 'not run')} />
        <InfoPill label="Render path" value={summary?.renderPath || (longformSegmentCount > 0 ? 'long form' : 'short form')} />
        <InfoPill label="Payloads" value={summary?.exactPayloads ? `${summary.exactPayloads}` : `${sceneCount}`} />
        <InfoPill label="Warnings" value={`${warningCount}`} tone={warningCount ? 'orange' : 'cyan'} />
      </div>
      {summary?.costUsd !== undefined && (
        <div className="mt-2 rounded-md border border-hairline bg-surface-1/70 px-3 py-2 text-[11px] text-text-muted">
          Dry-run estimated cost: <span className="font-semibold text-text">${summary.costUsd.toFixed(2)}</span>
          {summary.payloadSource ? ` · Source: ${summary.payloadSource}` : ''}
        </div>
      )}
      {summary && (summary.warnings.length > 0 || summary.blockers.length > 0) && (
        <div className="mt-2 grid gap-1">
          {[...summary.blockers, ...summary.warnings].slice(0, 4).map((item, index) => (
            <div key={`${item}-${index}`} className="text-[11px] leading-relaxed text-text-muted">
              {item.replace(/_/g, ' ')}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ReferenceIntelligencePanel({ summary }: { summary: ReferenceIntelligenceSummary }) {
  const blocked = summary.status === 'blocked' || summary.blockers.length > 0;
  const needsReview = summary.status === 'needs_review' || summary.missingRequiredRoles.length > 0 || summary.warnings.length > 0;
  const tone = blocked || needsReview ? 'orange' : 'cyan';
  const visibleIssues = [...summary.blockers, ...summary.warnings].slice(0, 4);
  return (
    <div className="rounded-card border border-hairline bg-surface-2 p-3">
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck size={15} className={tone === 'cyan' ? 'text-accent-cyan' : 'text-accent-orange'} />
          <div>
            <div className="text-[10px] font-bold uppercase text-text-subtle">Reference readiness</div>
            <div className="mt-0.5 text-xs font-semibold text-text">{formatLabel(summary.status)}</div>
          </div>
        </div>
        <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${
          tone === 'cyan'
            ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
            : 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange'
        }`}>
          {blocked ? 'blocked' : needsReview ? 'needs review' : 'ready'}
        </span>
      </div>
      <div className="grid gap-2 md:grid-cols-4">
        <InfoPill label="Assets" value={`${summary.assetCount}`} />
        <InfoPill label="Images" value={`${summary.imageCount}`} />
        <InfoPill label="Video" value={`${summary.videoCount}`} />
        <InfoPill label="Audio" value={`${summary.audioCount}`} />
      </div>
      {summary.missingRequiredRoles.length > 0 && (
        <div className="mt-2 text-[11px] leading-relaxed text-accent-orange">
          Missing: {summary.missingRequiredRoles.map(formatLabel).join(', ')}
        </div>
      )}
      {visibleIssues.length > 0 && (
        <div className="mt-2 grid gap-1">
          {visibleIssues.map((item, index) => (
            <div key={`${item}-${index}`} className="text-[11px] leading-relaxed text-text-muted">
              {formatLabel(item)}
            </div>
          ))}
        </div>
      )}
      {summary.insights.length > 0 && (
        <div className="mt-3 divide-y divide-hairline border-y border-hairline">
          {summary.insights.slice(0, 5).map((insight) => {
            const insightBlocked = insight.readiness === 'blocked';
            const insightWarn = insight.readiness === 'needs_review' || insight.warnings.length > 0 || insight.missingConfirmations.length > 0;
            return (
              <div key={insight.assetId} className="grid gap-2 py-2 md:grid-cols-[minmax(0,1fr)_140px]">
                <div>
                  <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-text">
                    <span>{insight.tag || insight.assetId}</span>
                    <span className="text-text-subtle">{formatLabel(insight.kind)}</span>
                    <span className="text-text-subtle">{formatLabel(insight.role)}</span>
                  </div>
                  {insight.bestUse && (
                    <div className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-text-muted">{insight.bestUse}</div>
                  )}
                  {[...insight.warnings, ...insight.missingConfirmations].length > 0 && (
                    <div className="mt-1 text-[11px] leading-relaxed text-text-muted">
                      {[...insight.warnings, ...insight.missingConfirmations].slice(0, 3).map(formatLabel).join(', ')}
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap items-center justify-start gap-1 md:justify-end">
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${
                    insightBlocked || insightWarn
                      ? 'border-accent-orange/25 text-accent-orange'
                      : 'border-accent-cyan/25 text-accent-cyan'
                  }`}>
                    {formatLabel(insight.readiness)}
                  </span>
                  <span className="rounded-full border border-hairline px-2 py-0.5 text-[10px] text-text-muted">
                    {insight.roleLocked ? 'locked' : 'unconfirmed'}
                  </span>
                  {insight.roleConfidence !== undefined && (
                    <span className="rounded-full border border-hairline px-2 py-0.5 text-[10px] text-text-muted">
                      {Math.round(insight.roleConfidence * 100)}%
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function LongformReviewFlow({
  plan,
  approvedSegmentIds,
  onToggleSegmentApproval,
  onApproveAllSegments,
}: {
  plan?: LongformReviewPlan | null;
  approvedSegmentIds: readonly string[];
  onToggleSegmentApproval?: (segmentId: string) => void;
  onApproveAllSegments?: () => void;
}) {
  const segments = plan?.segments ?? [];
  const approvedCount = segments.filter((segment, index) => approvedSegmentIds.includes(segment.segment_id || `segment-${index + 1}`)).length;
  const progress = segments.length > 0 ? Math.round((approvedCount / segments.length) * 100) : 100;
  const handoffs = plan?.handoffs ?? [];
  return (
    <div className="rounded-card border border-hairline bg-surface-2 p-3">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 text-[10px] font-bold uppercase text-text-subtle">
            <Layers3 size={13} />
            Long-form segment review
          </div>
          <div className="mt-1 text-xs text-text-muted">
            {plan?.total_duration_s ?? '-'}s / {segments.length} segments / continuity {plan?.continuity_pressure || 'medium'}
          </div>
        </div>
        {onApproveAllSegments && (
          <button type="button" onClick={onApproveAllSegments} className="btn-outline px-3 py-1.5 text-xs">
            <BadgeCheck size={13} />
            Approve all
          </button>
        )}
      </div>
      <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div className="h-full bg-cta-gradient transition-all duration-500" style={{ width: `${progress}%` }} />
      </div>
      <div className="grid gap-2">
        {segments.map((segment, index) => {
          const id = segment.segment_id || `segment-${index + 1}`;
          const approvedSegment = approvedSegmentIds.includes(id);
          return (
            <button
              key={id}
              type="button"
              onClick={() => onToggleSegmentApproval?.(id)}
              disabled={!onToggleSegmentApproval}
              className={`rounded-card border px-3 py-2 text-left transition disabled:cursor-not-allowed ${
                approvedSegment
                  ? 'border-accent-cyan/35 bg-accent-cyan/10'
                  : 'border-accent-orange/30 bg-accent-orange/10'
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-bold text-text">
                  Segment {index + 1} · {segment.start_s ?? 0}s → {(segment.start_s ?? 0) + (segment.duration_s ?? 0)}s
                </span>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${
                  approvedSegment
                    ? 'border-accent-cyan/25 text-accent-cyan'
                    : 'border-accent-orange/25 text-accent-orange'
                }`}>
                  {approvedSegment ? 'Approved' : 'Needs review'}
                </span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-text-muted">
                {segment.objective || 'Segment objective pending'}
              </p>
              <div className="mt-2 grid gap-1 md:grid-cols-2">
                <StateLine label="Entry" state={segment.entry_state} />
                <StateLine label="Exit" state={segment.exit_state} />
              </div>
              {(segment.handoff_requirements ?? []).length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {(segment.handoff_requirements ?? []).slice(0, 3).map((item) => (
                    <span key={item} className="rounded-full border border-hairline bg-surface-1/70 px-2 py-0.5 text-[10px] text-text-muted">
                      {item}
                    </span>
                  ))}
                </div>
              )}
            </button>
          );
        })}
      </div>
      {handoffs.length > 0 && (
        <div className="mt-3 rounded-card border border-hairline bg-surface-1/70 p-2">
          <div className="mb-1 flex items-center gap-1.5 text-[10px] font-bold uppercase text-text-subtle">
            <GitBranch size={12} />
            Handoff graph
          </div>
          <div className="grid gap-1">
            {handoffs.slice(0, 3).map((handoff, index) => (
              <div key={`handoff-${index}`} className="text-[11px] leading-relaxed text-text-muted">
                {formatState(handoff)}
              </div>
            ))}
          </div>
        </div>
      )}
      {(plan?.warnings ?? []).length > 0 && (
        <div className="mt-3 rounded-card border border-accent-orange/20 bg-accent-orange/10 px-3 py-2">
          <div className="mb-1 text-[10px] font-bold uppercase text-accent-orange">Planner warnings</div>
          <div className="grid gap-1">
            {(plan?.warnings ?? []).slice(0, 4).map((warning) => (
              <div key={warning} className="text-[11px] leading-relaxed text-text-muted">
                {warning.replace(/_/g, ' ')}
              </div>
            ))}
          </div>
        </div>
      )}
      {approvedCount < segments.length && (
        <p className="mt-2 text-xs text-accent-orange">
          Every segment must be approved before paid long-form render.
        </p>
      )}
    </div>
  );
}

function ConsistencyReviewBox({
  policy,
  approved,
  decision,
  reason,
  history,
  onReasonChange,
  onApprove,
  onReject,
}: {
  policy?: ConsistencyReviewPolicy | null;
  approved: boolean;
  decision: 'pending' | 'approved' | 'rejected';
  reason: string;
  history: readonly ConsistencyReviewHistoryItem[];
  onReasonChange?: (reason: string) => void;
  onApprove?: () => void;
  onReject?: () => void;
}) {
  const reasons = policy?.reasons ?? [];
  return (
    <div className="rounded-card border border-accent-orange/25 bg-accent-orange/10 p-3">
      <div className="mb-1 flex items-center gap-2 text-xs font-bold uppercase text-accent-orange">
        <AlertTriangle size={14} />
        Consistency review required
      </div>
      <p className="text-xs leading-relaxed text-text-muted">
        This plan has elevated continuity risk. Approve only after checking segment objectives, handoff frames, references and prompts.
      </p>
      {reasons.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {reasons.slice(0, 6).map((item) => (
            <span key={item} className="rounded-full border border-accent-orange/25 bg-surface-1/70 px-2 py-0.5 text-[10px] text-text-muted">
              {item.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}
      <div className="mt-3 grid gap-2">
        <textarea
          value={reason}
          onChange={(event) => onReasonChange?.(event.target.value)}
          rows={3}
          placeholder="Review note: why this consistency risk is acceptable, or what must be fixed before render."
          className="min-h-20 w-full rounded-card border border-hairline bg-surface-1/80 px-3 py-2 text-xs text-text outline-none placeholder:text-text-subtle focus:border-accent-cyan/50"
        />
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onApprove}
            disabled={approved || reason.trim().length < 3}
            className="btn-outline px-3 py-1.5 text-xs disabled:cursor-not-allowed disabled:opacity-50"
          >
            {approved ? <BadgeCheck size={13} /> : <ShieldCheck size={13} />}
            {approved ? 'Consistency approved' : 'Approve with note'}
          </button>
          <button
            type="button"
            onClick={onReject}
            disabled={reason.trim().length < 3}
            className="btn-outline border-accent-orange/30 px-3 py-1.5 text-xs text-accent-orange disabled:cursor-not-allowed disabled:opacity-50"
          >
            <XCircle size={13} />
            Reject with reason
          </button>
        </div>
        <div className="text-[11px] text-text-muted">
          Decision: <span className="font-semibold text-text">{decision}</span>
        </div>
        {history.length > 0 && (
          <div className="rounded-card border border-hairline bg-surface-1/60 p-2">
            <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">Review history</div>
            <div className="grid gap-1">
              {history.slice(-3).map((item) => (
                <div key={`${item.createdAt}-${item.decision}`} className="text-[11px] leading-relaxed text-text-muted">
                  <span className="font-semibold text-text">{item.decision}</span>
                  {' '}({item.segmentIds.length} segments, {formatDate(item.createdAt)}): {item.reason}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function InfoPill({
  label,
  value,
  tone = 'default',
}: {
  label: string;
  value: string;
  tone?: 'default' | 'cyan' | 'orange';
}) {
  const toneClass = tone === 'cyan'
    ? 'border-accent-cyan/25 text-accent-cyan'
    : tone === 'orange'
      ? 'border-accent-orange/25 text-accent-orange'
      : 'border-hairline text-text-muted';
  return (
    <div className={`rounded-md border bg-surface-1/70 px-3 py-2 ${toneClass}`}>
      <div className="text-[10px] font-bold uppercase">{label}</div>
      <div className="mt-0.5 truncate text-xs font-semibold text-text">{value}</div>
    </div>
  );
}

function StateLine({ label, state }: { label: string; state?: Record<string, unknown> }) {
  return (
    <div className="rounded-md border border-hairline bg-surface-1/60 px-2 py-1.5">
      <div className="text-[10px] font-bold uppercase text-text-subtle">{label}</div>
      <div className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-text-muted">
        {formatState(state)}
      </div>
    </div>
  );
}

function readinessLabel({
  approved,
  renderSourceReady,
  referencesConfirmed,
  segmentReviewComplete,
  consistencyComplete,
  hardBlockerCount,
}: {
  approved: boolean;
  renderSourceReady: boolean;
  referencesConfirmed: boolean;
  segmentReviewComplete: boolean;
  consistencyComplete: boolean;
  hardBlockerCount: number;
}) {
  if (hardBlockerCount > 0) return { label: `${hardBlockerCount} blocker${hardBlockerCount > 1 ? 's' : ''}`, tone: 'orange' as const };
  if (!referencesConfirmed) return { label: 'confirm refs', tone: 'orange' as const };
  if (!approved) return { label: 'dry-run pending', tone: 'orange' as const };
  if (!segmentReviewComplete) return { label: 'review segments', tone: 'orange' as const };
  if (!consistencyComplete) return { label: 'consistency note', tone: 'orange' as const };
  if (renderSourceReady) return { label: 'ready for paid render', tone: 'cyan' as const };
  return { label: 'locking source', tone: 'orange' as const };
}

function summarizeDryRunReport(report?: Record<string, unknown> | null): DryRunSummary | null {
  if (!report) return null;
  const costEstimate = getRecord(report, 'cost_estimate');
  const planSummary = getRecord(report, 'plan_summary');
  return {
    status: getString(report, 'status') || 'ready',
    renderPath: getString(report, 'render_path') || getString(planSummary, 'render_path'),
    exactPayloads: getNumber(report, 'payload_count') ?? getNumber(report, 'shot_count') ?? getNumber(planSummary, 'shot_count'),
    payloadSource: getString(report, 'payload_source') || getString(report, 'source'),
    costUsd: getNumber(report, 'estimated_total_cost_usd')
      ?? getNumber(report, 'total_cost_usd')
      ?? getNumber(costEstimate, 'estimated_total_usd')
      ?? getNumber(costEstimate, 'high_usd'),
    warnings: [
      ...getStringList(report, 'warnings'),
      ...getStringList(report, 'linter_warnings'),
    ],
    blockers: [
      ...getStringList(report, 'hard_failures'),
      ...getStringList(report, 'errors'),
    ],
  };
}

function summarizeReferenceIntelligence(report?: Record<string, unknown> | null): ReferenceIntelligenceSummary | null {
  const reference = getRecord(report, 'reference_intelligence');
  if (!reference) return null;
  const insights = getRecordList(reference, 'insights').map((item): ReferenceInsightSummary => ({
    assetId: getString(item, 'asset_id') || 'reference',
    kind: getString(item, 'kind') || 'asset',
    tag: getString(item, 'tag'),
    role: getString(item, 'role') || 'unknown',
    readiness: getString(item, 'readiness') || 'needs_review',
    roleConfidence: getNumber(item, 'role_confidence'),
    roleLocked: Boolean(item.role_locked),
    bestUse: getString(item, 'best_use'),
    warnings: getStringList(item, 'warnings'),
    missingConfirmations: getStringList(item, 'missing_confirmations'),
  }));
  return {
    status: getString(reference, 'status') || 'needs_review',
    assetCount: getNumber(reference, 'asset_count') ?? insights.length,
    imageCount: getNumber(reference, 'image_count') ?? 0,
    videoCount: getNumber(reference, 'video_count') ?? 0,
    audioCount: getNumber(reference, 'audio_count') ?? 0,
    missingRequiredRoles: getStringList(reference, 'missing_required_roles'),
    warnings: getStringList(reference, 'warnings'),
    blockers: getStringList(reference, 'blockers'),
    insights,
  };
}

function getRecord(record: Record<string, unknown> | null | undefined, key: string): Record<string, unknown> | undefined {
  const value = record?.[key];
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
}

function getRecordList(record: Record<string, unknown> | null | undefined, key: string): Record<string, unknown>[] {
  const value = record?.[key];
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object' && !Array.isArray(item));
}

function getString(record: Record<string, unknown> | null | undefined, key: string): string | undefined {
  const value = record?.[key];
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function getNumber(record: Record<string, unknown> | null | undefined, key: string): number | undefined {
  const value = record?.[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function getStringList(record: Record<string, unknown> | null | undefined, key: string): string[] {
  const value = record?.[key];
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || '').trim()).filter(Boolean);
}

function formatState(state?: Record<string, unknown>): string {
  if (!state) return 'none';
  const parts = Object.entries(state)
    .filter(([, value]) => value !== null && value !== undefined && value !== '' && !(Array.isArray(value) && value.length === 0))
    .slice(0, 5)
    .map(([key, value]) => `${key.replace(/_/g, ' ')}=${formatValue(value)}`);
  return parts.length > 0 ? parts.join(', ') : 'none';
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => String(item)).join(' / ').slice(0, 120);
  if (value && typeof value === 'object') return JSON.stringify(value).slice(0, 120);
  return String(value).slice(0, 120);
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatLabel(value: string): string {
  return value.replace(/[:.]/g, ' ').replace(/_/g, ' ').replace(/\s+/g, ' ').trim() || value;
}
