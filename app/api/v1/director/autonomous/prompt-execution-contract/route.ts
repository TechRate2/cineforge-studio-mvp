import { NextResponse } from 'next/server';

const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8001';

export async function POST(req: Request) {
  try {
    const body = await req.text();
    const res = await fetch(`${BACKEND}/api/v1/director/autonomous/prompt-execution-contract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch prompt execution contract' },
      { status: 500 },
    );
  }
}
