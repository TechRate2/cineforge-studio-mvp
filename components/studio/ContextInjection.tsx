'use client';
import { useState } from 'react';
import { ChevronDown, Lightbulb } from 'lucide-react';

export interface ContextValue {
  pain_points?: string;
  real_reviews?: string;
  usps?: string;
  forbidden_to_say?: string;
  mood_hint?: string;
}

interface Props {
  value: ContextValue;
  onChange: (v: ContextValue) => void;
}

const FIELDS: { key: keyof ContextValue; label: string; placeholder: string }[] = [
  { key: 'pain_points', label: 'Pain points', placeholder: 'vd: da khô bong tróc, son bị khô môi sau 2h...' },
  { key: 'usps', label: 'USPs', placeholder: 'vd: dưỡng ẩm 8h, giá 89k, vegan...' },
  { key: 'real_reviews', label: 'Real reviews', placeholder: 'Trích đoạn review thật để LLM dùng tone tự nhiên...' },
  { key: 'forbidden_to_say', label: 'Forbidden claims', placeholder: 'vd: KHÔNG nói "chữa bệnh", KHÔNG so sánh đối thủ...' },
  { key: 'mood_hint', label: 'Mood hint', placeholder: 'vd: chill, hài hước, drama, FOMO...' },
];

export function ContextInjection({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const filledCount = Object.values(value).filter((v) => v && v.trim()).length;

  return (
    <div className="surface-2 rounded-card">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-3 px-5 py-4 hover:bg-surface-3 transition rounded-card"
      >
        <div className="flex items-center gap-3">
          <Lightbulb size={16} className="text-accent-yellow" />
          <div className="text-left">
            <div className="text-sm font-semibold">Context injection</div>
            <div className="text-[11px] text-text-subtle">
              {filledCount > 0
                ? `${filledCount}/5 trường đã điền — tone & angle sắc hơn`
                : 'Tuỳ chọn — pain points, USPs, forbidden claims...'}
            </div>
          </div>
        </div>
        <ChevronDown size={16} className={`text-text-muted transition ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="px-5 pb-5 grid md:grid-cols-2 gap-3 border-t border-hairline pt-4">
          {FIELDS.map((f) => (
            <div key={f.key} className={f.key === 'real_reviews' || f.key === 'forbidden_to_say' ? 'md:col-span-2' : ''}>
              <label className="text-[11px] uppercase tracking-wider text-text-subtle">{f.label}</label>
              <textarea
                value={value[f.key] ?? ''}
                onChange={(e) => onChange({ ...value, [f.key]: e.target.value })}
                placeholder={f.placeholder}
                rows={2}
                className="field mt-1 text-sm resize-none"
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
