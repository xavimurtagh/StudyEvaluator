import Link from "next/link";

export default function AboutPage() {
  return (
    <article className="prose prose-stone max-w-3xl space-y-8">
      <Link href="/" className="text-sm text-muted hover:text-ink">
        ← back
      </Link>

      <h1 className="text-3xl font-semibold tracking-tight">How StudyEvaluator works</h1>

      <p className="text-lg text-muted">
        The problem isn't that science is wrong. It's that "science" is being
        used as a marketing prop — a single small study, often industry-funded,
        often on mice, gets screenshotted as proof of a claim the study doesn't
        actually make. We built a six-stage pipeline to evaluate the actual
        body of evidence for a product or ingredient, transparently.
      </p>

      <Section title="1. Ingest">
        For a query like "collagen peptides", we hit PubMed's E-utilities API
        with MeSH-aware queries, pulling up to 25 candidate studies. We don't
        filter by publication type — weak studies <em>should</em> be in the
        set, so they can be visibly scored as weak.
      </Section>

      <Section title="2. Feature extraction">
        For each paper we extract structured features from the title +
        abstract: study design (RCT / cohort / animal / in vitro / etc.),
        sample size, duration, blinding, randomization, placebo control,
        pre-registration, funding source, declared COI, and the directional
        findings (positive / null / negative effect).
      </Section>

      <Section title="3. Study quality classifier">
        Each study is scored 0–1 on overall quality with sub-scores for
        internal validity, external validity, risk of bias, and reporting.
        The current implementation is an interpretable rubric based on
        Cochrane RoB 2 — every score comes with the list of reasons that
        produced it. The same feature vector is the contract for a trained
        gradient-boosted classifier (drop-in replacement, in{" "}
        <code>api/pipeline/quality.py</code>).
      </Section>

      <Section title="4. Claim discovery">
        From the corpus, we derive the marketed claims people actually make
        about the product ("improves skin elasticity", "reduces joint pain").
        Users can also supply a specific claim to fact-check directly — the
        rest of the pipeline runs the same way.
      </Section>

      <Section title="5. Claim-evidence alignment">
        For each (claim, study) pair, a separate classifier decides whether
        the study <em>supports</em>, <em>contradicts</em>, or is{" "}
        <em>unrelated</em> to the claim. This is the piece that catches the
        "study showed X in mice at 100× human dose" failure mode — the study
        might be real, but the claim it's used to back isn't what it found.
      </Section>

      <Section title="6. Evidence grading">
        GRADE-inspired aggregation: start from the strongest design tier
        supporting the claim, downgrade for inconsistency, small samples,
        single-study evidence, or low average quality. Heterogeneity and
        funding concentration are surfaced as separate <em>red flags</em>
        rather than hidden inside a single number.
      </Section>

      <h2 className="pt-4 text-2xl font-semibold">Principles</h2>
      <ul className="ml-5 list-disc space-y-2 text-muted">
        <li>
          <strong className="text-ink">Show the work.</strong> Every claim is
          clickable down to the studies that produced it, and every study has
          a quality breakdown.
        </li>
        <li>
          <strong className="text-ink">Name the absence of evidence.</strong>{" "}
          "Insufficient" is a valid, useful answer. We don't pretend there's a
          verdict when there isn't.
        </li>
        <li>
          <strong className="text-ink">Distinguish ingredient from product.</strong>{" "}
          Studies test isolated compounds at specific doses. The product on
          the shelf often isn't equivalent. We surface this gap.
        </li>
        <li>
          <strong className="text-ink">Deterministic.</strong> Same query, same
          verdict. Every grade traces to the same auditable scoring rules and
          model version.
        </li>
      </ul>

      <h2 className="pt-4 text-2xl font-semibold">What's next</h2>
      <ul className="ml-5 list-disc space-y-2 text-muted">
        <li>
          Train the ML quality classifier on Cochrane RoB labels (the
          interface is ready — see <code>MLQualityScorer</code>).
        </li>
        <li>
          Swap the rule-based alignment for a fine-tuned NLI model on SciFact
          / HealthVer.
        </li>
        <li>
          Add Retraction Watch cross-checks and full-text fetching for
          open-access PDFs.
        </li>
        <li>
          A "paste this TikTok claim" form that runs the alignment classifier
          against the literature directly.
        </li>
        <li>Browser extension that fact-checks claims inline as you scroll.</li>
      </ul>

      <p className="text-sm text-muted">
        StudyEvaluator is for informational use only. It is not a substitute
        for medical advice.
      </p>
    </article>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h2 className="text-xl font-semibold">{title}</h2>
      <p className="text-muted">{children}</p>
    </section>
  );
}
