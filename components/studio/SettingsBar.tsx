'use client';

import { type ReactNode } from 'react';
import { Clock, Gauge, MonitorPlay, RectangleHorizontal, SlidersHorizontal } from 'lucide-react';

export interface StudioSettingOption<TValue extends string | number = string> {
  value: TValue;
  label: string;
  hint?: string;
  resolution?: string;
}

export interface SettingsBarProps {
  modelValue: string;
  durationValue: number;
  aspectRatioValue: string;
  qualityValue: string;
  targetMarketValue?: string;
  modelOptions: readonly StudioSettingOption<string>[];
  durationOptions: readonly StudioSettingOption<number>[];
  aspectRatioOptions: readonly StudioSettingOption<string>[];
  qualityOptions: readonly StudioSettingOption<string>[];
  targetMarketOptions?: readonly StudioSettingOption<string>[];
  selectedResolution?: string;
  onModelChange: (value: string) => void;
  onDurationChange: (value: number) => void;
  onAspectRatioChange: (value: string) => void;
  onQualityChange: (value: string) => void;
  onTargetMarketChange?: (value: string) => void;
}

function SelectField<TValue extends string | number>({
  label,
  value,
  options,
  icon,
  onChange,
}: {
  label: string;
  value: TValue;
  options: readonly StudioSettingOption<TValue>[];
  icon: ReactNode;
  onChange: (value: TValue) => void;
}) {
  return (
    <label className="min-w-0">
      <span className="mb-1 flex items-center gap-1.5 text-[10px] font-bold uppercase text-text-subtle">
        {icon}
        {label}
      </span>
      <select
        value={String(value)}
        onChange={(event) => {
          const option = options.find((item) => String(item.value) === event.target.value);
          if (option) onChange(option.value);
        }}
        className="w-full rounded-card border border-hairline bg-surface-2 px-3 py-2 text-xs font-semibold text-text outline-none transition focus:border-accent-cyan/60 focus:ring-2 focus:ring-accent-cyan/15"
      >
        {options.map((option) => (
          <option key={String(option.value)} value={String(option.value)}>
            {option.label}{option.resolution ? ` ${option.resolution}` : ''}
          </option>
        ))}
      </select>
    </label>
  );
}

export function SettingsBar({
  modelValue,
  durationValue,
  aspectRatioValue,
  qualityValue,
  targetMarketValue,
  modelOptions,
  durationOptions,
  aspectRatioOptions,
  qualityOptions,
  targetMarketOptions = [],
  selectedResolution,
  onModelChange,
  onDurationChange,
  onAspectRatioChange,
  onQualityChange,
  onTargetMarketChange,
}: SettingsBarProps) {
  const selectedModel = modelOptions.find((option) => option.value === modelValue);
  const selectedDuration = durationOptions.find((option) => option.value === durationValue);
  const selectedAspect = aspectRatioOptions.find((option) => option.value === aspectRatioValue);
  const selectedQuality = qualityOptions.find((option) => option.value === qualityValue);

  return (
    <section className="rounded-sheet border border-hairline bg-surface-1 p-4 shadow-card-soft">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-normal text-accent-cyan">
            <SlidersHorizontal size={14} />
            Settings
          </div>
          <h2 className="mt-1 text-lg font-extrabold text-text">Render intent</h2>
        </div>
        {selectedResolution && (
          <span className="rounded-full border border-hairline bg-surface-2 px-2.5 py-1 text-[10px] font-semibold uppercase text-text-subtle">
            {selectedResolution}
          </span>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <SelectField
          label="Model"
          value={modelValue}
          options={modelOptions}
          icon={<MonitorPlay size={12} />}
          onChange={onModelChange}
        />
        <SelectField
          label="Duration"
          value={durationValue}
          options={durationOptions}
          icon={<Clock size={12} />}
          onChange={onDurationChange}
        />
        <SelectField
          label="Aspect"
          value={aspectRatioValue}
          options={aspectRatioOptions}
          icon={<RectangleHorizontal size={12} />}
          onChange={onAspectRatioChange}
        />
        <SelectField
          label="Quality"
          value={qualityValue}
          options={qualityOptions}
          icon={<Gauge size={12} />}
          onChange={onQualityChange}
        />
        {targetMarketValue !== undefined && onTargetMarketChange && targetMarketOptions.length > 0 && (
          <SelectField
            label="Market"
            value={targetMarketValue}
            options={targetMarketOptions}
            icon={<SlidersHorizontal size={12} />}
            onChange={onTargetMarketChange}
          />
        )}
      </div>

      <div className="mt-3 grid gap-2 text-xs text-text-muted md:grid-cols-4">
        <div className="rounded-card border border-hairline bg-surface-2 px-3 py-2">
          <span className="block font-bold text-text">Model route</span>
          {selectedModel?.hint || 'Agent chooses the safest model route.'}
        </div>
        <div className="rounded-card border border-hairline bg-surface-2 px-3 py-2">
          <span className="block font-bold text-text">Timing</span>
          {selectedDuration?.hint || 'Duration selected by the agent.'}
        </div>
        <div className="rounded-card border border-hairline bg-surface-2 px-3 py-2">
          <span className="block font-bold text-text">Frame</span>
          {selectedAspect?.hint || 'Aspect ratio selected for the target channel.'}
        </div>
        <div className="rounded-card border border-hairline bg-surface-2 px-3 py-2">
          <span className="block font-bold text-text">Output</span>
          {selectedQuality?.hint || 'Quality preset controls cost and detail.'}
        </div>
      </div>
    </section>
  );
}
