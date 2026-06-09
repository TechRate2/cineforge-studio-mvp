import { NextResponse } from 'next/server';
import { backendUrl } from '@/lib/server/backend-url';

const BACKEND = backendUrl();

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
