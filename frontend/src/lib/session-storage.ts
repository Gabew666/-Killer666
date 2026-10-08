const key = "atlas-active-session-id";

export function readActiveSessionId(): number | null {
  const raw = window.localStorage.getItem(key);
  const id = Number(raw);
  return raw && Number.isSafeInteger(id) && id > 0 ? id : null;
}

export function saveActiveSessionId(id: number): void {
  window.localStorage.setItem(key, String(id));
}

export function clearActiveSessionId(): void {
  window.localStorage.removeItem(key);
}
