"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { GradePill } from "@/components/GradePill";
import { deleteWatch, listWatches } from "@/lib/api";
import { getClientId } from "@/lib/client";
import type { WatchView } from "@/lib/types";

export default function WatchesPage() {
  const [watches, setWatches] = useState<WatchView[] | null>(null);

  useEffect(() => {
    const cid = getClientId();
    if (!cid) return;
    listWatches(cid).then(setWatches);
  }, []);

  async function remove(id: number) {
    const cid = getClientId();
    await deleteWatch(cid, id);
    setWatches((ws) => (ws ?? []).filter((w) => w.id !== id));
  }

  if (watches === null) {
    return <p className="text-muted">Loading your watchlist...</p>;
  }

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <Link href="/" className="text-sm text-muted hover:text-ink">
          ← back
        </Link>
        <h1 className="text-3xl font-semibold tracking-tight">
          Your watchlist
        </h1>
        <p className="text-muted">
          Products you're tracking. We re-run the analysis pipeline on a
          schedule and flag entries with new evidence so you don't have to
          keep checking yourself.
        </p>
      </header>

      {watches.length === 0 ? (
        <div className="rounded-lg border border-dashed border-line bg-white p-8 text-center">
          <p className="font-medium">Nothing watched yet.</p>
          <p className="mt-1 text-sm text-muted">
            Open a verdict page and click <em>Watch</em> to add it here.
          </p>
          <Link
            href="/"
            className="mt-4 inline-block rounded-md bg-ink px-4 py-2 text-sm font-medium text-white"
          >
            Search a product
          </Link>
        </div>
      ) : (
        <ul className="space-y-3">
          {watches.map((w) => (
            <li
              key={w.id}
              className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-white p-4 ${
                w.has_new ? "border-accent ring-2 ring-accent/10" : "border-line"
              }`}
            >
              <Link
                href={`/product/${w.slug}`}
                className="min-w-0 flex-1 hover:underline"
              >
                <p className="truncate font-medium capitalize">{w.name}</p>
                <p className="text-xs text-muted">
                  Last checked {new Date(w.last_checked_at).toLocaleString()} ·{" "}
                  {w.last_study_count} studies
                  {w.has_new && w.new_since_seen > 0 && (
                    <>
                      {" "}
                      ·{" "}
                      <span className="font-medium text-accent">
                        +{w.new_since_seen} new
                      </span>
                    </>
                  )}
                </p>
              </Link>
              <GradePill grade={w.overall_grade} />
              <button
                onClick={() => remove(w.id)}
                className="text-sm text-muted hover:text-red-700"
                title="Remove from watchlist"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
