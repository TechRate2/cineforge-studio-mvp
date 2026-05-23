'use client';
import { MODEL_CONFIGS } from '@/lib/studio/model-config';
import type { VideoModel } from '@/lib/types/backend';
import { Zap, Award, Sparkles } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface ShowcaseModel {
  id: VideoModel;
  badge: string;
  badgeIcon: LucideIcon;
  tagline: string;
  highlight: 'magenta' | 'orange' | 'cyan';
}

// Pulled from MODEL_CONFIGS — not hardcoded data, only display ordering/tagline UI hint.
const FEATURED: ShowcaseModel[] = [
  { id: 'seedance_2_0', badge: 'Cinematic', badgeIcon: Award, tagline: 'Multi-shot timeline + native audio', highlight: 'magenta' },
  { id: 'seedance_2_0_fast', badge: 'Fast draft', badgeIcon: Zap, tagline: 'Iterate ý tưởng 5× rẻ hơn', highlight: 'orange' },
  { id: 'vidu_q3_mix', badge: 'Premium ref', badgeIcon: Sparkles, tagline: '@image_N tags · 1080p detail', highlight: 'cyan' },
];

export function ModelShowcase({ onPick }: { onPick: (m: VideoModel) => void }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {FEATURED.map((f) => {
        const cfg = MODEL_CONFIGS[f.id];
        const Icon = f.badgeIcon;
        const ringColor = {
          magenta: 'from-accent-magenta/25',
          orange: 'from-accent-orange/25',
          cyan: 'from-accent-cyan/25',
        }[f.highlight];
        return (
          <button
            key={f.id}
            onClick={() => onPick(f.id)}
            className={`relative group text-left rounded-card overflow-hidden border border-hairline
                        bg-gradient-to-br ${ringColor} via-surface-2 to-surface-2
                        hover:border-hairline-strong transition p-4`}
          >
            <div className="flex items-center justify-between mb-3">
              <span className="chip text-[10px]">
                <Icon size={10} /> {f.badge}
              </span>
              <span className="text-[10px] text-text-subtle font-mono">${cfg.cost_per_second_usd}/s</span>
            </div>
            <h4 className="font-bold text-base leading-tight">{cfg.name_vn}</h4>
            <p className="text-xs text-text-muted mt-1.5 leading-relaxed">{f.tagline}</p>
            <div className="flex flex-wrap gap-1 mt-3">
              {cfg.best_for.slice(0, 2).map((b) => (
                <span key={b} className="text-[10px] text-text-subtle px-1.5 py-0.5 rounded bg-surface-3 border border-hairline">
                  {b}
                </span>
              ))}
            </div>
          </button>
        );
      })}
    </div>
  );
}
