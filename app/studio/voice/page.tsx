'use client';
import { useMemo, useRef, useState } from 'react';
import {
  Mic2, Loader2, Play, Pause, Download, Sparkles,
  AlertCircle, Crown, Wallet, Gauge,
} from 'lucide-react';
import { useTTSVoices, useTTSGenerate, type VoicePreset } from '@/lib/studio/use-tts-playground';

const SAMPLE_TEXTS = [
  'Bạn đã sẵn sàng tăng doanh thu chưa? Hôm nay tôi sẽ chia sẻ một bí mật ít người biết.',
  'Sản phẩm này không chỉ thay đổi cách bạn làm việc mà còn tiết kiệm hàng giờ mỗi ngày.',
  'Trong 30 giây tiếp theo, bạn sẽ học được kỹ thuật mà các creator hàng đầu đang dùng.',
];

export default function VoicePage() {
  const { voices, loading: voicesLoading, error: voicesError } = useTTSVoices();
  const { generate, isLoading, error: genError } = useTTSGenerate();

  const [text, setText] = useState(SAMPLE_TEXTS[0]);
  const [selectedAlias, setSelectedAlias] = useState<string>('mai');
  const [speed, setSpeed] = useState(1.0);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const selected = useMemo(
    () => voices.find((v) => v.alias === selectedAlias) ?? voices[0],
    [voices, selectedAlias]
  );

  const charCount = text.length;
  const estimatedCredits = useMemo(() => {
    const provider = selected?.provider ?? 'elevenlabs';
    const per100 = provider === 'minimax' ? 0.5 : 1.0;
    return ((charCount / 100) * per100).toFixed(2);
  }, [charCount, selected?.provider]);

  const groupedVoices = useMemo(() => {
    const premium = voices.filter((v) => v.tier === 'premium');
    const budget = voices.filter((v) => v.tier === 'budget');
    return { premium, budget };
  }, [voices]);

  const handleGenerate = async () => {
    if (!text.trim() || !selected) return;
    setAudioUrl(null);
    try {
      const res = await generate({
        text: text.trim(),
        voicePreset: selected.alias,
        speed,
      });
      if (res.audio_url) {
        setAudioUrl(res.audio_url);
        setTimeout(() => audioRef.current?.play().catch(() => {}), 200);
      }
    } catch {
      // error surfaced via genError
    }
  };

  const togglePlay = () => {
    const a = audioRef.current;
    if (!a) return;
    if (a.paused) {
      a.play().catch(() => {});
    } else {
      a.pause();
    }
  };

  return (
    <div className="min-h-full px-5 md:px-10 py-10 max-w-container mx-auto">
      {/* Header */}
      <header className="mb-8 flex items-center gap-3">
        <div className="w-11 h-11 rounded-card bg-cta-gradient grid place-items-center">
          <Mic2 size={20} className="text-white" strokeWidth={2.2} />
        </div>
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Voice Playground</h1>
          <p className="text-sm text-text-muted mt-0.5">
            GenMax TTS · 12 giọng Việt — 6 ElevenLabs premium + 6 MiniMax budget
          </p>
        </div>
      </header>

      <div className="grid lg:grid-cols-[1fr_360px] gap-6">
        {/* LEFT — Text + Voice picker */}
        <div className="space-y-6">
          {/* Text input */}
          <section className="glass-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold">Script tiếng Việt</h2>
              <span className={`text-xs ${charCount > 4500 ? 'text-accent-orange' : 'text-text-subtle'}`}>
                {charCount} / 5000 ký tự
              </span>
            </div>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value.slice(0, 5000))}
              placeholder="Nhập văn bản tiếng Việt cần TTS..."
              className="w-full min-h-[140px] resize-y rounded-md bg-surface-2 border border-hairline
                         focus:border-accent-magenta/60 focus:outline-none p-3 text-sm leading-relaxed"
            />
            <div className="flex flex-wrap gap-1.5 mt-3">
              {SAMPLE_TEXTS.map((s, i) => (
                <button
                  key={i}
                  onClick={() => setText(s)}
                  className="text-[11px] px-2.5 py-1 rounded-full border border-hairline
                             text-text-muted hover:text-text hover:border-accent-magenta/50 transition"
                >
                  Mẫu {i + 1}
                </button>
              ))}
            </div>
          </section>

          {/* Voice picker */}
          <section className="glass-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold">Chọn giọng</h2>
              {voicesLoading && <Loader2 size={14} className="animate-spin text-text-muted" />}
            </div>

            {voicesError && (
              <div className="surface-2 rounded-card p-3 mb-4 flex items-start gap-2 border-accent-orange/40">
                <AlertCircle size={14} className="text-accent-orange shrink-0 mt-0.5" />
                <span className="text-xs text-accent-orange">{voicesError}</span>
              </div>
            )}

            {voices.length > 0 && (
              <>
                <VoiceGroup
                  title="ElevenLabs Premium"
                  tag="$0.30/1k chars"
                  icon={<Crown size={12} className="text-accent-yellow" />}
                  voices={groupedVoices.premium}
                  selected={selectedAlias}
                  onSelect={setSelectedAlias}
                />
                <div className="h-px bg-hairline my-4" />
                <VoiceGroup
                  title="MiniMax Budget"
                  tag="$0.15/1k chars"
                  icon={<Wallet size={12} className="text-accent-cyan" />}
                  voices={groupedVoices.budget}
                  selected={selectedAlias}
                  onSelect={setSelectedAlias}
                />
              </>
            )}
          </section>

          {/* Speed */}
          <section className="glass-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold flex items-center gap-2">
                <Gauge size={14} /> Tốc độ
              </h2>
              <span className="chip">{speed.toFixed(2)}×</span>
            </div>
            <input
              type="range"
              min={0.5}
              max={2.0}
              step={0.05}
              value={speed}
              onChange={(e) => setSpeed(parseFloat(e.target.value))}
              className="w-full accent-accent-magenta"
            />
            <div className="flex justify-between text-[10px] text-text-subtle mt-1.5">
              <span>0.5× chậm</span>
              <span>1.0× chuẩn</span>
              <span>2.0× nhanh</span>
            </div>
          </section>
        </div>

        {/* RIGHT — Sticky preview / generate */}
        <aside className="lg:sticky lg:top-6 self-start space-y-4">
          <div className="glass-card p-5">
            <h3 className="text-sm font-semibold mb-3">Ước tính</h3>
            <div className="space-y-2 text-xs">
              <Row k="Provider" v={selected?.provider ?? '—'} />
              <Row k="Voice ID" v={selected?.voice_id ? selected.voice_id.slice(0, 16) + '…' : '—'} mono />
              <Row k="Ký tự" v={`${charCount}`} />
              <Row k="Credit" v={`~${estimatedCredits}`} highlight />
              <Row k="VND" v={`~${Math.round(parseFloat(estimatedCredits) * 500).toLocaleString('vi-VN')}đ`} />
            </div>

            <button
              onClick={handleGenerate}
              disabled={isLoading || !text.trim() || !selected}
              className="btn-cta w-full mt-5 justify-center"
            >
              {isLoading ? (
                <><Loader2 size={15} className="animate-spin" /> Đang tạo... ~10-20s</>
              ) : (
                <><Sparkles size={15} /> Tạo giọng</>
              )}
            </button>

            {genError && (
              <div className="surface-2 rounded-card p-3 mt-3 border-accent-orange/40">
                <p className="text-[11px] text-accent-orange font-mono">{genError}</p>
              </div>
            )}
          </div>

          {/* Audio preview */}
          {audioUrl && (
            <div className="glass-card p-5">
              <div className="flex items-center gap-3 mb-3">
                <button
                  onClick={togglePlay}
                  className="w-10 h-10 rounded-full bg-cta-gradient grid place-items-center
                             hover:brightness-110 transition shrink-0"
                >
                  {playing ? <Pause size={16} className="text-white" /> : <Play size={16} className="text-white ml-0.5" />}
                </button>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold truncate">{selected?.label_vn}</div>
                  <div className="text-[10px] text-text-subtle">{selected?.provider}</div>
                </div>
                <a
                  href={audioUrl}
                  download
                  className="btn-icon shrink-0"
                  title="Download MP3"
                >
                  <Download size={14} />
                </a>
              </div>

              <audio
                ref={audioRef}
                src={audioUrl}
                onPlay={() => setPlaying(true)}
                onPause={() => setPlaying(false)}
                onEnded={() => setPlaying(false)}
                controls
                className="w-full mt-1"
                style={{ height: 36 }}
              />
            </div>
          )}

          {/* Tips */}
          <div className="surface-2 rounded-card p-4 text-[11px] text-text-subtle leading-relaxed">
            <div className="font-semibold text-text-muted mb-2">Mẹo viết script TTS:</div>
            <ul className="space-y-1 list-disc list-inside">
              <li>Dấu phẩy để giọng nghỉ ngắn, chấm để nghỉ dài</li>
              <li>15-25 từ/câu để natural pacing</li>
              <li>Tránh viết tắt — phát âm có thể sai</li>
              <li>Số: viết chữ thay vì "12" → "mười hai"</li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}

function VoiceGroup({
  title, tag, icon, voices, selected, onSelect,
}: {
  title: string;
  tag: string;
  icon: React.ReactNode;
  voices: VoicePreset[];
  selected: string;
  onSelect: (alias: string) => void;
}) {
  if (voices.length === 0) return null;
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h3 className="text-[11px] uppercase tracking-wider text-text-subtle font-semibold">{title}</h3>
        <span className="chip ml-auto text-[10px]">{tag}</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
        {voices.map((v) => {
          const active = v.alias === selected;
          return (
            <button
              key={v.alias}
              onClick={() => onSelect(v.alias)}
              className={`text-left p-3 rounded-card border transition
                          ${active
                            ? 'border-accent-magenta/60 bg-accent-magenta/8 shadow-[0_0_0_3px_rgba(217,70,239,0.08)]'
                            : 'border-hairline bg-surface-2 hover:border-hairline-strong hover:bg-surface-3'}`}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="text-sm font-semibold truncate">{v.label_vn}</span>
                <span className={`text-[9px] uppercase tracking-wider shrink-0
                                  ${v.gender === 'female' ? 'text-accent-magenta' : 'text-accent-cyan'}`}>
                  {v.gender === 'female' ? '♀' : '♂'}
                </span>
              </div>
              <div className="text-[10px] text-text-subtle font-mono truncate">{v.alias}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Row({ k, v, mono, highlight }: { k: string; v: string; mono?: boolean; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-text-subtle">{k}</span>
      <span className={`${mono ? 'font-mono' : ''} ${highlight ? 'text-accent-magenta font-semibold' : 'text-text'}`}>
        {v}
      </span>
    </div>
  );
}
