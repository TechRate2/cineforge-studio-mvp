import { NextRequest, NextResponse } from 'next/server';

const BACKEND = process.env.BACKEND_URL || 'http://localhost:8001';

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const res = await fetch(`${BACKEND}/api/v1/upload-media`, {
      method: 'POST',
      body: formData,
    });
    return NextResponse.json(await res.json(), { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export const runtime = 'nodejs';
