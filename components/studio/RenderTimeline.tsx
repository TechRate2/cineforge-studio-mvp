'use client';

import { AlertTriangle, BadgeCheck, ClipboardCheck, Loader2, Play, ShieldCheck, Video } from 'lucide-react';
import { deliverableUrl } from '@/lib/studio/deliverable-url';
import type { StudioLanguage } from './studio-i18n';
import { statusLabel, statusTone, t } from './studio-i18n';
import { summarizeReferenceIntelligence } from './ReferenceIntelligencePanel';

export interface RenderTimelineBlocker {
  key: string;
  label: string;
  detail?: string;
  severity?: string;
}

export interface RenderTimelineSegment {
  segment_id?: string;
  index?: number;
  start_s?: number;
  duration_s?: number;
  objective?: string;
  status?: string;
}

export interface RenderTimelineLongformPlan {
  longform_plan_id?: string;
  total_duration_s?: number;
  segments?: RenderTimelineSegment[];
  warnings?: string[];
}

export interface RenderTimelineConsistencyPolicy {
  action?: string;
  reasons?: string[];
  review_approved?: boolean;
  review_decision?: string;
  review_reason?: string;
  reviewed_segment_ids?: string[];
}

export interface RenderTimelineJobStatus {
  job_id?: string;
  status?: string;
  progress?: number;
  output_path?: string | null;
  output_url?: string | null;
  error_message?: string | null;
  feedback_summary?: {
    feedback_count?: number;
    latest_rating?: string | null;
    recommended_next_action?: string;
  };
  render_execution?: {
    status?: string;
    qa_reports?: Array<Record<string, unknown>>;
    repair_attempts_by_shot?: Record<string, number>;
    rendered_segments?: Array<Record<string, unknown>>;
  } | null;
  longform_render_execution?: {
    status?: string;
    qa_reports?: Array<Record<string, unknown>>;
    repair_attempts_by_segment?: Record<string, number>;
    rendered_segments?: Array<Record<string, unknown>>;
  } | null;
  assembly_result?: {
    status?: string;
    error?: string | null;
    final_video_url?: string | null;
    final_delivery_qa?: {
      status?: string;
      delivery_url?: string | null;
      errors?: string[];
      warnings?: string[];
    } | null;
    storage_delivery_url?: string | null;
    storage_public_url?: string | null;
    storage_cdn_url?: string | null;
    storage_presigned_url?: string | null;
  };
}

export interface RenderTimelineProps {
  approved: boolean;
  renderSourceReady: boolean;
  loading?: boolean;
  planning?: boolean;
  renderDisabled?: boolean;
  referencesConfirmed?: boolean;
  hasBrief?: boolean;
  hasPlan?: boolean;
  hasStoryboard?: boolean;
  dryRunReport?: Record<string, unknown> | null;
  longformPlan?: RenderTimelineLongformPlan | null;
  consistencyPolicy?: RenderTimelineConsistencyPolicy | null;
  consistencyReviewApproved?: boolean;
  consistencyReviewReason?: string;
  consistencyReviewDecision?: 'pending' | 'approved' | 'rejected';
  approvedSegmentIds?: readonly string[];
  blockers: readonly RenderTimelineBlocker[];
  repairAttemptsByShot?: Record<string, number> | null;
  finalOutputUrl?: string | null;
  jobStatus?: RenderTimelineJobStatus | null;
  benchmarkEvidence?: Record<string, unknown> | null;
  language?: StudioLanguage;
  onToggleSegmentApproval?: (segmentId: string) => void;
  onApproveAllSegments?: () => void;
  onConsistencyReviewReasonChange?: (reason: string) => void;
  onConsistencyReviewApprove?: () => void;
  onConsistencyReviewReject?: () => void;
  onApprove: () => void | Promise<void>;
  onRender: () => void | Promise<void>;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function list(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || '').trim()).filter(Boolean);
}

function toneClass(status?: string) {
  const tone = statusTone(status);
  if (tone === 'ready') return 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan';
  if (tone === 'blocked') return 'border-red-400/30 bg-red-500/10 text-red-300';
  if (tone === 'review') return 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange';
  return 'border-hairline bg-surface-2 text-text-subtle';
}

function stepStatus(done: boolean, blocked = false, active = false): string {
  if (blocked) return 'blocked';
  if (done) return 'ready';
  if (active) return 'needs_review';
  return 'pending';
}

export function RenderTimeline({
  approved,
  renderSourceReady,
  loading = false,
  planning = false,
  renderDisabled = false,
  referencesConfirmed = false,
  hasBrief = false,
  hasPlan = false,
  hasStoryboard = false,
  dryRunReport,
  longformPlan,
  consistencyPolicy,
  consistencyReviewApproved = false,
  consistencyReviewReason = '',
  consistencyReviewDecision = 'pending',
  approvedSegmentIds = [],
  blockers,
  repairAttemptsByShot,
  finalOutputUrl,
  jobStatus,
  benchmarkEvidence,
  language = 'vi',
  onToggleSegmentApproval,
  onApproveAllSegments,
  onConsistencyReviewReasonChange,
  onConsistencyReviewApprove,
  onConsistencyReviewReject,
  onApprove,
  onRender,
}: RenderTimelineProps) {
  const hardBlockers = blockers.filter((blocker) => blocker.severity !== 'soft' && blocker.severity !== 'warning');
  const referenceSummary = summarizeReferenceIntelligence(dryRunReport);
  const hardFailures = list(dryRunReport?.hard_failures);
  const shotPayloads = Array.isArray(dryRunReport?.shot_payloads) ? dryRunReport?.shot_payloads : [];
  const segments = longformPlan?.segments ?? [];
  const segmentReviewComplete = segments.length === 0 || segments.every((segment, index) => (
    approvedSegmentIds.includes(segment.segment_id || `segment-${index + 1}`)
  ));
  const needsConsistencyReview = consistencyPolicy?.action === 'requires_review';
  const jobQaReports = collectJobQaReports(jobStatus);
  const repairAttempts = {
    ...(repairAttemptsByShot ?? {}),
    ...(jobStatus?.render_execution?.repair_attempts_by_shot ?? {}),
    ...(jobStatus?.longform_render_execution?.repair_attempts_by_segment ?? {}),
  };
  const repairCount = Object.values(repairAttempts).reduce((sum, value) => sum + (Number.isFinite(value) ? value : 0), 0);
  const assemblyStatus = assemblyStatusFromJob(jobStatus);
  const deliveryStatus = deliveryStatusFromJob(jobStatus, finalOutputUrl);
  const qaStatus = qaStatusFromReports(jobQaReports, jobStatus);
  const benchmarkStatus = benchmarkStatusFromEvidence(benchmarkEvidence, language);
  const activeRender = loading || Boolean(jobStatus && !['done', 'failed', 'cancelled', 'dry_run'].includes(String(jobStatus.status || '')));
  const renderBlocked = renderDisabled || hardBlockers.length > 0 || hardFailures.length > 0;

  const steps = [
    {
      key: 'idea',
      label: language === 'vi' ? 'Agent đã hiểu ý tưởng' : 'Idea understood',
      status: stepStatus(hasBrief && (hasPlan || hasStoryboard), false, planning),
      detail: hasBrief ? (hasPlan ? 'Preflight returned a real plan.' : 'Brief is saved, plan pending.') : 'No brief yet.',
    },
    {
      key: 'references',
      label: language === 'vi' ? 'Tham chiếu đã kiểm tra' : 'References checked',
      status: referenceSummary ? referenceSummary.status : stepStatus(referencesConfirmed, false, false),
      detail: referenceSummary
        ? `${referenceSummary.assetCount} assets, ${referenceSummary.blockers.length} blockers`
        : (language === 'vi' ? 'Backend Reference Intelligence chạy sau dry-run.' : 'Backend Reference Intelligence runs after dry-run.'),
    },
    {
      key: 'script',
      label: t(language, 'script'),
      status: stepStatus(hasPlan),
      detail: hasPlan ? 'Creative plan/script data returned.' : 'Waiting for real preflight output.',
    },
    {
      key: 'storyboard',
      label: t(language, 'storyboard'),
      status: stepStatus(hasStoryboard),
      detail: hasStoryboard ? 'Storyboard beats are available.' : 'Waiting for storyboard beats.',
    },
    {
      key: 'prompt',
      label: t(language, 'promptStrategy'),
      status: stepStatus(shotPayloads.length > 0 || hasStoryboard),
      detail: shotPayloads.length > 0 ? `${shotPayloads.length} dry-run payloads` : 'Prompt preview pending dry-run.',
    },
    {
      key: 'dry-run',
      label: t(language, 'preRenderCheck'),
      status: stepStatus(Boolean(dryRunReport), hardFailures.length > 0, planning),
      detail: dryRunReport ? `${hardFailures.length} hard failures` : 'No dry-run report yet.',
    },
    {
      key: 'approval',
      label: t(language, 'approveRender'),
      status: stepStatus(approved && renderSourceReady, approved && !renderSourceReady),
      detail: renderSourceReady ? 'ApprovalLock source matches current input.' : 'Approval required before paid render.',
    },
    {
      key: 'rendering',
      label: language === 'vi' ? 'Rendering' : 'Rendering',
      status: stepStatus(jobStatus?.status === 'done', jobStatus?.status === 'failed' || jobStatus?.status === 'cancelled', activeRender),
      detail: jobStatus
        ? `${jobStatus.status || 'unknown'}${typeof jobStatus.progress === 'number' ? `, ${jobStatus.progress}%` : ''}`
        : (loading ? 'Render request is in flight.' : 'No active render request.'),
    },
    {
      key: 'qa',
      label: t(language, 'qaChecking'),
      status: qaStatus.status,
      detail: qaStatus.detail,
    },
    {
      key: 'repair',
      label: t(language, 'autoRepair'),
      status: stepStatus(repairCount > 0),
      detail: repairCount > 0 ? `${repairCount} repair attempts recorded` : 'No repair attempts reported yet.',
    },
    {
      key: 'assembly',
      label: language === 'vi' ? 'Final assembly' : 'Final assembly',
      status: assemblyStatus.status,
      detail: assemblyStatus.detail,
    },
    {
      key: 'delivery',
      label: t(language, 'videoDone'),
      status: deliveryStatus.status,
      detail: deliveryStatus.detail,
    },
    {
      key: 'benchmark',
      label: language === 'vi' ? 'Bằng chứng benchmark' : 'Benchmark evidence',
      status: benchmarkStatus.status,
      detail: benchmarkStatus.detail || feedbackDetail(jobStatus) || 'No real benchmark evidence attached to this Studio state.',
    },
  ];

  return (
    <section className="rounded-sheet border border-hairline bg-surface-1 p-4 shadow-card-soft">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-bold uppercase tracking-normal text-accent-cyan">{t(language, 'renderTimeline')}</div>
          <h2 className="mt-1 text-lg font-extrabold text-text">
            {language === 'vi' ? 'Từ dry-run đến video hoàn tất' : 'From dry-run to final video'}
          </h2>
          <p className="mt-1 max-w-xl text-xs leading-relaxed text-text-muted">
            {language === 'vi'
              ? 'Timeline chỉ đánh dấu hoàn tất khi có dữ liệu thật từ state hoặc backend.'
              : 'The timeline marks steps complete only when real state or backend data exists.'}
          </p>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase ${toneClass(renderBlocked ? 'blocked' : renderSourceReady ? 'ready' : 'needs_review')}`}>
          {renderBlocked ? <AlertTriangle size={12} /> : <ShieldCheck size={12} />}
          {renderBlocked ? t(language, 'blocked') : renderSourceReady ? t(language, 'ready') : t(language, 'needsReview')}
        </span>
      </div>

      {blockers.length > 0 && (
        <div className="mb-3 rounded-card border border-accent-orange/25 bg-accent-orange/10 p-3 text-accent-orange">
          <div className="text-xs font-bold uppercase">{t(language, 'blockers')}</div>
          <div className="mt-2 grid gap-2">
            {blockers.map((blocker) => (
              <div key={blocker.key} className="text-xs leading-relaxed">
                <span className="font-bold">{blocker.label}:</span> {blocker.detail}
              </div>
            ))}
          </div>
        </div>
      )}

      {hardFailures.length > 0 && (
        <div className="mb-3 rounded-card border border-red-400/25 bg-red-500/10 p-3 text-red-200">
          <div className="text-xs font-bold uppercase">Dry-run hard failures</div>
          <ul className="mt-2 grid gap-1 text-xs leading-relaxed">
            {hardFailures.map((failure) => <li key={failure}>{failure}</li>)}
          </ul>
        </div>
      )}

      {segments.length > 0 && (
        <div className="mb-3 rounded-card border border-hairline bg-surface-2 p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs font-bold uppercase text-accent-cyan">{language === 'vi' ? 'Duyệt segment long-form' : 'Long-form segment review'}</div>
            {onApproveAllSegments && (
              <button type="button" onClick={onApproveAllSegments} className="btn-outline px-2.5 py-1 text-[10px]">
                <ClipboardCheck size={12} />
                {language === 'vi' ? 'Duyệt tất cả' : 'Approve all'}
              </button>
            )}
          </div>
          <div className="grid gap-2">
            {segments.map((segment, index) => {
              const id = segment.segment_id || `segment-${index + 1}`;
              const checked = approvedSegmentIds.includes(id);
              return (
                <label key={id} className="flex items-start gap-2 rounded-card border border-hairline bg-surface-1 px-3 py-2 text-xs text-text-muted">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggleSegmentApproval?.(id)}
                    className="mt-0.5"
                  />
                  <span>
                    <span className="font-bold text-text">Segment {index + 1}</span>
                    {' '}{segment.duration_s ? `${segment.duration_s}s` : ''} {segment.objective || ''}
                  </span>
                </label>
              );
            })}
          </div>
        </div>
      )}

      {needsConsistencyReview && (
        <div className="mb-3 rounded-card border border-accent-orange/25 bg-accent-orange/10 p-3 text-accent-orange">
          <div className="text-xs font-bold uppercase">{language === 'vi' ? 'Cần duyệt consistency' : 'Consistency review required'}</div>
          <textarea
            value={consistencyReviewReason}
            onChange={(event) => onConsistencyReviewReasonChange?.(event.target.value)}
            placeholder={language === 'vi' ? 'Ghi lý do duyệt hoặc từ chối...' : 'Add approval or rejection reason...'}
            className="mt-2 min-h-[72px] w-full rounded-card border border-accent-orange/25 bg-surface-1 px-3 py-2 text-xs text-text outline-none"
          />
          <div className="mt-2 flex flex-wrap gap-2">
            <button type="button" onClick={onConsistencyReviewApprove} className="btn-outline px-3 py-2 text-xs">
              {language === 'vi' ? 'Duyệt consistency' : 'Approve consistency'}
            </button>
            <button type="button" onClick={onConsistencyReviewReject} className="btn-outline px-3 py-2 text-xs">
              {language === 'vi' ? 'Từ chối' : 'Reject'}
            </button>
            <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-[10px] font-semibold uppercase text-text-subtle">
              {consistencyReviewDecision}
            </span>
          </div>
        </div>
      )}

      <div className="grid gap-2">
        {steps.map((step) => (
          <article key={step.key} className="rounded-card border border-hairline bg-surface-2 px-3 py-3">
            <div className="flex items-start gap-3">
              <div className={`grid h-8 w-8 shrink-0 place-items-center rounded-card border ${toneClass(step.status)}`}>
                {step.status === 'needs_review' && loading ? <Loader2 size={15} className="animate-spin" /> : step.status === 'ready' ? <BadgeCheck size={15} /> : step.status === 'blocked' ? <AlertTriangle size={15} /> : <Video size={15} />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-bold text-text">{step.label}</h3>
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${toneClass(step.status)}`}>
                    {statusLabel(language, step.status)}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-relaxed text-text-muted">{step.detail}</p>
              </div>
            </div>
          </article>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <button
          type="button"
          onClick={() => void onApprove()}
          disabled={planning || hardFailures.length > 0}
          className="btn-outline px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-45"
        >
          <ClipboardCheck size={15} />
          {approved ? (language === 'vi' ? 'Dry-run đã khóa' : 'Dry-run locked') : t(language, 'approveRender')}
        </button>
        <button
          type="button"
          onClick={() => void onRender()}
          disabled={renderBlocked}
          className="inline-flex items-center gap-2 rounded-card bg-cta-gradient px-4 py-2 text-sm font-bold text-white shadow-cta-glow transition hover:brightness-110 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-45"
        >
          {loading ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
          {loading ? (language === 'vi' ? 'Đang render' : 'Rendering') : t(language, 'startRender')}
        </button>
      </div>
    </section>
  );
}

function collectJobQaReports(job?: RenderTimelineJobStatus | null): Array<Record<string, unknown>> {
  return [
    ...(job?.render_execution?.qa_reports ?? []),
    ...(job?.longform_render_execution?.qa_reports ?? []),
  ];
}

function qaStatusFromReports(reports: Array<Record<string, unknown>>, job?: RenderTimelineJobStatus | null): { status: string; detail: string } {
  if (reports.length > 0) {
    const statuses = reports.map((report) => String(report.status || '').toLowerCase());
    const failCount = statuses.filter((status) => status === 'fail').length;
    const warnCount = statuses.filter((status) => status === 'warn' || status === 'warning').length;
    if (failCount > 0) return { status: 'blocked', detail: `${failCount}/${reports.length} QA reports failed.` };
    if (warnCount > 0) return { status: 'needs_review', detail: `${warnCount}/${reports.length} QA reports returned warnings.` };
    return { status: 'ready', detail: `${reports.length} QA reports returned pass status.` };
  }
  if (job?.status === 'failed') return { status: 'blocked', detail: job.error_message || 'Render failed before QA reports were available.' };
  if (job && ['rendering', 'assembling', 'uploading', 'graph_executing'].includes(String(job.status || ''))) {
    return { status: 'needs_review', detail: 'Job is still running; QA reports are not final yet.' };
  }
  return { status: 'pending', detail: 'Waiting for real job QA reports.' };
}

function deliverableUrlFromJob(job?: RenderTimelineJobStatus | null): string {
  return deliverableUrl(
    job?.assembly_result?.storage_delivery_url
    || job?.assembly_result?.storage_public_url
    || job?.assembly_result?.storage_cdn_url
    || job?.assembly_result?.storage_presigned_url
    || job?.assembly_result?.final_video_url
    || job?.output_url
    || '',
  );
}

function assemblyStatusFromJob(job?: RenderTimelineJobStatus | null): { status: string; detail: string } {
  const assembly = job?.assembly_result;
  if (!assembly) {
    return {
      status: 'pending',
      detail: 'No final assembly result attached to this job yet.',
    };
  }
  if (assembly.error) return { status: 'blocked', detail: assembly.error };
  const outputUrl = deliverableUrlFromJob(job);
  if (outputUrl) return { status: 'ready', detail: assembly.status ? `Assembly ${assembly.status}; output URL available.` : 'Output URL available.' };
  if (assembly.status) return { status: 'needs_review', detail: `Assembly status: ${assembly.status}` };
  return { status: 'pending', detail: 'Assembly result exists but has no final URL yet.' };
}

function deliveryStatusFromJob(job?: RenderTimelineJobStatus | null, finalOutputUrl?: string | null): { status: string; detail: string } {
  const qa = job?.assembly_result?.final_delivery_qa;
  const errors = Array.isArray(qa?.errors) ? qa?.errors.filter(Boolean) : [];
  const qaStatus = String(qa?.status || '').toLowerCase();
  if (qaStatus === 'fail' || errors.length > 0 || job?.assembly_result?.error) {
    return {
      status: 'blocked',
      detail: errors.length > 0 ? errors.slice(0, 3).join('; ') : (job?.assembly_result?.error || 'Final delivery QA failed.'),
    };
  }

  const outputUrl = deliverableUrlFromJob(job) || deliverableUrl(finalOutputUrl);
  if (outputUrl) {
    const warningCount = Array.isArray(qa?.warnings) ? qa.warnings.length : 0;
    if (!qaStatus) {
      return {
        status: 'needs_review',
        detail: `${outputUrl} (preview URL available; final delivery QA is not attached yet)`,
      };
    }
    if (qaStatus === 'warn' || qaStatus === 'warning' || warningCount > 0) {
      return { status: 'needs_review', detail: `${outputUrl} (${warningCount || 1} delivery warning${warningCount === 1 ? '' : 's'})` };
    }
    if (['pass', 'success', 'succeeded'].includes(qaStatus)) {
      return { status: 'ready', detail: outputUrl };
    }
    return {
      status: 'needs_review',
      detail: `${outputUrl} (delivery QA status: ${qaStatus})`,
    };
  }

  if (job?.output_path && !deliverableUrl(job.output_path)) {
    return {
      status: 'pending',
      detail: 'Local output path exists, but no public or presigned delivery URL is available yet.',
    };
  }

  return { status: 'pending', detail: 'Waiting for real URL from job/delivery result.' };
}

function formatBenchmarkMissingReason(reason: string, language: StudioLanguage): string {
  const normalized = reason.trim();
  if (normalized === 'feedback_integrity_not_safe') {
    return language === 'vi'
      ? 'feedback đã lưu chưa đủ an toàn để làm bằng chứng ra mắt'
      : 'saved feedback is not safe to use as launch evidence';
  }
  if (normalized === 'missing_real_output_url') {
    return language === 'vi'
      ? 'thiếu URL video render thật'
      : 'missing a real rendered video URL';
  }
  if (normalized === 'missing_clean_final_delivery_qa') {
    return language === 'vi'
      ? 'thiếu final delivery QA pass sạch'
      : 'missing clean final delivery QA pass';
  }
  if (normalized === 'missing_qa_score') {
    return language === 'vi' ? 'thiếu điểm QA thật' : 'missing real QA score';
  }
  if (normalized === 'missing_human_score') {
    return language === 'vi' ? 'thiếu điểm review người thật' : 'missing real human review score';
  }
  if (normalized === 'missing_cost_usd') {
    return language === 'vi' ? 'thiếu cost render thật' : 'missing real render cost';
  }
  if (normalized === 'missing_latency_s') {
    return language === 'vi' ? 'thiếu latency render thật' : 'missing real render latency';
  }
  return normalized.replaceAll('_', ' ');
}

function benchmarkStatusFromEvidence(evidence?: Record<string, unknown> | null, language: StudioLanguage = 'vi'): { status: string; detail: string } {
  if (!evidence) return { status: 'pending', detail: 'No real benchmark evidence attached to this Studio state.' };
  const validation = asRecord(evidence.evidence_validation_preview) || asRecord(evidence.evidence_validation);
  const draft = asRecord(evidence.benchmark_result_draft);
  const promotionReady = validation?.promotion_ready === true;
  const missingReasons = list(validation?.missing_reasons);
  const feedbackIntegrity = asRecord(validation?.feedback_integrity);
  const feedbackIntegrityIssues = list(feedbackIntegrity?.issues);
  const readableReasons = missingReasons.map((reason) => formatBenchmarkMissingReason(reason, language));
  const draftStatus = String(draft?.status || evidence.status || '').trim();
  if (promotionReady) {
    return {
      status: 'ready',
      detail: 'Benchmark evidence is promotion-ready according to the backend validator.',
    };
  }
  if (validation) {
    return {
      status: 'needs_review',
      detail: readableReasons.length > 0
        ? `Benchmark draft is not promotion-ready: ${readableReasons.slice(0, 4).join(', ')}${feedbackIntegrityIssues.length > 0 ? ` (${feedbackIntegrityIssues.length} feedback integrity issue${feedbackIntegrityIssues.length === 1 ? '' : 's'}).` : '.'}`
        : 'Benchmark draft exists but is not promotion-ready yet.',
    };
  }
  if (draftStatus) {
    return {
      status: 'needs_review',
      detail: `Benchmark draft available with status ${draftStatus}; promotion validation is missing.`,
    };
  }
  return {
    status: 'pending',
    detail: 'Benchmark evidence payload has no validator result yet.',
  };
}

function feedbackDetail(job?: RenderTimelineJobStatus | null): string {
  const count = job?.feedback_summary?.feedback_count ?? 0;
  if (!count) return '';
  return `Output feedback evidence saved (${count}); benchmark row is not attached to the Studio timeline yet.`;
}
