import { WorkspaceRail } from '@/components/workspace/WorkspaceRail';
import { PromoBanner } from '@/components/workspace/PromoBanner';

export default function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 flex flex-col bg-bg text-text overflow-hidden">
      <PromoBanner />
      <div className="flex-1 min-h-0 flex overflow-hidden">
        <WorkspaceRail />
        <div className="flex-1 min-w-0 flex flex-col overflow-hidden">{children}</div>
      </div>
    </div>
  );
}
