'use client';
import { useState } from 'react';
import { X, Sparkles } from 'lucide-react';

export function AnnouncementBar() {
  const [hidden, setHidden] = useState(false);
  if (hidden) return null;
  return (
    <div className="h-8 shrink-0 relative bg-cta-gradient text-white text-xs font-medium grid place-items-center px-4">
      <div className="flex items-center gap-2">
        <Sparkles size={12} />
        <span>
          <b>New</b> · Reference Chaining + Cost Gate Draft-First — render 5× rẻ hơn cho plan sketch.
        </span>
      </div>
      <button
        onClick={() => setHidden(true)}
        className="absolute right-3 top-1/2 -translate-y-1/2 opacity-80 hover:opacity-100"
        aria-label="Dismiss"
      >
        <X size={13} />
      </button>
    </div>
  );
}
