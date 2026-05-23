/**
 * Backend Client — gọi Python FastAPI (ugc_vietnam_backend).
 *
 * Server-side only (chỉ dùng trong API routes Next.js).
 * Browser KHÔNG gọi trực tiếp — phải qua /app/api/v1/* proxy.
 */

import type {
  CreateJobRequest,
  JobCreatedResponse,
  JobStatus,
  Template,
  Avatar,
} from './types/backend';

// BUG-H5 fix: production phải set BACKEND_URL — KHÔNG default localhost
function _resolveBackendUrl(): string {
  if (process.env.BACKEND_URL) return process.env.BACKEND_URL;
  if (process.env.NODE_ENV === 'production') {
    throw new Error(
      'BACKEND_URL env missing in production — set BACKEND_URL=https://api.yourdomain.com '
      + 'trong Vercel/Railway env vars.',
    );
  }
  // Sprint3 B2 — backend dev port is 8001 (matches next.config.js + run scripts)
  return 'http://localhost:8001';
}

const BACKEND_URL = _resolveBackendUrl();
const BACKEND_TIMEOUT_MS = 30000;

class BackendError extends Error {
  constructor(public status: number, public detail: string) {
    super(`Backend ${status}: ${detail}`);
  }
}

async function fetchBackend<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${BACKEND_URL}${path}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);

  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      signal: controller.signal,
      cache: 'no-store',
    });

    clearTimeout(timeoutId);

    if (!res.ok) {
      const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
      throw new BackendError(res.status, errorBody.detail || res.statusText);
    }

    return (await res.json()) as T;
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof BackendError) throw err;
    throw new BackendError(500, (err as Error).message);
  }
}

// ============================================
// JOBS API
// ============================================

export const backendClient = {
  // Create UGC job
  async createJob(request: CreateJobRequest): Promise<JobCreatedResponse> {
    return fetchBackend<JobCreatedResponse>('/api/v1/jobs/ugc', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  // Poll job status
  async getJobStatus(jobId: string): Promise<JobStatus> {
    return fetchBackend<JobStatus>(`/api/v1/jobs/${jobId}`);
  },

  // Cancel job
  async cancelJob(jobId: string): Promise<{ status: string; job_id: string }> {
    return fetchBackend(`/api/v1/jobs/${jobId}`, { method: 'DELETE' });
  },

  // ============================================
  // TEMPLATES API
  // ============================================

  async listTemplates(filters?: {
    category?: string;
    tier?: 'S' | 'A' | 'B';
    audio_mode?: string;
  }): Promise<{ templates: Template[]; total: number }> {
    const params = new URLSearchParams();
    if (filters?.category) params.set('category', filters.category);
    if (filters?.tier) params.set('tier', filters.tier);
    if (filters?.audio_mode) params.set('audio_mode', filters.audio_mode);

    const qs = params.toString();
    return fetchBackend(`/api/v1/templates${qs ? `?${qs}` : ''}`);
  },

  async getTemplate(id: string): Promise<Template & { scenes?: any[] }> {
    return fetchBackend(`/api/v1/templates/${id}`);
  },

  // ============================================
  // AVATARS API
  // ============================================

  async listAvatars(filters?: {
    ethnicity?: string;
    gender?: 'female' | 'male';
    age_min?: number;
    age_max?: number;
  }): Promise<{ avatars: Avatar[]; total: number }> {
    const params = new URLSearchParams();
    if (filters?.ethnicity) params.set('ethnicity', filters.ethnicity);
    if (filters?.gender) params.set('gender', filters.gender);
    if (filters?.age_min) params.set('age_min', String(filters.age_min));
    if (filters?.age_max) params.set('age_max', String(filters.age_max));

    const qs = params.toString();
    return fetchBackend(`/api/v1/avatars${qs ? `?${qs}` : ''}`);
  },

  async getAvatar(id: string): Promise<Avatar> {
    return fetchBackend(`/api/v1/avatars/${id}`);
  },
};

// Export utility for browser polling
export async function pollJobUntilDone(
  jobId: string,
  onUpdate?: (status: JobStatus) => void,
  intervalMs: number = 5000,
  timeoutMs: number = 600000,
): Promise<JobStatus> {
  const startTime = Date.now();

  while (Date.now() - startTime < timeoutMs) {
    const status = await backendClient.getJobStatus(jobId);
    onUpdate?.(status);

    if (status.status === 'done' || status.status === 'failed') {
      return status;
    }

    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error(`Job ${jobId} timeout after ${timeoutMs}ms`);
}
