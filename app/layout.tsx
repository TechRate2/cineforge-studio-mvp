import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'CineForge — AI Video Studio',
  description: 'AI video generation studio — brief → Continuity Bible → Shot List → render. Director Agent V3 pipeline.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className="min-h-screen bg-bg text-text">{children}</body>
    </html>
  );
}
