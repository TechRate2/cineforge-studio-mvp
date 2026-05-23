'use client';

/**
 * ReferenceZones — 3 upload buckets per CineForge v2.1 §5:
 *   1) Character References — face / outfit anchor
 *   2) Product / Props       — what we're showcasing
 *   3) Storyboard Frames     — optional pre-baked composition refs
 *
 * Each zone collects images + pre-tags them with a role so the Director
 * Agent doesn't have to guess (vision pass becomes confirmation-only).
 *
 * Output (via onChange):
 *   {
 *     images: string[],            // flat list (data URLs / external URLs)
 *     roles:  ReferenceRole[],     // same length, role per image
 *     storyboardImages: string[],  // subset that came from the storyboard zone
 *   }
 */

import { useCallback, useRef, useState } from 'react';
import { User, Package, Image as ImgIcon, Upload, X, Library, Save } from 'lucide-react';
import type { ReferenceRole } from '@/lib/studio/parse-image-mentions';
import { AssetLibrary } from './AssetLibrary';
import type { Asset, AssetType } from '@/lib/studio/use-asset-library';

export interface ReferenceZonesValue {
  images: string[];
  roles: (ReferenceRole | null)[];
  storyboardImages: string[];
}

interface Props {
  value: ReferenceZonesValue;
  onChange: (next: ReferenceZonesValue) => void;
  maxTotal?: number;  // default 12 (AtlasCloud max)
}

type ZoneKey = 'character' | 'product' | 'storyboard';

// Map zone → backend Asset type (AssetLibrary stores 3 same buckets)
const ZONE_TO_ASSET_TYPE: Record<ZoneKey, AssetType> = {
  character: 'character',
  product: 'product',
  storyboard: 'storyboard',
};

const ZONE_META: Record<ZoneKey, {
  label: string;
  hint: string;
  icon: React.ReactNode;
  role: ReferenceRole;
  storyboardOnly?: boolean;
}> = {
  character: {
    label: 'Character',
    hint: 'Ảnh nhân vật chính — giữ face / outfit nhất quán',
    icon: <User className="w-3.5 h-3.5" />,
    role: 'primary_subject',
  },
  product: {
    label: 'Product / Props',
    hint: 'Sản phẩm hoặc đạo cụ chính trong cảnh',
    icon: <Package className="w-3.5 h-3.5" />,
    role: 'product_hero',
  },
  storyboard: {
    label: 'Storyboard',
    hint: 'Frame tham khảo bố cục / style (tuỳ chọn)',
    icon: <ImgIcon className="w-3.5 h-3.5" />,
    role: 'style_reference',
    storyboardOnly: true,
  },
};

export function ReferenceZones({ value, onChange, maxTotal = 12 }: Props) {
  // Bucket the current flat list back into the 3 zones for rendering.
  // We track which indices originated as storyboard so we can render them in the
  // 3rd zone while keeping a single underlying list for upload to the backend.
  const buckets = bucketByRole(value);

  // Library modal state — which zone opened it (so picks land in right bucket)
  const [libraryFor, setLibraryFor] = useState<ZoneKey | null>(null);

  const handleSaveToLibrary = useCallback(
    async (zone: ZoneKey, url: string) => {
      const name = window.prompt(
        `Lưu vào Asset Library (${ZONE_META[zone].label}). Đặt tên:`,
        `${ZONE_META[zone].label} ${new Date().toLocaleDateString('vi-VN')}`,
      );
      if (!name?.trim()) return;
      try {
        const res = await fetch('/api/v1/assets/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type: ZONE_TO_ASSET_TYPE[zone],
            name: name.trim(),
            image_url: url,
            payload: {},
            tags: '',
          }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        // Visual feedback: small toast-style alert (lightweight)
        // Sau này có thể replace bằng proper toast component.
        // eslint-disable-next-line no-console
        console.log('[ReferenceZones] saved to library:', name);
      } catch (e) {
        alert(`Lỗi lưu library: ${e instanceof Error ? e.message : e}`);
      }
    },
    [],
  );

  const handleLibraryPick = useCallback(
    (zone: ZoneKey, assets: Asset[]) => {
      if (assets.length === 0) return;
      const role = ZONE_META[zone].role;
      const remaining = maxTotal - value.images.length;
      const toAdd = assets.slice(0, remaining);
      const urls = toAdd.map((a) => a.image_url);
      const roles = toAdd.map(() => role) as (ReferenceRole | null)[];
      const storyboardAdd = zone === 'storyboard' ? urls : [];
      onChange({
        images: [...value.images, ...urls],
        roles: [...value.roles, ...roles],
        storyboardImages: [...value.storyboardImages, ...storyboardAdd],
      });
    },
    [value, onChange, maxTotal],
  );

  const addToZone = useCallback(
    (zone: ZoneKey, files: FileList | null) => {
      if (!files || files.length === 0) return;
      if (value.images.length >= maxTotal) return;

      const role = ZONE_META[zone].role;
      const remaining = maxTotal - value.images.length;
      const toAdd = Array.from(files).slice(0, remaining);

      Promise.all(
        toAdd.map(
          (f) =>
            new Promise<string>((res) => {
              const r = new FileReader();
              r.onload = () => res(r.result as string);
              r.readAsDataURL(f);
            }),
        ),
      ).then((dataUrls) => {
        const nextImages = [...value.images, ...dataUrls];
        const nextRoles: (ReferenceRole | null)[] = [
          ...value.roles,
          ...dataUrls.map(() => role),
        ];
        const nextStoryboard =
          zone === 'storyboard'
            ? [...value.storyboardImages, ...dataUrls]
            : value.storyboardImages;
        onChange({
          images: nextImages,
          roles: nextRoles,
          storyboardImages: nextStoryboard,
        });
      });
    },
    [value, onChange, maxTotal],
  );

  const removeImage = useCallback(
    (index: number) => {
      const url = value.images[index];
      onChange({
        images: value.images.filter((_, i) => i !== index),
        roles: value.roles.filter((_, i) => i !== index),
        storyboardImages: value.storyboardImages.filter((u) => u !== url),
      });
    },
    [value, onChange],
  );

  return (
    <div className="space-y-2">
      <div className="text-[11px] uppercase tracking-widest text-text-subtle font-medium flex items-center justify-between">
        <span>Reference Pack</span>
        <span className="text-text-subtle">
          {value.images.length}/{maxTotal}
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
        <Zone
          zone="character"
          items={buckets.character}
          onAdd={(files) => addToZone('character', files)}
          onRemove={removeImage}
          onSaveToLibrary={(url) => handleSaveToLibrary('character', url)}
          onOpenLibrary={() => setLibraryFor('character')}
          remaining={maxTotal - value.images.length}
        />
        <Zone
          zone="product"
          items={buckets.product}
          onAdd={(files) => addToZone('product', files)}
          onRemove={removeImage}
          onSaveToLibrary={(url) => handleSaveToLibrary('product', url)}
          onOpenLibrary={() => setLibraryFor('product')}
          remaining={maxTotal - value.images.length}
        />
        <Zone
          zone="storyboard"
          items={buckets.storyboard}
          onAdd={(files) => addToZone('storyboard', files)}
          onRemove={removeImage}
          onSaveToLibrary={(url) => handleSaveToLibrary('storyboard', url)}
          onOpenLibrary={() => setLibraryFor('storyboard')}
          remaining={maxTotal - value.images.length}
        />
      </div>

      {libraryFor && (
        <AssetLibrary
          open={true}
          initialType={ZONE_TO_ASSET_TYPE[libraryFor]}
          onClose={() => setLibraryFor(null)}
          onPick={(assets) => {
            handleLibraryPick(libraryFor, assets);
            setLibraryFor(null);
          }}
        />
      )}
    </div>
  );
}

// ============================================================
// Sub: one zone column
// ============================================================
function Zone({
  zone,
  items,
  onAdd,
  onRemove,
  onSaveToLibrary,
  onOpenLibrary,
  remaining,
}: {
  zone: ZoneKey;
  items: Array<{ index: number; url: string }>;
  onAdd: (files: FileList | null) => void;
  onRemove: (index: number) => void;
  onSaveToLibrary: (url: string) => void;
  onOpenLibrary: () => void;
  remaining: number;
}) {
  const meta = ZONE_META[zone];
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        onAdd(e.dataTransfer.files);
      }}
      className={`rounded-lg border ${dragOver ? 'border-brand-500 bg-brand-500/5' : 'border-border bg-bg-soft'} px-2.5 py-2 min-h-[120px] flex flex-col gap-1.5 transition`}
    >
      <div className="flex items-center justify-between text-[11px]">
        <div className="flex items-center gap-1.5 text-text font-medium">
          {meta.icon} <span>{meta.label}</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onOpenLibrary}
            className="text-text-subtle hover:text-brand-300 inline-flex items-center"
            title="Mở Asset Library"
          >
            <Library className="w-3 h-3" />
          </button>
          <button
            onClick={() => inputRef.current?.click()}
            disabled={remaining <= 0}
            className="text-text-subtle hover:text-brand-300 disabled:opacity-40 inline-flex items-center gap-1"
            title="Upload ảnh"
          >
            <Upload className="w-3 h-3" />
          </button>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(e) => onAdd(e.target.files)}
          />
        </div>
      </div>
      <div className="text-[10px] text-text-subtle leading-snug">{meta.hint}</div>
      <div className="flex flex-wrap gap-1 mt-auto">
        {items.length === 0 ? (
          <div className="text-[10px] text-text-subtle italic py-2">
            Kéo ảnh vào đây · click ↑ upload · 📚 chọn từ Library
          </div>
        ) : (
          items.map(({ index, url }) => (
            <div key={index} className="relative group">
              <img src={url} alt="" className="w-12 h-12 rounded-md object-cover border border-border" />
              <button
                onClick={() => onSaveToLibrary(url)}
                className="absolute -bottom-1 -left-1 w-4 h-4 rounded-full bg-emerald-500 text-white opacity-0 group-hover:opacity-100 transition flex items-center justify-center"
                title="Lưu vào Library để reuse"
              >
                <Save className="w-2.5 h-2.5" />
              </button>
              <button
                onClick={() => onRemove(index)}
                className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-rose-500 text-white opacity-0 group-hover:opacity-100 transition flex items-center justify-center"
                title="Xoá khỏi shot này"
              >
                <X className="w-2.5 h-2.5" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ============================================================
// Helpers
// ============================================================
function bucketByRole(value: ReferenceZonesValue): Record<ZoneKey, Array<{ index: number; url: string }>> {
  const out: Record<ZoneKey, Array<{ index: number; url: string }>> = {
    character: [],
    product: [],
    storyboard: [],
  };
  value.images.forEach((url, i) => {
    if (value.storyboardImages.includes(url)) {
      out.storyboard.push({ index: i, url });
      return;
    }
    const role = value.roles[i];
    if (role === 'primary_subject' || role === 'secondary_subject') {
      out.character.push({ index: i, url });
    } else if (role === 'product_hero' || role === 'product_detail' || role === 'brand_asset') {
      out.product.push({ index: i, url });
    } else {
      out.storyboard.push({ index: i, url });
    }
  });
  return out;
}
