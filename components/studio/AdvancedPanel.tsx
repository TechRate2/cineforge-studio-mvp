'use client';

/**
 * AdvancedPanel — Collapsible wrapper cho 3 panel "advanced":
 *   - Product URL + Image upload
 *   - Context Injection
 *   - Niche dropdown + Reference video URL
 *
 * Default ẨN — pattern copy TopView V2 + Krea AI: input gọn 1 prompt + 4 controls.
 * User click "Advanced ▼" để expand khi cần override.
 */

import { useState, type ReactNode } from 'react';
import { ChevronDown, ChevronUp, Sliders } from 'lucide-react';

interface Props {
  filledCount: number; // số option user đã tinh chỉnh (badge)
  children: ReactNode;
}

export function AdvancedPanel({ filledCount, children }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mb-3">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-bg-soft/40 hover:bg-bg-hover border border-border hover:border-brand-600/50 transition text-xs text-text-muted hover:text-text"
      >
        <Sliders className="w-3.5 h-3.5 text-brand-300" />
        <span className="font-medium">Advanced</span>
        {filledCount > 0 && (
          <span className="px-1.5 py-0 rounded-full bg-brand-700/30 text-brand-200 text-[10px] font-bold">
            {filledCount}
          </span>
        )}
        <span className="ml-auto text-text-subtle">
          {open ? 'Ẩn' : 'Niche / Context / Product URL / Video clone'}
        </span>
        {open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {open && (
        <div className="mt-2 space-y-3 px-1">
          {children}
        </div>
      )}
    </div>
  );
}
