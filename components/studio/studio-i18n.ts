export type StudioLanguage = 'vi' | 'en';

export const studioCopy = {
  vi: {
    idea: 'Ý tưởng video',
    ideaHint: 'Gõ ý tưởng bằng tiếng Việt hoặc tiếng Anh. Agent sẽ biến nó thành concept, kịch bản, storyboard và kế hoạch render.',
    uploadRefs: 'Tải ảnh/video/âm thanh tham chiếu',
    smartRefs: 'Tham chiếu thông minh',
    productHero: 'Sản phẩm chính',
    mainCharacter: 'Nhân vật chính',
    styleReference: 'Phong cách tham khảo',
    cameraMotion: 'Chuyển động camera',
    brandLogo: 'Logo/Thương hiệu',
    voice: 'Giọng đọc',
    music: 'Nhạc nền',
    ready: 'Sẵn sàng',
    needsReview: 'Cần xem lại',
    blocked: 'Bị chặn',
    script: 'Kịch bản',
    storyboard: 'Storyboard',
    promptStrategy: 'Chiến lược prompt',
    preRenderCheck: 'Kiểm tra trước render',
    approveRender: 'Phê duyệt render',
    startRender: 'Bắt đầu render',
    qaChecking: 'Đang kiểm tra chất lượng',
    autoRepair: 'Tự sửa lỗi',
    videoDone: 'Video hoàn tất',
    agentPlan: 'Kế hoạch của Agent',
    renderTimeline: 'Tiến trình sản xuất',
    referenceRole: 'Vai trò tham chiếu',
    lockedRole: 'Đã khóa vai trò',
    needsConfirm: 'Cần xác nhận',
    bestUse: 'Dùng tốt nhất',
    warnings: 'Cảnh báo',
    blockers: 'Chặn render',
    pending: 'Đang chờ',
    unknown: 'Chưa có dữ liệu',
    advanced: 'Chi tiết nâng cao',
    dryRun: 'Dry-run',
  },
  en: {
    idea: 'Video idea',
    ideaHint: 'Write the idea in Vietnamese or English. The Agent turns it into concept, script, storyboard, and render plan.',
    uploadRefs: 'Upload reference image/video/audio',
    smartRefs: 'Smart references',
    productHero: 'Main product',
    mainCharacter: 'Main character',
    styleReference: 'Style reference',
    cameraMotion: 'Camera motion',
    brandLogo: 'Logo/Brand',
    voice: 'Voice',
    music: 'Background music',
    ready: 'Ready',
    needsReview: 'Needs review',
    blocked: 'Blocked',
    script: 'Script',
    storyboard: 'Storyboard',
    promptStrategy: 'Prompt strategy',
    preRenderCheck: 'Pre-render check',
    approveRender: 'Approve render',
    startRender: 'Start render',
    qaChecking: 'Checking quality',
    autoRepair: 'Auto repair',
    videoDone: 'Video complete',
    agentPlan: 'Agent plan',
    renderTimeline: 'Production timeline',
    referenceRole: 'Reference role',
    lockedRole: 'Locked role',
    needsConfirm: 'Needs confirm',
    bestUse: 'Best use',
    warnings: 'Warnings',
    blockers: 'Render blockers',
    pending: 'Pending',
    unknown: 'No data yet',
    advanced: 'Advanced details',
    dryRun: 'Dry-run',
  },
} as const;

export type StudioCopyKey = keyof typeof studioCopy.vi;

export function t(language: StudioLanguage, key: StudioCopyKey): string {
  return studioCopy[language]?.[key] ?? studioCopy.en[key] ?? key;
}

export function statusLabel(language: StudioLanguage, status?: string): string {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'ready' || normalized === 'pass' || normalized === 'completed') return t(language, 'ready');
  if (normalized === 'blocked' || normalized === 'fail' || normalized === 'rejected') return t(language, 'blocked');
  if (normalized === 'needs_review' || normalized === 'warn' || normalized === 'warning') return t(language, 'needsReview');
  if (normalized === 'pending' || !normalized) return t(language, 'pending');
  return normalized.replace(/_/g, ' ');
}

export function statusTone(status?: string): 'ready' | 'review' | 'blocked' | 'pending' {
  const normalized = String(status || '').toLowerCase();
  if (normalized === 'ready' || normalized === 'pass' || normalized === 'completed') return 'ready';
  if (normalized === 'blocked' || normalized === 'fail' || normalized === 'rejected') return 'blocked';
  if (normalized === 'needs_review' || normalized === 'warn' || normalized === 'warning') return 'review';
  return 'pending';
}
