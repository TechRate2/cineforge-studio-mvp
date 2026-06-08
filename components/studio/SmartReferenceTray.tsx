'use client';

import { BadgeCheck, Plus, ShieldAlert } from 'lucide-react';
import { ReferenceAssetCard, type StudioReferenceAsset, type StudioReferenceKind, type StudioReferenceRoleOption } from './ReferenceAssetCard';
import { ReferenceIntelligencePanel, summarizeReferenceIntelligence, type ReferenceInsightSummary } from './ReferenceIntelligencePanel';
import type { StudioLanguage } from './studio-i18n';
import { t } from './studio-i18n';
import { useRef } from 'react';

export interface SmartReferenceTrayProps {
  refs: readonly StudioReferenceAsset[];
  readyRefs?: readonly StudioReferenceAsset[];
  rolesConfirmed: boolean;
  approvalLockRevision?: number;
  dryRunReport?: Record<string, unknown> | null;
  language?: StudioLanguage;
  roleOptionsForKind: (kind: StudioReferenceKind) => readonly StudioReferenceRoleOption[];
  getReferenceTag?: (ref: StudioReferenceAsset) => string;
  getPreviewUrl?: (ref: StudioReferenceAsset) => string;
  onAddReference?: () => void;
  onFilesSelected?: (files: FileList | File[]) => void | Promise<void>;
  onRemoveReference: (id: string) => void;
  onConfirmRoles: () => void;
  onRoleChange: (id: string, role: string) => void;
}

function fallbackTag(ref: StudioReferenceAsset) {
  return `${ref.kind} reference`;
}

function insightKey(value?: string) {
  return String(value || '').trim().toLowerCase();
}

export function SmartReferenceTray({
  refs,
  readyRefs,
  rolesConfirmed,
  approvalLockRevision = 0,
  dryRunReport,
  language = 'vi',
  roleOptionsForKind,
  getReferenceTag = fallbackTag,
  getPreviewUrl = (ref) => ref.previewUrl || ref.url,
  onAddReference,
  onFilesSelected,
  onRemoveReference,
  onConfirmRoles,
  onRoleChange,
}: SmartReferenceTrayProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const resolvedReadyRefs = readyRefs ?? refs.filter((ref) => !ref.uploading && ref.url);
  const pendingRoles = resolvedReadyRefs.filter((ref) => !ref.roleConfirmed || ref.role === 'unknown').length;
  const referenceSummary = summarizeReferenceIntelligence(dryRunReport);
  const insightsByTag = new Map<string, ReferenceInsightSummary>();
  const insightsByAsset = new Map<string, ReferenceInsightSummary>();
  for (const insight of referenceSummary?.insights ?? []) {
    if (insight.tag) insightsByTag.set(insightKey(insight.tag), insight);
    if (insight.assetId) insightsByAsset.set(insightKey(insight.assetId), insight);
  }

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
            {t(language, 'smartRefs')}
          </div>
          <h2 className="mt-1 text-lg font-extrabold text-text">{t(language, 'uploadRefs')}</h2>
          <p className="mt-1 max-w-xl text-xs leading-relaxed text-text-muted">
            {language === 'vi'
              ? 'Agent tự gợi ý vai trò, nhưng bạn cần khóa vai trò trước khi phê duyệt render trả phí.'
              : 'The Agent can suggest roles, but you lock them before paid render approval.'}
          </p>
        </div>
        <button type="button" onClick={handleAddReference} className="btn-outline px-3 py-2 text-xs">
          <Plus size={14} />
          {language === 'vi' ? 'Thêm media' : 'Add media'}
        </button>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${
          rolesConfirmed
            ? 'border-accent-cyan/25 bg-accent-cyan/10 text-accent-cyan'
            : 'border-accent-orange/25 bg-accent-orange/10 text-accent-orange'
        }`}>
          {rolesConfirmed ? <BadgeCheck size={12} /> : <ShieldAlert size={12} />}
          {rolesConfirmed
            ? (language === 'vi' ? 'Vai trò đã xác nhận' : 'Roles confirmed')
            : `${pendingRoles} ${language === 'vi' ? 'vai trò cần xác nhận' : 'roles pending'}`}
        </span>
        <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-[10px] font-semibold uppercase text-text-subtle">
          ApprovalLock v{approvalLockRevision}
        </span>
        {!referenceSummary && (
          <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-[10px] font-semibold uppercase text-text-subtle">
            {language === 'vi' ? 'Reference Intelligence sau dry-run' : 'Reference Intelligence after dry-run'}
          </span>
        )}
      </div>

      {referenceSummary && <div className="mb-3"><ReferenceIntelligencePanel summary={referenceSummary} language={language} compact /></div>}

      {refs.length === 0 ? (
        <button
          type="button"
          onClick={handleAddReference}
          className="flex min-h-[124px] w-full flex-col items-center justify-center rounded-card border border-dashed border-hairline bg-surface-2 px-4 py-5 text-center transition hover:border-accent-cyan/45 hover:bg-surface-3"
        >
          <Plus size={18} className="mb-2 text-accent-cyan" />
          <span className="text-sm font-bold text-text">{t(language, 'uploadRefs')}</span>
          <span className="mt-1 max-w-md text-xs leading-relaxed text-text-muted">
            {language === 'vi'
              ? 'Ảnh khóa sản phẩm/nhân vật, video hướng dẫn chuyển động, audio hướng dẫn giọng hoặc nhạc.'
              : 'Images anchor products/characters, video guides motion, audio guides voice or music.'}
          </span>
        </button>
      ) : (
        <div className="grid gap-3">
          {refs.map((ref) => {
            const tag = getReferenceTag(ref);
            const intelligence = insightsByTag.get(insightKey(tag)) || insightsByAsset.get(insightKey(ref.id));
            return (
              <ReferenceAssetCard
                key={ref.id}
                refAsset={ref}
                tag={tag}
                previewUrl={getPreviewUrl(ref)}
                roleOptions={roleOptionsForKind(ref.kind)}
                intelligence={intelligence}
                language={language}
                onRoleChange={onRoleChange}
                onRemove={onRemoveReference}
              />
            );
          })}
        </div>
      )}

      {refs.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-card border border-hairline bg-surface-2 px-3 py-2">
          <p className="max-w-xl text-xs leading-relaxed text-text-muted">
            {language === 'vi'
              ? 'Đổi vai trò sẽ làm mất hiệu lực ApprovalLock hiện tại. Hãy chạy lại kiểm tra trước render sau khi chỉnh.'
              : 'Changing roles invalidates the current ApprovalLock. Review the pipeline again after edits.'}
          </p>
          <button type="button" onClick={onConfirmRoles} className="btn-outline px-3 py-2 text-xs">
            <BadgeCheck size={14} />
            {language === 'vi' ? 'Xác nhận vai trò' : 'Confirm roles'}
          </button>
        </div>
      )}
    </section>
  );
}
