import type { EvidenceGrade, StudyDesign } from "./types";

export const GRADE_LABEL: Record<EvidenceGrade, string> = {
  strong: "Strong",
  moderate: "Moderate",
  weak: "Weak",
  insufficient: "Insufficient",
  contradicted: "Contradicted",
};

export const GRADE_BLURB: Record<EvidenceGrade, string> = {
  strong:
    "Multiple high-quality studies consistently support this. Closest the evidence base gets to certainty.",
  moderate:
    "Good-quality studies support this, but more replication or larger trials would increase confidence.",
  weak:
    "Some evidence exists, but it's limited by small samples, biased designs, or sparse replication.",
  insufficient:
    "There isn't enough evidence to say either way. That absence is itself informative.",
  contradicted:
    "The actual literature pushes against this claim. Marketing to the contrary isn't backed by science.",
};

export const DESIGN_LABEL: Record<StudyDesign, string> = {
  meta_analysis: "Meta-analysis",
  systematic_review: "Systematic review",
  rct: "Randomized trial",
  cohort: "Cohort study",
  case_control: "Case-control",
  cross_sectional: "Cross-sectional",
  case_series: "Case series",
  animal: "Animal study",
  in_vitro: "In vitro",
  narrative_review: "Review",
  unknown: "Other",
};

export function formatDuration(weeks: number | null): string | null {
  if (!weeks) return null;
  if (weeks < 4) return `${Math.round(weeks)} week${weeks === 1 ? "" : "s"}`;
  if (weeks < 52) return `${(weeks / 4.345).toFixed(1)} months`;
  return `${(weeks / 52.18).toFixed(1)} years`;
}

export function formatPercent(n: number): string {
  return `${Math.round(n * 100)}%`;
}
