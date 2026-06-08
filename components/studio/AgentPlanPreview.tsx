'use client';

import type { ReactNode } from 'react';
import { AlertTriangle, BrainCircuit, ChevronDown, DollarSign, FileText, Sparkles } from 'lucide-react';
import { ReferenceIntelligencePanel, summarizeReferenceIntelligence } from './ReferenceIntelligencePanel';
import { StoryboardPreview, type StoryboardPreviewScene } from './StoryboardPreview';
import { VoiceAudioPlanPreview } from './VoiceAudioPlanPreview';
import type { StudioLanguage } from './studio-i18n';
import { t } from './studio-i18n';

export interface AgentPlanSpendPreview {
  totalSeconds?: number;
  lowUsd?: number;
  highUsd?: number;
  totalUsd?: number;
  source?: 'backend_dry_run' | 'pending';
}

export interface AgentPlanPreviewProps {
  loading?: boolean;
  approved?: boolean;
  renderSourceReady?: boolean;
  referencesConfirmed?: boolean;
  preflight?: unknown;
  productionDecision?: unknown;
  dryRunReport?: Record<string, unknown> | null;
  scenes: readonly StoryboardPreviewScene[];
  spendPreview?: AgentPlanSpendPreview | null;
  activeSceneId?: string | null;
  language?: StudioLanguage;
  onSelectScene?: (id: string) => void;
  onCopyPrompt?: (prompt: string) => void;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function stringValue(value: unknown): string {
  return typeof value === 'string' && value.trim() ? value.trim() : '';
}

function numberValue(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || '').trim()).filter(Boolean);
}

function firstText(...values: unknown[]): string {
  for (const value of values) {
    const text = stringValue(value);
    if (text) return text;
  }
  return '';
}

function formatCost(spend?: AgentPlanSpendPreview | null) {
  if (!spend) return '';
  if (spend.source !== 'backend_dry_run') return '';
  if (typeof spend.lowUsd === 'number' && typeof spend.highUsd === 'number') {
    if (spend.lowUsd === spend.highUsd) return `$${spend.lowUsd.toFixed(2)}`;
    return `$${spend.lowUsd.toFixed(2)} - $${spend.highUsd.toFixed(2)}`;
  }
  if (typeof spend.totalUsd === 'number') return `$${spend.totalUsd.toFixed(2)}`;
  if (typeof spend.highUsd === 'number') return `$${spend.highUsd.toFixed(2)}`;
  if (typeof spend.lowUsd === 'number') return `$${spend.lowUsd.toFixed(2)}`;
  return '';
}

export function AgentPlanPreview({
  loading = false,
  approved = false,
  renderSourceReady = false,
  referencesConfirmed = false,
  preflight,
  productionDecision,
  dryRunReport,
  scenes,
  spendPreview,
  activeSceneId,
  language = 'vi',
  onSelectScene,
  onCopyPrompt,
}: AgentPlanPreviewProps) {
  const preflightRecord = asRecord(preflight);
  const productionRecord = asRecord(productionDecision);
  const creativePlan = asRecord(preflightRecord?.creative_plan);
  const summary = asRecord(preflightRecord?.summary);
  const producer = asRecord(preflightRecord?.creative_producer_v2);
  const selectedAngle = asRecord(producer?.selected_angle);
  const promptContract = asRecord(preflightRecord?.prompt_execution_contract_v3);
  const modelPlan = asRecord(promptContract?.model_plan);
  const decision = asRecord(productionRecord?.decision);
  const referenceSummary = summarizeReferenceIntelligence(dryRunReport);
  const warnings = [
    ...stringList(preflightRecord?.input_suggestions).slice(0, 0),
    ...stringList(promptContract?.warnings),
    ...stringList(dryRunReport?.warnings),
    ...stringList(dryRunReport?.hard_failures),
  ].slice(0, 8);

  const objective = firstText(
    asRecord(preflightRecord?.creative_brief_contract)?.parsed && asRecord(asRecord(preflightRecord?.creative_brief_contract)?.parsed)?.output_intent,
    creativePlan?.logline,
    creativePlan?.viewer_promise,
    preflightRecord?.approved_brief,
  );
  const concept = firstText(
    creativePlan?.title,
    creativePlan?.creative_angle,
    selectedAngle?.label,
    selectedAngle?.hook,
  );
  const scriptBeats = Array.isArray(preflightRecord?.script_outline)
    ? preflightRecord?.script_outline as Array<Record<string, unknown>>
    : Array.isArray(producer?.script_beats)
      ? producer?.script_beats as Array<Record<string, unknown>>
      : [];
  const scriptSummary = scriptBeats
    .map((beat) => firstText(beat.script, beat.beat, beat.purpose))
    .filter(Boolean)
    .slice(0, 4);
  const promptStrategy = firstText(
    modelPlan?.primary_visual_model,
    summary?.prompt_primary_visual_model,
    decision?.primary_model_route,
    dryRunReport?.model,
  );
  const costLabel = formatCost(spendPreview);

  return (
    <section className="rounded-sheet border border-hairline bg-surface-1 p-4 shadow-card-soft">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-normal text-accent-cyan">
            <BrainCircuit size={14} />
            {t(language, 'agentPlan')}
          </div>
          <h2 className="mt-1 text-lg font-extrabold text-text">
            {language === 'vi' ? 'Agent hiểu gì và sẽ sản xuất ra sao' : 'What the Agent understands and will produce'}
          </h2>
        </div>
        <span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase ${
          renderSourceReady
            ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
            : approved
              ? 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange'
              : 'border-hairline bg-surface-2 text-text-subtle'
        }`}>
          {loading ? (language === 'vi' ? 'Agent đang nghĩ' : 'Planning') : renderSourceReady ? 'ApprovalLock' : approved ? t(language, 'dryRun') : t(language, 'pending')}
        </span>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <PlanTile icon={<Sparkles size={15} />} label={language === 'vi' ? 'Mục tiêu' : 'Objective'} value={objective || t(language, 'unknown')} />
        <PlanTile icon={<FileText size={15} />} label={language === 'vi' ? 'Concept' : 'Concept'} value={concept || t(language, 'unknown')} />
        <PlanTile label="Niche" value={firstText(summary?.niche, decision?.niche, productionRecord?.niche) || t(language, 'unknown')} />
        <PlanTile label="Platform / Market" value={`${firstText(summary?.target_platform, decision?.target_platform) || 'auto'} / ${firstText(summary?.market, decision?.target_market) || 'auto'}`} />
        <PlanTile label={language === 'vi' ? 'Thời lượng / Khung hình' : 'Duration / Frame'} value={`${numberValue(summary?.target_duration_s) ?? spendPreview?.totalSeconds ?? dryRunReport?.duration_s ?? t(language, 'unknown')}s / ${firstText(dryRunReport?.aspect_ratio, decision?.aspect_ratio) || 'auto'}`} />
        <PlanTile icon={<DollarSign size={15} />} label={language === 'vi' ? 'Chi phí ước tính' : 'Cost estimate'} value={costLabel || t(language, 'pending')} />
      </div>

      <div className="mt-3 grid gap-3">
        <section className="rounded-card border border-hairline bg-surface-2 p-3">
          <div className="text-xs font-bold uppercase text-accent-cyan">{t(language, 'script')}</div>
          {scriptSummary.length === 0 ? (
            <p className="mt-2 text-xs leading-relaxed text-text-muted">{language === 'vi' ? 'Kịch bản sẽ xuất hiện khi preflight trả script thật.' : 'Script appears when preflight returns real script beats.'}</p>
          ) : (
            <ol className="mt-2 grid gap-2">
              {scriptSummary.map((item, index) => (
                <li key={`${index}-${item}`} className="rounded-card border border-hairline bg-surface-1 px-3 py-2 text-xs leading-relaxed text-text-muted">
                  <span className="font-bold text-text">{index + 1}. </span>{item}
                </li>
              ))}
            </ol>
          )}
        </section>

        <section className="rounded-card border border-hairline bg-surface-2 p-3">
          <div className="text-xs font-bold uppercase text-accent-cyan">{t(language, 'promptStrategy')}</div>
          <p className="mt-2 text-xs leading-relaxed text-text-muted">
            {promptStrategy
              ? `${promptStrategy}. ${referencesConfirmed ? (language === 'vi' ? 'Vai trò tham chiếu đã được khóa trong manifest.' : 'Reference roles are locked in the manifest.') : (language === 'vi' ? 'Cần khóa vai trò tham chiếu trước render.' : 'Reference roles need confirmation before render.')}`
              : (language === 'vi' ? 'Chưa có chiến lược prompt thật từ backend.' : 'No real backend prompt strategy yet.')}
          </p>
        </section>

        <VoiceAudioPlanPreview scenes={scenes} preflight={preflightRecord} language={language} />

        {referenceSummary && <ReferenceIntelligencePanel summary={referenceSummary} language={language} />}

        {warnings.length > 0 && (
          <section className="rounded-card border border-accent-orange/25 bg-accent-orange/10 p-3 text-accent-orange">
            <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase">
              <AlertTriangle size={14} />
              {language === 'vi' ? 'Rủi ro cần xem' : 'Risk warnings'}
            </div>
            <ul className="mt-2 grid gap-1 text-xs leading-relaxed">
              {warnings.map((warning) => <li key={warning}>{warning}</li>)}
            </ul>
          </section>
        )}
      </div>

      <div className="mt-4">
        <StoryboardPreview
          scenes={scenes}
          activeSceneId={activeSceneId ?? undefined}
          language={language}
          onSelectScene={onSelectScene}
          onCopyPrompt={onCopyPrompt}
        />
      </div>

      <details className="mt-4 rounded-card border border-hairline bg-surface-2 p-3">
        <summary className="flex cursor-pointer items-center justify-between gap-3 text-sm font-bold text-text">
          <span>{t(language, 'advanced')}</span>
          <ChevronDown size={15} />
        </summary>
        <div className="mt-3 grid gap-3">
          <AdvancedBlock title="Compiled prompts" value={JSON.stringify((dryRunReport?.shot_payloads ?? scenes.map((scene) => ({ id: scene.id, prompt: scene.prompt }))), null, 2)} />
          <AdvancedBlock title="Negative prompt" value={extractNegativePrompts(dryRunReport)} />
          <AdvancedBlock title="Seedance preflight" value={JSON.stringify(extractSeedancePreflight(dryRunReport, preflightRecord), null, 2)} />
          <AdvancedBlock title="Dry-run payload" value={dryRunReport ? JSON.stringify(dryRunReport, null, 2) : t(language, 'unknown')} />
        </div>
      </details>
    </section>
  );
}

function PlanTile({ icon, label, value }: { icon?: ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-card border border-hairline bg-surface-2 px-3 py-3">
      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase text-text-subtle">
        {icon}
        {label}
      </div>
      <p className="mt-1 line-clamp-3 text-sm font-semibold leading-relaxed text-text">{value}</p>
    </div>
  );
}

function AdvancedBlock({ title, value }: { title: string; value: string }) {
  return (
    <div>
      <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">{title}</div>
      <pre className="max-h-[240px] overflow-auto rounded-card border border-hairline bg-surface-1 p-3 text-[11px] leading-relaxed text-text-muted">
        {value}
      </pre>
    </div>
  );
}

function extractNegativePrompts(dryRunReport?: Record<string, unknown> | null): string {
  const payloads = Array.isArray(dryRunReport?.shot_payloads) ? dryRunReport?.shot_payloads as Array<Record<string, unknown>> : [];
  const values = payloads
    .map((shot) => asRecord(shot.payload)?.negative_prompt)
    .filter((value): value is string => typeof value === 'string' && value.trim().length > 0);
  return values.length > 0 ? values.join('\n\n') : 'No negative prompt returned yet.';
}

function extractSeedancePreflight(dryRunReport?: Record<string, unknown> | null, preflight?: Record<string, unknown> | null): unknown {
  const payloads = Array.isArray(dryRunReport?.shot_payloads) ? dryRunReport?.shot_payloads as Array<Record<string, unknown>> : [];
  const shotPreflight = payloads
    .map((shot) => asRecord(shot.payload)?.seedance_preflight)
    .filter(Boolean);
  return {
    dry_run_warnings: dryRunReport?.warnings ?? [],
    dry_run_hard_failures: dryRunReport?.hard_failures ?? [],
    prompt_contract_status: asRecord(preflight?.summary)?.prompt_contract_status,
    shot_preflight: shotPreflight,
  };
}
