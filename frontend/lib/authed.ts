/** JSON call with the current Firebase ID token (owner, staff or signed-in shopper). */
import { API, ApiError } from "./api";
import { idToken } from "./firebase";

export async function authed<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await idToken();
  const res = await fetch(`${API}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(init.headers ?? {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) } });
  if (!res.ok) { let d = res.statusText; try { d = (await res.json()).detail ?? d; } catch {} throw new ApiError(res.status, String(d)); }
  return res.json();
}
