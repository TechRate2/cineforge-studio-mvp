/**
 * POST /api/v1/jobs/propose/stream — SSE pass-through proxy.
 *
 * Pass-through SSE bytes từ Python backend FastAPI sang frontend.
 * Frontend consume bằng fetch + ReadableStream (vì EventSource KHÔNG support POST body).
 */

import { NextRequest } from 'next/server';

const BACKEND = process.env.BACKEND_URL || 'http://localhost:8001';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
// Allow long-running stream (Vercel/Next limit). 5 min đủ cho /propose 60-180s.
export const maxDuration = 300;

export async function POST(req: NextRequest) {
  const body = await req.text();

  const backendRes = await fetch(`${BACKEND}/api/v1/jobs/propose/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    // KHÔNG cache + KHÔNG buffer
    cache: 'no-store',
    // @ts-expect-error — Next.js node fetch supports duplex
    duplex: 'half',
  });

  if (!backendRes.ok || !backendRes.body) {
    return new Response(
      JSON.stringify({ error: `Backend ${backendRes.status}` }),
      { status: backendRes.status || 500, headers: { 'Content-Type': 'application/json' } },
    );
  }

  return new Response(backendRes.body, {
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}
