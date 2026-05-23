'use client';

/**
 * AssetLibrary — Modal browse Character/Product/Storyboard refs đã lưu.
 *
 * Mở từ ReferenceZones (📚 button). User pick 1 hoặc nhiều asset → trả về
 * caller qua onPick callback để inject vào zone tương ứng.
 *
 * Filter theo type (tab pill) + tìm theo name/tags. Sort theo last_used_at
 * desc (backend đã handle).
 */

import { useState } from 'react';
import { X, Search, User, Package, Image as ImgIcon, Trash2, CheckSquare, Square } from 'lucide-react';
import { useAssetLibrary, type Asset, type AssetType } from '@/lib/studio/use-asset-library';

interface Props {
  open: boolean;
  initialType?: AssetType;
  onClose: () => void;
  onPick: (assets: Asset[]) => void;
}

const TYPE_META: Record<AssetType, { label: string; icon: React.ReactNode }> = {
  character: { label: 'Character', icon: <User className="w-3.5 h-3.5" /> },
  product: { label: 'Product', icon: <Package className="w-3.5 h-3.5" /> },
  storyboard: { label: 'Storyboard', icon: <ImgIcon className="w-3.5 h-3.5" /> },
};

export function AssetLibrary({ open, initialType, onClose, onPick }: Props) {
  const lib = useAssetLibrary(initialType);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  if (!open) return null;

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleInsert = () => {
    const picked = lib.items.filter((a) => selected.has(a.id));
    picked.forEach((a) => lib.touch(a.id));
    onPick(picked);
    setSelected(new Set());
    onClose();
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Xoá asset này khỏi library?')) return;
    try {
      await lib.remove(id);
      setSelected((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    } catch (err) {
      alert(`Xoá lỗi: ${err instanceof Error ? err.message : err}`);
    }
  };

  return (
    <div className="fixed inset-0 z-[55] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-bg-card border border-border rounded-2xl shadow-2xl w-full max-w-4xl max-h-[85vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-brand-300 font-medium">Asset Library</div>
            <div className="text-sm font-semibold text-text">
              Reusable references · {lib.items.length} {lib.typeFilter ?? 'total'}
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-bg-hover text-text-muted hover:text-text">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Filter bar */}
        <div className="px-5 py-2.5 border-b border-border flex items-center gap-2 flex-wrap">
          <FilterChip
            active={!lib.typeFilter}
            onClick={() => lib.setTypeFilter(undefined)}
          >
            All
          </FilterChip>
          {(['character', 'product', 'storyboard'] as AssetType[]).map((t) => (
            <FilterChip
              key={t}
              active={lib.typeFilter === t}
              onClick={() => lib.setTypeFilter(t)}
              icon={TYPE_META[t].icon}
            >
              {TYPE_META[t].label}
            </FilterChip>
          ))}
          <div className="flex-1" />
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-text-subtle" />
            <input
              value={lib.search}
              onChange={(e) => lib.setSearch(e.target.value)}
              placeholder="Tìm theo name / tags"
              className="pl-7 pr-2 py-1.5 text-xs bg-bg-soft border border-border rounded-md text-text focus:outline-none focus:border-brand-500 placeholder:text-text-subtle w-56"
            />
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {lib.loading ? (
            <div className="text-center py-12 text-text-subtle text-sm">Đang tải…</div>
          ) : lib.error ? (
            <div className="text-center py-12 text-rose-300 text-sm">Lỗi: {lib.error}</div>
          ) : lib.items.length === 0 ? (
            <div className="text-center py-12 text-text-subtle text-sm">
              Chưa có asset nào{lib.typeFilter ? ` cho type "${lib.typeFilter}"` : ''}.
              <div className="text-xs mt-1.5">Lưu từ ReferenceZones (icon 💾 mỗi ảnh).</div>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              {lib.items.map((a) => {
                const isSelected = selected.has(a.id);
                return (
                  <button
                    key={a.id}
                    onClick={() => toggleSelect(a.id)}
                    className={`group relative text-left rounded-lg border overflow-hidden transition ${
                      isSelected
                        ? 'border-brand-500 ring-2 ring-brand-500/30'
                        : 'border-border hover:border-brand-500/50'
                    }`}
                  >
                    <div className="aspect-square bg-bg-soft relative">
                      <img
                        src={a.image_url}
                        alt={a.name}
                        className="w-full h-full object-cover"
                      />
                      {/* Selection check */}
                      <div className="absolute top-1.5 left-1.5">
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-brand-300 drop-shadow" />
                        ) : (
                          <Square className="w-4 h-4 text-white/60 drop-shadow opacity-0 group-hover:opacity-100" />
                        )}
                      </div>
                      {/* Delete */}
                      <button
                        onClick={(e) => handleDelete(a.id, e)}
                        className="absolute top-1.5 right-1.5 p-1 rounded bg-rose-500/80 text-white opacity-0 group-hover:opacity-100 transition"
                        title="Xoá khỏi library"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                      {/* Type badge */}
                      <div className="absolute bottom-1.5 left-1.5 px-1.5 py-0.5 rounded bg-black/60 text-white text-[10px] font-medium inline-flex items-center gap-1">
                        {TYPE_META[a.type].icon} {a.type}
                      </div>
                    </div>
                    <div className="px-2 py-1.5 bg-bg-soft">
                      <div className="text-xs text-text font-medium truncate" title={a.name}>{a.name}</div>
                      {a.tags && (
                        <div className="text-[10px] text-text-subtle truncate">#{a.tags.split(',').slice(0, 3).join(' #')}</div>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-border px-5 py-3 flex items-center justify-between gap-3">
          <div className="text-xs text-text-subtle">
            {selected.size > 0 ? `Đã chọn ${selected.size}` : 'Click ảnh để chọn (multi-select)'}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3 py-2 text-xs rounded-md border border-border bg-bg-soft hover:bg-bg-hover text-text-muted"
            >
              Huỷ
            </button>
            <button
              onClick={handleInsert}
              disabled={selected.size === 0}
              className="px-4 py-2 text-xs font-medium rounded-md bg-gradient-to-r from-brand-500 to-fuchsia-500 hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed text-white"
            >
              Chèn vào Reference Pack ({selected.size})
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function FilterChip({
  active, onClick, icon, children,
}: { active: boolean; onClick: () => void; icon?: React.ReactNode; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition ${
        active
          ? 'bg-brand-500/15 text-brand-200 border border-brand-500/30'
          : 'text-text-muted hover:text-text hover:bg-bg-soft border border-transparent'
      }`}
    >
      {icon} {children}
    </button>
  );
}
