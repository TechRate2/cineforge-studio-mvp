'use client';

import Link from 'next/link';
import { useRef } from 'react';
import { useProjectHistory } from '@/lib/studio/use-project-history';
import { CheckCircle2, AlertCircle, Clock, ArrowRight, Loader2 } from 'lucide-react';

async function safePlay(el: HTMLVideoElement, abortRef: { aborted: boolean }) {
  try {
    await el.play();
    if (abortRef.aborted) {
      el.pause();
      el.currentTime = 0;
    }
  } catch {
    /* AbortError / autoplay block: ignore */
  }
}

export function RecentGenerations() {
  const { items, loading } = useProjectHistory();
  const recent = items.slice(0, 6);

  if (loading && items.length === 0) {
    return (
      <div className="flex items-center gap-2 text-xs text-text-subtle">
        <Loader2 size={12} className="animate-spin" /> Loading recent renders...
      </div>
    );
  }
  if (recent.length === 0) return null;

  return (
    <div>
      <div className="mb-3 flex items-center justify-between px-1">
        <h3 className="text-[11px] font-semibold uppercase text-text-subtle">
          Recent autonomous renders - {items.length} total
        </h3>
        <Link href="/studio/history" className="inline-flex items-center gap-0.5 text-[11px] text-text-muted hover:text-text">
          View all <ArrowRight size={10} />
        </Link>
      </div>
      <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 lg:grid-cols-6">
        {recent.map((item) => (
          <Link
            key={item.job_id}
            href="/studio/history"
            className="group relative aspect-[9/16] overflow-hidden rounded-card border border-hairline bg-surface-2 transition hover:border-accent-magenta/50"
          >
            {item.output_url ? (
              <RecentVideo src={item.output_url} />
            ) : (
              <div className="absolute inset-0 grid place-items-center text-text-subtle">
                <Clock size={20} />
              </div>
            )}
            <div className="absolute right-1.5 top-1.5">
              {item.status === 'done' ? (
                <CheckCircle2 size={13} className="text-accent-green drop-shadow" />
              ) : item.status === 'failed' || item.status === 'cancelled' ? (
                <AlertCircle size={13} className="text-accent-orange drop-shadow" />
              ) : (
                <Loader2 size={13} className="animate-spin text-accent-yellow drop-shadow" />
              )}
            </div>
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent p-2">
              <div className="line-clamp-2 text-[10px] font-semibold leading-tight text-white">
                {item.title || 'Autonomous render'}
              </div>
              {item.duration_s != null && (
                <div className="mt-0.5 text-[9px] text-white/60">
                  {item.duration_s}s - Autonomous
                </div>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function RecentVideo({ src }: { src: string }) {
  const ref = useRef<HTMLVideoElement | null>(null);
  const abortRef = useRef({ aborted: false });
  return (
    <video
      ref={ref}
      src={src}
      muted
      loop
      preload="metadata"
      playsInline
      onMouseEnter={() => {
        const el = ref.current;
        if (!el) return;
        abortRef.current.aborted = false;
        void safePlay(el, abortRef.current);
      }}
      onMouseLeave={() => {
        const el = ref.current;
        if (!el) return;
        abortRef.current.aborted = true;
        if (!el.paused) {
          el.pause();
          el.currentTime = 0;
        }
      }}
      className="absolute inset-0 h-full w-full object-cover"
    />
  );
}
