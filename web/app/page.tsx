"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { submitSearch } from "@/lib/api";

const SAMPLES = [
  "collagen peptides",
  "ashwagandha",
  "creatine for hair loss",
  "retinol",
  "magnesium for sleep",
];

export default function Home() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function go(query: string) {
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

  return (
    <div className="space-y-16">
      <section className="space-y-6">
        <h1 className="text-4xl font-semibold tracking-tight md:text-5xl">
          What do the studies <em className="font-serif italic">actually</em> say?
        </h1>
        <p className="max-w-2xl text-lg text-muted">
          Wellness misinformation thrives on screenshots of "studies" that
          either don't say what the post claims, or come from small,
          industry-funded, or animal-only research. StudyEvaluator pulls the
          real literature, scores each study, and tells you the evidence-graded
          verdict — with every paper and reason visible.
        </p>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (q.trim()) go(q.trim());
          }}
          className="flex max-w-2xl flex-col gap-3 sm:flex-row"
        >
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="e.g. collagen peptides, ashwagandha, retinol..."
            className="w-full rounded-lg border border-line bg-white px-4 py-3 text-base shadow-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
            disabled={loading}
          />
          <button
            disabled={loading || !q.trim()}
            className="rounded-lg bg-ink px-5 py-3 font-medium text-white shadow-sm transition hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "Analyzing..." : "Analyze"}
          </button>
        </form>

        {error && (
          <p className="text-sm text-red-700">{error}</p>
        )}

        <div className="flex flex-wrap gap-2 text-sm">
          <span className="text-muted">Try:</span>
          {SAMPLES.map((s) => (
            <button
              key={s}
              onClick={() => {
                setQ(s);
                go(s);
              }}
              className="rounded-full border border-line bg-white px-3 py-1 hover:border-ink"
            >
              {s}
            </button>
          ))}
        </div>
      </section>

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
        <h2 className="text-xl font-semibold">How it differs from asking ChatGPT</h2>
        <ul className="ml-5 list-disc space-y-1 text-muted">
          <li>Same query, same verdict. Deterministic and auditable.</li>
          <li>Every grade traces to specific studies and specific quality features.</li>
          <li>
            Catches "study showed X in mice at 100× human dose" being marketed
            as "proven to do X" — the alignment classifier does that job
            explicitly.
          </li>
          <li>Surfaces industry funding, sample size, and design-tier issues, not just a number.</li>
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

function Card({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-line bg-white p-5">
      <h3 className="mb-2 font-medium">{title}</h3>
      <p className="text-sm text-muted">{body}</p>
    </div>
  );
}
