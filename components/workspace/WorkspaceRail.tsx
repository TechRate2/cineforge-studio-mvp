'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Sparkles,
  Image as ImgIcon,
  AudioLines,
  Home,
  FolderArchive,
  Settings,
} from 'lucide-react';

type NavItem = {
  href: string;
  icon: typeof Sparkles;
  label: string;
  desc: string;
  accent: string;
};

const NAV_ITEMS: NavItem[] = [
  {
    href: '/studio',
    icon: Sparkles,
    label: 'Studio',
    desc: 'AI agent — paste link → video',
    accent: 'from-brand-500 to-brand-700',
  },
  {
    href: '/image',
    icon: ImgIcon,
    label: 'Image',
    desc: 'Tự lái — 8 model AtlasCloud',
    accent: 'from-fuchsia-500 to-purple-700',
  },
  {
    href: '/audio',
    icon: AudioLines,
    label: 'Audio',
    desc: 'GenMax TTS — 12 giọng VN',
    accent: 'from-emerald-500 to-teal-700',
  },
];

export function WorkspaceRail() {
  const path = usePathname();
  return (
    <aside className="w-[96px] shrink-0 bg-bg-soft border-r border-border flex flex-col items-center py-4 relative z-30">
      {/* Logo */}
      <Link
        href="/"
        title="Vidhyper home"
        className="w-12 h-12 rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-lg shadow-brand-600/40 mb-3 hover:scale-105 transition"
      >
        <svg viewBox="0 0 24 24" fill="white" className="w-6 h-6">
          <path d="M12 2l2.4 7.4H22l-6 4.6 2.3 7.4L12 16.8 5.7 21.4 8 14l-6-4.6h7.6L12 2z" />
        </svg>
      </Link>
      <div className="w-10 h-px bg-border mb-3" />

      {/* Main nav */}
      <nav className="flex flex-col gap-1 w-full px-1.5">
        {NAV_ITEMS.map((item) => {
          const active = path?.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              title={item.desc}
              className={`group relative flex flex-col items-center justify-center gap-1.5 py-2.5 rounded-2xl transition ${
                active
                  ? 'bg-bg-card border border-border shadow-sm'
                  : 'hover:bg-bg-hover border border-transparent'
              }`}
            >
              <span
                className={`w-10 h-10 rounded-xl flex items-center justify-center transition ${
                  active
                    ? `bg-gradient-to-br ${item.accent} text-white shadow-md`
                    : 'bg-bg-card border border-border text-text-muted group-hover:text-text'
                }`}
              >
                <Icon className="w-5 h-5" strokeWidth={active ? 2.4 : 2} />
              </span>
              <span
                className={`text-[11px] font-semibold tracking-tight leading-none ${
                  active ? 'text-text' : 'text-text-muted group-hover:text-text'
                }`}
              >
                {item.label}
              </span>
              {active && (
                <span className="absolute -left-1.5 top-4 bottom-4 w-1 rounded-r-full bg-brand-400" />
              )}
            </Link>
          );
        })}
      </nav>

      <div className="flex-1" />

      {/* Bottom utilities */}
      <div className="flex flex-col gap-1 w-full px-1.5">
        <Link
          href="/"
          title="Trang chủ Vidhyper"
          className="group flex flex-col items-center gap-1 py-2 rounded-2xl text-text-subtle hover:bg-bg-hover hover:text-text transition"
        >
          <Home className="w-4 h-4" />
          <span className="text-[10px] font-medium">Trang chủ</span>
        </Link>
        <button
          title="Generations history"
          className="group flex flex-col items-center gap-1 py-2 rounded-2xl text-text-subtle hover:bg-bg-hover hover:text-text transition"
        >
          <FolderArchive className="w-4 h-4" />
          <span className="text-[10px] font-medium">Lịch sử</span>
        </button>
        <button
          title="Settings"
          className="group flex flex-col items-center gap-1 py-2 rounded-2xl text-text-subtle hover:bg-bg-hover hover:text-text transition"
        >
          <Settings className="w-4 h-4" />
          <span className="text-[10px] font-medium">Cài đặt</span>
        </button>
      </div>
    </aside>
  );
}
