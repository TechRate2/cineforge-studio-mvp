'use client';
import { Sparkles, ArrowRight, Loader2 } from 'lucide-react';
/* eslint-disable @typescript-eslint/no-unused-vars */

interface PromptCardProps {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  isLoading?: boolean;
  placeholder?: string;
  ctaLabel?: string;
  rows?: number;
  /** Optional chips below textarea (presets, niche hints, suggestions) */
  chips?: { label: string; value: string }[];
}

export function PromptCard({
  value, onChange, onSubmit, disabled, isLoading,
  placeholder = 'Mô tả ý tưởng video của bạn... vd: "TikTok 15s nữ Gen Z thử son lì matte, golden hour, bàn make-up"',
  ctaLabel = 'Generate Plan',
  rows = 4,
  chips,
}: PromptCardProps) {
  return (
    <div className="glass-card p-5 md:p-6">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 shrink-0 rounded-lg bg-cta-gradient grid place-items-center">
          <Sparkles size={17} className="text-white" />
        </div>
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          rows={rows}
          disabled={disabled}
          className="field-bare resize-none flex-1 min-h-[88px] text-[15px] leading-relaxed"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && !disabled) onSubmit();
          }}
        />
      </div>

      {/* Chips row */}
      {chips && chips.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-4 pl-12">
          {chips.map((chip) => (
            <button
              key={chip.value}
              onClick={() => onChange(value ? `${value}\n${chip.value}` : chip.value)}
              className="chip hover:border-accent-magenta/40 hover:text-text transition"
            >
              {chip.label}
            </button>
          ))}
        </div>
      )}

      {/* Footer — keyboard hint + CTA */}
      <div className="flex items-center justify-between gap-3 mt-5 pl-12">
        <span className="text-[11px] text-text-subtle">
          <kbd className="px-1.5 py-0.5 text-[10px] rounded border border-hairline bg-surface-3 mr-1">⌘</kbd>
          <kbd className="px-1.5 py-0.5 text-[10px] rounded border border-hairline bg-surface-3">↵</kbd>
          {' '}to submit
        </span>
        <button
          onClick={onSubmit}
          disabled={disabled || isLoading || !value.trim()}
          className="btn-cta"
        >
          {isLoading ? (
            <>
              <Loader2 size={15} className="animate-spin" /> Đang dựng plan...
            </>
          ) : (
            <>
              {ctaLabel} <ArrowRight size={15} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
