// Anonymous, browser-scoped identity. Generated on first visit and
// persisted to localStorage so watches/notifications stay with this
// browser. Replace with a real auth identity if/when sign-in lands.

const KEY = "studyeval:client_id";

export function getClientId(): string {
  if (typeof window === "undefined") return "";
  const existing = window.localStorage.getItem(KEY);
  if (existing) return existing;
  const id =
    (crypto as any).randomUUID?.() ??
    Math.random().toString(36).slice(2) + Date.now().toString(36);
  window.localStorage.setItem(KEY, id);
  return id;
}
