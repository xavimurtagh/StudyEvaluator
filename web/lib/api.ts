import type {
  CheckClaimResponse,
  JobStatus,
  ProductListEntry,
  ProductVerdict,
  WatchView,
} from "./types";

const API = "/api";
const CREDS: RequestCredentials = "include";

export async function submitSearch(
  query: string,
  claims?: string[],
  maxStudies?: number,
): Promise<JobStatus> {
  const res = await fetch(`${API}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      claims,
      ...(maxStudies ? { max_studies: maxStudies } : {}),
    }),
    credentials: CREDS,
  });
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export async function checkClaim(text: string): Promise<CheckClaimResponse> {
  const res = await fetch(`${API}/check-claim`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
    credentials: CREDS,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Claim check failed: ${res.status}`);
  }
  return res.json();
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API}/jobs/${jobId}`, { cache: "no-store", credentials: CREDS });
  if (!res.ok) throw new Error(`Job not found: ${res.status}`);
  return res.json();
}

export async function getProduct(slug: string): Promise<ProductVerdict> {
  const res = await fetch(`${API}/products/${slug}`, { cache: "no-store", credentials: CREDS });
  if (!res.ok) throw new Error(`Product not found: ${res.status}`);
  return res.json();
}

export async function listProducts(): Promise<ProductListEntry[]> {
  const res = await fetch(`${API}/products`, { cache: "no-store", credentials: CREDS });
  if (!res.ok) return [];
  return res.json();
}

function watchUrl(path: string, clientId?: string | null): string {
  const qs = clientId
    ? `${path.includes("?") ? "&" : "?"}client_id=${encodeURIComponent(clientId)}`
    : "";
  return `${API}${path}${qs}`;
}

export async function listWatches(clientId?: string | null): Promise<WatchView[]> {
  const res = await fetch(watchUrl("/watches", clientId), {
    cache: "no-store",
    credentials: CREDS,
  });
  if (!res.ok) return [];
  return res.json();
}

export async function createWatch(
  clientId: string | null,
  slug: string,
): Promise<WatchView> {
  const res = await fetch(`${API}/watches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId ?? undefined, slug }),
    credentials: CREDS,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Could not watch: ${res.status}`);
  }
  return res.json();
}

export async function deleteWatch(
  clientId: string | null,
  id: number,
): Promise<void> {
  await fetch(watchUrl(`/watches/${id}`, clientId), {
    method: "DELETE",
    credentials: CREDS,
  });
}

export async function markWatchSeen(
  clientId: string | null,
  id: number,
): Promise<WatchView | null> {
  const res = await fetch(watchUrl(`/watches/${id}/seen`, clientId), {
    method: "POST",
    credentials: CREDS,
  });
  if (!res.ok) return null;
  return res.json();
}

export interface Me {
  id: number;
  email: string;
}

export async function getMe(): Promise<Me | null> {
  const res = await fetch(`${API}/me`, { cache: "no-store", credentials: CREDS });
  if (res.status === 401) return null;
  if (!res.ok) return null;
  return res.json();
}

export async function requestMagicLink(
  email: string,
  clientId: string | null,
): Promise<void> {
  const res = await fetch(`${API}/auth/request-link`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, client_id: clientId ?? undefined }),
    credentials: CREDS,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Could not send link: ${res.status}`);
  }
}

export async function signOut(): Promise<void> {
  await fetch(`${API}/auth/logout`, { method: "POST", credentials: CREDS });
}
