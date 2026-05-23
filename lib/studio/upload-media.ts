'use client';

/**
 * R2 upload helper — convert local File → public URL via /api/v1/upload-media.
 * Falls back to data: base64 if upload fails (so render still proceeds).
 */
export async function uploadMediaToR2(file: File): Promise<string> {
  const form = new FormData();
  form.append('file', file);
  try {
    const res = await fetch('/api/v1/upload-media', {
      method: 'POST',
      body: form,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const url = data.url || data.public_url || data.media_url;
    if (typeof url === 'string' && url.length > 5) return url;
    throw new Error('No url in response');
  } catch (err) {
    // Fallback to base64 data URL so the user flow doesn't break
    console.warn('[uploadMediaToR2] fallback to base64', err);
    return fileToDataUrl(file);
  }
}

export function fileToDataUrl(f: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result as string);
    r.onerror = reject;
    r.readAsDataURL(f);
  });
}
