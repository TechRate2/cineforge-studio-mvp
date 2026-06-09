import { NextResponse } from 'next/server';
import { backendUrl } from '@/lib/server/backend-url';

const BACKEND = backendUrl();

export async function GET(
  _req: Request,
  { params }: { params: { jobId: string } },
) {
  try {
    const res = await fetch(
      `${BACKEND}/api/v1/director/jobs/${params.jobId}/production-report`,
      { cache: 'no-store' },
    );
    return NextResponse.json(await res.json(), { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
