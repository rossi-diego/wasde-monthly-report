"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { CommodityName, T, useT } from "@/components/chrome/I18n";
import LangToggle from "@/components/chrome/LangToggle";
import ThemeToggle from "@/components/chrome/ThemeToggle";
import { num } from "@/lib/format";
import { LENSES, REPORTS } from "@/lib/reports";

function LogoMark() {
  return (
    <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] bg-[var(--r-wasde)]">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round">
        <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
      </svg>
    </span>
  );
}

const itemBase = "flex min-h-11 items-center gap-2.5 rounded-[10px] px-3 text-ink";

function NavLink({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) {
  const path = usePathname() ?? "/";
  // "page" for the exact page; "true" when the item is the section the page belongs to.
  const current = active ? (path === href || path === href.replace(/\/$/, "") ? "page" : "true") : undefined;
  return (
    <Link
      href={href}
      aria-current={current}
      className={`${itemBase} ${active ? "bg-nav-active font-semibold" : "hover:bg-nav-active"} hover:no-underline`}
    >
      {children}
    </Link>
  );
}

function GroupLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="col-span-full px-3 pb-1.5 pt-3.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">
      {children}
    </div>
  );
}

export default function Sidebar({
  reports,
  rows,
  esrReleases = null,
  crushReleases = null,
  cpReleases = null,
  gsReleases = null,
}: {
  reports: number;
  rows: number;
  esrReleases?: number | null;
  crushReleases?: number | null;
  cpReleases?: number | null;
  gsReleases?: number | null;
}) {
  const path = usePathname() ?? "/";
  const t = useT();
  const is = (p: string) => (p === "/" ? path === "/" : path.startsWith(p));
  // Below 1024px the nav is a drawer under the app bar, closed by default.
  // It remembers the page it was opened on, so following a link closes it.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = openOn === path;
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpenOn(null);
        document.getElementById("menu-button")?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);
  return (
    <>
    {/* Below 1024px: a 56px sticky app bar (logo, theme, language, Menu) instead of the sidebar. */}
    <header className="sticky top-0 z-30 box-border flex h-14 shrink-0 items-center justify-between gap-2 border-b border-line bg-side px-4 min-[1024px]:hidden" data-testid="app-bar">
      <Link href="/" className="flex min-w-0 items-center gap-2.5 hover:no-underline" aria-label={t("brand.title")}>
        <LogoMark />
        <span className="min-w-0 max-[559px]:hidden" aria-hidden="true">
          <span className="block truncate text-[15px] font-bold">
            <T k="brand.title" />
          </span>
          <span className="block truncate text-xs text-muted">
            <T k="brand.sub" />
          </span>
        </span>
      </Link>
      <div className="flex shrink-0 items-center gap-2">
        <ThemeToggle />
        <LangToggle />
        <button
          id="menu-button"
          type="button"
          aria-expanded={open}
          aria-controls="site-nav"
          onClick={() => setOpenOn(open ? null : path)}
          className="flex h-10 cursor-pointer items-center gap-1.5 whitespace-nowrap rounded-full border border-line bg-card px-3.5 text-[13px] font-semibold text-ink"
        >
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            {open ? <path d="M6 6l12 12M18 6L6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
          </svg>
          <T k="nav.menu" />
        </button>
      </div>
    </header>
    <nav
      id="site-nav"
      aria-label={t("nav.main")}
      className={`box-border flex-col gap-5 bg-side px-4 py-6 max-[1023px]:fixed max-[1023px]:inset-x-0 max-[1023px]:bottom-0 max-[1023px]:top-14 max-[1023px]:z-20 max-[1023px]:overflow-y-auto max-[1023px]:border-b max-[1023px]:border-line min-[1024px]:flex min-[1024px]:w-[220px] min-[1024px]:shrink-0 min-[1024px]:border-r min-[1024px]:border-line ${open ? "flex" : "hidden"}`}
    >
      <Link href="/" className="flex items-center gap-2.5 px-2 hover:no-underline max-[1023px]:hidden">
        <LogoMark />
        <span>
          <span className="block text-[15px] font-bold">
            <T k="brand.title" />
          </span>
          <span className="block text-xs text-muted">
            <T k="brand.sub" />
          </span>
        </span>
      </Link>

      {/* One column in the sidebar; two columns when the sidebar stacks on top at phone width. */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-0.5">
        <NavLink href="/" active={is("/")}>
          <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="7" height="9" rx="1.5" />
            <rect x="14" y="3" width="7" height="5" rx="1.5" />
            <rect x="14" y="12" width="7" height="9" rx="1.5" />
            <rect x="3" y="16" width="7" height="5" rx="1.5" />
          </svg>
          <T k="nav.overview" />
        </NavLink>

        <GroupLabel>
          <T k="nav.reports" />
        </GroupLabel>
        {REPORTS.map((r) => {
          const inner = (
            <>
              <span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 rounded-[3px]" style={{ background: r.color }} />
              <span className="grow">{t(r.name)}</span>
              <span className="text-[11px] text-muted">{r.live ? t(r.cadence) : t("nav.soon")}</span>
            </>
          );
          if (r.live && r.href) {
            // /commodity/<id>/ pages are WASDE views, so they keep the WASDE row active too
            // (the trailing slash keeps the /commodities/ lenses out of it).
            const on = r.id === "wasde" ? is(r.href) || is("/commodity/") : is(r.href);
            return (
              <NavLink key={r.id} href={r.href} active={on}>
                {inner}
              </NavLink>
            );
          }
          // Not a link: the report page does not exist yet (no dead links). Hidden on phones,
          // where the "Other USDA reports" cards already announce them, to keep the nav short.
          return (
            <span key={r.id} className={`${itemBase} max-[780px]:hidden`} aria-disabled="true">
              {inner}
            </span>
          );
        })}

        <NavLink href="/reports/" active={path === "/reports/" || path === "/reports"}>
          <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="5" width="18" height="16" rx="2" />
            <path d="M3 10h18M8 3v4M16 3v4" />
          </svg>
          <T k="nav.allReports" />
        </NavLink>

        <GroupLabel>
          <T k="nav.commodities" />
        </GroupLabel>
        {LENSES.map((l) => (
          <NavLink key={l.id} href={`/commodities/${l.id}/`} active={is(`/commodities/${l.id}`)}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M12 21V9M12 9c0-3 2-5 5-6 0 3-2 5-5 6zM12 13c0-3-2-5-5-6 0 3 2 5 5 6zM12 17c0-2.5 1.8-4.2 4.5-5" />
            </svg>
            <CommodityName id={l.id} fallback={l.label} />
          </NavLink>
        ))}

        <GroupLabel>
          <T k="nav.data" />
        </GroupLabel>
        <NavLink href="/data/" active={is("/data") || is("/downloads")}>
          <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <ellipse cx="12" cy="5" rx="8" ry="3" />
            <path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
          </svg>
          <T k="nav.catalogue" />
        </NavLink>
        <NavLink href="/methodology/" active={is("/methodology")}>
          <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 8v5M12 16.5v.5" />
          </svg>
          <T k="nav.methodology" />
        </NavLink>
      </div>

      {/* At the bottom of the sidebar; below 1024px, at the end of the Menu drawer. */}
      <div className="mt-auto rounded-xl border border-line bg-card px-3 py-3.5 text-xs text-muted">
        <div className="font-semibold text-ink">
          <T k="pipeline.title" />
        </div>
        <div>
          <T k="pipeline.counts" v={{ reports: num(reports), rows: num(rows) }} />
        </div>
        {(() => {
          // One compact line: "+ 850 Export Sales · 133 Crush (NASS) · … releases"
          const parts = (
            [
              [esrReleases, "report.export_sales"],
              [crushReleases, "report.crush"],
              [cpReleases, "report.crop_progress"],
              [gsReleases, "report.grain_stocks"],
            ] as const
          ).filter(([n]) => Boolean(n));
          if (!parts.length) return null;
          return (
            <div data-testid="pipeline-releases">
              {t("pipeline.releases", { list: parts.map(([n, k]) => `${num(n)} ${t(k)}`).join(" · ") })}
            </div>
          );
        })()}
        <div>
          <T k="pipeline.auto" />
        </div>
        <Link href="/methodology/" className="inline-flex min-h-11 items-center font-semibold text-link">
          <T k="pipeline.how" />
        </Link>
      </div>
    </nav>
    </>
  );
}
