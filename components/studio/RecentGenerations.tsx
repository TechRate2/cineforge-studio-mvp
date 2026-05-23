'use client';
import Link from 'next/link';
import { useProjectHistory } from '@/lib/studio/use-project-history';
import { CheckCircle2, AlertCircle, Clock, ArrowRight, Loader2 } from 'lucide-react';

export function RecentGenerations() {
  const { items, loading } = useProjectHistory();
  const recent = items.slice(0, 6);

  if (loading && items.length === 0) {
    return (
      <div className="flex items-center gap-2 text-xs text-text-subtle">
        <Loader2 size={12} className="animate-spin" /> Loading recent…
      </div>
    );
  }
  if (recent.length === 0) return null;

  return (
    <div>
      <div className="flex items-center justify-between mb-3 px-1">
        <h3 className="text-[11px] uppercase tracking-wider text-text-subtle font-semibold">
          Video gần đây · {items.length} total
        </h3>
        <Link href="/studio/history" className="text-[11px] text-text-muted hover:text-text inline-flex items-center gap-0.5">
          Xem tất cả <ArrowRight size={10} />
        </Link>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2.5">
        {recent.map((item) => (
          <Link
            key={item.job_id}
            href="/studio/history"
            className="group relative aspect-[9/16] rounded-card overflow-hidden bg-surface-2
                       border border-hairline hover:border-accent-magenta/50 transition"
          >
            {item.output_url ? (
              <video
                src={item.output_url}
                muted
                loop
                preload="metadata"
                playsInline
                onMouseEnter={(e) => void e.currentTarget.play().catch(() => {})}
                onMouseLeave={(e) => { e.currentTarget.pause(); e.currentTarget.currentTime = 0; }}
                className="absolute inset-0 w-full h-full object-cover"
              />
            ) : (
              <div className="absolute inset-0 grid place-items-center text-text-subtle">
                <Clock size={20} />
              </div>
            )}
            {/* Status overlay */}
            <div className="absolute top-1.5 right-1.5">
              {item.status === 'done' ? (
                <CheckCircle2 size={13} className="text-accent-green drop-shadow" />
              ) : item.status === 'failed' || item.status === 'cancelled' ? (
                <AlertCircle size={13} className="text-accent-orange drop-shadow" />
              ) : (
                <Loader2 size={13} className="text-accent-yellow animate-spin drop-shadow" />
              )}
            </div>
            {/* Title overlay */}
            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent p-2">
              <div className="text-[10px] font-semibold text-white line-clamp-2 leading-tight">
                {item.title || `Job ${item.job_id.slice(-6)}`}
              </div>
              {item.duration_s != null && (
                <div className="text-[9px] text-white/60 mt-0.5">
                  {item.duration_s}s
                  {item.cost_estimate_usd != null && ` · $${item.cost_estimate_usd.toFixed(2)}`}
                </div>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
