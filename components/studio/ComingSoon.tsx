import { Construction, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

export function ComingSoon({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="px-5 md:px-10 py-16 max-w-container mx-auto">
      <div className="surface-2 rounded-sheet p-12 text-center">
        <div className="w-14 h-14 rounded-card bg-cta-gradient/15 grid place-items-center mx-auto mb-4 border border-accent-magenta/30">
          <Construction size={26} className="text-accent-magenta" />
        </div>
        <h1 className="h-section mb-3">{title}</h1>
        <p className="text-sm text-text-muted max-w-md mx-auto">
          {hint || 'Tính năng này đang được wire vào pipeline. Hiện tại vào Director Studio để build video từ brief.'}
        </p>
        <Link href="/studio" className="btn-cta mt-6">
          <ArrowLeft size={14} /> Quay về Director Studio
        </Link>
      </div>
    </div>
  );
}
