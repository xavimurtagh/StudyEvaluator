"use client";

import { useState } from "react";

import type { ScoredStudy } from "@/lib/types";
import { DESIGN_LABEL, formatDuration, formatPercent } from "@/lib/format";

export function StudyCard({ s }: { s: ScoredStudy }) {
  const [open, setOpen] = useState(false);
  const e = s.extracted;
  const q = s.quality;
  return (
    <article className="rounded-lg border border-line bg-white p-5">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h4 className="text-base font-medium leading-snug">
            <a
              href={e.url ?? "#"}
              target="_blank"
              rel="noreferrer"
              className="hover:underline"
            >
              {e.title}
            </a>
          </h4>
          <p className="mt-1 text-sm text-muted">
            {e.journal && <span>{e.journal} · </span>}
            {e.year && <span>{e.year} · </span>}
            {e.authors.slice(0, 3).join(", ")}
            {e.authors.length > 3 && " et al."}
          </p>
        </div>
        <QualityBadge score={q.score} />
      </header>

      <div className="mt-4 flex flex-wrap gap-2 text-xs">
        <Chip label={DESIGN_LABEL[e.design]} />
        {e.sample_size != null && <Chip label={`n = ${e.sample_size}`} />}
        {e.duration_weeks != null && (
          <Chip label={formatDuration(e.duration_weeks) ?? ""} />
        )}
        {e.randomized === true && <Chip label="Randomized" />}
        {e.blinded === true && <Chip label="Blinded" />}
        {e.placebo_controlled === true && <Chip label="Placebo-controlled" />}
        {e.preregistered === true && <Chip label="Pre-registered" tone="good" />}
        {e.industry_funded === true && (
          <Chip label="Industry funded" tone="warn" />
        )}
        {e.conflict_of_interest === true && <Chip label="COI declared" tone="warn" />}
        {e.human_subjects === false && (
          <Chip label="Non-human" tone="warn" />
        )}
        {e.retracted && <Chip label="RETRACTED" tone="bad" />}
      </div>

      <button
        onClick={() => setOpen((o) => !o)}
        className="mt-4 text-sm font-medium text-accent hover:underline"
      >
        {open ? "Hide" : "Show"} quality breakdown
      </button>

      {open && (
        <div className="mt-3 space-y-3 border-t border-line pt-3 text-sm">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <SubBar label="Internal validity" v={q.subscores.internal_validity} />
            <SubBar label="External validity" v={q.subscores.external_validity} />
            <SubBar label="Risk of bias" v={q.subscores.risk_of_bias} />
            <SubBar label="Reporting" v={q.subscores.reporting} />
          </div>
          <ul className="ml-4 list-disc space-y-1 text-muted">
            {q.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
          <p className="pt-1 text-xs text-muted">Scoring model: {q.model_version}</p>
        </div>
      )}
    </article>
  );
}

function QualityBadge({ score }: { score: number }) {
  const tone =
    score >= 0.7
      ? "bg-green-50 text-green-900 ring-green-200"
      : score >= 0.5
      ? "bg-lime-50 text-lime-900 ring-lime-200"
      : score >= 0.3
      ? "bg-yellow-50 text-yellow-900 ring-yellow-200"
      : "bg-red-50 text-red-900 ring-red-200";
  return (
    <div
      className={`rounded-md px-3 py-1 text-xs font-medium ring-1 ${tone}`}
      title="Overall study quality (0–1). Click 'quality breakdown' for reasons."
    >
      Quality {formatPercent(score)}
    </div>
  );
}

function Chip({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: "neutral" | "good" | "warn" | "bad";
}) {
  const cls =
    tone === "good"
      ? "bg-green-50 text-green-900 ring-green-200"
      : tone === "warn"
      ? "bg-amber-50 text-amber-900 ring-amber-200"
      : tone === "bad"
      ? "bg-red-50 text-red-900 ring-red-200"
      : "bg-stone-50 text-stone-700 ring-stone-200";
  return <span className={`rounded-full px-2 py-0.5 ring-1 ${cls}`}>{label}</span>;
}

function SubBar({ label, v }: { label: string; v: number }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs text-muted">
        <span>{label}</span>
        <span>{formatPercent(v)}</span>
      </div>
      <div className="h-1.5 rounded-full bg-stone-100">
        <div
          className="h-1.5 rounded-full bg-ink"
          style={{ width: `${Math.round(v * 100)}%` }}
        />
      </div>
    </div>
  );
}
