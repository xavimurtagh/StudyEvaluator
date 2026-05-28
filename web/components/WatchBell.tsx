"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { listWatches } from "@/lib/api";
import { getClientId } from "@/lib/client";

export function WatchBell() {
  const [newCount, setNewCount] = useState(0);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    const cid = getClientId();
    if (!cid) return;
    let cancelled = false;
    async function refresh() {
      const watches = await listWatches(cid);
      if (cancelled) return;
      setTotal(watches.length);
      setNewCount(watches.filter((w) => w.has_new).length);
    }
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (total === 0) return null;
  return (
    <Link
      href="/watches"
      className="relative inline-flex items-center text-muted hover:text-ink"
      title={
        newCount > 0
          ? `${newCount} watched product(s) have new evidence`
          : "Your watchlist"
      }
    >
      <svg
        viewBox="0 0 20 20"
        className="h-5 w-5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      >
        <path
          d="M5 8a5 5 0 0 1 10 0v3l1.5 2.5h-13L5 11Z"
          strokeLinejoin="round"
        />
        <path d="M8 16.5a2 2 0 0 0 4 0" strokeLinecap="round" />
      </svg>
      {newCount > 0 && (
        <span className="absolute -top-1 -right-2 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold leading-none text-white">
          {newCount}
        </span>
      )}
    </Link>
  );
}
