import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

import { WatchBell } from "@/components/WatchBell";

export const metadata: Metadata = {
  title: "StudyEvaluator — what the studies actually say",
  description:
    "Evidence-graded verdicts on health and wellness products. We pull the studies, score their quality, and tell you what the literature actually supports.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen font-sans antialiased">
        <header className="border-b border-line bg-white">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
            <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
              <span className="inline-block h-6 w-6 rounded-md bg-ink" aria-hidden />
              <span>StudyEvaluator</span>
            </Link>
            <nav className="flex items-center gap-6 text-sm text-muted">
              <Link href="/about" className="hover:text-ink">
                How it works
              </Link>
              <a
                href="https://www.who.int/news-room/spotlight/health-misinformation"
                target="_blank"
                rel="noreferrer"
                className="hover:text-ink"
              >
                Why this exists
              </a>
              <WatchBell />
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
        <footer className="mx-auto max-w-5xl px-6 py-10 text-sm text-muted">
          <p>
            Not medical advice. Verdicts reflect the literature we found, not a
            personal recommendation. Always talk to a clinician for individual
            decisions.
          </p>
        </footer>
      </body>
    </html>
  );
}
