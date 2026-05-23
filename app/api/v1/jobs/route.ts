/**
 * POST /api/v1/jobs — Tạo UGC video job
 * Proxy tới Python backend (ugc_vietnam_backend).
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendClient } from '@/lib/backend-client';
import type { CreateJobRequest } from '@/lib/types/backend';

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as CreateJobRequest;

    if (
      !body.product_input ||
      (!body.product_input.url &&
        !body.product_input.text_description &&
        !(body.product_input.image_urls?.length))
    ) {
      return NextResponse.json(
        {
          error: {
            code: 'bad_request',
            message: 'Cần có product_input.url, text_description hoặc image_urls',
          },
        },
        { status: 400 },
      );
    }

    if (!body.settings?.model) {
      return NextResponse.json(
        { error: { code: 'bad_request', message: 'settings.model bắt buộc' } },
        { status: 400 },
      );
    }

    const job = await backendClient.createJob(body);

    return NextResponse.json(job, { status: 201 });
  } catch (err: any) {
    console.error('[/api/v1/jobs POST] Error:', err);
    return NextResponse.json(
      {
        error: {
          code: 'backend_error',
          message: err.message || 'Lỗi backend không xác định',
        },
      },
      { status: err.status || 500 },
    );
  }
}
