'use client';

import { BarChart3, Building2, Library, Save, WalletCards } from 'lucide-react';

export interface BrandKitOption {
  brand_id: string;
  name: string;
  primary_colors?: string[];
  fonts?: string[];
  voice?: string;
  style_guide?: string;
}

export interface CommercialTemplateOption {
  template_id: string;
  name: string;
  niche?: string;
  hook_pattern?: string;
  recommended_duration_s?: number;
}

export interface CommercialUsageSummary {
  credits_balance?: number;
  ledger?: Array<Record<string, unknown>>;
}

export interface CommercialAnalyticsSummary {
  render_count?: number;
  success_rate?: number;
  credits_spent?: number;
  popular_templates?: Record<string, number>;
}

interface CommercialControlsProps {
  brandKits: BrandKitOption[];
  templates: CommercialTemplateOption[];
  selectedBrandKitId: string;
  selectedTemplateId: string;
  usage: CommercialUsageSummary | null;
  analytics: CommercialAnalyticsSummary | null;
  loading: boolean;
  brandDraftName: string;
  brandDraftVoice: string;
  brandDraftStyleGuide: string;
  brandDraftColors: string;
  onBrandKitChange: (brandId: string) => void;
  onTemplateChange: (templateId: string) => void;
  onBrandDraftNameChange: (value: string) => void;
  onBrandDraftVoiceChange: (value: string) => void;
  onBrandDraftStyleGuideChange: (value: string) => void;
  onBrandDraftColorsChange: (value: string) => void;
  onSaveBrandKit: () => void;
}

function formatCreditBalance(value?: number): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'Not loaded';
  return value.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function formatSuccessRate(value?: number): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'No data';
  return `${Math.round(value * 100)}%`;
}

function topTemplateLabel(value?: Record<string, number>): string {
  const entries = Object.entries(value ?? {});
  if (entries.length === 0) return 'None yet';
  const [templateId, count] = entries.sort((a, b) => b[1] - a[1])[0];
  return `${templateId} (${count})`;
}

export function CommercialControls({
  brandKits,
  templates,
  selectedBrandKitId,
  selectedTemplateId,
  usage,
  analytics,
  loading,
  brandDraftName,
  brandDraftVoice,
  brandDraftStyleGuide,
  brandDraftColors,
  onBrandKitChange,
  onTemplateChange,
  onBrandDraftNameChange,
  onBrandDraftVoiceChange,
  onBrandDraftStyleGuideChange,
  onBrandDraftColorsChange,
  onSaveBrandKit,
}: CommercialControlsProps) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-950/80 p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-100">Commercial setup</h2>
          <p className="text-xs text-slate-400">Brand, template, credits, and account performance.</p>
        </div>
        {loading ? <span className="text-xs text-slate-500">Syncing</span> : null}
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="block">
          <span className="mb-1 flex items-center gap-2 text-xs font-medium text-slate-300">
            <Building2 className="h-3.5 w-3.5" />
            Brand kit
          </span>
          <select
            value={selectedBrandKitId}
            onChange={(event) => onBrandKitChange(event.target.value)}
            className="h-10 w-full rounded-md border border-slate-700 bg-slate-900 px-3 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
          >
            <option value="">No brand kit</option>
            {brandKits.map((brand) => (
              <option key={brand.brand_id} value={brand.brand_id}>
                {brand.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-1 flex items-center gap-2 text-xs font-medium text-slate-300">
            <Library className="h-3.5 w-3.5" />
            Template
          </span>
          <select
            value={selectedTemplateId}
            onChange={(event) => onTemplateChange(event.target.value)}
            className="h-10 w-full rounded-md border border-slate-700 bg-slate-900 px-3 text-sm text-slate-100 outline-none transition focus:border-cyan-500"
          >
            <option value="">No template</option>
            {templates.map((template) => (
              <option key={template.template_id} value={template.template_id}>
                {template.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        <div className="rounded-md border border-slate-800 bg-slate-900/70 p-3">
          <div className="mb-1 flex items-center gap-2 text-xs text-slate-400">
            <WalletCards className="h-3.5 w-3.5" />
            Credits
          </div>
          <div className="text-sm font-semibold text-slate-100">{formatCreditBalance(usage?.credits_balance)}</div>
        </div>
        <div className="rounded-md border border-slate-800 bg-slate-900/70 p-3">
          <div className="mb-1 flex items-center gap-2 text-xs text-slate-400">
            <BarChart3 className="h-3.5 w-3.5" />
            Success
          </div>
          <div className="text-sm font-semibold text-slate-100">{formatSuccessRate(analytics?.success_rate)}</div>
        </div>
        <div className="rounded-md border border-slate-800 bg-slate-900/70 p-3">
          <div className="mb-1 text-xs text-slate-400">Top template</div>
          <div className="truncate text-sm font-semibold text-slate-100">{topTemplateLabel(analytics?.popular_templates)}</div>
        </div>
      </div>

      <div className="mt-4 rounded-md border border-slate-800 bg-slate-900/50 p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-slate-300">Create brand kit</span>
          <button
            type="button"
            onClick={onSaveBrandKit}
            disabled={loading || brandDraftName.trim().length < 2}
            className="inline-flex h-8 items-center gap-2 rounded-md border border-cyan-500/50 px-3 text-xs font-medium text-cyan-100 transition hover:border-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5" />
            Save
          </button>
        </div>
        <div className="grid gap-2 md:grid-cols-2">
          <input
            value={brandDraftName}
            onChange={(event) => onBrandDraftNameChange(event.target.value)}
            placeholder="Brand name"
            className="h-9 rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-500"
          />
          <input
            value={brandDraftColors}
            onChange={(event) => onBrandDraftColorsChange(event.target.value)}
            placeholder="Colors: #111827, #06b6d4"
            className="h-9 rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-500"
          />
          <input
            value={brandDraftVoice}
            onChange={(event) => onBrandDraftVoiceChange(event.target.value)}
            placeholder="Voice: premium, direct, warm"
            className="h-9 rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-500"
          />
          <input
            value={brandDraftStyleGuide}
            onChange={(event) => onBrandDraftStyleGuideChange(event.target.value)}
            placeholder="Style guide"
            className="h-9 rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-500"
          />
        </div>
      </div>
    </section>
  );
}
