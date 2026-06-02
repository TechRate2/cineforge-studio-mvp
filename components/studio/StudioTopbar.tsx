'use client';

import Link from 'next/link';
import type { LucideIcon } from 'lucide-react';
import { Clock, FolderKanban, Sparkles, UserRound } from 'lucide-react';

export function StudioTopbar() {
  return (
    <header className="h-14 shrink-0 border-b border-hairline bg-surface-1/85 px-5 backdrop-blur-xl md:px-7">
      <div className="flex h-full items-center justify-between gap-4">
        <Link href="/studio" className="flex min-w-0 items-center gap-3">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-card bg-cta-gradient text-white shadow-cta-glow">
            <Sparkles size={16} strokeWidth={2.4} />
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-extrabold text-text">
              CineJelly Autonomous
            </span>
            <span className="hidden truncate text-[10px] font-medium text-text-subtle sm:block">
              Agent-first video studio
            </span>
          </span>
        </Link>

        <div className="flex items-center gap-2">
          <TopbarLink href="/studio/library" icon={FolderKanban} label="Library" />
          <TopbarLink href="/studio/history" icon={Clock} label="History" />
          <button
            type="button"
            className="grid h-9 w-9 place-items-center rounded-full border border-hairline bg-surface-3 text-text-muted transition hover:text-text"
            aria-label="Account"
          >
            <UserRound size={15} />
          </button>
        </div>
      </div>
    </header>
  );
}

function TopbarLink({
  href,
  icon: Icon,
  label,
}: {
  href: string;
  icon: LucideIcon;
  label: string;
}) {
  return (
    <Link
      href={href}
      className="hidden items-center gap-1.5 rounded-full border border-hairline bg-surface-2 px-3 py-1.5 text-xs font-semibold text-text-muted transition hover:border-hairline-strong hover:text-text sm:inline-flex"
    >
      <Icon size={13} />
      {label}
    </Link>
  );
}
