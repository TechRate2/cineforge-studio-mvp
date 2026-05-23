/**
 * GET /api/v1/jobs/[id] — Poll status job
 * DELETE /api/v1/jobs/[id] — Cancel job
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendClient } from '@/lib/backend-client';

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  try {
    const status = await backendClient.getJobStatus(params.id);
    return NextResponse.json(status);
  } catch (err: any) {
    return NextResponse.json(
      {
        error: {
          code: err.status === 404 ? 'job_not_found' : 'backend_error',
          message: err.message || 'Lỗi không xác định',
        },
      },
      { status: err.status || 500 },
    );
  }
}

export async function DELETE(_req: NextRequest, { params }: { params: { id: string } }) {
  try {
    const result = await backendClient.cancelJob(params.id);
    return NextResponse.json(result);
  } catch (err: any) {
    return NextResponse.json(
      { error: { code: 'backend_error', message: err.message } },
      { status: err.status || 500 },
    );
  }
}
