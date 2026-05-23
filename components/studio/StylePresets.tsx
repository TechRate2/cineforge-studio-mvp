'use client';
import { STYLE_PRESETS, type StylePreset } from '@/lib/studio/style-presets';

interface Props {
  onPick: (preset: StylePreset) => void;
  activeId?: string;
}

const ACCENT_CLASSES: Record<StylePreset['accent'], string> = {
  magenta: 'from-accent-magenta/20 border-accent-magenta/40 text-accent-magenta',
  orange: 'from-accent-orange/20 border-accent-orange/40 text-accent-orange',
  cyan: 'from-accent-cyan/20 border-accent-cyan/40 text-accent-cyan',
  yellow: 'from-accent-yellow/20 border-accent-yellow/40 text-accent-yellow',
  green: 'from-accent-green/20 border-accent-green/40 text-accent-green',
};

export function StylePresets({ onPick, activeId }: Props) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
      {STYLE_PRESETS.map((preset) => {
        const Icon = preset.icon;
        const isActive = preset.id === activeId;
        return (
          <button
            key={preset.id}
            onClick={() => onPick(preset)}
            className={`group relative text-left p-3 rounded-card border transition
                        bg-gradient-to-br to-transparent
                        ${ACCENT_CLASSES[preset.accent]}
                        ${isActive
                          ? 'ring-2 ring-accent-magenta/50 bg-surface-3'
                          : 'hover:bg-surface-3 hover:border-hairline-strong'}`}
          >
            <div className="flex items-center gap-2 mb-1.5">
              <Icon size={14} strokeWidth={2.2} />
              <span className="text-xs font-semibold text-text">{preset.label_vn}</span>
            </div>
            <p className="text-[10.5px] text-text-muted leading-snug line-clamp-2">
              {preset.description_vn}
            </p>
            <div className="mt-2 flex items-center gap-1 text-[9px] text-text-subtle uppercase tracking-wider">
              <span>{preset.settings.model.replace(/_/g, ' ')}</span>
              <span>·</span>
              <span>{preset.settings.duration_s}s</span>
              <span>·</span>
              <span>{preset.settings.aspect_ratio}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}
