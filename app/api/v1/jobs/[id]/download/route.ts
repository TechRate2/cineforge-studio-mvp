/**
 * GET /api/v1/jobs/[id]/download — Stream final MP4 từ backend local temp.
 *
 * V3.4 — dev mode fallback khi R2 chưa setup. Production cần migrate sang R2 + public URL.
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001';

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  try {
    const backendRes = await fetch(`${BACKEND_URL}/api/v1/jobs/${params.id}/download`, {
      // Stream binary — no transform
      cache: 'no-store',
    });

    if (!backendRes.ok) {
      const errText = await backendRes.text();
      return NextResponse.json(
        { error: { code: 'backend_error', message: errText } },
        { status: backendRes.status },
      );
    }

    // Proxy stream MP4 binary to browser
    return new NextResponse(backendRes.body, {
      status: 200,
      headers: {
        'Content-Type': backendRes.headers.get('Content-Type') || 'video/mp4',
        'Content-Disposition': backendRes.headers.get('Content-Disposition') || `inline; filename="ugc_video_${params.id}.mp4"`,
        'Cache-Control': 'public, max-age=300',
      },
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: { code: 'proxy_error', message: err.message || 'Proxy fail' } },
      { status: 500 },
    );
  }
}
