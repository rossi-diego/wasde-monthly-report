import type { Metadata } from "next";
import Link from "next/link";

import { T } from "@/components/chrome/I18n";
import TopBar, { CommodityPills } from "@/components/chrome/TopBar";
import Upcoming from "@/components/home/Upcoming";
import { commodityPills, releaseInfo } from "@/lib/dashboard";
import { getIndex, getMeta } from "@/lib/data";
import { monthLabel, num, shortDate } from "@/lib/format";

export const metadata: Metadata = { title: "Reports · USDA Reports Dashboard" };

function Row({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap justify-between gap-x-4 border-t border-line py-2">
      <dt className="text-muted">{label}</dt>
      <dd className="m-0 text-right font-semibold">{children}</dd>
    </div>
  );
}

export default function ReportsPage() {
  const meta = getMeta();
  const index = getIndex();
  return (
    <>
      <TopBar title={<T k="reports.title" />} release={releaseInfo(meta)}>
        <CommodityPills pills={commodityPills()} />
      </TopBar>

      <article id="wasde" aria-labelledby="h-wasde" className="card flex flex-col gap-3 p-5" style={{ borderColor: "var(--r-wasde)" }}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="eyebrow">
              <T k="cadence.monthly" />
            </div>
            <h2 id="h-wasde" className="m-0 text-[17px] font-bold">
              World Agricultural Supply and Demand Estimates (WASDE)
            </h2>
          </div>
          <span className="rounded-full px-3 py-1 text-xs font-semibold text-white" style={{ background: "var(--pill-active)" }}>
            <T k="reports.live" />
          </span>
        </div>
        <dl className="m-0 grid max-w-xl">
          <Row label={<T k="reports.latest" />}>
            {meta.latest.label}
            {meta.latest.wasde_number !== null ? ` · #${meta.latest.wasde_number}` : ""}
            {meta.latest.release_date ? ` · ${shortDate(meta.latest.release_date)}` : ""}
          </Row>
          <Row label={<T k="reports.next" />}>{shortDate(meta.next_release) ?? "—"}</Row>
          <Row label={<T k="reports.history" />}>
            {num(meta.history.reports)} reports since {monthLabel(meta.history.first_report)} · {num(meta.history.rows)} rows
          </Row>
        </dl>
        <div className="flex flex-wrap gap-x-5">
          <Link href="/" className="inline-flex min-h-11 items-center font-semibold text-link">
            <T k="reports.open" />
          </Link>
          {index.map((c) => (
            <Link key={c.id} href={`/commodity/${c.id}/`} className="inline-flex min-h-11 items-center text-link">
              {c.label}
            </Link>
          ))}
        </div>
      </article>

      <Upcoming />
    </>
  );
}
