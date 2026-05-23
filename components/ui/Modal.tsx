'use client';
import { X } from 'lucide-react';
import { useEffect } from 'react';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  maxWidth?: string;
  title?: string;
  subtitle?: string;
  showClose?: boolean;
}

export function Modal({
  open, onClose, children, maxWidth = 'max-w-4xl',
  title, subtitle, showClose = true,
}: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-8 animate-fade-in">
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-md"
        onClick={onClose}
        aria-hidden
      />
      <div
        className={`relative w-full ${maxWidth} max-h-[90vh] flex flex-col
                    glass-card border-hairline-strong overflow-hidden animate-fade-up`}
      >
        {(title || showClose) && (
          <div className="flex items-start justify-between gap-4 px-6 md:px-8 py-5 border-b border-hairline">
            <div className="min-w-0">
              {title && <h2 className="text-xl md:text-2xl font-bold tracking-tight">{title}</h2>}
              {subtitle && <p className="text-sm text-text-muted mt-1">{subtitle}</p>}
            </div>
            {showClose && (
              <button onClick={onClose} className="btn-icon shrink-0" aria-label="Close">
                <X size={18} />
              </button>
            )}
          </div>
        )}
        <div className="flex-1 min-h-0 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

export function Drawer({
  open, onClose, children, side = 'right', width = 'w-[min(90vw,560px)]',
  title,
}: {
  open: boolean; onClose: () => void; children: React.ReactNode;
  side?: 'right' | 'left'; width?: string; title?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div
        className={`absolute top-0 ${side === 'right' ? 'right-0' : 'left-0'} h-full ${width}
                    bg-surface-1 border-l border-hairline shadow-2xl
                    flex flex-col animate-fade-up`}
      >
        {title && (
          <div className="flex items-center justify-between px-5 py-4 border-b border-hairline">
            <h3 className="text-base font-semibold">{title}</h3>
            <button onClick={onClose} className="btn-icon"><X size={16} /></button>
          </div>
        )}
        <div className="flex-1 min-h-0 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
