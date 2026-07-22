// Single fetch client for the whole app.
//
// - Everything is same-origin (`/api/...`) via the Vite dev proxy in dev and via
//   FastAPI static hosting in prod, so httpOnly session cookies ride along with
//   `credentials: "include"`.
// - Non-GET requests echo the non-httpOnly `csrf_token` cookie into the
//   `X-CSRF-Token` header (double-submit, see backend deps.csrf_protect).
// - On a 401 we silently try `POST /auth/refresh` once, then retry the original
//   request. If that also fails we broadcast a session-expired event so the
//   router can bounce to /login.

const BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export const SESSION_EXPIRED_EVENT = 'auth:session-expired';

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

function broadcastSessionExpired(): void {
  window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
}

const CSRF_COOKIE = 'csrf_token';
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

interface RequestOptions {
  method?: string;
  body?: unknown;
  // Skip the silent refresh-and-retry (used by /auth/refresh itself).
  skipRefresh?: boolean;
  signal?: AbortSignal;
}

async function parseBody(res: Response): Promise<unknown> {
  if (res.status === 204) return null;
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function errorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && 'detail' in detail) {
    const inner = (detail as { detail: unknown }).detail;
    if (typeof inner === 'string') return inner;
  }
  return fallback;
}

async function rawRequest(path: string, opts: RequestOptions): Promise<Response> {
  const method = (opts.method ?? 'GET').toUpperCase();
  const headers: Record<string, string> = {};
  const isFormData = opts.body instanceof FormData;
  if (opts.body !== undefined && !isFormData) headers['Content-Type'] = 'application/json';
  let body: BodyInit | undefined;
  if (opts.body instanceof FormData) {
    body = opts.body;
  } else if (opts.body !== undefined) {
    body = JSON.stringify(opts.body);
  }
  if (!SAFE_METHODS.has(method)) {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) headers['X-CSRF-Token'] = csrf;
  }
  return fetch(`${BASE}${path}`, {
    method,
    headers,
    credentials: 'include',
    body,
    signal: opts.signal,
  });
}

async function tryRefresh(): Promise<boolean> {
  try {
    const res = await rawRequest('/auth/refresh', { method: 'POST', skipRefresh: true });
    return res.ok;
  } catch {
    return false;
  }
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  let res = await rawRequest(path, opts);

  if (res.status === 401 && !opts.skipRefresh) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      res = await rawRequest(path, opts);
    } else {
      broadcastSessionExpired();
    }
  }

  const data = await parseBody(res);
  if (!res.ok) {
    throw new ApiError(res.status, data, errorMessage(data, `Request failed (${res.status})`));
  }
  return data as T;
}
