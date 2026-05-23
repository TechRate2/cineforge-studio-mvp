import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: '#0a0a0b', soft: '#111114', card: '#16161a', hover: '#1d1d22' },
        border: { DEFAULT: '#26262d', soft: '#1f1f25' },
        text: { DEFAULT: '#f4f4f5', muted: '#a1a1aa', subtle: '#71717a' },
        brand: {
          50: '#f3eeff', 100: '#e7dcff', 200: '#cdb8ff',
          400: '#9b6bff', 500: '#7c4dff', 600: '#6a3aff',
          700: '#5a2ee0', 800: '#4824b3', 900: '#321a7d',
        },
        accent: { teal: '#14b8a6', amber: '#f59e0b', rose: '#f43f5e', emerald: '#10b981' },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(124,77,255,0.3), 0 8px 32px -8px rgba(124,77,255,0.4)',
      },
    },
  },
  plugins: [],
};
export default config;
