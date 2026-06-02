import { NextResponse } from 'next/server';

const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8001';

export async function POST(
  _req: Request,
  { params }: { params: { jobId: string } },
) {
  try {
    const res = await fetch(
      `${BACKEND}/api/v1/director/autonomous/benchmarks/results/from-job/${params.jobId}`,
      { method: 'POST' },
    );
    return NextResponse.json(await res.json(), { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
