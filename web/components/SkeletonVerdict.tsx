export function SkeletonVerdict({
  message,
  progress,
}: {
  message?: string | null;
  progress: number;
}) {
  return (
    <div className="space-y-10 animate-pulse">
      <div className="space-y-3">
        <div className="h-9 w-2/3 rounded bg-stone-200" />
        <div className="h-6 w-24 rounded-full bg-stone-200" />
      </div>

      <div className="space-y-2">
        <div className="h-4 w-full rounded bg-stone-200" />
        <div className="h-4 w-5/6 rounded bg-stone-200" />
      </div>

      <div className="h-2 w-full overflow-hidden rounded-full bg-stone-100">
        <div
          className="h-2 rounded-full bg-ink transition-all"
          style={{ width: `${Math.round(Math.max(progress, 0.05) * 100)}%` }}
        />
      </div>

      <p className="text-sm text-muted not-italic">
        {message ?? "Searching PubMed and scoring the studies..."}
      </p>

      <div className="space-y-3">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="rounded-xl border border-line bg-white p-6 space-y-3"
          >
            <div className="flex justify-between gap-3">
              <div className="h-5 w-1/2 rounded bg-stone-200" />
              <div className="h-5 w-20 rounded-full bg-stone-200" />
            </div>
            <div className="h-4 w-full rounded bg-stone-100" />
            <div className="h-4 w-2/3 rounded bg-stone-100" />
          </div>
        ))}
      </div>
    </div>
  );
}
