'use client';

import { AlertTriangle, BadgeCheck, FileAudio, FileVideo, Image as ImageIcon, ShieldAlert } from 'lucide-react';
import type { StudioLanguage } from './studio-i18n';
import { statusLabel, statusTone, t } from './studio-i18n';

export interface ReferenceInsightSummary {
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
  blockers: string[];
}

export interface ReferenceIntelligenceSummary {
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

export interface ReferenceIntelligencePanelProps {
  summary: ReferenceIntelligenceSummary;
  language?: StudioLanguage;
  compact?: boolean;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || '').trim()).filter(Boolean);
}

function numberValue(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function toneClass(status?: string) {
  const tone = statusTone(status);
  if (tone === 'ready') return 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan';
  if (tone === 'blocked') return 'border-red-400/30 bg-red-500/10 text-red-300';
  if (tone === 'review') return 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange';
  return 'border-hairline bg-surface-2 text-text-subtle';
}

function kindIcon(kind: string) {
  if (kind === 'image') return <ImageIcon size={13} />;
  if (kind === 'video') return <FileVideo size={13} />;
  if (kind === 'audio') return <FileAudio size={13} />;
  return <ShieldAlert size={13} />;
}

export function summarizeReferenceIntelligence(report?: Record<string, unknown> | null): ReferenceIntelligenceSummary | null {
  const reference = asRecord(report?.reference_intelligence);
  if (!reference) return null;
  const blockers = stringList(reference.blockers);
  const insights = Array.isArray(reference.insights) ? reference.insights : [];
  return {
    status: String(reference.status || 'needs_review'),
    assetCount: numberValue(reference.asset_count) ?? insights.length,
    imageCount: numberValue(reference.image_count) ?? 0,
    videoCount: numberValue(reference.video_count) ?? 0,
    audioCount: numberValue(reference.audio_count) ?? 0,
    missingRequiredRoles: stringList(reference.missing_required_roles),
    warnings: stringList(reference.warnings),
    blockers,
    insights: insights.map((item) => {
      const insight = asRecord(item) ?? {};
      const assetId = String(insight.asset_id || '');
      return {
        assetId,
        kind: String(insight.kind || 'unknown'),
        tag: typeof insight.tag === 'string' ? insight.tag : undefined,
        role: String(insight.role || 'unknown'),
        readiness: String(insight.readiness || 'needs_review'),
        roleConfidence: numberValue(insight.role_confidence),
        roleLocked: Boolean(insight.role_locked),
        bestUse: typeof insight.best_use === 'string' ? insight.best_use : undefined,
        warnings: stringList(insight.warnings),
        missingConfirmations: stringList(insight.missing_confirmations),
        blockers: blockers.filter((blocker) => blocker.includes(assetId)),
      };
    }),
  };
}

export function ReferenceIntelligencePanel({ summary, language = 'vi', compact = false }: ReferenceIntelligencePanelProps) {
  return (
    <section className="rounded-card border border-hairline bg-surface-2 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-bold uppercase text-accent-cyan">{t(language, 'smartRefs')}</div>
          <h3 className="mt-1 text-sm font-extrabold text-text">
            {language === 'vi' ? 'Tình trạng tham chiếu' : 'Reference readiness'}
          </h3>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase ${toneClass(summary.status)}`}>
          {statusTone(summary.status) === 'ready' ? <BadgeCheck size={12} /> : <AlertTriangle size={12} />}
          {statusLabel(language, summary.status)}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-4 gap-2">
        <Metric label={language === 'vi' ? 'Tệp' : 'Assets'} value={summary.assetCount} />
        <Metric label="Image" value={summary.imageCount} />
        <Metric label="Video" value={summary.videoCount} />
        <Metric label="Audio" value={summary.audioCount} />
      </div>

      {(summary.missingRequiredRoles.length > 0 || summary.blockers.length > 0 || summary.warnings.length > 0) && (
        <div className="mt-3 grid gap-2">
          {summary.missingRequiredRoles.length > 0 && (
            <Notice tone="review" title={language === 'vi' ? 'Thiếu vai trò bắt buộc' : 'Missing required roles'} items={summary.missingRequiredRoles} />
          )}
          {summary.blockers.length > 0 && (
            <Notice tone="blocked" title={t(language, 'blockers')} items={summary.blockers} />
          )}
          {summary.warnings.length > 0 && !compact && (
            <Notice tone="review" title={t(language, 'warnings')} items={summary.warnings.slice(0, 5)} />
          )}
        </div>
      )}

      {!compact && summary.insights.length > 0 && (
        <div className="mt-3 grid gap-2">
          {summary.insights.map((insight) => (
            <article key={`${insight.assetId}-${insight.tag || insight.role}`} className="rounded-card border border-hairline bg-surface-1 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${toneClass(insight.readiness)}`}>
                  {kindIcon(insight.kind)}
                  {statusLabel(language, insight.readiness)}
                </span>
                <span className="text-xs font-bold text-text">{insight.tag || insight.assetId || insight.kind}</span>
                <span className="text-xs text-text-muted">{insight.role.replace(/_/g, ' ')}</span>
                {typeof insight.roleConfidence === 'number' && (
                  <span className="text-[10px] font-semibold uppercase text-text-subtle">
                    {Math.round(insight.roleConfidence * 100)}%
                  </span>
                )}
              </div>
              {insight.bestUse && (
                <p className="mt-1 text-xs leading-relaxed text-text-muted">{insight.bestUse}</p>
              )}
              {[...insight.missingConfirmations, ...insight.warnings, ...insight.blockers].length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {[...insight.missingConfirmations, ...insight.warnings, ...insight.blockers].slice(0, 5).map((item) => (
                    <span key={`${insight.assetId}-${item}`} className="rounded-full border border-accent-orange/25 bg-accent-orange/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-accent-orange">
                      {item}
                    </span>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-card border border-hairline bg-surface-1 px-2 py-2 text-center">
      <div className="text-sm font-extrabold text-text">{value}</div>
      <div className="mt-0.5 text-[10px] font-semibold uppercase text-text-subtle">{label}</div>
    </div>
  );
}

function Notice({ tone, title, items }: { tone: 'review' | 'blocked'; title: string; items: string[] }) {
  const cls = tone === 'blocked'
    ? 'border-red-400/25 bg-red-500/10 text-red-200'
    : 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange';
  return (
    <div className={`rounded-card border px-3 py-2 ${cls}`}>
      <div className="text-[10px] font-bold uppercase">{title}</div>
      <ul className="mt-1 grid gap-1 text-xs leading-relaxed">
        {items.map((item) => <li key={`${title}-${item}`}>{item}</li>)}
      </ul>
    </div>
  );
}
