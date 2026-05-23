import { StudioRail } from '@/components/studio/StudioRail';
import { StudioTopbar } from '@/components/studio/StudioTopbar';
import { AnnouncementBar } from '@/components/studio/AnnouncementBar';

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 flex flex-col bg-canvas text-text">
      <AnnouncementBar />
      <div className="flex-1 min-h-0 flex">
        <StudioRail />
        <div className="flex-1 min-w-0 flex flex-col">
          <StudioTopbar />
          <main className="flex-1 min-h-0 overflow-y-auto">{children}</main>
        </div>
      </div>
    </div>
  );
}
