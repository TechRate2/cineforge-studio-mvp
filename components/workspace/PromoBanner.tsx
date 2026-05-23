'use client';

import { useState } from 'react';
import { Sparkles, X } from 'lucide-react';

export function PromoBanner() {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;
  return (
    <div className="relative shrink-0 h-9 bg-gradient-to-r from-brand-700 via-fuchsia-600 to-emerald-500 text-white flex items-center justify-center px-4 text-[12.5px] font-medium tracking-tight overflow-hidden">
      <Sparkles className="w-3.5 h-3.5 mr-2 opacity-90" />
      <span className="opacity-95">
        UGC Vietnam Studio · 21 model AI · GenMax TTS 12 giọng VN · Live giá AtlasCloud
      </span>
      <span className="hidden sm:inline mx-2 opacity-50">|</span>
      <span className="hidden sm:inline opacity-90">
        Beta · Giảm 30% gói Pro trong tháng này
      </span>
      <button
        onClick={() => setDismissed(true)}
        className="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 rounded-md hover:bg-white/15 flex items-center justify-center transition"
        aria-label="Dismiss"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
