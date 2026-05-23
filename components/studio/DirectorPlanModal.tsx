'use client';

/**
 * DirectorPlanModal — V3 entry modal.
 *
 * Wraps DirectorPlanTab (Human-in-the-Loop review) + handles approve→render handoff.
 * Replaces the legacy SceneEditorModal as the canonical V3 review surface.
 */

import { useEffect, useState } from 'react';
import { X, MessageSquare } from 'lucide-react';
import { DirectorPlanTab } from './DirectorPlanTab';
import { WorkspaceChat } from './WorkspaceChat';
import {
  useDirectorPlan,
  generateFromPlan,
  fetchDirectorJob,
  type DirectorPlan,
} from '@/lib/studio/use-director-plan';
import type { VideoSettings } from '@/lib/types/backend';

interface Props {
  open: boolean;
  initialRequest: Parameters<ReturnType<typeof useDirectorPlan>['createPlan']>[0] | null;
  referenceImages: string[];
  settings: VideoSettings;
  onClose: () => void;
  onJobStarted: (jobId: string) => void;
}

export function DirectorPlanModal({
  open,
  initialRequest,
  referenceImages,
  settings,
  onClose,
  onJobStarted,
}: Props) {
  const { createPlan, plan, progress, isLoading, error, reset } = useDirectorPlan();
  const [approving, setApproving] = useState(false);
  const [jobError, setJobError] = useState<string | null>(null);
  // V3 Workspace Chat — collapsible sidebar bên phải
  const [chatOpen, setChatOpen] = useState(false);
  // Revised plan từ chat — DirectorPlanTab nhận như "fresh plan" qua useDirectorPlan
  // result (instead of overwriting `plan` từ hook, we keep a chat-override).
  const [chatOverride, setChatOverride] = useState<DirectorPlan | null>(null);

  useEffect(() => {
    if (open && initialRequest) {
      createPlan(initialRequest);
      setChatOverride(null);
    }
    if (!open) {
      reset();
      setJobError(null);
      setApproving(false);
      setChatOverride(null);
      setChatOpen(false);
    }
  }, [open, initialRequest, createPlan, reset]);

  if (!open) return null;

  const handleApprove = async (
    finalPlan: DirectorPlan,
    audioPlan?: { driven_audio_urls?: Record<string, string> },
  ) => {
    setApproving(true);
    setJobError(null);
    try {
      const job = await generateFromPlan({
        plan: finalPlan,
        reference_images: referenceImages,
        settings,
        audio_plan: audioPlan,
      });
      onJobStarted(job.job_id);
      onClose();
    } catch (e) {
      setJobError(e instanceof Error ? e.message : String(e));
    } finally {
      setApproving(false);
    }
  };

  const handleRetry = () => {
    if (!initialRequest) return;
    reset();
    createPlan(initialRequest);
  };

  const effectivePlan = chatOverride ?? plan;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className={`bg-bg-card border border-border rounded-2xl shadow-2xl w-full ${chatOpen ? 'max-w-6xl' : 'max-w-5xl'} max-h-[90vh] flex flex-col overflow-hidden transition-all`}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-brand-300 font-medium">CineForge Director V3</div>
            <div className="text-sm font-semibold text-text">Continuity Bible · Shot List · Storyboard</div>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setChatOpen((v) => !v)}
              className={`p-1.5 rounded-md transition inline-flex items-center gap-1 text-xs ${
                chatOpen ? 'bg-fuchsia-500/15 text-fuchsia-200 border border-fuchsia-500/30' : 'hover:bg-bg-hover text-text-muted hover:text-text'
              }`}
              title="Toggle Workspace Chat (revise plan với LLM)"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Chat</span>
            </button>
            <button onClick={onClose} className="p-1.5 rounded-md hover:bg-bg-hover text-text-muted hover:text-text">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
        <div className="flex-1 min-h-0 overflow-hidden flex">
          <div className="flex-1 min-w-0 overflow-hidden">
            <DirectorPlanTab
              plan={effectivePlan}
              referenceImages={referenceImages}
              isLoading={isLoading || approving}
              progress={progress}
              error={error || jobError}
              onApprove={handleApprove}
              onRetry={handleRetry}
              onCancel={onClose}
              // V3 §3.5 Refine — enable per-shot refine drawer + quick-refine from Evaluation
              // suggestions. Modal is opened DURING the pre-render review here, so the
              // shotId → last_frame_url map starts empty; once the user runs the first
              // render, StudioMain can pipe `chain.last_frame_url`s back via this prop.
              refine={{
                settings,
                lastFramesByShotId: {},
              }}
            />
          </div>
          {chatOpen && effectivePlan && (
            <WorkspaceChat
              plan={effectivePlan}
              settings={settings}
              onApplyRevision={(revised) => setChatOverride(revised)}
              onCollapse={() => setChatOpen(false)}
            />
          )}
        </div>
      </div>
    </div>
  );
}

/** Lightweight job poller — caller can use directly or copy. */
export function useDirectorJobPoll(jobId: string | null, intervalMs = 2500) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const j = await fetchDirectorJob(jobId);
        if (cancelled) return;
        setData(j);
        if (j.status === 'done' || j.status === 'failed' || j.status === 'cancelled') return;
      } catch {
        /* swallow */
      }
      if (!cancelled) setTimeout(tick, intervalMs);
    };
    tick();
    return () => { cancelled = true; };
  }, [jobId, intervalMs]);
  return data;
}
