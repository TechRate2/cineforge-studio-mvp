'use client';

/**
 * ProjectHistoryDrawer — List/replay/fork recent Director V3 render jobs.
 *
 * 3 actions per job:
 *   • Replay   — open <video> preview với output_url
 *   • Fork     — load plan vào DirectorPlanModal mới (caller handle)
 *   • Delete   — remove from history (UI only — actual file vẫn ở R2)
 */

import { useState } from 'react';
import {
  X, History as HistoryIcon, Play, GitFork, Trash2, Loader2,
  CheckCircle2, AlertTriangle, Clock, Film,
} from 'lucide-react';
import {
  useProjectHistory,
  type HistoryItem,
  type HistoryDetail,
} from '@/lib/studio/use-project-history';
import type { DirectorPlan } from '@/lib/studio/use-director-plan';
import { TimelineEditor } from './TimelineEditor';

interface Props {
  open: boolean;
  onClose: () => void;
  /** Called when user clicks "Fork" — caller opens DirectorPlanModal seeded
   *  with this plan (typically pre-fill StudioMain state from plan). */
  onFork?: (plan: DirectorPlan) => void;
}

export function ProjectHistoryDrawer({ open, onClose, onFork }: Props) {
  const hist = useProjectHistory();
  const [previewJob, setPreviewJob] = useState<HistoryItem | null>(null);
  const [forking, setForking] = useState(false);
  const [timelineJobId, setTimelineJobId] = useState<string | null>(null);

  if (!open) return null;

  const handleFork = async (job: HistoryItem) => {
    if (!onFork) return;
    setForking(true);
    try {
      const detail = await hist.getDetail(job.job_id);
      if (detail.plan) onFork(detail.plan);
      onClose();
    } catch (e) {
      alert(`Fork lỗi: ${e instanceof Error ? e.message : e}`);
    } finally {
      setForking(false);
    }
  };

  const handleDelete = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Xoá khỏi history? File MP4 trên R2 không bị xoá.')) return;
    try {
      await hist.remove(jobId);
      if (previewJob?.job_id === jobId) setPreviewJob(null);
    } catch (e) {
      alert(`Lỗi: ${e instanceof Error ? e.message : e}`);
    }
  };

  return (
    <div className="fixed inset-0 z-[55] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-bg-card border border-border rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            <HistoryIcon className="w-4 h-4 text-brand-300" />
            <div>
              <div className="text-[10px] uppercase tracking-widest text-brand-300 font-medium">Project History</div>
              <div className="text-sm font-semibold text-text">
                Render đã hoàn thành · {hist.items.length} jobs
              </div>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-bg-hover text-text-muted hover:text-text">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body — 2 cols */}
        <div className="flex-1 min-h-0 flex">
          {/* Left: list */}
          <div className="w-[420px] border-r border-border overflow-y-auto">
            {hist.loading ? (
              <div className="p-6 text-center text-text-subtle text-sm">Đang tải…</div>
            ) : hist.error ? (
              <div className="p-6 text-center text-rose-300 text-sm">Lỗi: {hist.error}</div>
            ) : hist.items.length === 0 ? (
              <div className="p-6 text-center text-text-subtle text-sm">
                Chưa có render nào.
                <div className="text-xs mt-1.5">Render plan qua Director Modal → tự lưu vào đây.</div>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {hist.items.map((it) => (
                  <HistoryRow
                    key={it.job_id}
                    item={it}
                    active={previewJob?.job_id === it.job_id}
                    onClick={() => setPreviewJob(it)}
                    onDelete={(e) => handleDelete(it.job_id, e)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Right: preview */}
          <div className="flex-1 overflow-y-auto p-5">
            {previewJob ? (
              <HistoryPreview
                item={previewJob}
                onFork={onFork ? () => handleFork(previewJob) : undefined}
                onOpenTimeline={() => setTimelineJobId(previewJob.job_id)}
                forking={forking}
              />
            ) : (
              <div className="h-full flex items-center justify-center text-text-subtle text-sm">
                Chọn job ở danh sách để xem preview + fork
              </div>
            )}
          </div>
        </div>

        {/* Timeline Editor modal — đè trên ProjectHistoryDrawer */}
        <TimelineEditor
          open={!!timelineJobId}
          historyJobId={timelineJobId}
          onClose={() => setTimelineJobId(null)}
        />

        {/* Footer */}
        <div className="border-t border-border px-5 py-3 flex items-center justify-end gap-2">
          <button onClick={hist.refresh} className="text-xs px-3 py-2 rounded-md border border-border bg-bg-soft hover:bg-bg-hover text-text-muted">
            Refresh
          </button>
          <button onClick={onClose} className="text-xs px-3 py-2 rounded-md border border-border bg-bg-soft hover:bg-bg-hover text-text-muted">
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Sub: list row
// ============================================================
function HistoryRow({
  item, active, onClick, onDelete,
}: {
  item: HistoryItem;
  active: boolean;
  onClick: () => void;
  onDelete: (e: React.MouseEvent) => void;
}) {
  const statusIcon = item.status === 'done'
    ? <CheckCircle2 className="w-3 h-3 text-emerald-400" />
    : item.status === 'failed'
      ? <AlertTriangle className="w-3 h-3 text-rose-400" />
      : <Clock className="w-3 h-3 text-text-subtle" />;
  return (
    <button
      onClick={onClick}
      className={`group w-full text-left px-4 py-3 transition ${
        active ? 'bg-brand-500/10 border-l-2 border-brand-500' : 'hover:bg-bg-soft border-l-2 border-transparent'
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5 text-[11px] text-text-muted">
          {statusIcon}
          <span className="font-mono">{item.job_id.slice(0, 16)}</span>
        </div>
        <button
          onClick={onDelete}
          className="opacity-0 group-hover:opacity-100 p-1 text-rose-400 hover:text-rose-300 transition"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>
      <div className="text-xs text-text font-medium truncate">
        {item.title ?? '(no title)'}
      </div>
      <div className="text-[10px] text-text-subtle flex items-center gap-2 mt-0.5">
        <span>{item.duration_s ?? '—'}s</span>
        {item.cost_estimate_usd != null && <span>${item.cost_estimate_usd.toFixed(2)}</span>}
        <span className="capitalize">{item.mode}</span>
        {item.finished_at && (
          <span>· {new Date(item.finished_at).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' })}</span>
        )}
      </div>
    </button>
  );
}

// ============================================================
// Sub: preview pane
// ============================================================
function HistoryPreview({
  item, onFork, onOpenTimeline, forking,
}: {
  item: HistoryItem;
  onFork?: () => void;
  onOpenTimeline?: () => void;
  forking: boolean;
}) {
  return (
    <div className="space-y-3">
      <div>
        <div className="text-xs text-text-subtle">Title</div>
        <div className="text-sm font-semibold text-text">{item.title ?? '(no title)'}</div>
      </div>
      <div className="grid grid-cols-2 gap-3 text-xs">
        <KV label="Status" value={item.status} />
        <KV label="Mode" value={item.mode} />
        <KV label="Duration" value={`${item.duration_s ?? '—'}s`} />
        <KV label="Cost est." value={item.cost_estimate_usd != null ? `$${item.cost_estimate_usd.toFixed(2)}` : '—'} />
        <KV label="Plan ID" value={item.plan_id ?? '—'} mono />
        <KV label="Job ID" value={item.job_id} mono />
        <KV
          label="Finished"
          value={item.finished_at
            ? new Date(item.finished_at).toLocaleString('vi-VN')
            : '—'}
        />
      </div>

      {item.output_url ? (
        item.output_url.endsWith('.mp4') || item.output_url.startsWith('http') ? (
          <video
            controls
            src={item.output_url}
            className="w-full rounded-md border border-border bg-black"
          />
        ) : (
          <a href={item.output_url} target="_blank" rel="noopener noreferrer" className="block text-xs text-brand-300 underline break-all">
            {item.output_url}
          </a>
        )
      ) : (
        <div className="px-3 py-2 rounded bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs">
          Job không có output URL — có thể fail hoặc local-only.
        </div>
      )}

      <div className="flex items-center gap-2 pt-2 flex-wrap">
        {onFork && (
          <button
            onClick={onFork}
            disabled={forking}
            className="text-xs px-4 py-2 rounded-md bg-gradient-to-r from-brand-500 to-fuchsia-500 hover:opacity-90 disabled:opacity-40 text-white font-medium inline-flex items-center gap-1.5"
          >
            {forking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <GitFork className="w-3.5 h-3.5" />}
            Fork plan này
          </button>
        )}
        {onOpenTimeline && item.status === 'done' && (
          <button
            onClick={onOpenTimeline}
            className="text-xs px-4 py-2 rounded-md border border-brand-500/50 bg-brand-500/10 hover:bg-brand-500/20 text-brand-200 font-medium inline-flex items-center gap-1.5"
          >
            <Film className="w-3.5 h-3.5" /> Open Timeline
          </button>
        )}
        {item.output_url && (
          <a
            href={item.output_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs px-4 py-2 rounded-md border border-border bg-bg-soft hover:bg-bg-hover text-text-muted inline-flex items-center gap-1.5"
          >
            <Play className="w-3.5 h-3.5" /> Mở tab mới
          </a>
        )}
      </div>
    </div>
  );
}

function KV({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-text-subtle text-[10px] uppercase tracking-wider">{label}</div>
      <div className={`text-text ${mono ? 'font-mono text-[11px]' : ''}`}>{value}</div>
    </div>
  );
}
