"use client";

import { useEffect, useState } from "react";

import {
  createWatch,
  deleteWatch,
  listWatches,
  markWatchSeen,
} from "@/lib/api";
import { getClientId } from "@/lib/client";

export function WatchButton({ slug }: { slug: string }) {
  const [watchId, setWatchId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // On mount: check if this slug is already watched, and mark any new
  // evidence as seen now that the user is looking at the verdict.
  useEffect(() => {
    const cid = getClientId();
    if (!cid) return;
    listWatches(cid).then((watches) => {
      const match = watches.find((w) => w.slug === slug);
      if (match) {
        setWatchId(match.id);
        if (match.has_new) {
          markWatchSeen(cid, match.id).catch(() => {});
        }
      }
    });
  }, [slug]);

  async function toggle() {
    setError(null);
    setLoading(true);
    const cid = getClientId();
    try {
      if (watchId) {
        await deleteWatch(cid, watchId);
        setWatchId(null);
      } else {
        const w = await createWatch(cid, slug);
        setWatchId(w.id);
      }
    } catch (e: any) {
      setError(e.message ?? "Could not update watch.");
    } finally {
      setLoading(false);
    }
  }

  const active = watchId !== null;

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={toggle}
        disabled={loading}
        className={`flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition disabled:opacity-50 ${
          active
            ? "border-ink bg-ink text-white hover:opacity-90"
            : "border-line bg-white text-ink hover:border-ink"
        }`}
        title={
          active
            ? "You'll be notified when new studies for this product appear"
            : "Get notified when new studies appear"
        }
      >
        <BellIcon filled={active} />
        {active ? "Watching" : "Watch"}
      </button>
      {error && <p className="text-xs text-red-700">{error}</p>}
    </div>
  );
}

function BellIcon({ filled }: { filled: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      className="h-4 w-4"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.6"
    >
      <path
        d="M5 8a5 5 0 0 1 10 0v3l1.5 2.5h-13L5 11Z"
        strokeLinejoin="round"
      />
      <path d="M8 16.5a2 2 0 0 0 4 0" strokeLinecap="round" />
    </svg>
  );
}
