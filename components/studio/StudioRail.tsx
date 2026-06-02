'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { LucideIcon } from 'lucide-react';
import { Clock, FolderKanban, Sparkles, Wand2 } from 'lucide-react';

interface RailItem {
  href: string;
  icon: LucideIcon;
  label: string;
}

const NAV_ITEMS: RailItem[] = [
  { href: '/studio', icon: Wand2, label: 'Director' },
  { href: '/studio/library', icon: FolderKanban, label: 'Library' },
  { href: '/studio/history', icon: Clock, label: 'History' },
];

export function StudioRail() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-[72px] shrink-0 flex-col items-center border-r border-hairline bg-surface-1 py-4 md:flex">
      <Link
        href="/studio"
        className="grid h-11 w-11 place-items-center rounded-card bg-cta-gradient text-white transition hover:brightness-110"
        aria-label="CineJelly Autonomous"
      >
        <Sparkles size={20} strokeWidth={2.4} />
      </Link>

      <nav className="mt-8 flex flex-1 flex-col items-center gap-1.5">
        {NAV_ITEMS.map((item) => (
          <RailIcon key={item.href} item={item} active={pathname === item.href} />
        ))}
      </nav>
    </aside>
  );
}

function RailIcon({ item, active }: { item: RailItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={`group relative grid h-11 w-11 place-items-center rounded-card transition ${
        active
          ? 'bg-surface-3 text-text shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]'
          : 'text-text-subtle hover:bg-surface-3 hover:text-text'
      }`}
      title={item.label}
      aria-label={item.label}
    >
      <Icon size={19} strokeWidth={1.8} />
      {active && (
        <span className="absolute -left-1 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-cta-gradient" />
      )}
      <span className="pointer-events-none absolute left-full z-50 ml-3 whitespace-nowrap rounded-md border border-hairline-strong bg-surface-4 px-2.5 py-1 text-xs text-text opacity-0 transition group-hover:translate-x-0 group-hover:opacity-100">
        {item.label}
      </span>
    </Link>
  );
}
