'use client';
import { StudioMain } from './StudioMain';

/**
 * StudioShell — Marketing Studio (AI Agent) main content.
 * Global navigation (rail) handled by app/(workspace)/layout.tsx.
 */
export function StudioShell() {
  return (
    <div className="flex-1 min-w-0 flex bg-bg text-text overflow-hidden">
      <StudioMain />
    </div>
  );
}
