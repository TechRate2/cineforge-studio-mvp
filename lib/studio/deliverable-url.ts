const LOOPBACK_HOSTS = new Set(['localhost', '0.0.0.0', '::1', '[::1]']);

export function deliverableUrl(value: unknown): string {
  const text = String(value || '').trim();
  if (!text) return '';

  let parsed: URL;
  try {
    parsed = new URL(text);
  } catch {
    return '';
  }

  const protocol = parsed.protocol.toLowerCase();
  if (protocol !== 'http:' && protocol !== 'https:') return '';

  const hostname = parsed.hostname.toLowerCase();
  if (LOOPBACK_HOSTS.has(hostname) || hostname.endsWith('.localhost')) return '';
  if (/^127(?:\.\d{1,3}){3}$/.test(hostname)) return '';

  return text;
}

export function deliverableUrlOrNull(value: unknown): string | null {
  return deliverableUrl(value) || null;
}
