'use client';

import { GitBranch, ListChecks, Route, Sparkles } from 'lucide-react';

export interface PipelineTraceEntry {
  stage: string;
  input_hash?: string;
  output_hash?: string;
  decision?: string;
  reasoning_summary?: string;
  rules_applied?: readonly string[];
  examples_used?: readonly string[];
  warnings?: readonly string[];
  model_route?: string;
  cost_estimate?: string | number;
  source_repo?: string;
  source_repos?: readonly string[];
}

export interface PipelineTraceViewProps {
  entries?: readonly PipelineTraceEntry[];
  preflight?: unknown;
  productionDecision?: unknown;
  referenceManifest?: unknown;
  approvalLockRevision?: number;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function toStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (typeof item === 'string') return item;
      if (item && typeof item === 'object') {
        const record = item as Record<string, unknown>;
        return String(record.rule_id || record.example_id || record.source_repo || record.id || '');
      }
      return '';
    })
    .filter(Boolean);
}

function inferEntries(
  preflight?: unknown,
  productionDecision?: unknown,
  approvalLockRevision = 0,
): PipelineTraceEntry[] {
  const preflightRecord = asRecord(preflight);
  const productionRecord = asRecord(productionDecision);
  const decision = asRecord(productionRecord?.decision);
  const creativePlan = asRecord(preflightRecord?.creative_plan);
  const route = asRecord(productionRecord?.llm_brain_route);
  const ruleIds = [
    ...toStringList(preflightRecord?.knowledge_rule_ids),
    ...toStringList(productionRecord?.knowledge_rule_ids),
    ...toStringList(decision?.rules_applied),
  ];
  const exampleIds = [
    ...toStringList(preflightRecord?.curated_example_ids),
    ...toStringList(productionRecord?.curated_example_ids),
    ...toStringList(decision?.examples_used),
  ];
  const sourceRepos = Array.from(new Set([
    ...toStringList(preflightRecord?.knowledge_sources),
    ...toStringList(productionRecord?.knowledge_sources),
    ...toStringList(decision?.sources_used),
    ...toStringList(decision?.source_repos),
  ])).slice(0, 6);

  return [
    {
      stage: 'Input Analysis',
      decision: String(decision?.niche || decision?.niche_name || preflightRecord?.status || 'waiting'),
      reasoning_summary: String(decision?.reasoning_summary || preflightRecord?.analysis_summary || 'Agent extracts niche, target market, references, and risk before planning.'),
      model_route: String(route?.analyzer_model || route?.primary_text_model || decision?.model_route || 'auto'),
      rules_applied: ruleIds.slice(0, 4),
      examples_used: exampleIds.slice(0, 4),
      source_repos: sourceRepos,
    },
    {
      stage: 'Creative Plan',
      decision: String(creativePlan?.hook_pattern || creativePlan?.strategy || decision?.strategy || 'pending'),
      reasoning_summary: String(creativePlan?.summary || decision?.reference_strategy || 'Agent chooses shot strategy, reference strategy, and continuity constraints.'),
      rules_applied: ruleIds.slice(0, 6),
      examples_used: exampleIds.slice(0, 4),
      source_repos: sourceRepos,
    },
    {
      stage: 'Approval Lock',
      decision: approvalLockRevision > 0 ? `frontend invalidation v${approvalLockRevision}` : 'waiting',
      reasoning_summary: 'Reference role, settings, prompt, plan, and cost must match the approved source before paid render.',
      model_route: String(decision?.model_route || 'Seedance route locked after approval'),
      warnings: preflightRecord?.status === 'needs_user_input' ? ['User clarification required before approval.'] : [],
    },
  ];
}

export function PipelineTraceView({
  entries,
  preflight,
  productionDecision,
  approvalLockRevision = 0,
}: PipelineTraceViewProps) {
  const traceEntries = entries && entries.length > 0
    ? [...entries]
    : inferEntries(preflight, productionDecision, approvalLockRevision);

  return (
    <section className="rounded-sheet border border-hairline bg-surface-1 p-4 shadow-card-soft">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-normal text-accent-cyan">
            <GitBranch size={14} />
            Pipeline trace
          </div>
          <h2 className="mt-1 text-lg font-extrabold text-text">Why the agent made each choice</h2>
        </div>
        <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-[10px] font-semibold uppercase text-text-subtle">
          {traceEntries.length} stages
        </span>
      </div>

      <div className="grid gap-3">
        {traceEntries.map((entry) => (
          <article key={`${entry.stage}-${entry.input_hash || entry.output_hash || entry.decision}`} className="rounded-card border border-hairline bg-surface-2 p-3">
            <div className="flex items-start gap-3">
              <div className="grid h-8 w-8 shrink-0 place-items-center rounded-card border border-hairline bg-surface-1 text-accent-cyan">
                <Route size={15} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-bold text-text">{entry.stage}</h3>
                  {entry.model_route && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-hairline bg-surface-1 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
                      <Sparkles size={11} />
                      {entry.model_route}
                    </span>
                  )}
                  {entry.source_repo && (
                    <span className="rounded-full border border-hairline bg-surface-1 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
                      {entry.source_repo}
                    </span>
                  )}
                  {entry.source_repos?.map((repo) => (
                    <span key={`${entry.stage}-${repo}`} className="rounded-full border border-hairline bg-surface-1 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
                      {repo}
                    </span>
                  ))}
                </div>
                <p className="mt-1 text-xs leading-relaxed text-text-muted">
                  <span className="font-bold text-text">Decision:</span> {entry.decision || 'pending'}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-text-muted">
                  {entry.reasoning_summary || 'No reasoning summary returned yet.'}
                </p>

                <div className="mt-2 flex flex-wrap gap-1.5">
                  {entry.rules_applied?.map((rule) => (
                    <span key={`rule-${rule}`} className="inline-flex items-center gap-1 rounded-full border border-accent-cyan/20 bg-accent-cyan/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-accent-cyan">
                      <ListChecks size={10} />
                      {rule}
                    </span>
                  ))}
                  {entry.examples_used?.map((example) => (
                    <span key={`example-${example}`} className="rounded-full border border-hairline bg-surface-1 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
                      {example}
                    </span>
                  ))}
                  {entry.warnings?.map((warning) => (
                    <span key={`warning-${warning}`} className="rounded-full border border-accent-orange/25 bg-accent-orange/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-accent-orange">
                      {warning}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
