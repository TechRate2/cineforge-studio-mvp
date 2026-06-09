import { NextRequest, NextResponse } from 'next/server';
import { backendUrl } from '@/lib/server/backend-url';

const BACKEND = backendUrl();

export async function GET(request: NextRequest) {
  try {
    const qs = request.nextUrl.searchParams.toString();
    const res = await fetch(`${BACKEND}/api/v1/director/autonomous/paid-benchmark-manifest${qs ? `?${qs}` : ''}`, {
      cache: 'no-store',
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch paid benchmark manifest' },
      { status: 500 },
    );
  }
}
