import type {
  CheckClaimResponse,
  JobStatus,
  ProductListEntry,
  ProductVerdict,
} from "./types";

const API = "/api";

export async function submitSearch(
  query: string,
  claims?: string[],
): Promise<JobStatus> {
  const res = await fetch(`${API}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, claims }),
  });
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export async function checkClaim(text: string): Promise<CheckClaimResponse> {
  const res = await fetch(`${API}/check-claim`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Claim check failed: ${res.status}`);
  }
  return res.json();
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API}/jobs/${jobId}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Job not found: ${res.status}`);
  return res.json();
}

export async function getProduct(slug: string): Promise<ProductVerdict> {
  const res = await fetch(`${API}/products/${slug}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Product not found: ${res.status}`);
  return res.json();
}

export async function listProducts(): Promise<ProductListEntry[]> {
  const res = await fetch(`${API}/products`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}
