'use client';
import { useState, useRef } from 'react';
import { Play, Eye } from 'lucide-react';

export type MentionChip = {
  id: string;
  label: string;
  type?: 'image' | 'character' | 'video' | 'audio';
};

export type FormatCard = {
  id: string;
  label: string;
  video: string;
  cost: number;
  chips?: MentionChip[];
  headerLabel?: string;
  body: string;
  productImg?: string | null;
  avatarImg?: string | null;
};

/**
 * InspirationCard — chỉ hiển thị video demo + nhãn category, KHÔNG còn button "Dùng template này".
 * 24 video bên dưới Hero giờ là INSPIRATION GALLERY, không phải template picker.
 * User chọn template thật ở "Bước 2" qua TemplatePickerModal.
 */
function InspirationCard({ c }: { c: FormatCard }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isHover, setIsHover] = useState(false);

  const handleMouseEnter = () => {
    setIsHover(true);
    const v = videoRef.current;
    if (v) {
      v.currentTime = 0;
      v.play().catch(() => {});
    }
  };
  const handleMouseLeave = () => {
    setIsHover(false);
    const v = videoRef.current;
    if (v) {
      v.pause();
      v.currentTime = 0;
    }
  };

  return (
    <div
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className="relative aspect-[3/4] rounded-2xl overflow-hidden border border-white/10 bg-black group cursor-default hover:border-white/30 transition-all duration-300"
    >
      <video
        ref={videoRef}
        src={c.video}
        muted
        loop
        playsInline
        preload="metadata"
        className="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/10 to-transparent pointer-events-none" />

      {/* Top label */}
      <div className="absolute top-2.5 left-2.5 right-2.5 flex items-start justify-between gap-2">
        <span className="px-2 py-0.5 rounded-md bg-black/60 backdrop-blur text-white text-[10px] font-semibold border border-white/20">
          {c.label}
        </span>
        <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-white/10 backdrop-blur text-white/70 text-[9px] font-medium border border-white/20">
          <Eye className="w-2.5 h-2.5" /> Demo
        </span>
      </div>

      {/* Bottom — body preview only, no button */}
      <div className="absolute inset-x-0 bottom-0 p-3">
        <p className="text-[10px] text-white/70 leading-relaxed line-clamp-2">
          {c.body.slice(0, 100)}
          {c.body.length > 100 ? '…' : ''}
        </p>
      </div>

      {/* Play icon center khi không hover */}
      <div
        className={`absolute inset-0 flex items-center justify-center pointer-events-none transition-opacity ${
          isHover ? 'opacity-0' : 'opacity-100'
        }`}
      >
        <div className="w-10 h-10 rounded-full bg-white/15 backdrop-blur border border-white/30 flex items-center justify-center">
          <Play className="w-3.5 h-3.5 fill-white text-white ml-0.5" />
        </div>
      </div>
    </div>
  );
}

/**
 * InspirationGallery — replaces GenerateFormats.
 * Hiển thị 24 video demo từ Higgsfield API như cảm hứng, KHÔNG còn action.
 */
export function GenerateFormats({ cards }: { cards: FormatCard[] }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {cards.map((c) => (
        <InspirationCard key={c.id} c={c} />
      ))}
    </div>
  );
}
