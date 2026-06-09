import { NextResponse } from 'next/server';
import { backendUrl } from '@/lib/server/backend-url';

const BACKEND = backendUrl();

export async function GET(req: Request) {
  try {
    const qs = new URL(req.url).searchParams.toString();
    const res = await fetch(`${BACKEND}/api/v1/director/autonomous/niche-audit${qs ? `?${qs}` : ''}`, {
      cache: 'no-store',
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch autonomous niche audit' },
      { status: 500 },
    );
  }
}
