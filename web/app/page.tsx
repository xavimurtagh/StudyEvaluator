"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { GradePill } from "@/components/GradePill";
import { checkClaim, listProducts, submitSearch } from "@/lib/api";
import type { ProductListEntry } from "@/lib/types";

const SAMPLES = [
  "collagen peptides",
  "ashwagandha",
  "creatine",
  "retinol",
  "magnesium for sleep",
];

const CLAIM_SAMPLES = [
  "Collagen supplements regrow hair",
  "Ashwagandha reduces stress",
  "Magnesium helps with sleep",
];

type Mode = "product" | "claim";

export default function Home() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("product");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recent, setRecent] = useState<ProductListEntry[]>([]);

  useEffect(() => {
    listProducts().then(setRecent).catch(() => setRecent([]));
  }, []);

  async function goProduct(query: string) {
    setError(null);
    setLoading(true);
    try {
      const job = await submitSearch(query);
      if (job.state === "complete" && job.slug) {
        router.push(`/product/${job.slug}`);
      } else if (job.slug) {
        router.push(`/product/${job.slug}?job=${job.job_id}`);
      } else {
        setError("Could not start analysis.");
        setLoading(false);
      }
    } catch (e: any) {
      setError(e.message ?? "Something went wrong.");
      setLoading(false);
    }
  }

  async function goClaim(text: string) {
    setError(null);
    setLoading(true);
    try {
      const resp = await checkClaim(text);
      const job = resp.job;
      const slug = job.slug ?? "";
      const highlight = encodeURIComponent(resp.predicate);
      if (job.state === "complete" && slug) {
        router.push(`/product/${slug}?highlight=${highlight}`);
      } else if (slug) {
        router.push(
          `/product/${slug}?job=${job.job_id}&highlight=${highlight}`,
        );
      } else {
        setError("Could not start the claim check.");
        setLoading(false);
      }
    } catch (e: any) {
      setError(e.message ?? "Something went wrong.");
      setLoading(false);
    }
  }

  function submitForm() {
    if (!q.trim()) return;
    if (mode === "product") goProduct(q.trim());
    else goClaim(q.trim());
  }

  return (
    <div className="space-y-16">
      <section className="space-y-6">
        <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">
          What do the studies <em className="font-serif italic">actually</em>{" "}
          say?
        </h1>
        <p className="max-w-2xl text-lg text-muted">
          Wellness misinformation thrives on screenshots of "studies" that
          either don't say what the post claims, or come from small,
          industry-funded, or animal-only research. StudyEvaluator pulls the
          real literature, scores each study, and tells you the
          evidence-graded verdict — with every paper and reason visible.
        </p>

        <div className="inline-flex rounded-lg border border-line bg-white p-1 text-sm">
          <ModeButton
            active={mode === "product"}
            onClick={() => setMode("product")}
            label="Search a product"
          />
          <ModeButton
            active={mode === "claim"}
            onClick={() => setMode("claim")}
            label="Check a claim"
          />
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            submitForm();
          }}
          className="flex max-w-2xl flex-col gap-3 sm:flex-row"
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={
              mode === "product"
                ? "e.g. collagen peptides, ashwagandha..."
                : 'e.g. "Collagen supplements regrow hair"'
            }
            className="w-full rounded-lg border border-line bg-white px-4 py-3 text-base shadow-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
            disabled={loading}
          />
          <button
            disabled={loading || !q.trim()}
            className="rounded-lg bg-ink px-5 py-3 font-medium text-white shadow-sm transition hover:opacity-90 disabled:opacity-50"
          >
            {loading
              ? "Analyzing..."
              : mode === "product"
              ? "Analyze"
              : "Fact-check"}
          </button>
        </form>

        {error && <p className="text-sm text-red-700">{error}</p>}

        <div className="flex flex-wrap gap-2 text-sm">
          <span className="text-muted">Try:</span>
          {(mode === "product" ? SAMPLES : CLAIM_SAMPLES).map((s) => (
            <button
              key={s}
              onClick={() => {
                setQ(s);
                mode === "product" ? goProduct(s) : goClaim(s);
              }}
              className="rounded-full border border-line bg-white px-3 py-1 hover:border-ink"
            >
              {s}
            </button>
          ))}
        </div>
      </section>

      {recent.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-xl font-semibold">Recently analyzed</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((p) => (
              <Link
                key={p.slug}
                href={`/product/${p.slug}`}
                className="flex items-center justify-between gap-3 rounded-lg border border-line bg-white p-4 hover:border-ink"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium capitalize">{p.name}</p>
                  <p className="text-xs text-muted">
                    {p.study_count} studies analyzed
                  </p>
                </div>
                <GradePill grade={p.overall_grade} />
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="grid gap-6 md:grid-cols-3">
        <Card
          title="Pulls real studies"
          body="Searches PubMed (and extensions: Cochrane, Semantic Scholar) for the product or ingredient. No cherry-picking — weak studies are in the set so you can see they're weak."
        />
        <Card
          title="Scores each one"
          body="An interpretable classifier rates each study on internal validity, risk of bias, generalizability, and reporting. Every score has a list of reasons."
        />
        <Card
          title="Aligns claims to evidence"
          body="A separate model decides whether each study actually supports, contradicts, or is unrelated to the marketed claim. That's the failure mode for screenshot 'proof'."
        />
      </section>

      <section className="space-y-3 rounded-xl border border-line bg-white p-6">
        <h2 className="text-xl font-semibold">
          How it differs from asking ChatGPT
        </h2>
        <ul className="ml-5 list-disc space-y-1 text-muted">
          <li>Same query, same verdict. Deterministic and auditable.</li>
          <li>
            Every grade traces to specific studies and specific quality
            features.
          </li>
          <li>
            Catches "study showed X in mice at 100× human dose" being marketed
            as "proven to do X" — the alignment classifier does that job
            explicitly.
          </li>
          <li>
            Surfaces industry funding, sample size, and design-tier issues,
            not just a number.
          </li>
        </ul>
        <p className="pt-2 text-sm text-muted">
          <Link href="/about" className="underline">
            Read about the architecture →
          </Link>
        </p>
      </section>
    </div>
  );
}

function ModeButton({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 transition ${
        active ? "bg-ink text-white" : "text-muted hover:text-ink"
      }`}
    >
      {label}
    </button>
  );
}

function Card({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-line bg-white p-5">
      <h3 className="mb-2 font-medium">{title}</h3>
      <p className="text-sm text-muted">{body}</p>
    </div>
  );
}
