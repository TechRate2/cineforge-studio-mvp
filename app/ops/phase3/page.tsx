'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { AlertTriangle, CheckCircle2, Loader2, ShieldCheck } from 'lucide-react';

type AuditRecord = Record<string, unknown>;

interface Phase3Audit {
  schema_version?: string;
  phase?: string;
  verdict?: {
    ready_for_controlled_paid_benchmark?: boolean;
    top_tier_claim_allowed?: boolean;
    failed_count?: number;
    warning_count?: number;
    why?: string;
  };
  docs_alignment?: {
    last_reviewed?: string;
    sources?: AuditRecord[];
    local_policy?: string[];
  };
  model_route_contracts?: AuditRecord[];
  niche_prompt_matrix?: {
    niche_count?: number;
    rows?: AuditRecord[];
  };
  paid_benchmark_gate?: AuditRecord;
  phase3b_feedback_loop?: AuditRecord;
  next_engineering_actions?: AuditRecord[];
}

interface Phase4Audit {
  schema_version?: string;
  verdict?: {
    non_paid_phase4_complete?: boolean;
    current_claim_level?: string;
    passed_count?: number;
    locked_count?: number;
    failed_count?: number;
    readiness_percentages?: AuditRecord;
    plain_answer?: string;
  };
  vendor_call_policy?: AuditRecord;
  phase4a_controlled_benchmark?: AuditRecord;
  phase4b_post_render_qa?: AuditRecord;
  phase4c_long_form_graph?: AuditRecord;
  phase4d_e2e_verification?: AuditRecord;
  phase4e_feedback_evidence?: AuditRecord;
  phase4f_operator_controls?: AuditRecord;
}

export default function AdminPage() {
  const [audit, setAudit] = useState<Phase3Audit | null>(null);
  const [phase4, setPhase4] = useState<Phase4Audit | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function loadAudit() {
      try {
        const [phase3Res, phase4Res] = await Promise.all([
          fetch('/api/v1/director/autonomous/phase3-prompt-route-audit', { cache: 'no-store' }),
          fetch('/api/v1/director/autonomous/phase4-completion-audit', { cache: 'no-store' }),
        ]);
        if (!phase3Res.ok) throw new Error(`Phase 3 HTTP ${phase3Res.status}`);
        if (!phase4Res.ok) throw new Error(`Phase 4 HTTP ${phase4Res.status}`);
        const [phase3Data, phase4Data] = await Promise.all([
          phase3Res.json(),
          phase4Res.json(),
        ]);
        if (!cancelled) {
          setAudit(phase3Data);
          setPhase4(phase4Data);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadAudit();
    return () => {
      cancelled = true;
    };
  }, []);

  const verdict = audit?.verdict;
  const routes = audit?.model_route_contracts ?? [];
  const nicheRows = audit?.niche_prompt_matrix?.rows ?? [];
  const sources = audit?.docs_alignment?.sources ?? [];
  const actions = audit?.next_engineering_actions ?? [];

  return (
    <main className="min-h-screen bg-background px-4 py-8 text-text md:px-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.22em] text-accent-cyan">
              Operator Console
            </div>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight md:text-4xl">
              Phase 3 Route Audit
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-text-muted">
              Non-billable control room for Seedance routing, prompt contracts,
              niche coverage, benchmark gate status, and post-render evidence.
            </p>
          </div>
          <Link href="/studio" className="btn-outline">
            Back to Studio
          </Link>
        </div>

        {loading && (
          <div className="surface-2 rounded-card p-5 text-sm text-text-muted">
            <Loader2 size={16} className="mr-2 inline animate-spin text-accent-cyan" />
            Loading audit...
          </div>
        )}

        {error && (
          <div className="surface-2 rounded-card border-accent-orange/40 p-5 text-sm text-accent-orange">
            <AlertTriangle size={16} className="mr-2 inline" />
            Failed to load operator audit: {error}
          </div>
        )}

        {audit && (
          <>
            <section className="grid gap-3 md:grid-cols-4">
              <StatusCard
                label="Paid benchmark"
                value={verdict?.ready_for_controlled_paid_benchmark ? 'Ready' : 'Blocked'}
                detail="Controlled only, never auto-run."
                good={Boolean(verdict?.ready_for_controlled_paid_benchmark)}
              />
              <StatusCard
                label="Top-tier claim"
                value={verdict?.top_tier_claim_allowed ? 'Allowed' : 'Locked'}
                detail="Requires real output evidence."
                good={false}
              />
              <StatusCard
                label="Failed checks"
                value={String(verdict?.failed_count ?? 0)}
                detail="Must stay at zero before render."
                good={(verdict?.failed_count ?? 0) === 0}
              />
              <StatusCard
                label="Warnings"
                value={String(verdict?.warning_count ?? 0)}
                detail={`Docs reviewed ${audit.docs_alignment?.last_reviewed || 'unknown'}.`}
                good={(verdict?.warning_count ?? 0) === 0}
              />
            </section>

            <section className="surface-2 rounded-card p-5">
              <SectionHeader title="Current Verdict" />
              <p className="text-sm leading-relaxed text-text-muted">
                {verdict?.why || 'Audit verdict unavailable.'}
              </p>
            </section>

            <section className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
              <div className="surface-2 rounded-card p-5">
                <SectionHeader title="Model Routes" subtitle={`${routes.length} concrete routes audited`} />
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-xs">
                    <thead className="text-[10px] uppercase text-text-subtle">
                      <tr>
                        <th className="py-2 pr-3">Model</th>
                        <th className="py-2 pr-3">Mode</th>
                        <th className="py-2 pr-3">Cost/s</th>
                        <th className="py-2 pr-3">Refs</th>
                        <th className="py-2 pr-3">Use when</th>
                      </tr>
                    </thead>
                    <tbody>
                      {routes.map((route) => (
                        <tr key={text(route.model_key)} className="border-t border-hairline">
                          <td className="py-3 pr-3 font-semibold text-text">{text(route.model_key)}</td>
                          <td className="py-3 pr-3 text-text-muted">{text(route.mode)}</td>
                          <td className="py-3 pr-3 text-text-muted">{cost(route.cost_per_second_usd)}</td>
                          <td className="py-3 pr-3 text-text-muted">{refs(route.reference_limits)}</td>
                          <td className="py-3 pr-3 text-text-muted">{listText(route.use_when)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="surface-2 rounded-card p-5">
                <SectionHeader title="Documentation Sources" subtitle="Audit input references" />
                <div className="space-y-2">
                  {sources.map((source, index) => (
                    <a
                      key={`${text(source.source)}:${index}`}
                      href={text(source.url)}
                      target="_blank"
                      rel="noreferrer"
                      className="block rounded-md border border-hairline bg-surface-3/60 p-3 text-xs transition hover:border-accent-cyan/40"
                    >
                      <div className="font-semibold text-text">{text(source.source)}</div>
                      <div className="mt-1 line-clamp-2 text-text-subtle">{listText(source.observations)}</div>
                    </a>
                  ))}
                </div>
              </div>
            </section>

            {phase4 && (
              <section className="surface-2 rounded-card p-5">
                <SectionHeader title="Phase 4 Non-Paid Completion" subtitle={phase4.verdict?.current_claim_level} />
                <div className="grid gap-3 md:grid-cols-4">
                  <InfoStat
                    label="No-paid complete"
                    value={phase4.verdict?.non_paid_phase4_complete ? 'Yes' : 'No'}
                    good={Boolean(phase4.verdict?.non_paid_phase4_complete)}
                  />
                  <InfoStat
                    label="Passed"
                    value={String(phase4.verdict?.passed_count ?? 0)}
                    good={(phase4.verdict?.failed_count ?? 0) === 0}
                  />
                  <InfoStat
                    label="Locked"
                    value={String(phase4.verdict?.locked_count ?? 0)}
                    good={false}
                  />
                  <InfoStat
                    label="Failed"
                    value={String(phase4.verdict?.failed_count ?? 0)}
                    good={(phase4.verdict?.failed_count ?? 0) === 0}
                  />
                </div>
                <p className="mt-4 text-xs leading-relaxed text-text-muted">
                  {phase4.verdict?.plain_answer || 'Phase 4 completion verdict unavailable.'}
                </p>
                <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  <KeyValue data={phase4.vendor_call_policy || {}} />
                  <KeyValue data={phase4.phase4b_post_render_qa || {}} />
                  <KeyValue data={phase4.phase4d_e2e_verification || {}} />
                </div>
              </section>
            )}

            <section className="surface-2 rounded-card p-5">
              <SectionHeader
                title="Niche Matrix"
                subtitle={`${audit.niche_prompt_matrix?.niche_count ?? nicheRows.length} niches routed through prompt contracts`}
              />
              <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {nicheRows.slice(0, 24).map((row) => (
                  <div key={text(row.niche)} className="rounded-md border border-hairline bg-surface-3/60 p-3">
                    <div className="text-sm font-semibold text-text">{label(row.niche)}</div>
                    <div className="mt-1 text-[11px] text-text-subtle">
                      Tier: {label(row.launch_tier)} / Runtime: {label(row.runtime_fit)}
                    </div>
                    <div className="mt-2 line-clamp-3 text-xs leading-relaxed text-text-muted">
                      {listText(row.prompt_requirements || row.route_contract || row.reference_contract)}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
              <div className="surface-2 rounded-card p-5">
                <SectionHeader title="Benchmark Gate" />
                <KeyValue data={audit.paid_benchmark_gate || {}} />
              </div>
              <div className="surface-2 rounded-card p-5">
                <SectionHeader title="Feedback Loop" subtitle="Phase 3B post-render evidence" />
                <KeyValue data={audit.phase3b_feedback_loop || {}} />
              </div>
              <div className="surface-2 rounded-card p-5">
                <SectionHeader title="Next Engineering Actions" />
                <div className="space-y-2">
                  {actions.length ? actions.map((action, index) => (
                    <div key={index} className="rounded-md border border-hairline bg-surface-3/60 p-3 text-xs">
                      <div className="font-semibold text-text">{label(action.action || action.title || `Action ${index + 1}`)}</div>
                      <div className="mt-1 text-text-muted">{listText(action.why || action.detail || action)}</div>
                    </div>
                  )) : (
                    <div className="text-sm text-text-muted">No open engineering actions reported.</div>
                  )}
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}

function StatusCard({
  label,
  value,
  detail,
  good,
}: {
  label: string;
  value: string;
  detail: string;
  good: boolean;
}) {
  return (
    <div className="surface-2 rounded-card p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-subtle">
          {label}
        </div>
        {good ? (
          <CheckCircle2 size={16} className="text-accent-cyan" />
        ) : (
          <ShieldCheck size={16} className="text-accent-orange" />
        )}
      </div>
      <div className="mt-3 text-2xl font-semibold">{value}</div>
      <div className="mt-1 text-xs text-text-muted">{detail}</div>
    </div>
  );
}

function InfoStat({
  label,
  value,
  good,
}: {
  label: string;
  value: string;
  good: boolean;
}) {
  return (
    <div className="rounded-md border border-hairline bg-surface-3/60 p-3">
      <div className="text-[10px] font-semibold uppercase text-text-subtle">{label}</div>
      <div className={good ? 'mt-1 text-lg font-semibold text-accent-cyan' : 'mt-1 text-lg font-semibold text-accent-orange'}>
        {value}
      </div>
    </div>
  );
}

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-3">
      <h2 className="text-sm font-semibold text-text">{title}</h2>
      {subtitle && <p className="mt-1 text-xs text-text-subtle">{subtitle}</p>}
    </div>
  );
}

function KeyValue({ data }: { data: AuditRecord }) {
  const entries = Object.entries(data).slice(0, 8);
  if (!entries.length) return <div className="text-sm text-text-muted">No data.</div>;
  return (
    <div className="space-y-2">
      {entries.map(([key, value]) => (
        <div key={key} className="rounded-md border border-hairline bg-surface-3/60 p-3 text-xs">
          <div className="font-semibold text-text-subtle">{label(key)}</div>
          <div className="mt-1 line-clamp-4 text-text-muted">{listText(value)}</div>
        </div>
      ))}
    </div>
  );
}

function text(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return '';
}

function label(value: unknown): string {
  const raw = text(value);
  return raw ? raw.replace(/_/g, ' ') : '-';
}

function listText(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => listText(item)).filter(Boolean).join(' | ');
  if (value && typeof value === 'object') {
    return Object.entries(value as AuditRecord)
      .slice(0, 4)
      .map(([key, item]) => `${label(key)}: ${listText(item)}`)
      .join(' | ');
  }
  return text(value) || '-';
}

function cost(value: unknown): string {
  return typeof value === 'number' ? `$${value.toFixed(3)}` : '-';
}

function refs(value: unknown): string {
  if (!value || typeof value !== 'object') return '-';
  const ref = value as AuditRecord;
  return `img ${text(ref.images) || 0} / vid ${text(ref.videos) || 0} / aud ${text(ref.audios) || 0}`;
}
