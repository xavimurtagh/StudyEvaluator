import type { EvidenceGrade } from "@/lib/types";
import { GRADE_LABEL } from "@/lib/format";

const CLASS: Record<EvidenceGrade, string> = {
  strong: "grade-pill grade-strong",
  moderate: "grade-pill grade-moderate",
  weak: "grade-pill grade-weak",
  insufficient: "grade-pill grade-insufficient",
  contradicted: "grade-pill grade-contradicted",
};

const DOT: Record<EvidenceGrade, string> = {
  strong: "bg-green-700",
  moderate: "bg-lime-600",
  weak: "bg-yellow-600",
  insufficient: "bg-stone-500",
  contradicted: "bg-red-600",
};

export function GradePill({ grade }: { grade: EvidenceGrade }) {
  return (
    <span className={CLASS[grade]}>
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${DOT[grade]}`} />
      {GRADE_LABEL[grade]}
    </span>
  );
}
