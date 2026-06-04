'use client';

/**
 * Upload helper: convert a local File into a renderer-readable public URL.
 * Failed uploads must block the reference; paid renders should never proceed
 * with silent base64 fallbacks or incomplete media inputs.
 */
export async function uploadMediaToR2(file: File): Promise<string> {
  const form = new FormData();
  form.append('file', file);

  const res = await fetch('/api/v1/upload-media', {
    method: 'POST',
    body: form,
  });

  if (!res.ok) {
    let message = `Upload failed with HTTP ${res.status}`;
    try {
      const data = await res.json();
      message = String(data?.detail || data?.error || data?.message || message);
    } catch {
      // Keep the HTTP status message when the backend did not return JSON.
    }
    throw new Error(message);
  }

  const data = await res.json();
  const url = data.url || data.public_url || data.media_url;
  if (typeof url === 'string' && /^https?:\/\//i.test(url)) return url;

  throw new Error('Upload response did not include a public media URL');
}

export function fileToDataUrl(f: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result as string);
    r.onerror = reject;
    r.readAsDataURL(f);
  });
}
