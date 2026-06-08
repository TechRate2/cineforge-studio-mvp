'use client';

import { Mic2, Music2 } from 'lucide-react';
import type { StoryboardPreviewScene } from './StoryboardPreview';
import type { StudioLanguage } from './studio-i18n';
import { t } from './studio-i18n';

export interface VoiceAudioPlanPreviewProps {
  scenes: readonly StoryboardPreviewScene[];
  preflight?: Record<string, unknown> | null;
  language?: StudioLanguage;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function stringValue(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function collectAudioFromStoryboard(preflight?: Record<string, unknown> | null): string[] {
  const storyboard = Array.isArray(preflight?.storyboard) ? preflight?.storyboard : [];
  return storyboard
    .map((item) => stringValue(asRecord(item)?.audio))
    .filter(Boolean)
    .slice(0, 4);
}

export function VoiceAudioPlanPreview({ scenes, preflight, language = 'vi' }: VoiceAudioPlanPreviewProps) {
  const creativePlan = asRecord(preflight?.creative_plan);
  const storyboardAudio = collectAudioFromStoryboard(preflight);
  const sceneAudio = scenes.map((scene) => scene.audio || '').filter(Boolean).slice(0, 4);
  const planItems = [
    stringValue(creativePlan?.tone),
    ...storyboardAudio,
    ...sceneAudio,
  ].filter(Boolean);

  return (
    <section className="rounded-card border border-hairline bg-surface-2 p-3">
      <div className="flex items-center gap-2">
        <div className="grid h-8 w-8 place-items-center rounded-card border border-hairline bg-surface-1 text-accent-cyan">
          <Mic2 size={15} />
        </div>
        <div>
          <div className="text-xs font-bold uppercase text-accent-cyan">{t(language, 'voice')} / {t(language, 'music')}</div>
          <h3 className="text-sm font-extrabold text-text">
            {language === 'vi' ? 'Kế hoạch giọng và âm thanh' : 'Voice and audio plan'}
          </h3>
        </div>
      </div>

      {planItems.length === 0 ? (
        <p className="mt-3 text-xs leading-relaxed text-text-muted">
          {language === 'vi'
            ? 'Chưa có kế hoạch âm thanh riêng từ backend. Timeline sẽ giữ trạng thái chờ cho tới khi Agent trả dữ liệu thật.'
            : 'No separate backend audio plan yet. The timeline remains pending until real data is returned.'}
        </p>
      ) : (
        <div className="mt-3 grid gap-2">
          {planItems.map((item, index) => (
            <div key={`${index}-${item}`} className="flex items-start gap-2 rounded-card border border-hairline bg-surface-1 px-3 py-2 text-xs text-text-muted">
              <Music2 size={13} className="mt-0.5 shrink-0 text-accent-cyan" />
              <span>{item}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
