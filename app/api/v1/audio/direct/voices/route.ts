import { NextRequest, NextResponse } from 'next/server';
import { backendUrl } from '@/lib/server/backend-url';
const BACKEND = backendUrl();

export async function GET(_req: NextRequest) {
  try {
    const res = await fetch(`${BACKEND}/api/v1/audio/direct/voices`, { cache: 'no-store' });
    return NextResponse.json(await res.json(), { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
