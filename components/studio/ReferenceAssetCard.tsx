'use client';

import { BadgeCheck, FileAudio, FileVideo, Image as ImageIcon, Loader2, ShieldAlert, Trash2 } from 'lucide-react';
import type { ReferenceInsightSummary } from './ReferenceIntelligencePanel';
import type { StudioLanguage } from './studio-i18n';
import { statusLabel, statusTone, t } from './studio-i18n';

export type StudioReferenceKind = 'image' | 'video' | 'audio';

export interface StudioReferenceAsset {
  id: string;
  url: string;
  previewUrl?: string;
  name: string;
  kind: StudioReferenceKind;
  role: string;
  roleConfirmed?: boolean;
  roleSource?: string;
  roleConfidence?: number;
  roleReason?: string;
  uploading?: boolean;
}

export interface StudioReferenceRoleOption {
  role: string;
  label: string;
  hint?: string;
}

export interface ReferenceAssetCardProps {
  refAsset: StudioReferenceAsset;
  tag: string;
  previewUrl?: string;
  roleOptions: readonly StudioReferenceRoleOption[];
  intelligence?: ReferenceInsightSummary;
  language?: StudioLanguage;
  onRoleChange: (id: string, role: string) => void;
  onRemove: (id: string) => void;
}

function kindIcon(kind: StudioReferenceKind | string) {
  if (kind === 'image') return <ImageIcon size={15} />;
  if (kind === 'video') return <FileVideo size={15} />;
  return <FileAudio size={15} />;
}

function toneClass(status?: string) {
  const tone = statusTone(status);
  if (tone === 'ready') return 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan';
  if (tone === 'blocked') return 'border-red-400/30 bg-red-500/10 text-red-300';
  if (tone === 'review') return 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange';
  return 'border-hairline bg-surface-3 text-text-subtle';
}

export function ReferenceAssetCard({
  refAsset,
  tag,
  previewUrl,
  roleOptions,
  intelligence,
  language = 'vi',
  onRoleChange,
  onRemove,
}: ReferenceAssetCardProps) {
  const readiness = intelligence?.readiness || (refAsset.uploading ? 'pending' : refAsset.roleConfirmed && refAsset.role !== 'unknown' ? 'ready' : 'needs_review');
  const confidence = intelligence?.roleConfidence ?? refAsset.roleConfidence;
  const roleLocked = intelligence?.roleLocked ?? Boolean(refAsset.roleConfirmed && refAsset.role !== 'unknown');
  const warnings = intelligence?.warnings ?? [];
  const missingConfirmations = intelligence?.missingConfirmations ?? [];
  const blockers = intelligence?.blockers ?? [];
  const detectedSignals = intelligence ? Object.keys(intelligence.detectedSignals) : [];
  const unavailableSignals = intelligence?.unavailableSignals ?? [];

  return (
    <article className="rounded-card border border-hairline bg-surface-2 p-3">
      <div className="grid gap-3 sm:grid-cols-[76px_minmax(0,1fr)]">
        <div className="grid h-[76px] w-[76px] place-items-center overflow-hidden rounded-card border border-hairline bg-surface-3 text-text-subtle">
          {refAsset.kind === 'image' && previewUrl ? (
            <img src={previewUrl} alt={refAsset.name} className="h-full w-full object-cover" />
          ) : refAsset.uploading ? (
            <Loader2 size={18} className="animate-spin text-accent-cyan" />
          ) : (
            kindIcon(refAsset.kind)
          )}
        </div>

        <div className="min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="truncate text-sm font-bold text-text">{refAsset.name}</div>
              <div className="mt-1 flex flex-wrap gap-1.5">
                <span className="inline-flex items-center gap-1 rounded-full border border-hairline bg-surface-3 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
                  {kindIcon(refAsset.kind)}
                  {refAsset.kind}
                </span>
                <span className="rounded-full border border-hairline bg-surface-3 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
                  {tag}
                </span>
                <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase ${toneClass(readiness)}`}>
                  {statusLabel(language, readiness)}
                </span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => onRemove(refAsset.id)}
              className="grid h-8 w-8 shrink-0 place-items-center rounded-card border border-hairline bg-surface-3 text-text-subtle transition hover:border-red-400/40 hover:text-red-300"
              aria-label={`Remove ${refAsset.name}`}
            >
              <Trash2 size={14} />
            </button>
          </div>

          <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
            <label className="min-w-0">
              <span className="mb-1 block text-[10px] font-bold uppercase text-text-subtle">
                {t(language, 'referenceRole')}
              </span>
              <select
                value={refAsset.role}
                onChange={(event) => onRoleChange(refAsset.id, event.target.value)}
                disabled={refAsset.uploading}
                className="w-full rounded-card border border-hairline bg-surface-1 px-3 py-2 text-xs font-semibold text-text outline-none focus:border-accent-cyan/60"
              >
                {roleOptions.map((option) => (
                  <option key={option.role} value={option.role}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <span className={`inline-flex items-center justify-center gap-1 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${roleLocked ? toneClass('ready') : toneClass('needs_review')}`}>
              {roleLocked ? <BadgeCheck size={12} /> : <ShieldAlert size={12} />}
              {roleLocked ? t(language, 'lockedRole') : t(language, 'needsConfirm')}
            </span>
          </div>

          <div className="mt-2 flex flex-wrap gap-1.5">
            {typeof confidence === 'number' && (
              <span className="rounded-full border border-hairline bg-surface-3 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
                {Math.round(confidence * 100)}% confidence
              </span>
            )}
            {intelligence?.bestUse && (
              <span className="rounded-full border border-hairline bg-surface-3 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
                {t(language, 'bestUse')}: {intelligence.bestUse.slice(0, 80)}
              </span>
            )}
            {intelligence?.evidenceStatus && (
              <span className="rounded-full border border-hairline bg-surface-3 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
                evidence {intelligence.evidenceStatus}
              </span>
            )}
            {detectedSignals.length > 0 && (
              <span className="rounded-full border border-accent-cyan/25 bg-accent-cyan/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-accent-cyan">
                {detectedSignals.length} detected
              </span>
            )}
            {unavailableSignals.length > 0 && (
              <span className="rounded-full border border-accent-orange/25 bg-accent-orange/10 px-2 py-0.5 text-[10px] font-semibold uppercase text-accent-orange">
                {unavailableSignals.length} unavailable
              </span>
            )}
          </div>

          {[...missingConfirmations, ...warnings, ...blockers].length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {[...missingConfirmations, ...warnings, ...blockers].slice(0, 6).map((item) => (
                <span key={`${refAsset.id}-${item}`} className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${item.includes('blocked') || blockers.includes(item) ? toneClass('blocked') : toneClass('needs_review')}`}>
                  {item}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
