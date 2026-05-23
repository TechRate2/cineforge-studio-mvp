'use client';

/**
 * WorkspaceChat — Sidebar chat panel cho user trò chuyện với Director Agent
 * để revise plan đang xem. User gõ "đổi shot 3 sang night" → POST /director/revise
 * → assistant trả revised plan + diff summary → user click Apply để swap vào editor.
 *
 * Designed as a collapsible right sidebar in DirectorPlanModal (mounted next to
 * DirectorPlanTab when prop `chat={true}` is set).
 */

import { useEffect, useRef, useState } from 'react';
import {
  MessageSquare, Send, Loader2, Sparkles, Check, AlertTriangle, ChevronRight,
} from 'lucide-react';
import type { DirectorPlan } from '@/lib/studio/use-director-plan';
import type { VideoSettings } from '@/lib/types/backend';
import { useWorkspaceChat } from '@/lib/studio/use-workspace-chat';

interface Props {
  plan: DirectorPlan;
  settings: VideoSettings;
  /** Caller swaps the revised plan into its editor when user clicks Apply. */
  onApplyRevision: (revised: DirectorPlan) => void;
  /** Optional: lets caller minimize the sidebar */
  onCollapse?: () => void;
}

const SAMPLE_PROMPTS = [
  'Đổi shot 1 sang ban đêm',
  'Tăng total duration lên 20s',
  'Soft mood hơn, ít dramatic',
  'Thêm 1 shot CTA cuối',
];

export function WorkspaceChat({ plan, settings, onApplyRevision, onCollapse }: Props) {
  const chat = useWorkspaceChat();
  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chat.turns.length, chat.busy]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || chat.busy) return;
    setInput('');
    void chat.send(text, plan, settings);
  };

  return (
    <div className="flex flex-col h-full bg-bg-card border-l border-border w-[340px]">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <div className="flex items-center gap-1.5">
          <MessageSquare className="w-3.5 h-3.5 text-fuchsia-300" />
          <span className="text-xs font-semibold text-text">Director Chat</span>
        </div>
        {onCollapse && (
          <button onClick={onCollapse} className="p-1 rounded hover:bg-bg-hover text-text-muted" title="Thu gọn">
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {chat.turns.length === 0 ? (
          <div className="space-y-3">
            <div className="text-xs text-text-subtle">
              Hỏi Director Agent điều chỉnh plan. Ví dụ:
            </div>
            <div className="space-y-1.5">
              {SAMPLE_PROMPTS.map((p) => (
                <button
                  key={p}
                  onClick={() => setInput(p)}
                  className="block w-full text-left text-xs px-2.5 py-1.5 rounded-md bg-bg-soft border border-border text-text-muted hover:text-text hover:border-brand-500/30 transition"
                >
                  <Sparkles className="inline w-3 h-3 mr-1 text-brand-300" />{p}
                </button>
              ))}
            </div>
          </div>
        ) : (
          chat.turns.map((t) => (
            <Turn key={t.id} turn={t} onApply={() => {
              if (t.revisedPlan) {
                onApplyRevision(t.revisedPlan);
                chat.markApplied(t.id);
              }
            }} />
          ))
        )}
        {chat.busy && (
          <div className="flex items-center gap-2 text-xs text-text-subtle px-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Director đang revise…
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-border p-2.5">
        <div className="flex items-start gap-1.5">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                handleSend();
              }
            }}
            rows={2}
            placeholder="Yêu cầu chỉnh sửa… (Ctrl/Cmd+Enter để gửi)"
            className="flex-1 bg-bg-soft border border-border rounded px-2 py-1.5 text-xs text-text focus:outline-none focus:border-brand-500 placeholder:text-text-subtle resize-none"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || chat.busy}
            className="p-2 rounded bg-gradient-to-br from-brand-500 to-fuchsia-500 text-white disabled:opacity-40"
            title="Gửi (Ctrl/Cmd+Enter)"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="text-[10px] text-text-subtle mt-1.5">
          Director sẽ revise plan + trả diff summary. Click "Apply" để áp vào editor.
        </div>
      </div>
    </div>
  );
}

// ============================================================
// Single turn
// ============================================================
function Turn({
  turn, onApply,
}: { turn: ReturnType<typeof useWorkspaceChat>['turns'][number]; onApply: () => void }) {
  if (turn.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] bg-brand-500/15 border border-brand-500/30 rounded-lg rounded-tr-sm px-3 py-1.5 text-xs text-text">
          {turn.text}
        </div>
      </div>
    );
  }
  // assistant
  return (
    <div className="space-y-1.5">
      <div className="flex items-start gap-1.5">
        <Sparkles className="w-3 h-3 text-fuchsia-300 mt-0.5 shrink-0" />
        <div className="text-xs text-text-muted leading-relaxed flex-1">{turn.text}</div>
      </div>
      {turn.error && (
        <div className="ml-4 px-2 py-1 rounded bg-rose-500/10 border border-rose-500/30 text-rose-200 text-[10px]">
          <AlertTriangle className="inline w-2.5 h-2.5 mr-1" /> {turn.error}
        </div>
      )}
      {turn.revisedPlan && !turn.applied && (
        <button
          onClick={onApply}
          className="ml-4 text-[10px] px-2 py-1 rounded bg-emerald-500/15 border border-emerald-500/30 text-emerald-200 hover:bg-emerald-500/25 inline-flex items-center gap-1"
        >
          <Check className="w-2.5 h-2.5" /> Apply revision
        </button>
      )}
      {turn.applied && (
        <div className="ml-4 text-[10px] text-emerald-300 inline-flex items-center gap-1">
          <Check className="w-2.5 h-2.5" /> Đã apply vào editor
        </div>
      )}
    </div>
  );
}
