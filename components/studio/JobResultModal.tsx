'use client';

import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui/Modal';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Download,
  Loader2,
  MessageSquare,
  RotateCcw,
  Sparkles,
  X,
} from 'lucide-react';
import { useDirectorJobPoll, type DirectorJobStatus } from '@/lib/studio/use-director-job-poll';
import { useJobCancel } from '@/lib/studio/use-job-cancel';

interface Props {
  open: boolean;
  jobId: string | null;
  onClose: () => void;
  onRetry?: () => void;
  estimatedDurationS?: number;
  jobStartedAt?: number | null;
}

const STAGE_LABELS: Record<string, string> = {
  pending: 'Queued',
  planning: 'Planning the render',
  rendering: 'Rendering scenes',
  graph_executing: 'Rendering scenes',
  graph_idle: 'Preparing final video',
  assembling: 'Assembling final video',
  uploading: 'Publishing output',
  done: 'Video ready',
  failed: 'Render failed',
  cancelled: 'Render cancelled',
};

export function JobResultModal({
  open,
  jobId,
  onClose,
  onRetry,
  estimatedDurationS,
  jobStartedAt,
}: Props) {
  const { job, error, timedOut } = useDirectorJobPoll(jobId);
  const { cancel, isCancelling } = useJobCancel();
  const [cancelConfirm, setCancelConfirm] = useState(false);

  const status = job?.status ?? 'pending';
  const progress = job?.progress ?? 0;
  const isDone = status === 'done';
  const isFailed = status === 'failed' || status === 'cancelled';
  const isWorking = !isDone && !isFailed && !timedOut;
  const videoUrl = (job?.output_url || job?.output_path || '') as string;

  const totalExpectedS = (estimatedDurationS ?? 15) * 5 + 60;
  const anchorTime = jobStartedAt ?? Date.now();
  const elapsedS = Math.max(0, (Date.now() - anchorTime) / 1000);
  const showEta = isWorking && progress >= 10 && progress < 95;
  const fractionDone = Math.max(0.1, Math.min(0.95, progress / 100));
  const projectedTotalS = elapsedS / fractionDone;
  const secondsLeft = showEta
    ? Math.max(0, Math.min(projectedTotalS, totalExpectedS) - elapsedS)
    : 0;

  useEffect(() => {
    if (isDone) {
      toast.success('Video render complete');
    }
  }, [isDone]);

  useEffect(() => {
    if (status === 'failed') toast.error('Render failed', { duration: 8000 });
    if (status === 'cancelled') toast.info('Render cancelled');
  }, [status]);

  const handleCancel = async () => {
    if (!jobId) return;
    if (!cancelConfirm) {
      setCancelConfirm(true);
      setTimeout(() => setCancelConfirm(false), 4000);
      return;
    }
    try {
      await cancel(jobId);
      toast.success('Render cancelled');
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Cancel failed: ${msg}`);
    }
    setCancelConfirm(false);
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isDone ? 'Video ready' : isFailed ? 'Render needs attention' : 'Rendering video'}
      subtitle={isDone ? 'Review the output and publishing package.' : 'You can close this window; rendering continues in the background.'}
      maxWidth="max-w-3xl"
    >
      <div className="space-y-6 p-6 md:p-8">
        {isWorking && (
          <RenderProgress
            status={status}
            progress={progress}
            showEta={showEta}
            secondsLeft={secondsLeft}
            onCancel={handleCancel}
            cancelConfirm={cancelConfirm}
            isCancelling={isCancelling}
          />
        )}

        {timedOut && !isFailed && !isDone && (
          <AttentionPanel
            title="Render is taking longer than expected"
            detail="The job is still tracked in History. You can keep waiting, close this window, or cancel if you no longer want this render."
            action={
              <button onClick={handleCancel} disabled={isCancelling} className="btn-outline">
                {isCancelling ? (
                  <><Loader2 size={12} className="animate-spin" /> Cancelling</>
                ) : cancelConfirm ? (
                  <><X size={12} /> Confirm cancel</>
                ) : (
                  <><X size={12} /> Cancel render</>
                )}
              </button>
            }
          />
        )}

        {isFailed && (
          <AttentionPanel
            title={status === 'cancelled' ? 'Render cancelled' : 'Render failed before completion'}
            detail={error || 'The agent did not receive a completed video. You can retry with the same approved plan or adjust the brief.'}
            action={onRetry ? (
              <button onClick={onRetry} className="btn-outline">
                <RotateCcw size={14} /> Retry
              </button>
            ) : undefined}
          />
        )}

        {isDone && videoUrl && (
          <>
            <VideoResult
              videoUrl={videoUrl}
              elapsedS={job?.elapsed_s}
              onClose={onClose}
            />
            <RenderFeedbackPanel
              key={jobId || job?.job_id || videoUrl}
              jobId={jobId || job?.job_id || ''}
              videoUrl={videoUrl}
              initialSummary={job?.feedback_summary}
            />
          </>
        )}

        <PlanSummary job={job} />
        <DistributionPackage job={job} />
        <AgentChecks job={job} />
        <MemoryUsed job={job} />
      </div>
    </Modal>
  );
}

function RenderProgress({
  status,
  progress,
  showEta,
  secondsLeft,
  onCancel,
  cancelConfirm,
  isCancelling,
}: {
  status: string;
  progress: number;
  showEta: boolean;
  secondsLeft: number;
  onCancel: () => void;
  cancelConfirm: boolean;
  isCancelling: boolean;
}) {
  return (
    <div className="surface-2 rounded-card p-5">
      <div className="mb-4 flex items-center gap-3">
        <Loader2 size={18} className="animate-spin text-accent-magenta" />
        <div>
          <div className="text-sm font-semibold">{STAGE_LABELS[status] || 'Rendering video'}</div>
          <div className="mt-0.5 text-xs text-text-subtle">The agent is turning the approved plan into a finished video.</div>
        </div>
        <div className="ml-auto flex items-center gap-2 text-xs">
          {showEta && (
            <span className="flex items-center gap-1 text-accent-cyan">
              <Clock size={11} /> {formatEta(secondsLeft)}
            </span>
          )}
          <span className="text-text-muted">{progress}%</span>
        </div>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div
          className="h-full bg-cta-gradient transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="mt-4 flex items-center justify-between gap-3">
        <span className="text-[11px] leading-relaxed text-text-subtle">
          Close the modal anytime. The render will keep running and appear in History.
        </span>
        <button
          onClick={onCancel}
          disabled={isCancelling}
          className={`btn-outline shrink-0 px-3 py-1.5 text-xs ${
            cancelConfirm ? 'border-accent-orange/60 bg-accent-orange/10 text-accent-orange' : ''
          }`}
        >
          {isCancelling ? (
            <><Loader2 size={12} className="animate-spin" /> Cancelling</>
          ) : cancelConfirm ? (
            <><X size={12} /> Confirm</>
          ) : (
            <><X size={12} /> Cancel</>
          )}
        </button>
      </div>
    </div>
  );
}

function VideoResult({
  videoUrl,
  elapsedS,
  onClose,
}: {
  videoUrl: string;
  elapsedS?: number;
  onClose: () => void;
}) {
  return (
    <>
      <div className="relative aspect-video overflow-hidden rounded-card bg-black">
        <video src={videoUrl} controls className="h-full w-full" playsInline />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs text-text-muted">
          {elapsedS ? `Render time: ${Math.round(elapsedS)}s` : 'Final MP4 is ready.'}
        </div>
        <div className="flex gap-2">
          <a href={videoUrl} download className="btn-outline">
            <Download size={14} /> Download MP4
          </a>
          <button onClick={onClose} className="btn-cta">
            <Sparkles size={14} /> Create another
          </button>
        </div>
      </div>
    </>
  );
}

const FEEDBACK_TAGS = [
  { id: 'weak_hook', label: 'Weak hook' },
  { id: 'face_drift', label: 'Face drift' },
  { id: 'product_drift', label: 'Product drift' },
  { id: 'wrong_niche', label: 'Wrong niche' },
  { id: 'bad_motion', label: 'Bad motion' },
  { id: 'audio_lipsync_issue', label: 'Audio/lip sync' },
  { id: 'prompt_mismatch', label: 'Prompt mismatch' },
  { id: 'text_artifact', label: 'Text artifact' },
  { id: 'continuity_break', label: 'Continuity break' },
  { id: 'too_generic', label: 'Too generic' },
];

type FeedbackRating = 'approved' | 'needs_work' | 'bad';

function RenderFeedbackPanel({
  jobId,
  videoUrl,
  initialSummary,
}: {
  jobId: string;
  videoUrl: string;
  initialSummary?: DirectorJobStatus['feedback_summary'];
}) {
  const initialRating = initialSummary?.latest_rating;
  const [rating, setRating] = useState<FeedbackRating>(
    initialRating === 'bad' || initialRating === 'needs_work' ? initialRating : 'approved',
  );
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [notes, setNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedSummary, setSubmittedSummary] = useState(initialSummary);

  const toggleTag = (tag: string) => {
    setSelectedTags((current) => (
      current.includes(tag)
        ? current.filter((item) => item !== tag)
        : [...current, tag].slice(0, 12)
    ));
  };

  const submitFeedback = async () => {
    if (!jobId) {
      toast.error('Missing job id for feedback');
      return;
    }
    setIsSubmitting(true);
    try {
      const issueTags = rating === 'approved' && selectedTags.length === 0
        ? ['good']
        : selectedTags;
      const res = await fetch(`/api/v1/director/jobs/${encodeURIComponent(jobId)}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rating,
          issue_tags: issueTags,
          notes,
          reviewer: 'studio_operator',
          output_url: videoUrl,
        }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setSubmittedSummary(data.summary);
      toast.success('Render feedback saved');
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Feedback failed: ${msg}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="surface-2 rounded-card p-5">
      <SectionHeader
        title="Output feedback"
        subtitle="Save real render evidence so future routing and benchmark decisions can learn from the result."
        badge={submittedSummary?.feedback_count ? `${submittedSummary.feedback_count} saved` : undefined}
      />
      <div className="mb-3 grid gap-2 md:grid-cols-3">
        {[
          { id: 'approved', label: 'Approved', tone: 'cyan' },
          { id: 'needs_work', label: 'Needs work', tone: 'orange' },
          { id: 'bad', label: 'Reject', tone: 'orange' },
        ].map((item) => {
          const active = rating === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setRating(item.id as FeedbackRating)}
              className={`rounded-md border px-3 py-2 text-left text-xs transition ${
                active
                  ? item.tone === 'cyan'
                    ? 'border-accent-cyan/50 bg-accent-cyan/15 text-accent-cyan'
                    : 'border-accent-orange/50 bg-accent-orange/15 text-accent-orange'
                  : 'border-hairline bg-surface-3/50 text-text-muted hover:text-text'
              }`}
            >
              <span className="flex items-center gap-2 font-semibold">
                {active ? <CheckCircle2 size={13} /> : <MessageSquare size={13} />}
                {item.label}
              </span>
            </button>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {FEEDBACK_TAGS.map((tag) => {
          const active = selectedTags.includes(tag.id);
          return (
            <button
              key={tag.id}
              type="button"
              onClick={() => toggleTag(tag.id)}
              className={`chip px-2 py-1 text-[10px] ${
                active ? 'border-accent-orange/40 bg-accent-orange/10 text-accent-orange' : ''
              }`}
            >
              {tag.label}
            </button>
          );
        })}
      </div>
      <textarea
        value={notes}
        onChange={(event) => setNotes(event.target.value.slice(0, 1200))}
        placeholder="Optional notes: what worked, what drifted, what should be fixed before the next render."
        className="mt-3 min-h-20 w-full rounded-md border border-hairline bg-surface-3/60 px-3 py-2 text-xs text-text outline-none placeholder:text-text-subtle focus:border-accent-cyan/50"
      />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <span className="text-[11px] text-text-subtle">
          This records evidence only; it never starts a paid render.
        </span>
        <button type="button" onClick={submitFeedback} disabled={isSubmitting} className="btn-outline">
          {isSubmitting ? (
            <><Loader2 size={12} className="animate-spin" /> Saving</>
          ) : (
            <><CheckCircle2 size={14} /> Save feedback</>
          )}
        </button>
      </div>
    </div>
  );
}

function PlanSummary({ job }: { job?: DirectorJobStatus | null }) {
  const decision = job?.autonomous_meta?.production_decision?.decision;
  if (!decision) return null;
  const items = [
    { label: 'Niche', value: cleanLabel(decision.niche) },
    { label: 'Market', value: cleanLabel(decision.target_market) },
    { label: 'Runtime', value: formatRuntime(decision.runtime_class, decision.target_duration_s) },
    { label: 'Format', value: decision.target_duration_s && decision.target_duration_s >= 180 ? 'Long-form story' : 'Short-form vertical' },
  ].filter((item) => item.value);

  if (items.length === 0) return null;
  return (
    <div className="surface-2 rounded-card p-5">
      <SectionHeader title="Agent plan" subtitle="The creative route used for this render." />
      <div className="grid gap-2 md:grid-cols-4">
        {items.map((item) => (
          <InfoTile key={item.label} label={item.label} value={item.value || '-'} />
        ))}
      </div>
    </div>
  );
}

function DistributionPackage({ job }: { job?: DirectorJobStatus | null }) {
  const editor = job?.editor_meta;
  const pkg = editor?.distribution_package;
  const caption = pkg?.caption_primary || editor?.caption_vn || editor?.caption_en;
  const hashtags = pkg?.hashtag_primary || editor?.hashtags_vn || editor?.hashtags_en || [];
  if (!caption && !pkg?.title_hint && !pkg?.cover_frame_cue && hashtags.length === 0) return null;

  return (
    <div className="surface-2 rounded-card p-5">
      <SectionHeader title="Publishing package" subtitle="Caption, cover cue and posting angle generated by the editor agent." />
      <div className="grid gap-2 md:grid-cols-2">
        <InfoTile label="Title" value={pkg?.title_hint || 'Auto title ready'} />
        <InfoTile label="Cover" value={pkg?.cover_frame_cue || 'Use the strongest proof frame'} />
        <InfoTile label="Caption" value={caption || '-'} wide />
        <InfoTile label="Post angle" value={pkg?.posting_hint || pkg?.cta_style || '-'} wide />
      </div>
      {hashtags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {hashtags.slice(0, 12).map((tag) => (
            <span key={tag} className="chip px-2 py-0.5 text-[10px]">
              #{String(tag).replace(/^#/, '')}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function AgentChecks({ job }: { job?: DirectorJobStatus | null }) {
  const checks = job?.autonomous_meta?.autonomous_preflight;
  if (!checks) return null;
  const status = String(checks.status || 'ready');
  const issues = [
    ...(checks.hard_failures ?? []),
    ...(checks.warnings ?? []),
  ].slice(0, 4);

  return (
    <div className="surface-2 rounded-card p-5">
      <SectionHeader
        title="Agent checks"
        subtitle={typeof checks.score === 'number' ? `Quality gate score ${checks.score}` : 'Pre-render checks completed.'}
        badge={status.replace(/_/g, ' ')}
        tone={status === 'fail' ? 'orange' : 'cyan'}
      />
      {issues.length > 0 ? (
        <div className="space-y-2">
          {issues.map((issue) => (
            <div key={issue} className="rounded-md border border-hairline bg-surface-3/60 px-3 py-2 text-xs leading-relaxed text-text-muted">
              {String(issue).replace(/_/g, ' ')}
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-md border border-accent-cyan/20 bg-accent-cyan/10 px-3 py-2 text-xs text-text-muted">
          No blocking issues were found before render.
        </div>
      )}
    </div>
  );
}

function MemoryUsed({ job }: { job?: DirectorJobStatus | null }) {
  const selection = job?.autonomous_meta?.auto_pin_selection;
  const selected = selection?.selected ?? [];
  const count = selection?.auto_selected_pin_ids?.length ?? selection?.count ?? 0;
  if (!selection?.enabled || (count === 0 && selected.length === 0)) return null;

  return (
    <div className="surface-2 rounded-card p-5">
      <SectionHeader title="Brand memory used" subtitle="Approved references the agent reused for consistency." />
      {selected.length > 0 ? (
        <div className="grid gap-2 md:grid-cols-3">
          {selected.slice(0, 6).map((item, index) => (
            <div key={`${item.role}:${item.asset_id}:${index}`} className="rounded-md border border-hairline bg-surface-3/60 p-2">
              <div className="truncate text-xs font-semibold text-text">
                {cleanLabel(item.role) || 'Memory'}
              </div>
              <div className="mt-1 text-[10px] leading-relaxed text-text-subtle">
                {[cleanLabel(item.target_market), cleanLabel(item.niche)].filter(Boolean).join(' / ') || 'Reusable anchor'}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-md border border-hairline bg-surface-3/60 px-3 py-2 text-xs text-text-muted">
          {count} approved memory anchors were applied.
        </div>
      )}
    </div>
  );
}

function AttentionPanel({
  title,
  detail,
  action,
}: {
  title: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <div className="surface-2 rounded-card border-accent-orange/40 p-5">
      <div className="flex items-start gap-3">
        <AlertTriangle size={18} className="mt-0.5 shrink-0 text-accent-orange" />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-accent-orange">{title}</div>
          <p className="mt-2 text-xs leading-relaxed text-text-muted">{detail}</p>
          {action && <div className="mt-4">{action}</div>}
        </div>
      </div>
    </div>
  );
}

function SectionHeader({
  title,
  subtitle,
  badge,
  tone = 'cyan',
}: {
  title: string;
  subtitle?: string;
  badge?: string;
  tone?: 'cyan' | 'orange';
}) {
  return (
    <div className="mb-3 flex items-start gap-3">
      <Sparkles size={18} className={`mt-0.5 shrink-0 ${tone === 'orange' ? 'text-accent-orange' : 'text-accent-cyan'}`} />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold">{title}</div>
        {subtitle && <div className="mt-0.5 text-xs text-text-subtle">{subtitle}</div>}
      </div>
      {badge && (
        <span className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase ${
          tone === 'orange'
            ? 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange'
            : 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
        }`}>
          {badge}
        </span>
      )}
    </div>
  );
}

function InfoTile({
  label,
  value,
  wide = false,
}: {
  label: string;
  value: string;
  wide?: boolean;
}) {
  return (
    <div className={`rounded-md border border-hairline bg-surface-3/60 p-2 ${wide ? 'md:col-span-2' : ''}`}>
      <div className="text-[9px] font-semibold uppercase text-text-subtle">
        {label}
      </div>
      <div className="mt-1 line-clamp-3 text-xs leading-relaxed text-text">
        {value}
      </div>
    </div>
  );
}

function formatEta(secondsLeft: number): string {
  if (secondsLeft <= 0) return 'almost done';
  if (secondsLeft < 60) return `~${Math.ceil(secondsLeft)}s left`;
  return `~${Math.ceil(secondsLeft / 60)}m left`;
}

function cleanLabel(value?: string | null): string {
  return String(value || '').replace(/_/g, ' ').trim();
}

function formatRuntime(runtime?: string, duration?: number): string {
  const label = cleanLabel(runtime) || 'auto';
  return duration ? `${label} / ${duration}s` : label;
}
