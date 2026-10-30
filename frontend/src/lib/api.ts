const TOKEN_KEY = "kaoyan.auth.token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch { /* 隐私模式下忽略 */ }
}

export function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = getToken();
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(extra ?? {}) };
}

function toLogin(): void {
  if (typeof window === "undefined") return;
  setToken(null);
  if (!window.location.pathname.startsWith("/login")) {
    window.location.href = "/login";
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: body === undefined
      ? authHeaders()
      : authHeaders({ "Content-Type": "application/json" }),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401) {
    toLogin();
    throw new Error("未登录");
  }
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${path} -> ${res.status}: ${detail.slice(0, 200)}`);
  }
  return res.json();
}

export const getJson = <T>(path: string) => request<T>("GET", path);
export const postJson = <T>(path: string, body?: unknown) => request<T>("POST", path, body);
export const putJson = <T>(path: string, body?: unknown) => request<T>("PUT", path, body);
export const delJson = <T>(path: string) => request<T>("DELETE", path);
