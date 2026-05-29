import type { ClaimEvidenceLink, ScoredStudy } from "@/lib/types";

/**
 * Visual bar showing the weighted balance of supporting vs contradicting
 * evidence behind a claim. Weight = link.confidence * study quality, which
 * mirrors how the aggregator actually grades the claim.
 *
 * Not the same as study counts: 1 strong meta-analysis can outweigh 3 weak
 * case series.
 */
export function EvidenceBar({
  supporting,
  contradicting,
  studiesByPmid,
}: {
  supporting: ClaimEvidenceLink[];
  contradicting: ClaimEvidenceLink[];
  studiesByPmid: Record<string, ScoredStudy>;
}) {
  const weight = (l: ClaimEvidenceLink) => {
    const s = studiesByPmid[l.pmid];
    if (!s) return 0;
    return Math.max(0, l.confidence) * Math.max(0.05, s.quality.score);
  };
  const sup = supporting.reduce((a, l) => a + weight(l), 0);
  const con = contradicting.reduce((a, l) => a + weight(l), 0);
  const total = sup + con;
  if (total <= 0) return null;
  const supPct = (sup / total) * 100;
  const conPct = 100 - supPct;
  return (
    <div className="mt-3 space-y-1">
      <div
        className="flex h-2 overflow-hidden rounded-full bg-stone-100"
        title={`Supporting weight ${sup.toFixed(2)} vs contradicting ${con.toFixed(2)}`}
      >
        <div className="bg-green-500" style={{ width: `${supPct}%` }} />
        <div className="bg-red-500" style={{ width: `${conPct}%` }} />
      </div>
      <div className="flex justify-between text-xs text-muted">
        <span>Supporting weight {supPct.toFixed(0)}%</span>
        <span>Contradicting {conPct.toFixed(0)}%</span>
      </div>
    </div>
  );
}
