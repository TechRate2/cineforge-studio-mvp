/**
 * parse-image-mentions — Parse [Image N] mentions trong prompt + auto detect role
 * theo context word lân cận (TopView V2 pattern).
 *
 * Workflow:
 *   user type: "A beauty influencer [Image 2] reviewing pink blush [Image 1]"
 *   → parseRoleHints(prompt, 2) =>
 *       [
 *         'product_hero',     // Image 1 cạnh "blush"
 *         'primary_subject'   // Image 2 cạnh "influencer"
 *       ]
 *
 * Khi user XOÁ ảnh: strip "[Image N]" khỏi prompt + re-index N+1, N+2... → N, N+1.
 */

// Local type — kept aligned with backend role taxonomy in `agent/schemas.py`.
// (Previously imported from the V2 use-propose-job hook which has been removed.)
export type ReferenceRole =
  | 'primary_subject'
  | 'secondary_subject'
  | 'product_hero'
  | 'product_detail'
  | 'style_reference'
  | 'environment'
  | 'brand_asset';

// Context-window keywords → role mapping (case-insensitive, VN + EN)
// Order quan trọng: nếu nhiều match thì lấy weight cao nhất.
const ROLE_KEYWORDS: Array<{ role: ReferenceRole; weight: number; patterns: RegExp[] }> = [
  {
    role: 'product_hero',
    weight: 10,
    patterns: [
      /\b(product|item|sản\s*phẩm|item|blush|cream|kem|serum|lotion|chai|tube|hộp|bottle|jar|package|packaging|design)\b/i,
      /\b(review(?:ing|s)?|đánh\s*giá|trial|test)\b/i,
    ],
  },
  {
    role: 'product_detail',
    weight: 9,
    patterns: [
      /\b(detail|close[-\s]?up|macro|texture|ingredient|swatch|powder|cấu\s*trúc|chất)\b/i,
    ],
  },
  {
    role: 'primary_subject',
    weight: 8,
    patterns: [
      /\b(influencer|creator|model|she|he|her|him|girl|guy|man|woman|cô|anh|chị|em|bạn|host|presenter|face|character|talent|actress|actor)\b/i,
      /\b(holds?|applies|wears|smiles|smiling|talks|talking|reviewing|cầm|đeo|đang)\b/i,
    ],
  },
  {
    role: 'secondary_subject',
    weight: 4,
    patterns: [/\b(friend|partner|bạn|đối\s*tác|companion|guest|coworker)\b/i],
  },
  {
    role: 'environment',
    weight: 6,
    patterns: [
      /\b(background|bg|scene|setting|location|environment|bedroom|bathroom|kitchen|cafe|office|studio|outdoor|street|park|gym|phòng|văn\s*phòng|quán)\b/i,
    ],
  },
  {
    role: 'style_reference',
    weight: 5,
    patterns: [
      /\b(style|aesthetic|vibe|color\s*grading|color\s*palette|filter|preset|look|inspo|inspiration|tone)\b/i,
    ],
  },
  {
    role: 'brand_asset',
    weight: 5,
    patterns: [
      /\b(logo|brand|font|typography|sticker|watermark|nhãn)\b/i,
    ],
  },
];

// Window chars trước & sau mention để scan context
const CONTEXT_WINDOW = 30;

export interface MentionParseResult {
  /** Số ảnh đã được mention trong prompt (unique indices, 1-based) */
  mentioned: number[];
  /** Role hints array — index aligned với reference_images[] (0-based) */
  role_hints: (ReferenceRole | null)[];
  /** Số mention tags tổng (có thể >mentioned.length nếu repeat) */
  total_mentions: number;
}

/**
 * Parse prompt + extract role hints cho mỗi ảnh được @-mention.
 *
 * @param prompt — prompt text user nhập
 * @param imageCount — số lượng reference_images hiện có (0-based length)
 * @returns role_hints[] cùng độ dài imageCount, null nếu không có context match
 */
export function parseRoleHints(prompt: string, imageCount: number): MentionParseResult {
  const hints: (ReferenceRole | null)[] = Array(imageCount).fill(null);
  const mentioned = new Set<number>();
  let totalMentions = 0;

  // Match [Image N] hoặc [image N] case-insensitive
  const regex = /\[Image\s+(\d+)\]/gi;
  const matches = Array.from(prompt.matchAll(regex));

  // Per-image weight tracker — giữ role có weight cao nhất nếu mention nhiều lần
  const weightTracker: number[] = Array(imageCount).fill(-1);

  for (const m of matches) {
    totalMentions++;
    const idx1Based = parseInt(m[1], 10);
    const idx0 = idx1Based - 1;
    if (idx0 < 0 || idx0 >= imageCount) continue;
    mentioned.add(idx1Based);

    const matchPos = m.index ?? 0;
    const start = Math.max(0, matchPos - CONTEXT_WINDOW);
    const end = Math.min(prompt.length, matchPos + m[0].length + CONTEXT_WINDOW);
    const context = prompt.slice(start, end);

    // Pick role với weight cao nhất khớp context
    let bestRole: ReferenceRole | null = null;
    let bestWeight = weightTracker[idx0];
    for (const { role, weight, patterns } of ROLE_KEYWORDS) {
      if (weight <= bestWeight) continue;
      if (patterns.some((p) => p.test(context))) {
        bestRole = role;
        bestWeight = weight;
      }
    }
    if (bestRole !== null) {
      hints[idx0] = bestRole;
      weightTracker[idx0] = bestWeight;
    }
  }

  return {
    mentioned: Array.from(mentioned).sort((a, b) => a - b),
    role_hints: hints,
    total_mentions: totalMentions,
  };
}

/**
 * Insert "[Image N]" vào prompt tại cursor position (hoặc cuối nếu cursor undefined).
 * Auto append space trước/sau nếu cần để chip render đẹp.
 */
export function insertMentionAtCursor(
  prompt: string,
  imageIndex1Based: number,
  cursorPos?: number,
): { newPrompt: string; newCursorPos: number } {
  const token = `[Image ${imageIndex1Based}]`;
  const pos = cursorPos ?? prompt.length;
  const before = prompt.slice(0, pos);
  const after = prompt.slice(pos);

  // Auto spacing
  const needSpaceBefore = before.length > 0 && !/\s$/.test(before);
  const needSpaceAfter = after.length > 0 && !/^\s/.test(after);
  const insert =
    (needSpaceBefore ? ' ' : '') + token + (needSpaceAfter ? ' ' : '');

  const newPrompt = before + insert + after;
  const newCursorPos = pos + insert.length;
  return { newPrompt, newCursorPos };
}

/**
 * Khi user xoá ảnh ở index `removedIdx0` (0-based), strip "[Image N]" tương ứng
 * khỏi prompt + re-index các mention N+1, N+2... thành N, N+1...
 *
 * Ex: prompt = "use [Image 1] before [Image 2] after [Image 3]"
 *     removeReference(prompt, 1) // remove Image 2
 *     → "use [Image 1] before  after [Image 2]"  (Image 3 → Image 2)
 */
export function stripAndReindexAfterRemoval(prompt: string, removedIdx0: number): string {
  const removedIdx1 = removedIdx0 + 1;

  // Step 1: remove tất cả [Image removedIdx1] (có thể repeat)
  let out = prompt.replace(
    new RegExp(`\\s?\\[Image\\s+${removedIdx1}\\]\\s?`, 'gi'),
    ' ',
  );

  // Step 2: re-index N → N-1 cho N > removedIdx1
  out = out.replace(/\[Image\s+(\d+)\]/gi, (match, num) => {
    const n = parseInt(num, 10);
    return n > removedIdx1 ? `[Image ${n - 1}]` : match;
  });

  // Step 3: collapse double spaces
  return out.replace(/\s{2,}/g, ' ').trim();
}

/**
 * Render-friendly: split prompt thành segments {text, mention?} để frontend
 * highlight inline chips (overlay technique).
 */
export interface PromptSegment {
  type: 'text' | 'mention';
  value: string;
  imageIndex?: number; // 1-based, chỉ có khi type='mention'
}

export function splitPromptSegments(prompt: string): PromptSegment[] {
  const segments: PromptSegment[] = [];
  const regex = /\[Image\s+(\d+)\]/gi;
  let lastEnd = 0;
  for (const m of prompt.matchAll(regex)) {
    const matchPos = m.index ?? 0;
    if (matchPos > lastEnd) {
      segments.push({ type: 'text', value: prompt.slice(lastEnd, matchPos) });
    }
    segments.push({
      type: 'mention',
      value: m[0],
      imageIndex: parseInt(m[1], 10),
    });
    lastEnd = matchPos + m[0].length;
  }
  if (lastEnd < prompt.length) {
    segments.push({ type: 'text', value: prompt.slice(lastEnd) });
  }
  return segments;
}
