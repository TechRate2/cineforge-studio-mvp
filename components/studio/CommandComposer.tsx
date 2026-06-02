'use client';

import { type Ref } from 'react';
import { ArrowRight, Link2, Loader2, Wand2 } from 'lucide-react';

export interface CommandComposerProps {
  value: string;
  chatValue?: string;
  revisionMode?: boolean;
  loading?: boolean;
  deepAnalyzeLoading?: boolean;
  productIntelligenceLoading?: boolean;
  disabled?: boolean;
  charLimit?: number;
  starterPrompts?: readonly string[];
  showStarterPrompts?: boolean;
  inputRef?: Ref<HTMLTextAreaElement>;
  onChange: (value: string) => void;
  onChatChange?: (value: string) => void;
  onSubmit: () => void | Promise<void>;
  onStarterPrompt?: (prompt: string) => void;
  onDeepAnalyze?: () => void | Promise<void>;
  onExtractProductUrl?: () => void | Promise<void>;
}

const DEFAULT_LIMIT = 3000;

export function CommandComposer({
  value,
  chatValue,
  revisionMode = false,
  loading = false,
  deepAnalyzeLoading = false,
  productIntelligenceLoading = false,
  disabled = false,
  charLimit = DEFAULT_LIMIT,
  starterPrompts = [],
  showStarterPrompts = false,
  inputRef,
  onChange,
  onChatChange,
  onSubmit,
  onStarterPrompt,
  onDeepAnalyze,
  onExtractProductUrl,
}: CommandComposerProps) {
  const currentValue = chatValue ?? value;
  const trimmed = currentValue.trim();
  const submitDisabled = disabled || loading || !trimmed;

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
          <div className="text-xs font-bold uppercase tracking-normal text-accent-cyan">
            Command
          </div>
          <h2 className="mt-1 text-lg font-extrabold text-text">What should the agent make?</h2>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-text-muted">
            Write the idea in plain language. Product details, audience, style, duration, and URLs are enough.
          </p>
        </div>
        {value.trim() && (
          <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-[10px] font-semibold uppercase text-text-subtle">
            Brief saved
          </span>
        )}
      </div>

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
            ? 'Ask for a revision, for example: make shot 2 more premium and keep the same product angle.'
            : 'Example: Create a 30s vertical product launch video for a VN beauty serum, premium but creator-native, with a proof-first hook.'
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
              Extract URL
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
              Deep analyze
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
            Preview pipeline
          </button>
        </div>
      </div>
    </section>
  );
}
