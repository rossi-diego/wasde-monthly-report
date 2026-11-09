import type { Metadata, Viewport } from "next";
import Link from "next/link";

import ThemeToggle, { themeBootScript } from "@/components/ThemeToggle";
import { getIndex, getMeta } from "@/lib/data";
import { monthLabel } from "@/lib/format";

import "./globals.css";

export const metadata: Metadata = {
  title: "USDA Reports Dashboard",
  description:
    "Every USDA WASDE report since 2010, harmonized and updated automatically on release day — revisions, drivers and stocks-to-use for corn, soybeans, wheat and cotton.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const meta = getMeta();
  const commodities = getIndex();
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className="min-h-screen">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2"
        >
          Skip to content
        </a>
        <header className="sticky top-0 z-20 border-b border-line bg-page/90 backdrop-blur">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
            <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
              <span aria-hidden className="grid h-7 w-7 place-items-center rounded-md bg-brand text-sm text-page">
                W
              </span>
              USDA Reports Dashboard
            </Link>
            <nav
              className="-mx-4 order-last flex w-[calc(100%+2rem)] items-center gap-1 overflow-x-auto whitespace-nowrap px-4 text-sm lg:order-none lg:mx-0 lg:w-auto lg:overflow-visible lg:px-0"
              aria-label="Main"
            >
              <Link className="rounded-md px-2.5 py-1.5 text-ink-2 hover:bg-surface-2 hover:text-ink" href="/">
                This report
              </Link>
              {commodities.map((c) => (
                <Link
                  key={c.id}
                  className="rounded-md px-2.5 py-1.5 text-ink-2 hover:bg-surface-2 hover:text-ink"
                  href={`/commodity/${c.id}/`}
                >
                  {c.label}
                </Link>
              ))}
              <Link className="rounded-md px-2.5 py-1.5 text-ink-2 hover:bg-surface-2 hover:text-ink" href="/downloads/">
                Data &amp; downloads
              </Link>
              <Link
                className="rounded-md px-2.5 py-1.5 text-ink-2 hover:bg-surface-2 hover:text-ink"
                href="/methodology/"
              >
                Methodology
              </Link>
            </nav>
            <div className="ml-auto flex items-center gap-3 text-xs text-muted">
              <span className="hidden sm:inline">
                Latest <strong className="text-ink">{meta.latest.label}</strong>
                {meta.next_release && (
                  <>
                    {" · "}next{" "}
                    {new Date(meta.next_release + "T12:00:00").toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                    })}
                  </>
                )}
              </span>
              <ThemeToggle />
            </div>
          </div>
        </header>
        <main id="main" className="mx-auto max-w-7xl px-4 py-8">{children}</main>
        <footer className="border-t border-line">
          <div className="mx-auto flex max-w-7xl flex-wrap gap-x-6 gap-y-1 px-4 py-6 text-xs text-muted">
            <span>
              Source: USDA World Agricultural Supply and Demand Estimates. {meta.history.reports} reports,{" "}
              {monthLabel(meta.history.first_report)} – {meta.latest.label}.
            </span>
            <span>
              Data {meta.data_release_tag ?? "local build"} · generated{" "}
              {new Date(meta.generated_at).toISOString().slice(0, 16).replace("T", " ")} UTC · updated automatically
              on every release
            </span>
            <a className="underline hover:text-ink" href="https://github.com/rossi-diego/usda-reports-dashboard">
              Source code
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
