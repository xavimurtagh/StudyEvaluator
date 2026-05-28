export type EvidenceGrade =
  | "strong"
  | "moderate"
  | "weak"
  | "insufficient"
  | "contradicted";

export type AlignmentLabel =
  | "supports"
  | "partially_supports"
  | "unrelated"
  | "contradicts";

export type StudyDesign =
  | "meta_analysis"
  | "systematic_review"
  | "rct"
  | "cohort"
  | "case_control"
  | "cross_sectional"
  | "case_series"
  | "animal"
  | "in_vitro"
  | "narrative_review"
  | "unknown";

export interface QualitySubscores {
  internal_validity: number;
  external_validity: number;
  risk_of_bias: number;
  reporting: number;
}

export interface QualityAssessment {
  score: number;
  subscores: QualitySubscores;
  reasons: string[];
  model_version: string;
}

export interface ExtractedFinding {
  text: string;
  direction: "positive" | "null" | "negative";
  effect_size: string | null;
}

export interface ProductListEntry {
  slug: string;
  name: string;
  overall_grade: EvidenceGrade;
  study_count: number;
  last_analyzed: string;
}

export interface CheckClaimResponse {
  subject: string;
  predicate: string;
  raw: string;
  job: JobStatus;
}

export interface ExtractedStudy {
  pmid: string;
  title: string;
  abstract: string | null;
  journal: string | null;
  year: number | null;
  authors: string[];
  doi: string | null;
  url: string | null;
  design: StudyDesign;
  sample_size: number | null;
  population: string | null;
  intervention: string | null;
  comparator: string | null;
  outcomes: string[];
  duration_weeks: number | null;
  blinded: boolean | null;
  randomized: boolean | null;
  placebo_controlled: boolean | null;
  preregistered: boolean | null;
  industry_funded: boolean | null;
  conflict_of_interest: boolean | null;
  human_subjects: boolean | null;
  retracted: boolean;
  findings: ExtractedFinding[];
}

export interface ScoredStudy {
  extracted: ExtractedStudy;
  quality: QualityAssessment;
}

export interface ClaimEvidenceLink {
  pmid: string;
  alignment: AlignmentLabel;
  confidence: number;
  quote: string | null;
}

export interface ClaimVerdict {
  claim: string;
  grade: EvidenceGrade;
  plain_language: string;
  supporting_studies: ClaimEvidenceLink[];
  contradicting_studies: ClaimEvidenceLink[];
  notes: string[];
}

export interface RedFlag {
  kind: string;
  message: string;
  severity: "info" | "warning" | "critical";
}

export interface ProductVerdict {
  product: string;
  slug: string;
  summary: string;
  overall_grade: EvidenceGrade;
  claims: ClaimVerdict[];
  studies: ScoredStudy[];
  red_flags: RedFlag[];
  generated_at: string;
  pipeline_version: string;
  notes: string[];
}

export interface JobStatus {
  job_id: string;
  state: "queued" | "running" | "complete" | "error";
  progress: number;
  message: string | null;
  slug: string | null;
}
