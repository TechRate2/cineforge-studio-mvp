import { NextResponse } from 'next/server';

const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8001';

export async function GET(req: Request) {
  try {
    const url = new URL(req.url);
    const res = await fetch(
      `${BACKEND}/api/v1/director/autonomous/benchmarks/plan?${url.searchParams.toString()}`,
      { cache: 'no-store' },
    );
    return NextResponse.json(await res.json(), { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
