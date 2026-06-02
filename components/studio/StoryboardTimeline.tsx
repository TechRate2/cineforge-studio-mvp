'use client';

import { Copy, Film, Volume2 } from 'lucide-react';

export interface StoryboardTimelineScene {
  id: string;
  label?: string;
  durationS?: number;
  prompt?: string;
  visual?: string;
  camera?: string;
  audio?: string;
  refs?: readonly string[];
  status?: string;
  spendUsd?: number;
}

export interface StoryboardTimelineProps {
  scenes: readonly StoryboardTimelineScene[];
  activeSceneId?: string | null;
  onSelectScene: (id: string) => void;
  onCopyPrompt?: (prompt: string) => void | Promise<void>;
}

function sceneTitle(scene: StoryboardTimelineScene, index: number) {
  return scene.label?.trim() || `Shot ${index + 1}`;
}

export function StoryboardTimeline({
  scenes,
  activeSceneId,
  onSelectScene,
  onCopyPrompt,
}: StoryboardTimelineProps) {
  const activeScene = scenes.find((scene) => scene.id === activeSceneId) ?? scenes[0] ?? null;

  return (
    <section className="rounded-sheet border border-hairline bg-surface-1 p-4 shadow-card-soft">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs font-bold uppercase tracking-normal text-accent-cyan">
            Storyboard
          </div>
          <h2 className="mt-1 text-lg font-extrabold text-text">Shot timeline</h2>
        </div>
        <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-[10px] font-semibold uppercase text-text-subtle">
          {scenes.length} shot{scenes.length === 1 ? '' : 's'}
        </span>
      </div>

      {scenes.length === 0 ? (
        <div className="rounded-card border border-dashed border-hairline bg-surface-2 px-4 py-8 text-center">
          <Film size={20} className="mx-auto mb-2 text-accent-cyan" />
          <div className="text-sm font-bold text-text">No storyboard yet</div>
          <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-text-muted">
            Send a command first. The agent will turn the idea into reviewable shots before render approval.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <div className="grid gap-2">
            {scenes.map((scene, index) => {
              const active = activeScene?.id === scene.id;
              return (
                <button
                  key={scene.id}
                  type="button"
                  onClick={() => onSelectScene(scene.id)}
                  className={`rounded-card border px-3 py-3 text-left transition ${
                    active
                      ? 'border-accent-cyan/45 bg-accent-cyan/10'
                      : 'border-hairline bg-surface-2 hover:border-accent-cyan/35 hover:bg-surface-3'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-bold text-text">{sceneTitle(scene, index)}</span>
                    <span className="rounded-full border border-hairline bg-surface-1 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
                      {scene.durationS ? `${scene.durationS}s` : 'auto'}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-text-muted">
                    {scene.visual || scene.prompt || 'Scene detail pending'}
                  </p>
                </button>
              );
            })}
          </div>

          <div className="rounded-card border border-hairline bg-surface-2 p-4">
            {activeScene ? (
              <>
                <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="text-base font-extrabold text-text">
                      {sceneTitle(activeScene, scenes.findIndex((scene) => scene.id === activeScene.id))}
                    </h3>
                    <div className="mt-1 text-xs text-text-subtle">
                      {activeScene.durationS ? `${activeScene.durationS}s` : 'Auto duration'}
                      {activeScene.spendUsd ? ` | est. $${activeScene.spendUsd.toFixed(2)}` : ''}
                    </div>
                  </div>
                  {activeScene.prompt && onCopyPrompt && (
                    <button
                      type="button"
                      onClick={() => void onCopyPrompt(activeScene.prompt || '')}
                      className="btn-outline px-3 py-2 text-xs"
                    >
                      <Copy size={14} />
                      Copy prompt
                    </button>
                  )}
                </div>

                <div className="grid gap-3">
                  <div>
                    <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">Beat / action</div>
                    <p className="rounded-card border border-hairline bg-surface-1 px-3 py-2 text-sm leading-relaxed text-text-muted">
                      {activeScene.visual || 'Action detail pending'}
                    </p>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div>
                      <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">Camera movement</div>
                      <p className="rounded-card border border-hairline bg-surface-1 px-3 py-2 text-sm leading-relaxed text-text-muted">
                        {activeScene.camera || 'Camera pending'}
                      </p>
                    </div>
                    <div>
                      <div className="mb-1 flex items-center gap-1 text-[10px] font-bold uppercase text-text-subtle">
                        <Volume2 size={12} />
                        Audio intent
                      </div>
                      <p className="rounded-card border border-hairline bg-surface-1 px-3 py-2 text-sm leading-relaxed text-text-muted">
                        {activeScene.audio || 'Audio pending'}
                      </p>
                    </div>
                  </div>
                  <div>
                    <div className="mb-1 text-[10px] font-bold uppercase text-text-subtle">Seedance prompt preview</div>
                    <p className="max-h-[180px] overflow-y-auto whitespace-pre-wrap rounded-card border border-hairline bg-surface-1 px-3 py-2 text-xs leading-relaxed text-text-muted">
                      {activeScene.prompt || 'Prompt pending'}
                    </p>
                  </div>
                  {activeScene.refs && activeScene.refs.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {activeScene.refs.map((ref) => (
                        <span key={ref} className="rounded-full border border-hairline bg-surface-1 px-2 py-0.5 text-[10px] font-semibold uppercase text-text-subtle">
                          {ref}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </>
            ) : null}
          </div>
        </div>
      )}
    </section>
  );
}
