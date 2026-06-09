const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8001';

export function backendUrl(): string {
  const configured = process.env.BACKEND_URL?.trim();
  if (configured) return configured.replace(/\/+$/, '');

  if (process.env.NODE_ENV === 'production') {
    throw new Error('BACKEND_URL must be set in production.');
  }

  return DEFAULT_BACKEND_URL;
}

