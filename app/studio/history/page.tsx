'use client';
import { useState } from 'react';
import { Clock, Loader2, Trash2, Play, RefreshCw } from 'lucide-react';
import { useProjectHistory } from '@/lib/studio/use-project-history';

export default function HistoryPage() {
  const { items, loading, refresh, remove, error } = useProjectHistory();
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  return (
    <div className="px-5 md:px-10 py-8 max-w-container mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="h-section flex items-center gap-3"><Clock size={26} /> Project history</h1>
          <p className="text-sm text-text-muted mt-1">Mọi plan & render bạn đã build — tái sử dụng / fork lại.</p>
        </div>
        <button onClick={refresh} className="btn-outline" disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {error && (
        <div className="surface-2 rounded-card p-4 mb-4 text-sm text-accent-orange border-accent-orange/40">
          {error}
        </div>
      )}

      {loading && items.length === 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="aspect-video rounded-card surface-2 shimmer" />
          ))}
        </div>
      )}

      {!loading && items.length === 0 && (
        <div className="surface-2 rounded-card p-12 text-center">
          <Clock size={32} className="mx-auto text-text-subtle mb-3" />
          <h3 className="font-semibold mb-1">Chưa có project nào</h3>
          <p className="text-sm text-text-muted">Quay lại Studio để tạo plan đầu tiên.</p>
        </div>
      )}

      {items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {items.map((it) => (
            <div key={it.job_id} className="bento group">
              <div className="aspect-video bg-surface-3 relative">
                {it.output_url ? (
                  <button
                    onClick={() => setPreviewUrl(it.output_url)}
                    className="absolute inset-0 grid place-items-center bg-black hover:bg-black/70 transition"
                  >
                    <Play size={28} className="text-white" />
                  </button>
                ) : (
                  <div className="absolute inset-0 grid place-items-center text-text-subtle text-xs">
                    {it.status === 'rendering' || it.status === 'pending' ? (
                      <Loader2 size={20} className="animate-spin" />
                    ) : (
                      <span>{it.status}</span>
                    )}
                  </div>
                )}
              </div>
              <div className="p-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <h4 className="text-sm font-semibold truncate">{it.title || 'Untitled'}</h4>
                    <p className="text-[11px] text-text-subtle mt-0.5">
                      {new Date(it.created_at).toLocaleString('vi-VN')}
                    </p>
                  </div>
                  <span className={`chip text-[10px] ${
                    it.status === 'done' ? 'border-accent-green/40 text-accent-green'
                    : it.status === 'failed' ? 'border-accent-orange/40 text-accent-orange'
                    : ''
                  }`}>{it.status}</span>
                </div>
                <div className="flex items-center justify-between mt-3 text-[11px] text-text-subtle">
                  <span>{it.duration_s ?? '—'}s · ${(it.cost_estimate_usd ?? 0).toFixed(2)}</span>
                  <button
                    onClick={() => remove(it.job_id)}
                    className="opacity-0 group-hover:opacity-100 transition text-text-subtle hover:text-accent-orange"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Lightbox */}
      {previewUrl && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur grid place-items-center p-4" onClick={() => setPreviewUrl(null)}>
          <video src={previewUrl} controls autoPlay className="max-w-5xl w-full rounded-card shadow-2xl" />
        </div>
      )}
    </div>
  );
}
