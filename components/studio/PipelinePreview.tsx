'use client';

import { BadgeCheck, BrainCircuit, Clapperboard, DollarSign, FileText, Loader2, ShieldAlert } from 'lucide-react';

export interface PipelinePreviewScene {
  id: string;
  label?: string;
  durationS?: number;
  prompt?: string;
  visual?: string;
  camera?: string;
  audio?: string;
  status?: string;
  spendUsd?: number;
}

export interface PipelineSpendPreview {
  totalSeconds?: number;
  lowUsd?: number;
  highUsd?: number;
}

export interface PipelinePreviewProps {
  loading?: boolean;
  approved?: boolean;
  renderSourceReady?: boolean;
  referencesConfirmed?: boolean;
  preflight?: unknown;
  productionDecision?: unknown;
  scenes: readonly PipelinePreviewScene[];
  spendPreview?: PipelineSpendPreview | null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function text(value: unknown, fallback = 'Waiting for agent output') {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}

function firstText(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return 'Waiting for agent output';
}

function statusClass(done: boolean, blocked = false) {
  if (blocked) return 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange';
  if (done) return 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan';
  return 'border-hairline bg-surface-2 text-text-subtle';
}

export function PipelinePreview({
  loading = false,
  approved = false,
  renderSourceReady = false,
  referencesConfirmed = false,
  preflight,
  productionDecision,
  scenes,
  spendPreview,
}: PipelinePreviewProps) {
  const preflightRecord = asRecord(preflight);
  const productionRecord = asRecord(productionDecision);
  const creativePlan = asRecord(preflightRecord?.creative_plan);
  const approvedPlan = asRecord(preflightRecord?.approved_plan);
  const decision = asRecord(productionRecord?.decision);
  const status = text(preflightRecord?.status, 'waiting');
  const needsInput = status === 'needs_user_input';
  const promptCount = scenes.filter((scene) => scene.prompt?.trim()).length;
  const analysisText = firstText(
    preflightRecord?.analysis_summary,
    decision?.niche,
    decision?.niche_name,
    productionRecord?.niche,
  );
  const planText = firstText(
    creativePlan?.strategy,
    creativePlan?.summary,
    approvedPlan?.summary,
    decision?.strategy,
  );
  const costLabel = spendPreview
    ? `$${(spendPreview.lowUsd ?? 0).toFixed(2)} - $${(spendPreview.highUsd ?? 0).toFixed(2)}`
    : 'Cost pending';

  const steps = [
    {
      key: 'analysis',
      label: 'Input Analysis',
      icon: <BrainCircuit size={15} />,
      done: Boolean(preflight || productionDecision),
      blocked: needsInput,
      detail: analysisText,
    },
    {
      key: 'plan',
      label: 'Creative Plan',
      icon: <FileText size={15} />,
      done: Boolean(creativePlan || approvedPlan || decision),
      blocked: needsInput,
      detail: planText,
    },
    {
      key: 'storyboard',
      label: 'Storyboard',
      icon: <Clapperboard size={15} />,
      done: scenes.length > 0,
      blocked: false,
      detail: scenes.length > 0 ? `${scenes.length} planned shot${scenes.length === 1 ? '' : 's'}` : 'Storyboard pending',
    },
    {
      key: 'prompts',
      label: 'Seedance Prompts',
      icon: <FileText size={15} />,
      done: promptCount > 0,
      blocked: !referencesConfirmed && scenes.length > 0,
      detail: promptCount > 0 ? `${promptCount} prompt preview${promptCount === 1 ? '' : 's'} ready` : 'Prompt preview pending',
    },
    {
      key: 'cost',
      label: 'Cost & Risk',
      icon: <DollarSign size={15} />,
      done: Boolean(spendPreview),
      blocked: !approved && Boolean(spendPreview),
      detail: `${costLabel}${renderSourceReady ? ' | render source locked' : ''}`,
    },
  ];

  return (
    <section className="rounded-sheet border border-hairline bg-surface-1 p-4 shadow-card-soft">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-bold uppercase tracking-normal text-accent-cyan">
            Pipeline preview
          </div>
          <h2 className="mt-1 text-lg font-extrabold text-text">Review before paid render</h2>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${
          statusClass(approved, needsInput)
        }`}>
          {loading ? <Loader2 size={12} className="animate-spin" /> : needsInput ? <ShieldAlert size={12} /> : <BadgeCheck size={12} />}
          {loading ? 'Planning' : status.replace(/_/g, ' ')}
        </span>
      </div>

      <div className="grid gap-2">
        {steps.map((step) => (
          <article key={step.key} className="rounded-card border border-hairline bg-surface-2 px-3 py-3">
            <div className="flex items-start gap-3">
              <div className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-card border ${statusClass(step.done, step.blocked)}`}>
                {loading && !step.done ? <Loader2 size={15} className="animate-spin" /> : step.icon}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-bold text-text">{step.label}</h3>
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${statusClass(step.done, step.blocked)}`}>
                    {step.blocked ? 'Needs review' : step.done ? 'Ready' : 'Pending'}
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-text-muted">{step.detail}</p>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
