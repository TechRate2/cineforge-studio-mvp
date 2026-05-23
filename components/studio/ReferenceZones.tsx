'use client';
import { useRef, useState } from 'react';
import { toast } from 'sonner';
import type { LucideIcon } from 'lucide-react';
import { Upload, X, User, Package, Image as ImageIcon, Loader2 } from 'lucide-react';
import { uploadMediaToR2 } from '@/lib/studio/upload-media';

export type RefRole = 'character_anchor' | 'product_hero' | 'style_reference' | null;

export interface ReferenceZonesValue {
  images: string[];
  roles: (RefRole)[];
  storyboardImages: string[];
}

const ZONES: { key: 'character' | 'product' | 'storyboard'; label: string; hint: string; role: RefRole; icon: LucideIcon; tint: string }[] = [
  { key: 'character', label: 'Character', hint: 'Khuôn mặt / trang phục — neo cho hầu hết shot', role: 'character_anchor', icon: User, tint: 'from-accent-magenta/30' },
  { key: 'product', label: 'Product / Props', hint: 'Sản phẩm hoặc đạo cụ chính', role: 'product_hero', icon: Package, tint: 'from-accent-orange/30' },
  { key: 'storyboard', label: 'Storyboard / Style', hint: 'Frame composition / style reference', role: 'style_reference', icon: ImageIcon, tint: 'from-accent-cyan/30' },
];

interface Props {
  value: ReferenceZonesValue;
  onChange: (v: ReferenceZonesValue) => void;
  maxRefs?: number;
}

export function ReferenceZones({ value, onChange, maxRefs = 9 }: Props) {
  const fileInputs = useRef<Record<string, HTMLInputElement | null>>({});
  const [uploading, setUploading] = useState<Record<string, boolean>>({});

  async function handleFiles(zoneKey: 'character' | 'product' | 'storyboard', files: FileList | null) {
    if (!files || files.length === 0) return;
    const list = Array.from(files);

    // V5.1 — hard cap BEFORE upload so we don't waste R2 bandwidth on rejects
    if (zoneKey !== 'storyboard') {
      const remaining = Math.max(0, maxRefs - value.images.length);
      if (remaining === 0) {
        toast.error(`Đã đạt limit ${maxRefs} reference cho model này. Xóa ảnh cũ trước khi upload.`);
        return;
      }
      if (list.length > remaining) {
        toast.warning(`Chỉ upload ${remaining}/${list.length} ảnh — model giới hạn ${maxRefs} reference.`);
        list.length = remaining;
      }
    }

    setUploading((u) => ({ ...u, [zoneKey]: true }));
    const urls = await Promise.all(list.map((f) => uploadMediaToR2(f)));
    setUploading((u) => ({ ...u, [zoneKey]: false }));
    const role = ZONES.find((z) => z.key === zoneKey)!.role;
    if (zoneKey === 'storyboard') {
      onChange({ ...value, storyboardImages: [...value.storyboardImages, ...urls] });
      toast.success(`Đã upload ${urls.length} ảnh storyboard`);
      return;
    }
    onChange({
      ...value,
      images: [...value.images, ...urls],
      roles: [...value.roles, ...urls.map(() => role)],
    });
    toast.success(`Đã upload ${urls.length} ảnh ${role?.replace('_', ' ') ?? ''}`);
  }

  function removeAt(zoneKey: string, idx: number) {
    if (zoneKey === 'storyboard') {
      onChange({ ...value, storyboardImages: value.storyboardImages.filter((_, i) => i !== idx) });
      return;
    }
    const target = ZONES.find((z) => z.key === zoneKey)!.role;
    const indicesOfRole = value.roles
      .map((r, i) => (r === target ? i : -1))
      .filter((i) => i >= 0);
    const actualIdx = indicesOfRole[idx];
    if (actualIdx === undefined) return;
    onChange({
      images: value.images.filter((_, i) => i !== actualIdx),
      roles: value.roles.filter((_, i) => i !== actualIdx),
      storyboardImages: value.storyboardImages,
    });
  }

  function imagesForZone(zoneKey: string): string[] {
    if (zoneKey === 'storyboard') return value.storyboardImages;
    const target = ZONES.find((z) => z.key === zoneKey)!.role;
    return value.images.filter((_, i) => value.roles[i] === target);
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {ZONES.map((zone) => {
        const Icon = zone.icon;
        const items = imagesForZone(zone.key);
        // V5.4 — shared pool: character + product zones consume from `value.images`
        // (pooled to maxRefs); storyboard is its own bucket. atLimit reflects pool
        // exhaustion so the user sees clearly when ANY non-storyboard zone is full.
        const totalUsed = value.images.length;
        const atLimit = zone.key !== 'storyboard' && totalUsed >= maxRefs;
        return (
          <div key={zone.key} className="surface-2 rounded-card p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className={`w-7 h-7 rounded-md bg-gradient-to-br ${zone.tint} to-transparent grid place-items-center`}>
                  <Icon size={14} />
                </div>
                <div className="text-sm font-semibold">{zone.label}</div>
              </div>
              <span className={`chip ${atLimit ? 'text-accent-orange border-accent-orange/40' : ''}`}>
                {zone.key === 'storyboard' ? items.length : `${totalUsed}/${maxRefs}`}
              </span>
            </div>
            <p className="text-[11px] text-text-subtle mb-3 leading-snug">{zone.hint}</p>

            {/* Thumbnail grid */}
            {items.length > 0 && (
              <div className="grid grid-cols-3 gap-1.5 mb-3">
                {items.map((src, i) => (
                  <div key={i} className="group relative aspect-square rounded-md overflow-hidden border border-hairline">
                    <img src={src} alt="" className="w-full h-full object-cover" />
                    <button
                      onClick={() => removeAt(zone.key, i)}
                      className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/60 text-white grid place-items-center
                                 opacity-0 group-hover:opacity-100 transition"
                    >
                      <X size={10} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <input
              ref={(el) => { fileInputs.current[zone.key] = el; }}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(e) => handleFiles(zone.key, e.target.files)}
            />
            <button
              onClick={() => fileInputs.current[zone.key]?.click()}
              disabled={uploading[zone.key] || atLimit}
              title={atLimit ? `Đã đạt limit ${maxRefs} ref. Xóa ảnh cũ để upload thêm.` : undefined}
              className="w-full flex items-center justify-center gap-1.5 py-2.5 rounded-md
                         border border-dashed border-hairline-strong hover:border-accent-magenta/50
                         text-xs text-text-muted hover:text-text transition
                         disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:border-hairline-strong"
            >
              {uploading[zone.key] ? (
                <><Loader2 size={13} className="animate-spin" /> Uploading...</>
              ) : atLimit ? (
                <>Đã đầy {maxRefs}/{maxRefs}</>
              ) : (
                <><Upload size={13} /> Upload</>
              )}
            </button>
          </div>
        );
      })}
    </div>
  );
}
