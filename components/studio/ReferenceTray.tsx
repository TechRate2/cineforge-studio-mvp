'use client';

import { useRef } from 'react';
import { BadgeCheck, FileAudio, FileVideo, Image as ImageIcon, Loader2, Plus, ShieldAlert, Trash2 } from 'lucide-react';

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

export interface ReferenceTrayProps {
  refs: readonly StudioReferenceAsset[];
  readyRefs?: readonly StudioReferenceAsset[];
  rolesConfirmed: boolean;
  approvalLockRevision?: number;
  roleOptionsForKind: (kind: StudioReferenceKind) => readonly StudioReferenceRoleOption[];
  getReferenceTag?: (ref: StudioReferenceAsset) => string;
  getPreviewUrl?: (ref: StudioReferenceAsset) => string;
  onAddReference?: () => void;
  onFilesSelected?: (files: FileList | File[]) => void | Promise<void>;
  onRemoveReference: (id: string) => void;
  onConfirmRoles: () => void;
  onRoleChange: (id: string, role: string) => void;
}

function kindIcon(kind: StudioReferenceKind) {
  if (kind === 'image') return <ImageIcon size={15} />;
  if (kind === 'video') return <FileVideo size={15} />;
  return <FileAudio size={15} />;
}

function fallbackTag(ref: StudioReferenceAsset) {
  return `${ref.kind} reference`;
}

export function ReferenceTray({
  refs,
  readyRefs,
  rolesConfirmed,
  approvalLockRevision = 0,
  roleOptionsForKind,
  getReferenceTag = fallbackTag,
  getPreviewUrl = (ref) => ref.previewUrl || ref.url,
  onAddReference,
  onFilesSelected,
  onRemoveReference,
  onConfirmRoles,
  onRoleChange,
}: ReferenceTrayProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const resolvedReadyRefs = readyRefs ?? refs.filter((ref) => !ref.uploading && ref.url);
  const pendingRoles = resolvedReadyRefs.filter((ref) => !ref.roleConfirmed || ref.role === 'unknown').length;

  const handleAddReference = () => {
    if (onAddReference) {
      onAddReference();
      return;
    }
    inputRef.current?.click();
  };

  return (
    <section className="rounded-sheet border border-hairline bg-surface-1 p-4 shadow-card-soft">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept="image/*,video/*,audio/*"
        className="hidden"
        onChange={(event) => {
          const files = event.target.files;
          if (files && onFilesSelected) void onFilesSelected(files);
          event.currentTarget.value = '';
        }}
      />

      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-bold uppercase tracking-normal text-accent-cyan">
            References
          </div>
          <h2 className="mt-1 text-lg font-extrabold text-text">Assets and roles</h2>
          <p className="mt-1 max-w-xl text-xs leading-relaxed text-text-muted">
            Assign what each upload should control before approval so the render plan can lock the same roles.
          </p>
        </div>
        <button type="button" onClick={handleAddReference} className="btn-outline px-3 py-2 text-xs">
          <Plus size={14} />
          Add media
        </button>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${
          rolesConfirmed
            ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
            : 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange'
        }`}>
          {rolesConfirmed ? <BadgeCheck size={12} /> : <ShieldAlert size={12} />}
          {rolesConfirmed ? 'Roles confirmed' : `${pendingRoles} role${pendingRoles === 1 ? '' : 's'} pending`}
        </span>
        <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-[10px] font-semibold uppercase text-text-subtle">
          ApprovalLock v{approvalLockRevision}
        </span>
      </div>

      {refs.length === 0 ? (
        <button
          type="button"
          onClick={handleAddReference}
          className="flex min-h-[116px] w-full flex-col items-center justify-center rounded-card border border-dashed border-hairline bg-surface-2 px-4 py-5 text-center transition hover:border-accent-cyan/45 hover:bg-surface-3"
        >
          <Plus size={18} className="mb-2 text-accent-cyan" />
          <span className="text-sm font-bold text-text">Upload reference media</span>
          <span className="mt-1 max-w-md text-xs leading-relaxed text-text-muted">
            Images anchor characters or products, video controls motion, audio controls voice or sound.
          </span>
        </button>
      ) : (
        <div className="grid gap-3">
          {refs.map((ref) => {
            const roleOptions = roleOptionsForKind(ref.kind);
            const previewUrl = getPreviewUrl(ref);
            return (
              <article key={ref.id} className="rounded-card border border-hairline bg-surface-2 p-3">
                <div className="grid gap-3 sm:grid-cols-[72px_minmax(0,1fr)]">
                  <div className="grid h-[72px] w-[72px] place-items-center overflow-hidden rounded-card border border-hairline bg-surface-3 text-text-subtle">
                    {ref.kind === 'image' && previewUrl ? (
                      <img src={previewUrl} alt={ref.name} className="h-full w-full object-cover" />
                    ) : ref.uploading ? (
                      <Loader2 size={18} className="animate-spin text-accent-cyan" />
                    ) : (
                      kindIcon(ref.kind)
                    )}
                  </div>

                  <div className="min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-bold text-text">{ref.name}</div>
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          <span className="inline-flex items-center gap-1 rounded-full border border-hairline bg-surface-3 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
                            {kindIcon(ref.kind)}
                            {ref.kind}
                          </span>
                          <span className="rounded-full border border-hairline bg-surface-3 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
                            {getReferenceTag(ref)}
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => onRemoveReference(ref.id)}
                        className="grid h-8 w-8 shrink-0 place-items-center rounded-card border border-hairline bg-surface-3 text-text-subtle transition hover:border-red-400/40 hover:text-red-300"
                        aria-label={`Remove ${ref.name}`}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>

                    <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                      <label className="min-w-0">
                        <span className="mb-1 block text-[10px] font-bold uppercase text-text-subtle">
                          ReferenceRole
                        </span>
                        <select
                          value={ref.role}
                          onChange={(event) => onRoleChange(ref.id, event.target.value)}
                          disabled={ref.uploading}
                          className="w-full rounded-card border border-hairline bg-surface-1 px-3 py-2 text-xs font-semibold text-text outline-none focus:border-accent-cyan/60"
                        >
                          {roleOptions.map((option) => (
                            <option key={option.role} value={option.role}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <span className={`inline-flex items-center justify-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${
                        ref.roleConfirmed && ref.role !== 'unknown'
                          ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
                          : 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange'
                      }`}>
                        {ref.roleConfirmed && ref.role !== 'unknown' ? 'Locked role' : 'Needs confirm'}
                      </span>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {refs.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-card border border-hairline bg-surface-2 px-3 py-2">
          <p className="max-w-xl text-xs leading-relaxed text-text-muted">
            Changing any role invalidates the current ApprovalLock. Review the pipeline again before paid render.
          </p>
          <button type="button" onClick={onConfirmRoles} className="btn-outline px-3 py-2 text-xs">
            <BadgeCheck size={14} />
            Confirm roles
          </button>
        </div>
      )}
    </section>
  );
}
