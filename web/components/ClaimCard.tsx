"use client";

import { useState } from "react";

import { GradePill } from "./GradePill";
import type {
  ClaimEvidenceLink,
  ClaimVerdict,
  ScoredStudy,
} from "@/lib/types";

export function ClaimCard({
  claim,
  studiesByPmid,
}: {
  claim: ClaimVerdict;
  studiesByPmid: Record<string, ScoredStudy>;
}) {
  const [open, setOpen] = useState(false);
  const sup = claim.supporting_studies;
  const con = claim.contradicting_studies;

  return (
    <article className="rounded-xl border border-line bg-white p-6">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h3 className="text-lg font-medium capitalize">{claim.claim}</h3>
        <GradePill grade={claim.grade} />
      </header>

      <p className="mt-2 text-muted">{claim.plain_language}</p>

      {claim.notes.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm text-muted">
          {claim.notes.map((n, i) => (
            <li key={i}>· {n}</li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex gap-6 text-sm text-muted">
        <span>
          <strong className="text-ink">{sup.length}</strong> supporting
        </span>
        <span>
          <strong className="text-ink">{con.length}</strong> contradicting
        </span>
      </div>

      <button
        onClick={() => setOpen((o) => !o)}
        className="mt-3 text-sm font-medium text-accent hover:underline"
      >
        {open ? "Hide" : "Show"} the studies behind this verdict
      </button>

      {open && (
        <div className="mt-4 space-y-4 border-t border-line pt-4 text-sm">
          {sup.length > 0 && (
            <LinkList title="Supports" links={sup} studiesByPmid={studiesByPmid} />
          )}
          {con.length > 0 && (
            <LinkList
              title="Contradicts / null finding"
              links={con}
              studiesByPmid={studiesByPmid}
            />
          )}
          {sup.length === 0 && con.length === 0 && (
            <p className="text-muted">
              No studies in the analyzed set are directly relevant to this claim.
            </p>
          )}
        </div>
      )}
    </article>
  );
}

function LinkList({
  title,
  links,
  studiesByPmid,
}: {
  title: string;
  links: ClaimEvidenceLink[];
  studiesByPmid: Record<string, ScoredStudy>;
}) {
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
        {title}
      </h4>
      <ul className="space-y-3">
        {links.map((l) => {
          const s = studiesByPmid[l.pmid];
          if (!s) return null;
          return (
            <li key={l.pmid} className="border-l-2 border-line pl-3">
              <a
                href={s.extracted.url ?? "#"}
                target="_blank"
                rel="noreferrer"
                className="font-medium hover:underline"
              >
                {s.extracted.title}
              </a>
              <p className="text-xs text-muted">
                {s.extracted.journal} · {s.extracted.year} · quality{" "}
                {Math.round(s.quality.score * 100)}%
              </p>
              {l.quote && (
                <blockquote className="mt-1 border-l border-stone-300 pl-2 italic text-stone-600">
                  “{l.quote}”
                </blockquote>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
