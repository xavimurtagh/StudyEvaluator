"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getMe, signOut, type Me } from "@/lib/api";

export function UserMenu() {
  const [me, setMe] = useState<Me | null | undefined>(undefined);

  useEffect(() => {
    getMe().then(setMe);
  }, []);

  if (me === undefined) {
    return <div className="h-7 w-24 animate-pulse rounded-md bg-stone-100" />;
  }

  if (me === null) {
    return (
      <Link
        href="/login"
        className="rounded-md border border-line bg-white px-3 py-1 text-sm hover:bg-stone-50"
      >
        Sign in
      </Link>
    );
  }

  async function handleSignOut() {
    await signOut();
    setMe(null);
    // Force any cached server data to clear by reloading.
    if (typeof window !== "undefined") window.location.href = "/";
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="hidden text-muted sm:inline" title={me.email}>
        {me.email}
      </span>
      <button
        onClick={handleSignOut}
        className="rounded-md border border-line bg-white px-3 py-1 hover:bg-stone-50"
      >
        Sign out
      </button>
    </div>
  );
}
