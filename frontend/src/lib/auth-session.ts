/**
 * Session helpers: access + refresh tokens in localStorage.
 * Prevents mass 403s when access JWT expires after days away.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/v1';

export type AuthTokens = {
  access_token: string;
  refresh_token?: string | null;
  tenant_id?: string | null;
};

let refreshInFlight: Promise<string | null> | null = null;

export function saveSession(data: AuthTokens) {
  if (typeof window === 'undefined') return;
  if (data.access_token) localStorage.setItem('token', data.access_token);
  if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
  if (data.tenant_id) localStorage.setItem('tenant_id', data.tenant_id);
}

export function clearSession() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem('token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('tenant_id');
}

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('token');
}

export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('refresh_token');
}

/** Try to mint a new access token via refresh_token. Returns new access or null. */
export async function refreshAccessToken(apiUrl: string = API_URL): Promise<string | null> {
  if (typeof window === 'undefined') return null;
  const refresh = getRefreshToken();
  if (!refresh) return null;

  // Single-flight: parallel 401s share one refresh
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${apiUrl}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (!res.ok) {
        clearSession();
        return null;
      }
      const data = await res.json();
      saveSession({
        access_token: data.access_token,
        refresh_token: data.refresh_token || refresh,
        tenant_id: data.tenant_id,
      });
      return data.access_token as string;
    } catch {
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

/**
 * fetch with Bearer token; on 401 try refresh once and retry.
 * If still unauthorized, clears session and returns the response.
 */
export async function fetchWithSession(
  url: string,
  options: RequestInit = {},
  apiUrl: string = API_URL,
): Promise<Response> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let res = await fetch(url, { ...options, headers });

  if (res.status === 401 || res.status === 403) {
    // Only try refresh when it looks like auth failure (not pure RBAC)
    // Heuristic: always try once if we have a refresh token
    if (getRefreshToken()) {
      const newToken = await refreshAccessToken(apiUrl);
      if (newToken) {
        headers['Authorization'] = `Bearer ${newToken}`;
        res = await fetch(url, { ...options, headers });
      }
    }
  }

  return res;
}
