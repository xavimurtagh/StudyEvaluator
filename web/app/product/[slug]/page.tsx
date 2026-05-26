"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";

import { ClaimCard } from "@/components/ClaimCard";
import { GradePill } from "@/components/GradePill";
import { RedFlags } from "@/components/RedFlags";
import { StudyCard } from "@/components/StudyCard";
import { getJob, getProduct } from "@/lib/api";
import { GRADE_BLURB } from "@/lib/format";
import type { JobStatus, ProductVerdict } from "@/lib/types";

export default function ProductPage() {
  const params = useParams<{ slug: string }>();
  const search = useSearchParams();
  const jobId = search.get("job");
  const slug = params.slug;

  const [verdict, setVerdict] = useState<ProductVerdict | null>(null);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState<"quality" | "year" | "design">("quality");

  // Initial product fetch.
  useEffect(() => {
    let cancelled = false;
    getProduct(slug)
      .then((v) => !cancelled && setVerdict(v))
      .catch(() => {
        // No verdict yet -- we expect a job to be running.
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  // Poll job until it finishes, then fetch the verdict.
  useEffect(() => {
    if (!jobId || jobId === "cached") return;
    if (verdict) return;
    let cancelled = false;
    let timer: any;

    async function tick() {
      try {
        const j = await getJob(jobId!);
        if (cancelled) return;
        setJob(j);
        if (j.state === "complete" && j.slug) {
          const v = await getProduct(j.slug);
          if (!cancelled) setVerdict(v);
        } else if (j.state === "error") {
          setError(j.message ?? "Analysis failed.");
        } else {
          timer = setTimeout(tick, 800);
        }
      } catch (e: any) {
        setError(e.message ?? "Lost connection to the API.");
      }
    }
    tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, verdict]);

  const studiesByPmid = useMemo(() => {
    const m: Record<string, any> = {};
    verdict?.studies.forEach((s) => (m[s.extracted.pmid] = s));
    return m;
  }, [verdict]);

  const sortedStudies = useMemo(() => {
    if (!verdict) return [];
    const a = [...verdict.studies];
    a.sort((x, y) => {
      if (sort === "quality") return y.quality.score - x.quality.score;
      if (sort === "year")
        return (y.extracted.year ?? 0) - (x.extracted.year ?? 0);
      return x.extracted.design.localeCompare(y.extracted.design);
    });
    return a;
  }, [verdict, sort]);

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-red-900">
        <p className="font-medium">Something went wrong</p>
        <p className="mt-1 text-sm">{error}</p>
        <Link href="/" className="mt-3 inline-block text-sm underline">
          ← back to search
        </Link>
      </div>
    );
  }

  if (!verdict) {
    return <LoadingState job={job} />;
  }

  return (
    <article className="space-y-12">
      <Link href="/" className="text-sm text-muted hover:text-ink">
        ← search again
      </Link>

      <section className="space-y-4">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h1 className="text-3xl font-semibold tracking-tight capitalize md:text-4xl">
            {verdict.product}
          </h1>
          <GradePill grade={verdict.overall_grade} />
        </div>
        <p className="text-lg text-muted">{verdict.summary}</p>
        <p className="text-sm text-muted">
          {GRADE_BLURB[verdict.overall_grade]}
        </p>
      </section>

      {verdict.red_flags.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Red flags in the evidence base</h2>
          <RedFlags flags={verdict.red_flags} />
        </section>
      )}

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Claims, graded</h2>
        <p className="text-sm text-muted">
          Each marketed benefit is graded against the actual studies. Click to
          see which papers (and what they actually found).
        </p>
        <div className="space-y-4">
          {verdict.claims.map((c) => (
            <ClaimCard
              key={c.claim}
              claim={c}
              studiesByPmid={studiesByPmid}
            />
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 className="text-xl font-semibold">
            All studies analyzed ({verdict.studies.length})
          </h2>
          <label className="text-sm text-muted">
            Sort by{" "}
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as any)}
              className="rounded-md border border-line bg-white px-2 py-1 text-sm"
            >
              <option value="quality">quality</option>
              <option value="year">year</option>
              <option value="design">design</option>
            </select>
          </label>
        </div>
        <div className="space-y-3">
          {sortedStudies.map((s) => (
            <StudyCard key={s.extracted.pmid} s={s} />
          ))}
        </div>
      </section>

      {verdict.notes.length > 0 && (
        <section className="rounded-lg border border-line bg-white p-5 text-sm text-muted">
          <h3 className="mb-2 font-medium text-ink">Caveats</h3>
          <ul className="ml-4 list-disc space-y-1">
            {verdict.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </section>
      )}

      <footer className="text-xs text-muted">
        Generated {new Date(verdict.generated_at).toLocaleString()} · pipeline{" "}
        {verdict.pipeline_version}
      </footer>
    </article>
  );
}

function LoadingState({ job }: { job: JobStatus | null }) {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Analyzing...</h1>
      <p className="text-muted">
        {job?.message ?? "Searching PubMed and scoring the studies..."}
      </p>
      <div className="h-2 w-full overflow-hidden rounded-full bg-stone-100">
        <div
          className="h-2 rounded-full bg-ink transition-all"
          style={{ width: `${Math.round((job?.progress ?? 0.1) * 100)}%` }}
        />
      </div>
    </div>
  );
}
