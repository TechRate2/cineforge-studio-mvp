'use client';
import { useState } from 'react';
import { Check, AlertTriangle, Film, BookText, Gauge, Loader2, Sparkles, LayoutGrid, RotateCcw, Download } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import type { LucideIcon } from 'lucide-react';
import type { DirectorPlan, Shot, StorytellingIssue } from '@/lib/studio/use-director-plan';
import { useMasterBoard } from '@/lib/studio/use-master-board';
import { useRefineShot } from '@/lib/studio/use-refine-shot';

interface Props {
  open: boolean;
  onClose: () => void;
  plan: DirectorPlan | null;
  onApprove: () => void;
  isRendering?: boolean;
  storytellingIssues?: StorytellingIssue[];
  referenceImages?: string[];
  settings?: Record<string, unknown>;
  onRefineJobStarted?: (jobId: string) => void;
}

type Tab = 'bible' | 'shots' | 'board' | 'eval';

export function DirectorPlanModal({
  open, onClose, plan, onApprove, isRendering,
  storytellingIssues = [],
  referenceImages = [],
  settings = {},
  onRefineJobStarted,
}: Props) {
  const [tab, setTab] = useState<Tab>('bible');
  const master = useMasterBoard();
  const refine = useRefineShot();

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={plan?.continuity_bible.title || 'Director Plan'}
      subtitle={plan ? `${plan.shot_list.length} shots · ${plan.continuity_bible.duration_s}s · ${plan.continuity_bible.aspect_ratio}` : undefined}
      maxWidth="max-w-6xl"
    >
      {!plan ? (
        <PlanSkeleton />
      ) : (
        <div className="flex flex-col h-full">
          {/* Tabs */}
          <div className="px-6 md:px-8 border-b border-hairline flex items-center gap-1 sticky top-0 bg-surface-1/95 backdrop-blur z-10">
            <TabBtn active={tab === 'bible'} onClick={() => setTab('bible')} icon={BookText} label="Continuity Bible" />
            <TabBtn active={tab === 'shots'} onClick={() => setTab('shots')} icon={Film} label={`Shot List · ${plan.shot_list.length}`} />
            <TabBtn active={tab === 'board'} onClick={() => setTab('board')} icon={LayoutGrid} label="Storyboard Board" />
            <TabBtn active={tab === 'eval'} onClick={() => setTab('eval')} icon={Gauge} label="Evaluation" badge={plan.evaluation.overall_score} issuesCount={storytellingIssues.length} />
          </div>

          {/* Content */}
          <div className="flex-1 min-h-0 overflow-y-auto px-6 md:px-8 py-6">
            {tab === 'bible' && <BibleView plan={plan} />}
            {tab === 'shots' && (
              <ShotsView
                shots={plan.shot_list}
                onRefine={async (shotId) => {
                  try {
                    const res = await refine.refine({
                      plan, shotId,
                      referenceImages,
                      settings,
                    });
                    onRefineJobStarted?.(res.job_id);
                  } catch (e) {
                    console.error('Refine fail', e);
                  }
                }}
                refiningShotId={refine.isLoading ? refine.lastResponse?.shot_id ?? '__pending__' : null}
              />
            )}
            {tab === 'board' && (
              <BoardView
                plan={plan}
                board={master.board}
                isLoading={master.isLoading}
                error={master.error}
                onGen={() => master.generate(plan)}
              />
            )}
            {tab === 'eval' && (
              <EvalView plan={plan} storytellingIssues={storytellingIssues} />
            )}
          </div>

          {/* Footer */}
          <footer className="border-t border-hairline px-6 md:px-8 py-4 flex items-center justify-between gap-3 bg-surface-1/80 backdrop-blur">
            <div className="flex items-center gap-3 text-xs text-text-muted">
              <span>Plan ID: <code className="text-text">{plan.plan_id}</code></span>
              <span>·</span>
              <span>${plan.cost_estimate.total_cost_usd.toFixed(2)} ước tính render</span>
            </div>
            <div className="flex gap-2">
              <button onClick={onClose} className="btn-outline">Close</button>
              <button
                onClick={onApprove}
                disabled={isRendering || (plan.evaluation.red_flags || []).length > 0}
                className="btn-cta"
              >
                {isRendering ? (
                  <><Loader2 size={15} className="animate-spin" /> Rendering...</>
                ) : (
                  <><Sparkles size={15} /> Approve &amp; Render</>
                )}
              </button>
            </div>
          </footer>
        </div>
      )}
    </Modal>
  );
}

function TabBtn({ active, onClick, icon: Icon, label, badge, issuesCount }: {
  active: boolean; onClick: () => void; icon: LucideIcon; label: string; badge?: number; issuesCount?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={`relative px-4 py-3 flex items-center gap-2 text-sm font-medium transition
                  ${active ? 'text-text' : 'text-text-muted hover:text-text'}`}
    >
      <Icon size={15} /> {label}
      {badge !== undefined && (
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full ml-1
                          ${badge >= 8 ? 'bg-accent-green/15 text-accent-green'
                          : badge >= 6 ? 'bg-accent-yellow/15 text-accent-yellow'
                          : 'bg-accent-orange/15 text-accent-orange'}`}>
          {badge.toFixed(1)}
        </span>
      )}
      {issuesCount !== undefined && issuesCount > 0 && (
        <span className="text-[10px] px-1.5 py-0.5 rounded-full ml-1 bg-accent-orange/20 text-accent-orange font-bold">
          {issuesCount}
        </span>
      )}
      {active && <span className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full bg-cta-gradient" />}
    </button>
  );
}

// ============================================================
// Master Storyboard Board view — V4 Sprint1
// ============================================================
function BoardView({ plan, board, isLoading, error, onGen }: {
  plan: DirectorPlan;
  board: ReturnType<typeof useMasterBoard>['board'];
  isLoading: boolean;
  error: string | null;
  onGen: () => void;
}) {
  if (!board && !isLoading && !error) {
    return (
      <div className="text-center py-12">
        <div className="w-14 h-14 rounded-card bg-cta-gradient/15 grid place-items-center mx-auto mb-4 border border-accent-magenta/30">
          <LayoutGrid size={26} className="text-accent-magenta" />
        </div>
        <h3 className="h-card mb-2">Master Storyboard Board</h3>
        <p className="text-sm text-text-muted max-w-md mx-auto mb-2">
          Gen <b>1 ảnh ultra-wide</b> chứa toàn bộ {plan.shot_list.length} panel + key visual + palette swatch + sound design + notes — kiểu director's sheet.
        </p>
        <p className="text-[11px] text-text-subtle max-w-md mx-auto mb-6">
          Lợi ích: identity character lock 100% qua tất cả panel (cùng pixel canvas), chỉ <b>$0.04</b> thay vì $0.43 cho 12 panel riêng.
          Sau khi gen, board sẽ làm style reference cho mọi shot Seedance.
        </p>
        <button onClick={onGen} className="btn-cta">
          <Sparkles size={14} /> Generate Board · ~$0.04
        </button>
      </div>
    );
  }
  if (isLoading) {
    return (
      <div className="space-y-3">
        <div className="surface-2 rounded-card p-4 flex items-center gap-3">
          <Loader2 size={16} className="animate-spin text-accent-magenta" />
          <div className="text-sm">Seedream v4.5 đang dựng board... ~30-60s</div>
        </div>
        <div className="aspect-[16/9] rounded-card surface-2 shimmer" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="surface-2 rounded-card p-5 border-accent-orange/40">
        <div className="flex items-start gap-3">
          <AlertTriangle size={18} className="text-accent-orange shrink-0 mt-0.5" />
          <div>
            <div className="text-sm font-semibold text-accent-orange">Master Board gen failed</div>
            <p className="text-xs text-text-muted mt-2 font-mono">{error}</p>
            <button onClick={onGen} className="btn-outline mt-4">
              <RotateCcw size={14} /> Retry
            </button>
          </div>
        </div>
      </div>
    );
  }
  if (!board) return null;
  return (
    <div className="space-y-4">
      <div className="relative rounded-card overflow-hidden border border-hairline">
        <img src={board.board_url} alt="Master storyboard board" className="w-full" />
      </div>
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="text-xs text-text-muted">
          {board.size} · ${board.cost_usd.toFixed(3)} · {board.elapsed_s}s
        </div>
        <div className="flex gap-2">
          <a href={board.board_url} download target="_blank" rel="noopener noreferrer" className="btn-outline">
            <Download size={14} /> Download PNG
          </a>
          <button onClick={onGen} className="btn-outline">
            <RotateCcw size={14} /> Regen
          </button>
        </div>
      </div>
      <details className="surface-2 rounded-card p-3 text-xs">
        <summary className="cursor-pointer text-text-muted">Show prompt used (debug)</summary>
        <pre className="mt-3 text-[11px] text-text-subtle whitespace-pre-wrap font-mono">{board.prompt}</pre>
      </details>
    </div>
  );
}

function BibleView({ plan }: { plan: DirectorPlan }) {
  const b = plan.continuity_bible;
  return (
    <div className="space-y-6">
      <Section title="Logline & Intent">
        <p className="text-base text-text leading-relaxed">{b.logline}</p>
        <div className="flex gap-2 mt-3">
          <span className="chip">{b.intent}</span>
          <span className="chip">{b.duration_s}s</span>
          <span className="chip">{b.aspect_ratio}</span>
        </div>
      </Section>

      {b.characters.length > 0 && (
        <Section title="Characters">
          <div className="grid md:grid-cols-2 gap-3">
            {b.characters.map((c) => (
              <div key={c.id} className="surface-2 rounded-card p-4">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold">{c.name}</h4>
                  <span className="chip">{c.role}</span>
                </div>
                <p className="text-xs text-text-muted mt-2">{c.face_signature}</p>
                <p className="text-xs text-text-subtle mt-1">Outfit: {c.outfit}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {b.products.length > 0 && (
        <Section title="Products">
          {b.products.map((p) => (
            <div key={p.id} className="surface-2 rounded-card p-4 mb-2">
              <h4 className="font-semibold">{p.name}</h4>
              <p className="text-xs text-text-muted mt-1">{p.packaging_description}</p>
              {p.hero_features.length > 0 && (
                <ul className="text-xs text-text-muted mt-2 list-disc list-inside space-y-0.5">
                  {p.hero_features.map((f, i) => <li key={i}>{f}</li>)}
                </ul>
              )}
            </div>
          ))}
        </Section>
      )}

      <Section title="Visual style">
        <Kv k="Cinematography" v={b.visual_style.cinematography} />
        <Kv k="Color grading" v={b.visual_style.color_grading} />
        <Kv k="Lighting" v={b.visual_style.lighting_design} />
        <Kv k="Camera" v={b.visual_style.camera_language} />
        <Kv k="Film grain" v={b.visual_style.film_grain} />
      </Section>

      <Section title="Audio design">
        <Kv k="Mood" v={b.audio_design.mood} />
        <Kv k="Tempo" v={b.audio_design.tempo} />
        <Kv k="Music genre" v={b.audio_design.music_genre} />
        <Kv k="Dialogue style" v={b.audio_design.dialogue_style} />
      </Section>

      <Section title="Setting">
        <Kv k="Location" v={b.setting.location} />
        <Kv k="Time of day" v={b.setting.time_of_day} />
        <Kv k="Atmosphere" v={b.setting.atmosphere} />
      </Section>

      <Section title="Constraints">
        <KvList k="Must have" items={b.constraints.must_have} />
        <KvList k="Must avoid" items={b.constraints.must_avoid} />
        <KvList k="Brand safety" items={b.constraints.brand_safety} />
      </Section>

      {b.director_notes && (
        <Section title="Director notes">
          <p className="text-sm text-text-muted leading-relaxed">{b.director_notes}</p>
        </Section>
      )}
    </div>
  );
}

function ShotsView({ shots, onRefine, refiningShotId }: {
  shots: Shot[];
  onRefine?: (shotId: string) => void;
  refiningShotId?: string | null;
}) {
  return (
    <div className="space-y-3">
      {shots.map((s, i) => (
        <div key={s.shot_id} className="surface-2 rounded-card p-4">
          <div className="flex items-start justify-between gap-3 mb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="chip-gradient">S{i + 1}</span>
                <h4 className="font-semibold">{s.purpose}</h4>
              </div>
              <p className="text-xs text-text-subtle mt-1">{s.emotion_beat}</p>
            </div>
            <div className="text-right shrink-0 flex items-start gap-2">
              <div>
                <div className="text-xs text-text-muted">{s.start_s}–{s.end_s}s</div>
                <div className="text-[10px] text-text-subtle">{s.duration_s}s · {s.visual.camera_shot}</div>
              </div>
              {onRefine && (
                <button
                  onClick={() => onRefine(s.shot_id)}
                  disabled={refiningShotId === s.shot_id || refiningShotId === '__pending__'}
                  title="Re-render this shot only (~$0.20-0.30)"
                  className="btn-icon shrink-0 hover:text-accent-magenta disabled:opacity-50"
                >
                  {refiningShotId === s.shot_id ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
                </button>
              )}
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-3 text-xs">
            <div className="space-y-1.5">
              <div className="text-text-subtle uppercase text-[10px] tracking-wider">Visual</div>
              <p className="text-text"><b className="text-text-muted">Subject:</b> {s.visual.subject}</p>
              <p className="text-text"><b className="text-text-muted">Action:</b> {s.visual.action}</p>
              <p className="text-text"><b className="text-text-muted">Camera:</b> {s.visual.camera_movement}</p>
              <p className="text-text-muted">{s.visual.background}</p>
            </div>
            <div className="space-y-1.5">
              <div className="text-text-subtle uppercase text-[10px] tracking-wider">Audio</div>
              {s.audio.dialogue_vn && (
                <p className="text-text italic">"{s.audio.dialogue_vn}"</p>
              )}
              {s.audio.caption_on_screen && (
                <p className="text-accent-yellow/80">📝 {s.audio.caption_on_screen}</p>
              )}
              {s.audio.sfx.length > 0 && (
                <p className="text-text-muted">SFX: {s.audio.sfx.join(', ')}</p>
              )}
            </div>
          </div>

          {(s.continuity.reference_indices?.length > 0 || s.continuity.previous_shot_id) && (
            <div className="mt-3 pt-3 border-t border-hairline flex flex-wrap gap-1.5 text-[10px]">
              {s.continuity.previous_shot_id && (
                <span className="chip">chains from {s.continuity.previous_shot_id}</span>
              )}
              {s.continuity.reference_indices?.map((idx) => (
                <span key={idx} className="chip">@image_{idx + 1}</span>
              ))}
              <span className="chip">→ {s.model_routing.preferred_model}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function EvalView({ plan, storytellingIssues = [] }: { plan: DirectorPlan; storytellingIssues?: StorytellingIssue[] }) {
  const e = plan.evaluation;
  const scores = [
    { k: 'Overall', v: e.overall_score, w: 'wide' },
    { k: 'Consistency', v: e.consistency_score },
    { k: 'Viral potential', v: e.viral_potential_score },
    { k: 'Cinematic', v: e.cinematic_score },
    { k: 'Pacing', v: e.pacing_score },
    { k: 'Brand safety', v: e.brand_safety_score },
  ];
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {scores.map((s) => (
          <div key={s.k} className={`${s.w === 'wide' ? 'col-span-2 md:col-span-3' : ''} surface-2 rounded-card p-4`}>
            <div className="text-xs text-text-muted mb-1">{s.k}</div>
            <div className="flex items-end justify-between">
              <div className={`text-3xl font-extrabold ${
                s.v >= 8 ? 'text-accent-green' : s.v >= 6 ? 'text-accent-yellow' : 'text-accent-orange'
              }`}>
                {s.v.toFixed(1)}<span className="text-base text-text-subtle">/10</span>
              </div>
              <div className="w-20 h-1.5 rounded-full bg-surface-3 overflow-hidden">
                <div
                  className="h-full bg-cta-gradient"
                  style={{ width: `${(s.v / 10) * 100}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* V4 — Storytelling validator issues (PRODUCT_OPENS, MISSING_HOOK, etc.) */}
      {storytellingIssues.length > 0 && (
        <section>
          <h3 className="text-[11px] uppercase tracking-wider text-text-subtle mb-3 font-semibold">
            Storytelling rule check · {storytellingIssues.length} issue{storytellingIssues.length > 1 ? 's' : ''}
          </h3>
          <ul className="space-y-2">
            {storytellingIssues.map((iss, i) => (
              <li key={i}
                  className={`px-3 py-2.5 rounded-md border text-sm flex items-start gap-2
                              ${iss.severity === 'error'
                                ? 'border-accent-orange/40 bg-accent-orange/8 text-accent-orange'
                                : 'border-accent-yellow/40 bg-accent-yellow/8 text-accent-yellow'}`}>
                <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                <div className="flex-1">
                  <div className="font-mono text-[10px] mb-0.5">[{iss.severity.toUpperCase()}] {iss.code}{iss.shot_id ? ` · ${iss.shot_id}` : ''}</div>
                  <div className="text-text">{iss.message}</div>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {e.red_flags?.length > 0 && (
        <FlagList title="Red flags" items={e.red_flags} tone="rose" icon={AlertTriangle} />
      )}
      {e.strengths?.length > 0 && (
        <FlagList title="Strengths" items={e.strengths} tone="green" icon={Check} />
      )}
      {e.weaknesses?.length > 0 && (
        <FlagList title="Weaknesses" items={e.weaknesses} tone="orange" icon={AlertTriangle} />
      )}
      {e.suggestions?.length > 0 && (
        <FlagList title="Suggestions" items={e.suggestions} tone="cyan" icon={Sparkles} />
      )}
    </div>
  );
}

function FlagList({ title, items, tone, icon: Icon }: {
  title: string; items: string[]; tone: 'rose' | 'green' | 'orange' | 'cyan';
  icon: LucideIcon;
}) {
  const colorMap = {
    rose: 'border-accent-orange/40 bg-accent-orange/8 text-accent-orange',
    green: 'border-accent-green/40 bg-accent-green/8 text-accent-green',
    orange: 'border-accent-yellow/40 bg-accent-yellow/8 text-accent-yellow',
    cyan: 'border-accent-cyan/40 bg-accent-cyan/8 text-accent-cyan',
  } as const;
  return (
    <Section title={title}>
      <ul className="space-y-2">
        {items.map((it, i) => (
          <li key={i} className={`px-3 py-2.5 rounded-md border text-sm flex items-start gap-2 ${colorMap[tone]}`}>
            <Icon size={14} className="mt-0.5 shrink-0" />
            <span className="text-text">{it}</span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-[11px] uppercase tracking-wider text-text-subtle mb-3 font-semibold">{title}</h3>
      {children}
    </section>
  );
}
function Kv({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-3 text-sm py-1">
      <span className="text-text-subtle min-w-[120px]">{k}</span>
      <span className="text-text flex-1">{v || '—'}</span>
    </div>
  );
}
function KvList({ k, items }: { k: string; items: string[] }) {
  return (
    <div className="flex gap-3 text-sm py-1">
      <span className="text-text-subtle min-w-[120px]">{k}</span>
      <span className="text-text flex-1">
        {items?.length ? items.join(' · ') : '—'}
      </span>
    </div>
  );
}

function PlanSkeleton() {
  return (
    <div className="p-8 space-y-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="h-20 rounded-card surface-2 shimmer" />
      ))}
    </div>
  );
}
