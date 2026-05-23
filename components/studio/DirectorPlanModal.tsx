'use client';
import { useState } from 'react';
import { Check, AlertTriangle, Film, BookText, Gauge, Loader2, Sparkles } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import type { LucideIcon } from 'lucide-react';
import type { DirectorPlan, Shot } from '@/lib/studio/use-director-plan';

interface Props {
  open: boolean;
  onClose: () => void;
  plan: DirectorPlan | null;
  onApprove: () => void;
  isRendering?: boolean;
}

type Tab = 'bible' | 'shots' | 'eval';

export function DirectorPlanModal({ open, onClose, plan, onApprove, isRendering }: Props) {
  const [tab, setTab] = useState<Tab>('bible');

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
            <TabBtn active={tab === 'eval'} onClick={() => setTab('eval')} icon={Gauge} label="Evaluation" badge={plan.evaluation.overall_score} />
          </div>

          {/* Content */}
          <div className="flex-1 min-h-0 overflow-y-auto px-6 md:px-8 py-6">
            {tab === 'bible' && <BibleView plan={plan} />}
            {tab === 'shots' && <ShotsView shots={plan.shot_list} />}
            {tab === 'eval' && <EvalView plan={plan} />}
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

function TabBtn({ active, onClick, icon: Icon, label, badge }: {
  active: boolean; onClick: () => void; icon: LucideIcon; label: string; badge?: number;
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
      {active && <span className="absolute bottom-0 left-2 right-2 h-0.5 rounded-full bg-cta-gradient" />}
    </button>
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

function ShotsView({ shots }: { shots: Shot[] }) {
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
            <div className="text-right shrink-0">
              <div className="text-xs text-text-muted">{s.start_s}–{s.end_s}s</div>
              <div className="text-[10px] text-text-subtle">{s.duration_s}s · {s.visual.camera_shot}</div>
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

function EvalView({ plan }: { plan: DirectorPlan }) {
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
