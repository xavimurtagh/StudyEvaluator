"use client";

import { useState } from "react";

export function ShareButton() {
  const [copied, setCopied] = useState(false);

  async function copy() {
    const url = typeof window === "undefined" ? "" : window.location.href.split("?")[0];
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard rejected (e.g. permissions). Fall back to selecting.
      prompt("Copy this link:", url);
    }
  }

  return (
    <button
      onClick={copy}
      className="rounded-md border border-line bg-white px-3 py-1.5 text-sm text-stone-700 hover:bg-stone-50 print:hidden"
      title="Copy a link to this verdict"
    >
      {copied ? "Copied!" : "Share verdict"}
    </button>
  );
}
