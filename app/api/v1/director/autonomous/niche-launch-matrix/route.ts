import { NextResponse } from 'next/server';

const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8001';

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/api/v1/director/autonomous/niche-launch-matrix`, {
      cache: 'no-store',
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch autonomous niche launch matrix' },
      { status: 500 },
    );
  }
}
