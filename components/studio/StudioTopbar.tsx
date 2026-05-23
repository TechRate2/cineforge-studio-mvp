'use client';
import { Coins, Globe2, ChevronDown, Bell, User } from 'lucide-react';
import Link from 'next/link';

export function StudioTopbar() {
  return (
    <header className="h-14 shrink-0 flex items-center justify-between px-5 md:px-7
                       border-b border-hairline bg-surface-1/60 backdrop-blur-xl">
      {/* Left — wordmark visible on mobile only (rail hidden) */}
      <div className="flex items-center gap-3">
        <Link href="/studio" className="md:hidden flex items-center gap-2">
          <span className="text-gradient text-lg font-extrabold tracking-tight">CineForge</span>
        </Link>
        <span className="hidden md:inline text-text text-base font-semibold tracking-tight">
          CineForge <span className="text-text-subtle font-normal">Studio</span>
        </span>
      </div>

      {/* Right — credit + lang + user */}
      <div className="flex items-center gap-2 md:gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-pill
                        border border-accent-magenta/40 bg-accent-magenta/10">
          <Coins size={14} className="text-accent-magenta" />
          <span className="text-xs font-semibold text-text">2,840</span>
          <span className="hidden sm:inline text-[10px] text-text-muted">credits</span>
          <span className="mx-1 h-3 w-px bg-accent-magenta/30" />
          <button className="text-[11px] font-semibold text-accent-magenta hover:text-accent-orange transition">
            Upgrade
          </button>
        </div>

        <button className="btn-icon hidden sm:inline-flex" title="Notifications">
          <Bell size={16} />
        </button>

        <button className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg
                           border border-hairline hover:bg-surface-3 transition text-xs text-text-muted">
          <Globe2 size={13} />
          VI
          <ChevronDown size={12} />
        </button>

        <button className="w-9 h-9 rounded-full bg-surface-3 border border-hairline
                           grid place-items-center text-text-muted hover:text-text transition">
          <User size={15} />
        </button>
      </div>
    </header>
  );
}
