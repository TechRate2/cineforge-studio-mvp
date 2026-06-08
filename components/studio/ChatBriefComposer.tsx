'use client';

import type { ReactNode, Ref } from 'react';
import { ArrowRight, Link2, Loader2, MessageSquare, Wand2 } from 'lucide-react';
import type { StudioLanguage } from './studio-i18n';
import { t } from './studio-i18n';

export interface ChatBriefMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  intent?: 'idea' | 'revision';
}

export interface ChatBriefComposerProps {
  value: string;
  chatValue?: string;
  messages?: readonly ChatBriefMessage[];
  revisionMode?: boolean;
  loading?: boolean;
  deepAnalyzeLoading?: boolean;
  productIntelligenceLoading?: boolean;
  disabled?: boolean;
  charLimit?: number;
  starterPrompts?: readonly string[];
  showStarterPrompts?: boolean;
  inputRef?: Ref<HTMLTextAreaElement>;
  language?: StudioLanguage;
  statusChips?: readonly string[];
  settingsSlot?: ReactNode;
  onChange: (value: string) => void;
  onChatChange?: (value: string) => void;
  onSubmit: () => void | Promise<void>;
  onStarterPrompt?: (prompt: string) => void;
  onDeepAnalyze?: () => void | Promise<void>;
  onExtractProductUrl?: () => void | Promise<void>;
}

const DEFAULT_LIMIT = 3000;

export function ChatBriefComposer({
  value,
  chatValue,
  messages = [],
  revisionMode = false,
  loading = false,
  deepAnalyzeLoading = false,
  productIntelligenceLoading = false,
  disabled = false,
  charLimit = DEFAULT_LIMIT,
  starterPrompts = [],
  showStarterPrompts = false,
  inputRef,
  language = 'vi',
  statusChips = [],
  settingsSlot,
  onChange,
  onChatChange,
  onSubmit,
  onStarterPrompt,
  onDeepAnalyze,
  onExtractProductUrl,
}: ChatBriefComposerProps) {
  const currentValue = chatValue ?? value;
  const trimmed = currentValue.trim();
  const submitDisabled = disabled || loading || !trimmed;
  const visibleMessages = messages.slice(-6);

  const handleTextChange = (nextValue: string) => {
    const clipped = nextValue.slice(0, charLimit);
    if (onChatChange) {
      onChatChange(clipped);
      return;
    }
    onChange(clipped);
  };

  return (
    <section className="rounded-sheet border border-hairline bg-surface-1 p-4 shadow-card-soft">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-normal text-accent-cyan">
            <MessageSquare size={14} />
            Chat Agent
          </div>
          <h2 className="mt-1 text-xl font-extrabold text-text">{t(language, 'idea')}</h2>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-text-muted">{t(language, 'ideaHint')}</p>
        </div>
        {value.trim() && (
          <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-[10px] font-semibold uppercase text-text-subtle">
            {language === 'vi' ? 'Đã lưu brief' : 'Brief saved'}
          </span>
        )}
      </div>

      {statusChips.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {statusChips.map((chip) => (
            <span key={chip} className="rounded-full border border-hairline bg-surface-2 px-3 py-1 text-xs font-semibold text-text-muted">
              {chip}
            </span>
          ))}
        </div>
      )}

      {visibleMessages.length > 0 && (
        <div className="mb-3 grid max-h-[260px] gap-2 overflow-y-auto pr-1">
          {visibleMessages.map((message) => (
            <div
              key={message.id}
              className={`max-w-[92%] rounded-card border px-3 py-2 text-xs leading-relaxed ${
                message.role === 'user'
                  ? 'ml-auto border-accent-cyan/25 bg-accent-cyan/10 text-text'
                  : 'mr-auto border-hairline bg-surface-2 text-text-muted'
                }`}
            >
              {message.role === 'assistant' ? localizeAssistantMessage(message.text, language) : message.text}
            </div>
          ))}
        </div>
      )}

      {showStarterPrompts && starterPrompts.length > 0 && (
        <div className="mb-3 grid gap-2 sm:grid-cols-2">
          {starterPrompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => {
                if (onStarterPrompt) onStarterPrompt(prompt);
                else handleTextChange(prompt);
              }}
              className="rounded-card border border-hairline bg-surface-2 px-3 py-2 text-left text-xs leading-relaxed text-text-muted transition hover:border-accent-cyan/40 hover:bg-surface-3 hover:text-text"
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      <textarea
        ref={inputRef}
        value={currentValue}
        onChange={(event) => handleTextChange(event.target.value)}
        onKeyDown={(event) => {
          if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
            event.preventDefault();
            if (!submitDisabled) void onSubmit();
          }
        }}
        placeholder={
          revisionMode
            ? (language === 'vi'
              ? 'Ví dụ: làm shot 2 cao cấp hơn, giữ nguyên góc sản phẩm và vai trò tham chiếu.'
              : 'Example: make shot 2 more premium and keep the same product angle.')
            : (language === 'vi'
              ? 'Ví dụ: Tạo video 15s dọc cho serum làm đẹp tại thị trường Việt Nam, mở đầu bằng bằng chứng hiệu quả, phong cách creator cao cấp.'
              : 'Example: Create a 15s vertical product launch video for a VN beauty serum, premium but creator-native.')
        }
        className="min-h-[150px] w-full resize-y rounded-card border border-hairline bg-surface-2 px-3 py-3 text-sm leading-relaxed text-text outline-none transition placeholder:text-text-subtle focus:border-accent-cyan/60 focus:ring-2 focus:ring-accent-cyan/15"
      />

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {onExtractProductUrl && (
            <button
              type="button"
              onClick={() => void onExtractProductUrl()}
              disabled={productIntelligenceLoading || loading}
              className="btn-outline px-3 py-2 text-xs"
            >
              {productIntelligenceLoading ? <Loader2 size={14} className="animate-spin" /> : <Link2 size={14} />}
              {language === 'vi' ? 'Đọc URL sản phẩm' : 'Extract URL'}
            </button>
          )}
          {onDeepAnalyze && (
            <button
              type="button"
              onClick={() => void onDeepAnalyze()}
              disabled={deepAnalyzeLoading || loading}
              className="btn-outline px-3 py-2 text-xs"
            >
              {deepAnalyzeLoading ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />}
              {language === 'vi' ? 'Phân tích sâu' : 'Deep analyze'}
            </button>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-semibold uppercase text-text-subtle">
            {currentValue.length}/{charLimit}
          </span>
          <button
            type="button"
            onClick={() => void onSubmit()}
            disabled={submitDisabled}
            className="inline-flex items-center gap-2 rounded-card bg-cta-gradient px-4 py-2 text-sm font-bold text-white shadow-cta-glow transition hover:brightness-110 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-45"
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />}
            {language === 'vi' ? 'Cho Agent lập kế hoạch' : 'Preview plan'}
          </button>
        </div>
      </div>

      {settingsSlot && <div className="mt-4">{settingsSlot}</div>}
    </section>
  );
}

function localizeAssistantMessage(text: string, language: StudioLanguage): string {
  if (language !== 'vi') return text;
  const trimmed = text.trim();
  if (trimmed === 'Approved. I can render this plan now.') {
    return 'Đã phê duyệt. Tôi có thể render kế hoạch này ngay.';
  }
  if (trimmed === 'I need one detail before building the render plan.') {
    return 'Tôi cần thêm một chi tiết trước khi dựng kế hoạch render.';
  }
  const revised = trimmed.match(/^I revised the (.+?) plan around your notes\. Review the updated script and storyboard, then approve to render\.$/);
  if (revised) {
    return `Tôi đã chỉnh kế hoạch ${revised[1]} theo ghi chú của bạn. Hãy xem lại kịch bản và storyboard, rồi phê duyệt để render.`;
  }
  const drafted = trimmed.match(/^I drafted a (.+?) plan: (.+?)\. Review the script and storyboard, edit the brief if needed, then approve to render\.$/);
  if (drafted) {
    return `Tôi đã dựng kế hoạch ${drafted[1]}: ${drafted[2]}. Hãy xem kịch bản và storyboard, chỉnh brief nếu cần, rồi phê duyệt để render.`;
  }
  return text;
}
