import type { RobotConfig } from './types';

export const baseUrl = (c: RobotConfig) => `http://${c.host.trim()}:${c.port}`;
export const wsUrl = (c: RobotConfig) => `ws://${c.host.trim()}:${c.port}/api/ws`;

async function fetchWithTimeout(url: string, init: RequestInit = {}, timeoutMs = 4000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

export type TestResult =
  | { ok: true; name: string; version: string }
  | { ok: false; reason: 'unreachable' | 'unauthorized' | 'not_a_robot'; message: string };

/** Checks the robot is reachable and the token is accepted. */
export async function testConnection(c: RobotConfig): Promise<TestResult> {
  let health: { ok?: boolean; name?: string; version?: string };
  try {
    const r = await fetchWithTimeout(`${baseUrl(c)}/api/health`);
    health = await r.json();
  } catch {
    return {
      ok: false,
      reason: 'unreachable',
      message: `Can't reach ${c.host}:${c.port}. Check that your phone and the robot are on the same WiFi.`,
    };
  }
  if (!health.ok) {
    return { ok: false, reason: 'not_a_robot', message: 'Something answered, but it is not the robot server.' };
  }
  const s = await fetchWithTimeout(`${baseUrl(c)}/api/status`, {
    headers: { Authorization: `Bearer ${c.token.trim()}` },
  }).catch(() => null);
  if (!s || s.status === 401) {
    return { ok: false, reason: 'unauthorized', message: 'The robot rejected this access token.' };
  }
  return { ok: true, name: health.name ?? 'Robot', version: health.version ?? '?' };
}

/** Short-lived ticket so the camera URL never contains the real token. */
export async function cameraStreamUrl(c: RobotConfig): Promise<string> {
  const r = await fetchWithTimeout(`${baseUrl(c)}/api/camera/ticket`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${c.token.trim()}` },
  });
  if (!r.ok) throw new Error(`ticket request failed (${r.status})`);
  const { ticket } = (await r.json()) as { ticket: string };
  return `${baseUrl(c)}/api/camera/stream?ticket=${encodeURIComponent(ticket)}`;
}
