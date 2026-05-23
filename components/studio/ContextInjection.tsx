'use client';

/**
 * ContextInjection — Collapsible panel cho user paste pain points + reviews + USPs thật.
 *
 * Pattern: AI-slop tránh được bằng cách inject REAL context user paste.
 * Mọi field optional — skip được, nhưng điền → quality +30-50%.
 *
 * Drop vào StudioMain ngay trên nút "Nhờ Director đề xuất":
 *     <ContextInjection value={context} onChange={setContext} />
 */

import { useState } from 'react';
import { ChevronDown, ChevronUp, Sparkles } from 'lucide-react';

// Local type — mirrors backend/api/routes/director.py ContextInjection schema.
// Kept local so this component is not coupled to any specific data hook.
export type ContextInjectionType = {
  pain_points?: string;
  real_reviews?: string;
  usps?: string;
  forbidden_to_say?: string;
  mood_hint?: string;
};

interface Props {
  value: ContextInjectionType;
  onChange: (next: ContextInjectionType) => void;
}

export function ContextInjection({ value, onChange }: Props) {
  const [open, setOpen] = useState(false);

  const filledCount = [
    value.pain_points,
    value.real_reviews,
    value.usps,
    value.forbidden_to_say,
    value.mood_hint,
  ].filter((v) => v && v.trim().length > 0).length;

  return (
    <div className="border border-border rounded-xl bg-bg-soft/40 overflow-hidden">
      {/* Header — clickable toggle */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-bg-hover transition text-left"
      >
        <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-text">
            💉 Context Injection (Optional)
          </div>
          <div className="text-xs text-text-muted mt-0.5">
            {filledCount > 0
              ? `${filledCount}/5 trường đã điền — video sẽ TỰ NHIÊN hơn nhiều`
              : 'Paste pain points + reviews thật → AI không bịa, output authentic'}
          </div>
        </div>
        {open ? (
          <ChevronUp className="w-4 h-4 text-text-muted shrink-0" />
        ) : (
          <ChevronDown className="w-4 h-4 text-text-muted shrink-0" />
        )}
      </button>

      {/* Expanded panel */}
      {open && (
        <div className="px-4 pb-4 pt-1 space-y-3 border-t border-border/50">
          <FieldTextarea
            label="🎯 Pain Points THẬT"
            placeholder="Paste reviews/comments khách phàn nàn về sản phẩm tương tự. Vd: 'Da khô môi nứt 8h văn phòng', 'Mua serum 5 hãng vẫn rát'..."
            value={value.pain_points || ''}
            onChange={(v) => onChange({ ...value, pain_points: v })}
            hint="AI sẽ reference pain THẬT thay vì bịa generic"
            maxLength={2000}
          />

          <FieldTextarea
            label="⭐ Reviews Highlight"
            placeholder="Paste 3-5 review thật từ khách (raw, không edit). Vd: 'Em xài 2 tuần thấy khác hẳn', 'Mẹ em cũng khen mịn'..."
            value={value.real_reviews || ''}
            onChange={(v) => onChange({ ...value, real_reviews: v })}
            hint="Body sẽ paraphrase review thật → authentic"
            maxLength={3000}
          />

          <FieldTextarea
            label="💎 USPs Riêng (Brand Brief)"
            placeholder="Paste differentiator brand muốn highlight. Vd: 'Chiết xuất Hàn Quốc', 'Test 30 ngày', 'Kiểm nghiệm Bộ Y Tế'..."
            value={value.usps || ''}
            onChange={(v) => onChange({ ...value, usps: v })}
            hint="Director sẽ nhấn USP cụ thể trong storyboard"
            maxLength={1500}
          />

          <FieldTextarea
            label="🚫 Tránh Nói"
            placeholder="Vd: 'trắng vĩnh viễn', 'so sánh Lancome', tên brand đối thủ..."
            value={value.forbidden_to_say || ''}
            onChange={(v) => onChange({ ...value, forbidden_to_say: v })}
            hint="Critic sẽ flag nếu script chứa các từ này"
            maxLength={1000}
          />

          <FieldInput
            label="🎨 Mood / Tone Hint"
            placeholder="Vd: 'girl-next-door, không lộ ad', 'energetic Gen Z', 'authority bác sĩ trẻ'..."
            value={value.mood_hint || ''}
            onChange={(v) => onChange({ ...value, mood_hint: v })}
            hint="Director áp vibe này vào CinematicBrief"
            maxLength={500}
          />

          <div className="text-xs text-text-muted pt-1 border-t border-border/30 mt-3">
            💡 <strong>Tip:</strong> Càng nhiều context THẬT (≥3 trường), Critic score viral
            càng cao. Skip hết = AI tự bịa (chất lượng AI-slop, dễ flag).
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================
// Inner field components
// ============================================

function FieldTextarea({
  label,
  placeholder,
  value,
  onChange,
  hint,
  maxLength,
}: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  hint?: string;
  maxLength?: number;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-text mb-1.5">{label}</label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        rows={3}
        className="w-full px-3 py-2 text-sm rounded-lg bg-bg border border-border focus:border-brand-500 focus:outline-none resize-y min-h-[72px] text-text placeholder:text-text-subtle"
      />
      {hint && (
        <div className="flex items-center justify-between mt-1">
          <span className="text-[10px] text-text-muted">{hint}</span>
          {maxLength && (
            <span className="text-[10px] text-text-subtle">
              {value.length}/{maxLength}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

function FieldInput({
  label,
  placeholder,
  value,
  onChange,
  hint,
  maxLength,
}: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  hint?: string;
  maxLength?: number;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-text mb-1.5">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        className="w-full px-3 py-2 text-sm rounded-lg bg-bg border border-border focus:border-brand-500 focus:outline-none text-text placeholder:text-text-subtle"
      />
      {hint && <div className="text-[10px] text-text-muted mt-1">{hint}</div>}
    </div>
  );
}
