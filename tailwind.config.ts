import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: '#040304',
        surface: {
          1: '#0F0F0F',
          2: '#18181A',
          3: '#1C1C21',
          4: '#1F1F25',
          5: '#22222A',
        },
        hairline: {
          DEFAULT: 'rgba(255,255,255,0.06)',
          strong: 'rgba(255,255,255,0.12)',
          soft: 'rgba(255,255,255,0.04)',
        },
        accent: {
          magenta: '#DF41FF',
          orange: '#FF8811',
          yellow: '#FFD30F',
          cyan: '#00A6C6',
          blue: '#2D73FF',
          green: '#2BBF64',
          pink: '#F66CFF',
        },
        text: {
          DEFAULT: '#FFFFFF',
          muted: '#AAAAB9',
          subtle: '#85858C',
          dim: '#5C5C66',
        },
      },
      fontFamily: {
        sans: ['var(--font-albert)', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        pill: '53px',
        card: '16px',
        sheet: '24px',
      },
      backgroundImage: {
        'cta-gradient': 'linear-gradient(90deg,#DF41FF 0%,#FF8811 100%)',
        'cta-gradient-soft': 'linear-gradient(90deg, rgba(223,65,255,0.18) 0%, rgba(255,136,17,0.18) 100%)',
        'glass-card': 'linear-gradient(180deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0) 100%)',
      },
      boxShadow: {
        'cta-glow': '0 8px 32px -8px rgba(223,65,255,0.45)',
        'card-soft': '0 1px 0 rgba(255,255,255,0.03) inset, 0 24px 48px -24px rgba(0,0,0,0.6)',
      },
      maxWidth: {
        container: '1200px',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(16px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'gradient-pan': {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.6s cubic-bezier(0.16,1,0.3,1) both',
        'fade-in': 'fade-in 0.5s ease-out both',
        shimmer: 'shimmer 2.5s linear infinite',
        'gradient-pan': 'gradient-pan 8s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
export default config;
