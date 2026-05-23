'use client';
import { useEffect, useRef, useState } from 'react';
import {
  Coins, Globe2, ChevronDown, Bell, User, RefreshCcw, Loader2,
  Check, XCircle, ExternalLink,
} from 'lucide-react';
import Link from 'next/link';
import { useAdminCredits, type CreditProvider } from '@/lib/studio/use-admin-credits';

export function StudioTopbar() {
  const [showCredits, setShowCredits] = useState(false);
  const popRef = useRef<HTMLDivElement | null>(null);
  const { credits, loading, error, refresh } = useAdminCredits(false);

  // Click outside to close
  useEffect(() => {
    if (!showCredits) return;
    const onClick = (e: MouseEvent) => {
      if (popRef.current && !popRef.current.contains(e.target as Node)) {
        setShowCredits(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [showCredits]);

  // Refresh when opening
  useEffect(() => {
    if (showCredits) void refresh();
  }, [showCredits, refresh]);

  const providerCount = credits
    ? ['atlascloud', 'atlascloud_llm', 'genmax', 'anthropic'].filter(
        (k) => (credits as Record<string, CreditProvider | undefined>)[k]?.key_set
      ).length
    : 0;

  return (
    <header className="h-14 shrink-0 flex items-center justify-between px-5 md:px-7
                       border-b border-hairline bg-surface-1/60 backdrop-blur-xl">
      <div className="flex items-center gap-3">
        <Link href="/studio" className="md:hidden flex items-center gap-2">
          <span className="text-gradient text-lg font-extrabold tracking-tight">CineForge</span>
        </Link>
        <span className="hidden md:inline text-text text-base font-semibold tracking-tight">
          CineForge <span className="text-text-subtle font-normal">Studio</span>
        </span>
      </div>

      <div className="flex items-center gap-2 md:gap-3">
        {/* Credit pill — clickable to open provider status popover */}
        <div ref={popRef} className="relative">
          <button
            onClick={() => setShowCredits((s) => !s)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-pill border transition
                        ${showCredits
                          ? 'border-accent-magenta/60 bg-accent-magenta/15'
                          : 'border-accent-magenta/40 bg-accent-magenta/10 hover:bg-accent-magenta/15'}`}
          >
            <Coins size={14} className="text-accent-magenta" />
            <span className="text-xs font-semibold text-text">
              {providerCount}/4
            </span>
            <span className="hidden sm:inline text-[10px] text-text-muted">providers</span>
            <ChevronDown size={11} className={`text-text-muted transition ${showCredits ? 'rotate-180' : ''}`} />
          </button>

          {showCredits && (
            <div className="absolute top-full right-0 mt-2 w-[360px] z-50
                            glass-card border-hairline-strong p-4 shadow-2xl animate-fade-up">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold">Provider status</h3>
                <button
                  onClick={() => void refresh()}
                  disabled={loading}
                  className="btn-icon"
                  title="Refresh"
                >
                  {loading ? <Loader2 size={13} className="animate-spin" /> : <RefreshCcw size={13} />}
                </button>
              </div>

              {error && (
                <div className="surface-2 rounded-card p-2.5 mb-3 border-accent-orange/40">
                  <p className="text-[11px] text-accent-orange font-mono">{error}</p>
                </div>
              )}

              {!credits && loading && (
                <div className="space-y-2">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-12 rounded-md surface-2 shimmer" />
                  ))}
                </div>
              )}

              {credits && (
                <div className="space-y-2">
                  <ProviderRow
                    name="AtlasCloud"
                    sub="Video + Image gen"
                    cfg={credits.atlascloud}
                    dashboardUrl="https://atlascloud.ai/dashboard"
                  />
                  <ProviderRow
                    name="AtlasCloud LLM"
                    sub="Coding Plan (Claude/GPT)"
                    cfg={credits.atlascloud_llm}
                    dashboardUrl="https://atlascloud.ai/dashboard"
                  />
                  <ProviderRow
                    name="GenMax"
                    sub="TTS · 12 giọng VN"
                    cfg={credits.genmax}
                    creditMode
                    dashboardUrl="https://genmax.com/dashboard"
                  />
                  <ProviderRow
                    name="Anthropic"
                    sub="Director Agent fallback"
                    cfg={credits.anthropic}
                    dashboardUrl="https://console.anthropic.com"
                  />

                  {credits.r2 && (
                    <div className="surface-2 rounded-md p-2.5 mt-3 border-t border-hairline pt-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold">Cloudflare R2</span>
                          {credits.r2.configured ? (
                            <Check size={12} className="text-accent-green" />
                          ) : (
                            <XCircle size={12} className="text-accent-orange" />
                          )}
                        </div>
                        {credits.r2.bucket && (
                          <code className="text-[10px] text-text-subtle">{credits.r2.bucket}</code>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}

              <div className="mt-4 pt-3 border-t border-hairline">
                <p className="text-[10px] text-text-subtle leading-relaxed">
                  Balance không hiển thị live — vendor không expose API. Track trên dashboard provider.
                </p>
              </div>
            </div>
          )}
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

function ProviderRow({
  name, sub, cfg, creditMode, dashboardUrl,
}: {
  name: string;
  sub: string;
  cfg: CreditProvider | undefined;
  creditMode?: boolean;
  dashboardUrl?: string;
}) {
  const set = cfg?.key_set ?? false;
  return (
    <div className="surface-2 rounded-md p-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold">{name}</span>
            {set ? (
              <Check size={12} className="text-accent-green shrink-0" />
            ) : (
              <XCircle size={12} className="text-accent-orange shrink-0" />
            )}
          </div>
          <div className="text-[10px] text-text-subtle mt-0.5">{sub}</div>
          {cfg?.key_masked && (
            <code className="text-[10px] text-text-muted font-mono mt-1 block truncate">
              {cfg.key_masked}
            </code>
          )}
        </div>
        <div className="text-right shrink-0">
          {set ? (
            <>
              <div className="text-xs font-semibold text-accent-magenta">
                {creditMode
                  ? cfg?.balance_credits != null ? `${cfg.balance_credits} cr` : '—'
                  : cfg?.balance_usd != null ? `$${cfg.balance_usd.toFixed(2)}` : '—'}
              </div>
              {dashboardUrl && (
                <a
                  href={dashboardUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[10px] text-text-subtle hover:text-text inline-flex items-center gap-0.5 mt-0.5"
                >
                  Dashboard <ExternalLink size={9} />
                </a>
              )}
            </>
          ) : (
            <span className="text-[10px] text-accent-orange">No key</span>
          )}
        </div>
      </div>
    </div>
  );
}
