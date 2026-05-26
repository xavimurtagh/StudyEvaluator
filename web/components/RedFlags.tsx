import type { RedFlag } from "@/lib/types";

export function RedFlags({ flags }: { flags: RedFlag[] }) {
  if (flags.length === 0) {
    return (
      <p className="text-sm text-muted">
        No red flags detected in the analyzed set.
      </p>
    );
  }
  return (
    <ul className="space-y-2">
      {flags.map((f, i) => (
        <li
          key={i}
          className={`flex gap-3 rounded-md p-3 text-sm ring-1 severity-${f.severity}`}
        >
          <span aria-hidden className="mt-0.5 font-bold">
            {f.severity === "critical" ? "!!" : "!"}
          </span>
          <div>
            <p className="font-medium capitalize">
              {f.kind.replace(/_/g, " ")}
            </p>
            <p>{f.message}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
