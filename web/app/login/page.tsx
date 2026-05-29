"use client";

import Link from "next/link";
import { useState } from "react";

import { requestMagicLink } from "@/lib/api";
import { getClientId } from "@/lib/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await requestMagicLink(email.trim(), getClientId());
      setSent(true);
    } catch (err: any) {
      setError(err.message ?? "Could not send the link.");
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <div className="mx-auto max-w-md space-y-4 rounded-xl border border-line bg-white p-6">
        <h1 className="text-xl font-semibold">Check your email</h1>
        <p className="text-muted">
          We sent a one-time sign-in link to <strong>{email}</strong>. It's
          valid for 15 minutes. Click the link to finish signing in — any
          watches you've started in this browser will follow you.
        </p>
        <p className="text-sm text-muted">
          No email? Check spam, then{" "}
          <button
            type="button"
            className="underline"
            onClick={() => setSent(false)}
          >
            try again
          </button>
          .
        </p>
        <Link href="/" className="text-sm text-muted underline">
          ← back home
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md space-y-4 rounded-xl border border-line bg-white p-6">
      <div>
        <h1 className="text-xl font-semibold">Sign in</h1>
        <p className="mt-1 text-sm text-muted">
          Get a magic link by email. No password to remember. Watches stay
          with your account so you can pick up on any device.
        </p>
      </div>
      <form onSubmit={onSubmit} className="space-y-3">
        <label className="block text-sm">
          Email
          <input
            autoFocus
            required
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="mt-1 w-full rounded-md border border-line bg-white px-3 py-2 text-sm focus:border-ink focus:outline-none"
          />
        </label>
        {error && <p className="text-sm text-red-700">{error}</p>}
        <button
          type="submit"
          disabled={busy || !email}
          className="w-full rounded-md bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Sending..." : "Email me a sign-in link"}
        </button>
      </form>
      <p className="text-xs text-muted">
        By signing in you agree to anonymous usage analytics for improving
        the evidence pipeline.
      </p>
    </div>
  );
}
