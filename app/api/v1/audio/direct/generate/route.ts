import { NextRequest, NextResponse } from 'next/server';
import { backendUrl } from '@/lib/server/backend-url';
const BACKEND = backendUrl();

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const adminKey = req.headers.get('x-admin-key');
    if (adminKey) headers['X-Admin-Key'] = adminKey;
    const res = await fetch(`${BACKEND}/api/v1/audio/direct/generate`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      cache: 'no-store',
    });
    return NextResponse.json(await res.json(), { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
