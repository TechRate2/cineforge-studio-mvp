import { ComingSoon } from '@/components/studio/ComingSoon';

export default function TextToVideoPage() {
  return (
    <ComingSoon
      title="Text → Video playground"
      hint="Quick text-to-video không qua Director Agent. Sẽ wire trực tiếp /api/v1/video/direct/generate. Coming next sprint."
    />
  );
}
