"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { T, useT } from "@/components/chrome/I18n";
import { num } from "@/lib/format";
import { REPORTS } from "@/lib/reports";

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

export default function Sidebar({ reports, rows, esrReleases = null }: { reports: number; rows: number; esrReleases?: number | null }) {
  const path = usePathname() ?? "/";
  const t = useT();
  const is = (p: string) => (p === "/" ? path === "/" : path.startsWith(p));
  return (
    <nav
      aria-label={t("nav.main")}
      className="box-border flex max-w-full flex-[1_1_220px] flex-col gap-5 border-b border-line bg-side px-4 py-6 min-[781px]:border-b-0 min-[781px]:border-r"
    >
      <Link href="/" className="flex items-center gap-2.5 px-2 hover:no-underline">
        <span aria-hidden="true" className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-[var(--r-wasde)]">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round">
            <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
          </svg>
        </span>
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
            // Commodity pages are WASDE views, so they keep the WASDE row active too.
            const on = r.id === "wasde" ? is(r.href) || is("/commodity") : is(r.href);
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

      {/* Hidden when the sidebar stacks on a phone: the data strip and footer repeat it. */}
      <div className="mt-auto rounded-xl border border-line bg-card px-3 py-3.5 text-xs text-muted max-[780px]:hidden">
        <div className="font-semibold text-ink">
          <T k="pipeline.title" />
        </div>
        <div>
          <T k="pipeline.counts" v={{ reports: num(reports), rows: num(rows) }} />
        </div>
        {esrReleases ? (
          <div>
            <T k="pipeline.esr" v={{ releases: num(esrReleases) }} />
          </div>
        ) : null}
        <div>
          <T k="pipeline.auto" />
        </div>
        <Link href="/methodology/" className="inline-flex min-h-11 items-center font-semibold text-link">
          <T k="pipeline.how" />
        </Link>
      </div>
    </nav>
  );
}
