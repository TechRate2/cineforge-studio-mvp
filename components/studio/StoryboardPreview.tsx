'use client';

import { Clapperboard, Copy } from 'lucide-react';
import type { StudioLanguage } from './studio-i18n';
import { t } from './studio-i18n';

export interface StoryboardPreviewScene {
  id: string;
  label?: string;
  durationS?: number;
  prompt?: string;
  visual?: string;
  camera?: string;
  audio?: string;
  modelKey?: string;
  renderMode?: string;
  refs?: readonly string[];
  status?: string;
}

export interface StoryboardPreviewProps {
  scenes: readonly StoryboardPreviewScene[];
  activeSceneId?: string;
  language?: StudioLanguage;
  onSelectScene?: (id: string) => void;
  onCopyPrompt?: (prompt: string) => void;
}

export function StoryboardPreview({
  scenes,
  activeSceneId,
  language = 'vi',
  onSelectScene,
  onCopyPrompt,
}: StoryboardPreviewProps) {
  return (
    <section className="rounded-sheet border border-hairline bg-surface-1 p-4 shadow-card-soft">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase text-accent-cyan">
            <Clapperboard size={14} />
            {t(language, 'storyboard')}
          </div>
          <h2 className="mt-1 text-lg font-extrabold text-text">
            {language === 'vi' ? 'Các nhịp hình trước khi render' : 'Visual beats before render'}
          </h2>
        </div>
        <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-[10px] font-semibold uppercase text-text-subtle">
          {scenes.length} shots
        </span>
      </div>

      {scenes.length === 0 ? (
        <div className="rounded-card border border-dashed border-hairline bg-surface-2 px-4 py-5 text-sm text-text-muted">
          {language === 'vi' ? 'Storyboard sẽ xuất hiện sau khi Agent phân tích brief.' : 'Storyboard appears after the Agent analyzes the brief.'}
        </div>
      ) : (
        <div className="grid gap-3">
          {scenes.map((scene, index) => {
            const active = activeSceneId === scene.id;
            return (
              <article
                key={scene.id}
                className={`rounded-card border p-3 transition ${
                  active ? 'border-accent-cyan/45 bg-accent-cyan/10' : 'border-hairline bg-surface-2 hover:bg-surface-3'
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelectScene?.(scene.id)}
                  className="w-full text-left"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-extrabold text-text">{scene.label || `Shot ${index + 1}`}</h3>
                    <span className="rounded-full border border-hairline bg-surface-1 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
                      {scene.durationS ? `${scene.durationS}s` : t(language, 'pending')}
                    </span>
                  </div>
                  <p className="mt-2 text-xs leading-relaxed text-text-muted">{scene.visual || scene.prompt || t(language, 'unknown')}</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {scene.modelKey && <Pill>{scene.modelKey}</Pill>}
                    {scene.renderMode && <Pill>{scene.renderMode}</Pill>}
                    {(scene.refs ?? []).slice(0, 4).map((ref) => <Pill key={`${scene.id}-${ref}`}>{ref}</Pill>)}
                  </div>
                </button>
                {scene.prompt && onCopyPrompt && (
                  <button
                    type="button"
                    onClick={() => onCopyPrompt(scene.prompt || '')}
                    className="mt-3 inline-flex items-center gap-1.5 rounded-card border border-hairline bg-surface-1 px-2.5 py-1 text-[10px] font-bold uppercase text-text-subtle transition hover:border-accent-cyan/40 hover:text-accent-cyan"
                  >
                    <Copy size={12} />
                    {language === 'vi' ? 'Sao chép prompt' : 'Copy prompt'}
                  </button>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function Pill({ children }: { children: string }) {
  return (
    <span className="rounded-full border border-hairline bg-surface-1 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
      {children}
    </span>
  );
}
