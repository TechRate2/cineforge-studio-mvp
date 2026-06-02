'use client';
import { useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Library, Search, RefreshCw, Trash2, User, Package, Image as ImageIcon } from 'lucide-react';
import { useAssetLibrary, type AssetType } from '@/lib/studio/use-asset-library';

const TYPE_TABS: { v: AssetType | undefined; label: string; icon: LucideIcon }[] = [
  { v: undefined, label: 'All', icon: Library },
  { v: 'character', label: 'Character', icon: User },
  { v: 'product', label: 'Product', icon: Package },
  { v: 'storyboard', label: 'Storyboard', icon: ImageIcon },
];

export default function LibraryPage() {
  const { items, loading, error, typeFilter, setTypeFilter, search, setSearch, refresh, remove } = useAssetLibrary();
  const [localSearch, setLocalSearch] = useState('');

  return (
    <div className="px-5 md:px-10 py-8 max-w-container mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="h-section flex items-center gap-3"><Library size={26} /> Asset library</h1>
          <p className="text-sm text-text-muted mt-1">Reusable character, product and style references for future autonomous videos.</p>
        </div>
        <button onClick={refresh} className="btn-outline" disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="flex gap-1.5">
          {TYPE_TABS.map((t) => {
            const Icon = t.icon;
            const active = typeFilter === t.v;
            return (
              <button
                key={t.label}
                onClick={() => setTypeFilter(t.v)}
                className={`px-3 py-1.5 rounded-pill text-xs font-medium flex items-center gap-1.5 transition
                            ${active
                              ? 'bg-cta-gradient text-white'
                              : 'surface-2 text-text-muted hover:text-text'}`}
              >
                <Icon size={12} /> {t.label}
              </button>
            );
          })}
        </div>

        <div className="relative flex-1 min-w-[240px] max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-subtle" />
          <input
            value={localSearch}
            onChange={(e) => setLocalSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && setSearch(localSearch)}
            placeholder="Search by name / tag..."
            className="field pl-9 py-2 text-sm"
          />
        </div>
      </div>

      {error && (
        <div className="surface-2 rounded-card p-4 mb-4 text-sm text-accent-orange border-accent-orange/40">
          {error}
        </div>
      )}

      {!loading && items.length === 0 && (
        <div className="surface-2 rounded-card p-12 text-center">
          <Library size={32} className="mx-auto text-text-subtle mb-3" />
          <h3 className="font-semibold mb-1">Library is empty</h3>
          <p className="text-sm text-text-muted">Approve references from Studio to reuse them across future videos.</p>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {items.map((a) => (
          <div key={a.id} className="bento group">
            <div className="aspect-square bg-surface-3 relative">
              <img src={a.image_url} alt={a.name} className="absolute inset-0 w-full h-full object-cover" />
            </div>
            <div className="p-2.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10px] uppercase text-text-subtle">{a.type}</span>
                <button
                  onClick={() => remove(a.id)}
                  className="opacity-0 group-hover:opacity-100 transition text-text-subtle hover:text-accent-orange"
                >
                  <Trash2 size={12} />
                </button>
              </div>
              <h4 className="text-xs font-semibold truncate mt-0.5">{a.name}</h4>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
