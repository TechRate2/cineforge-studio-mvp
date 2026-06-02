import { NextResponse } from 'next/server';

const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8001';

export async function GET(
  _req: Request,
  { params }: { params: { resultId: string } },
) {
  try {
    const res = await fetch(
      `${BACKEND}/api/v1/director/autonomous/benchmarks/results/${params.resultId}`,
      { cache: 'no-store' },
    );
    return NextResponse.json(await res.json(), { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function PATCH(
  req: Request,
  { params }: { params: { resultId: string } },
) {
  try {
    const body = await req.json();
    const res = await fetch(
      `${BACKEND}/api/v1/director/autonomous/benchmarks/results/${params.resultId}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      },
    );
    return NextResponse.json(await res.json(), { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function DELETE(
  _req: Request,
  { params }: { params: { resultId: string } },
) {
  try {
    const res = await fetch(
      `${BACKEND}/api/v1/director/autonomous/benchmarks/results/${params.resultId}`,
      { method: 'DELETE' },
    );
    return NextResponse.json(await res.json(), { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
