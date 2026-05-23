import './globals.css';
import type { Metadata } from 'next';
import { Albert_Sans } from 'next/font/google';

const albert = Albert_Sans({
  subsets: ['latin', 'latin-ext'],
  weight: ['400', '500', '600', '700', '800'],
  variable: '--font-albert',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'CineForge — One AI Platform · Endless Video Creation',
  description:
    'CineForge AI Studio — Director Agent V3: brief → Continuity Bible → Shot List → render. UGC video AI tối ưu thị trường Việt Nam.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" className={albert.variable}>
      <body className="min-h-screen bg-canvas text-text font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
