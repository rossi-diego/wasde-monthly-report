"use client";

import Link from "next/link";

import { T, useLang, useT } from "@/components/chrome/I18n";
import LangToggle from "@/components/chrome/LangToggle";
import ThemeToggle from "@/components/chrome/ThemeToggle";
import { shortDate } from "@/lib/format";
import { commodityName } from "@/lib/labels";

/** Raw values from meta.json; formatted here in the active language. */
export type ReleaseInfo = {
  number: number | null;
  releaseDate: string | null; // "2026-10-09T00:00:00"
  nextRelease: string | null; // "2026-11-10"
  reportMonth: string; // "2026-10"
};

export type Pill = { id: string; label: string };

const pillCls = (on: boolean) =>
  `flex min-h-9 min-w-11 shrink-0 items-center justify-center whitespace-nowrap rounded-full px-3.5 font-semibold ${
    on ? "bg-[var(--pill-active)] text-white" : "text-ink hover:bg-nav-active"
  }`;

/** Commodity switcher. With `onPick` the pills are toggle buttons (home); otherwise links to commodity pages.
 *  Below 480px the pills wrap onto a second line, so every commodity stays visible on a phone. */
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
  const { lang } = useLang();
  return (
    <div
      role="group"
      aria-label={t("top.commodity")}
      className="flex max-w-full flex-wrap gap-1 rounded-3xl border border-line bg-card p-1 min-[480px]:flex-nowrap min-[480px]:overflow-x-auto"
    >
      {pills.map((p) => {
        const label = commodityName(p.id, lang, p.label);
        return onPick ? (
          <button
            key={p.id}
            type="button"
            aria-pressed={active === p.id}
            onClick={() => onPick(p.id)}
            className={`${pillCls(active === p.id)} cursor-pointer`}
          >
            {label}
          </button>
        ) : (
          <Link
            key={p.id}
            href={`/commodity/${p.id}/`}
            aria-current={active === p.id ? "page" : undefined}
            className={`${pillCls(active === p.id)} hover:no-underline`}
          >
            {label}
          </Link>
        );
      })}
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
  const { lang } = useLang();
  const released = shortDate(release.releaseDate, true, lang);
  const next = shortDate(release.nextRelease, false, lang);
  return (
    <header className="flex flex-wrap items-center gap-3">
      <div className="min-w-0 flex-[1_1_320px]">
        <h1 className="m-0 text-2xl font-bold tracking-[-0.01em]">{title}</h1>
        <p className="m-0 text-muted">
          {release.number !== null && released && <T k="top.release" v={{ n: release.number, date: released }} />}
          {next && (
            <>
              {release.number !== null && released ? " · " : ""}
              <T k="top.next" v={{ date: next }} />
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
