import { NextResponse } from 'next/server';

const BACKEND = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export async function POST(req: Request) {
  try {
    const body = await req.text();
    const res = await fetch(`${BACKEND}/api/v1/director/autonomous/creative-producer-v2`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch creative producer v2' },
      { status: 500 },
    );
  }
}
