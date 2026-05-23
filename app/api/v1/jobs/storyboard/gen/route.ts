/**
 * POST /api/v1/jobs/storyboard/gen — proxy gen all keyframes (Phase 2.5).
 */
import { NextRequest, NextResponse } from 'next/server';

const BACKEND = process.env.BACKEND_URL || 'http://localhost:8001';

export const runtime = 'nodejs';
export const maxDuration = 120; // gen 7 ảnh parallel ~10-15s, để 120s buffer

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const res = await fetch(`${BACKEND}/api/v1/jobs/storyboard/gen`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    });
    return NextResponse.json(await res.json(), { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
