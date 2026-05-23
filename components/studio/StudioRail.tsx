'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { LucideIcon } from 'lucide-react';
import {
  Sparkles, Wand2, Image as ImageIcon, Film, Mic2,
  Clock, Settings2, Library, BookOpen,
} from 'lucide-react';

interface RailItem {
  href: string;
  icon: LucideIcon;
  label: string;
}

const PRIMARY: RailItem[] = [
  { href: '/studio', icon: Wand2, label: 'Director' },
  { href: '/studio/text-to-video', icon: Film, label: 'Text → Video' },
  { href: '/studio/image-to-video', icon: ImageIcon, label: 'Image → Video' },
  { href: '/studio/voice', icon: Mic2, label: 'Voice / TTS' },
];

const SECONDARY: RailItem[] = [
  { href: '/studio/library', icon: Library, label: 'Asset Library' },
  { href: '/studio/history', icon: Clock, label: 'History' },
  { href: '/studio/admin', icon: Settings2, label: 'Admin' },
];

export function StudioRail() {
  const pathname = usePathname();

  return (
    <aside className="hidden md:flex w-[72px] shrink-0 flex-col items-center justify-between
                      bg-surface-1 border-r border-hairline py-4">
      {/* Logo */}
      <Link
        href="/studio"
        className="group relative w-11 h-11 rounded-card bg-cta-gradient
                   grid place-items-center transition hover:brightness-110"
        aria-label="CineForge"
      >
        <Sparkles size={20} strokeWidth={2.4} className="text-white" />
      </Link>

      {/* Primary nav */}
      <nav className="flex flex-col items-center gap-1.5 flex-1 mt-8">
        {PRIMARY.map((item) => (
          <RailIcon key={item.href} item={item} active={pathname === item.href} />
        ))}

        <div className="h-px w-7 my-3 bg-hairline" />

        {SECONDARY.map((item) => (
          <RailIcon key={item.href} item={item} active={pathname === item.href} />
        ))}
      </nav>

      {/* Docs */}
      <RailIcon
        item={{ href: '/studio/docs', icon: BookOpen, label: 'Docs' }}
        active={pathname === '/studio/docs'}
      />
    </aside>
  );
}

function RailIcon({ item, active }: { item: RailItem; active: boolean }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className={`group relative w-11 h-11 rounded-card grid place-items-center transition
                  ${active
                    ? 'bg-surface-3 text-text shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]'
                    : 'text-text-subtle hover:text-text hover:bg-surface-3'}`}
      title={item.label}
    >
      <Icon size={19} strokeWidth={1.8} />
      {active && (
        <span className="absolute -left-1 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-full bg-cta-gradient" />
      )}
      {/* Tooltip */}
      <span className="pointer-events-none absolute left-full ml-3 px-2.5 py-1 rounded-md
                       bg-surface-4 text-text text-xs whitespace-nowrap border border-hairline-strong
                       opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0
                       transition z-50">
        {item.label}
      </span>
    </Link>
  );
}
