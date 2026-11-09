"use client";

import Link from "next/link";

import { T, useT } from "@/components/chrome/I18n";
import LangToggle from "@/components/chrome/LangToggle";
import ThemeToggle from "@/components/chrome/ThemeToggle";

export type ReleaseInfo = {
  number: number | null;
  released: string | null; // "Oct 9, 2026"
  next: string | null; // "Nov 10"
  label: string; // "October 2026"
};

export type Pill = { id: string; label: string };

const pillCls = (on: boolean) =>
  `flex min-h-9 min-w-11 shrink-0 items-center justify-center whitespace-nowrap rounded-full px-3.5 font-semibold ${
    on ? "bg-[var(--pill-active)] text-white" : "text-ink hover:bg-nav-active"
  }`;

/** Commodity switcher. With `onPick` the pills are toggle buttons (home); otherwise links to commodity pages. */
export function CommodityPills({
  pills,
  active,
  onPick,
}: {
  pills: Pill[];
  active?: string;
  onPick?: (id: string) => void;
}) {
  const t = useT();
  return (
    <div
      role="group"
      aria-label={t("top.commodity")}
      className="flex max-w-full gap-1 overflow-x-auto rounded-3xl border border-line bg-card p-1"
    >
      {pills.map((p) =>
        onPick ? (
          <button key={p.id} type="button" aria-pressed={active === p.id} onClick={() => onPick(p.id)} className={`${pillCls(active === p.id)} cursor-pointer`}>
            {p.label}
          </button>
        ) : (
          <Link
            key={p.id}
            href={`/commodity/${p.id}/`}
            aria-current={active === p.id ? "page" : undefined}
            className={`${pillCls(active === p.id)} hover:no-underline`}
          >
            {p.label}
          </Link>
        ),
      )}
    </div>
  );
}

export default function TopBar({
  title,
  release,
  children,
}: {
  title: React.ReactNode;
  release: ReleaseInfo;
  children?: React.ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-center gap-3">
      <div className="min-w-0 flex-[1_1_320px]">
        <h1 className="m-0 text-2xl font-bold tracking-[-0.01em]">{title}</h1>
        <p className="m-0 text-muted">
          {release.number !== null && release.released && (
            <T k="top.release" v={{ n: release.number, date: release.released }} />
          )}
          {release.next && (
            <>
              {release.number !== null && release.released ? " · " : ""}
              <T k="top.next" v={{ date: release.next }} />
            </>
          )}
        </p>
      </div>
      {children}
      <div className="flex items-center gap-3">
        <ThemeToggle />
        <LangToggle />
      </div>
    </header>
  );
}
