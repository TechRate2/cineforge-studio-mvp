import { NextResponse } from 'next/server';

const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8001';

export async function GET() {
  try {
    const res = await fetch(`${BACKEND}/api/v1/director/autonomous/operator-brief`, {
      cache: 'no-store',
    });
    return NextResponse.json(await res.json(), { status: res.status });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch autonomous operator brief' },
      { status: 500 },
    );
  }
}
