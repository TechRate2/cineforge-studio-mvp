'use client';

import type { StudioLanguage } from './studio-i18n';

export interface StudioLanguageToggleProps {
  value: StudioLanguage;
  onChange: (value: StudioLanguage) => void;
}

export function StudioLanguageToggle({ value, onChange }: StudioLanguageToggleProps) {
  return (
    <div className="inline-flex rounded-card border border-hairline bg-surface-2 p-1">
      {(['vi', 'en'] as const).map((language) => (
        <button
          key={language}
          type="button"
          onClick={() => onChange(language)}
          className={`rounded-card px-3 py-1.5 text-xs font-bold uppercase transition ${
            value === language
              ? 'bg-accent-cyan text-surface-0'
              : 'text-text-subtle hover:bg-surface-3 hover:text-text'
          }`}
          aria-pressed={value === language}
        >
          {language === 'vi' ? 'VI' : 'EN'}
        </button>
      ))}
    </div>
  );
}
