import { Toaster } from 'sonner';
import { StudioRail } from '@/components/studio/StudioRail';
import { StudioTopbar } from '@/components/studio/StudioTopbar';

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 flex flex-col bg-canvas text-text">
      <div className="flex-1 min-h-0 flex">
        <StudioRail />
        <div className="flex-1 min-w-0 flex flex-col">
          <StudioTopbar />
          <main className="flex-1 min-h-0 overflow-y-auto">{children}</main>
        </div>
      </div>
      <Toaster
        position="bottom-right"
        theme="dark"
        toastOptions={{
          style: {
            background: 'rgba(20,20,30,0.95)',
            border: '1px solid rgba(255,255,255,0.08)',
            color: 'rgb(240,240,250)',
          },
        }}
      />
    </div>
  );
}
