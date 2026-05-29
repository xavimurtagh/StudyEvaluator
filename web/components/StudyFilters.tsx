"use client";

import type { ScoredStudy, StudyDesign } from "@/lib/types";
import { DESIGN_LABEL } from "@/lib/format";

export interface StudyFilterState {
  designs: Set<StudyDesign>;
  excludeIndustry: boolean;
  excludeAnimal: boolean;
  hideRetracted: boolean;
}

export const EMPTY_FILTERS: StudyFilterState = {
  designs: new Set(),
  excludeIndustry: false,
  excludeAnimal: false,
  hideRetracted: true,
};

export function applyFilters(
  studies: ScoredStudy[],
  f: StudyFilterState,
): ScoredStudy[] {
  return studies.filter((s) => {
    const e = s.extracted;
    if (f.designs.size > 0 && !f.designs.has(e.design)) return false;
    if (f.excludeIndustry && e.industry_funded === true) return false;
    if (f.excludeAnimal && e.human_subjects === false) return false;
    if (f.hideRetracted && e.retracted) return false;
    return true;
  });
}

export function StudyFilters({
  studies,
  state,
  onChange,
}: {
  studies: ScoredStudy[];
  state: StudyFilterState;
  onChange: (s: StudyFilterState) => void;
}) {
  const counts: Record<string, number> = {};
  for (const s of studies) {
    counts[s.extracted.design] = (counts[s.extracted.design] ?? 0) + 1;
  }
  const designs = Object.keys(counts) as StudyDesign[];
  designs.sort((a, b) => counts[b] - counts[a]);

  const toggleDesign = (d: StudyDesign) => {
    const next = new Set(state.designs);
    if (next.has(d)) next.delete(d);
    else next.add(d);
    onChange({ ...state, designs: next });
  };

  return (
    <div className="space-y-2 print:hidden">
      <div className="flex flex-wrap items-center gap-2">
        {designs.map((d) => {
          const on = state.designs.has(d);
          return (
            <button
              key={d}
              onClick={() => toggleDesign(d)}
              className={`rounded-full px-2.5 py-1 text-xs ring-1 transition ${
                on
                  ? "bg-ink text-white ring-ink"
                  : "bg-white text-stone-700 ring-line hover:ring-stone-400"
              }`}
            >
              {DESIGN_LABEL[d]} <span className="opacity-60">({counts[d]})</span>
            </button>
          );
        })}
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted">
        <Toggle
          label="Hide industry-funded"
          on={state.excludeIndustry}
          onChange={(v) => onChange({ ...state, excludeIndustry: v })}
        />
        <Toggle
          label="Hide animal / in-vitro"
          on={state.excludeAnimal}
          onChange={(v) => onChange({ ...state, excludeAnimal: v })}
        />
        <Toggle
          label="Hide retracted"
          on={state.hideRetracted}
          onChange={(v) => onChange({ ...state, hideRetracted: v })}
        />
      </div>
    </div>
  );
}

function Toggle({
  label,
  on,
  onChange,
}: {
  label: string;
  on: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-1.5 select-none">
      <input
        type="checkbox"
        checked={on}
        onChange={(e) => onChange(e.target.checked)}
        className="h-3.5 w-3.5 accent-ink"
      />
      {label}
    </label>
  );
}
