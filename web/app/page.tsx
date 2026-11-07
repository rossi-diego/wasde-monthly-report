import Link from "next/link";

import Delta from "@/components/Delta";
import { getMeta, getOverview } from "@/lib/data";
import { decimals, flagLabel, monthLabel, num, qty, unitShort } from "@/lib/format";
import type { CardBlock } from "@/lib/types";

function CropRow({ label, block, crop }: { label: string; block: CardBlock; crop: "new" | "old" }) {
  const b = block?.[crop];
  if (!block || !b) return null;
  const d = decimals(block.unit, b.ending_stocks ?? 0);
  const suDelta =
    b.stocks_to_use_pct !== null && b.prev_stocks_to_use_pct !== null
      ? b.stocks_to_use_pct - b.prev_stocks_to_use_pct
      : null;
  return (
    <tr className="border-t border-line first:border-t-0">
      <th scope="row" className="py-2 pr-2 text-left font-normal text-ink-2">
        <div className="text-ink">{label}</div>
        <div className="text-xs text-muted">
          {b.market_year} {flagLabel(b.flag)}
        </div>
      </th>
      <td className="tabular py-2 text-right">
        <div className="font-medium">{num(b.ending_stocks, d)}</div>
        <Delta value={b.delta} digits={d} className="text-xs" />
      </td>
      <td className="tabular py-2 pl-3 text-right">
        <div>{num(b.stocks_to_use_pct, 1)}%</div>
        <Delta value={suDelta} digits={1} suffix=" pt" className="text-xs" />
      </td>
    </tr>
  );
}

export default function Home() {
  const ov = getOverview();
  const meta = getMeta();
  const sa = ov.south_america;
  return (
    <div className="space-y-10">
      <section className="space-y-3">
        <p className="text-sm font-medium text-brand">
          WASDE {meta.latest.wasde_number ? `#${meta.latest.wasde_number}` : ""} · released{" "}
          {meta.latest.release_date
            ? new Date(meta.latest.release_date.slice(0, 10) + "T12:00:00").toLocaleDateString("en-US", {
                month: "long",
                day: "numeric",
                year: "numeric",
              })
            : monthLabel(ov.report_month)}
        </p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{ov.report_label}: what changed</h1>
        {ov.context && <p className="max-w-3xl text-ink-2">{ov.context}</p>}
        <p className="text-sm text-muted">
          Compared with {meta.previous_report_month ? monthLabel(meta.previous_report_month) : "the previous report"}.
          Ranked by size and by how unusual the revision is for this time of year.
        </p>
      </section>

      <section aria-labelledby="h-headlines" className="card p-5 sm:p-6">
        <h2 id="h-headlines" className="mb-4 text-lg font-semibold">
          Headlines
        </h2>
        {ov.first_projections.length > 0 && (
          <ul className="mb-4 space-y-2 rounded-lg bg-surface-2 p-4 text-sm">
            {ov.first_projections.map((f) => (
              <li key={f.commodity}>{f.sentence}</li>
            ))}
          </ul>
        )}
        <ol className="space-y-4">
          {ov.highlights.map((h, i) => (
            <li key={`${h.commodity}-${h.region_id}-${h.market_year}`} className="flex gap-4">
              <span className="tabular mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-accent-soft text-sm font-semibold text-ink">
                {i + 1}
              </span>
              <div className="min-w-0 space-y-1.5">
                <p className="leading-relaxed">{h.sentence}</p>
                <div className="flex flex-wrap gap-1.5 text-xs">
                  <Link
                    href={`/commodity/${h.commodity}/`}
                    className="rounded-full border border-line px-2 py-0.5 text-ink-2 hover:bg-surface-2"
                  >
                    {h.commodity_label}
                  </Link>
                  <span className="rounded-full border border-line px-2 py-0.5 text-ink-2">{h.region}</span>
                  <span className="rounded-full border border-line px-2 py-0.5 text-ink-2">
                    {h.market_year} · {h.crop === "new" ? "new crop" : "old crop"}
                  </span>
                  {h.related.slice(0, 2).map((r) => (
                    <span key={r.attribute} className="rounded-full bg-surface-2 px-2 py-0.5 text-muted">
                      {r.label} {r.delta > 0 ? "+" : "−"}
                      {num(Math.abs(r.delta), decimals(r.unit, r.delta))} {unitShort(r.unit)}
                    </span>
                  ))}
                </div>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="h-cards" className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <h2 id="h-cards" className="text-lg font-semibold">
            Ending stocks and stocks-to-use
          </h2>
          <p className="text-xs text-muted">Change vs previous report · U.S. in native units, world in MMT / bales</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {ov.cards.map((c) => (
            <Link
              key={c.commodity}
              href={`/commodity/${c.commodity}/`}
              className="card group block p-5 transition hover:border-accent"
            >
              <div className="mb-2 flex items-baseline justify-between">
                <h3 className="text-base font-semibold group-hover:text-accent">{c.label}</h3>
                <span className="text-xs text-muted">Open →</span>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-muted">
                    <th className="pb-1 text-left font-normal" scope="col">
                      &nbsp;
                    </th>
                    <th className="pb-1 text-right font-normal" scope="col">
                      Ending stocks
                    </th>
                    <th className="pb-1 pl-3 text-right font-normal" scope="col">
                      Stocks/use
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <CropRow label={`U.S. (${unitShort(c.us?.unit)})`} block={c.us} crop="new" />
                  <CropRow label="U.S. old crop" block={c.us} crop="old" />
                  <CropRow label={`World ex-China (${unitShort(c.world_ex_china?.unit)})`} block={c.world_ex_china} crop="new" />
                </tbody>
              </table>
            </Link>
          ))}
        </div>
      </section>

      {sa.length > 0 && (
        <section aria-labelledby="h-sa" className="card p-5 sm:p-6">
          <h2 id="h-sa" className="mb-1 text-lg font-semibold">
            South American crops
          </h2>
          <p className="mb-4 text-sm text-muted">Production, million metric tons — the U.S. export competition.</p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-sm">
              <thead className="text-xs text-muted">
                <tr>
                  <th className="pb-2 text-left font-normal">Crop</th>
                  <th className="pb-2 text-left font-normal">Country</th>
                  <th className="pb-2 text-left font-normal">Marketing year</th>
                  <th className="pb-2 text-right font-normal">Production</th>
                  <th className="pb-2 text-right font-normal">vs last month</th>
                </tr>
              </thead>
              <tbody>
                {sa.map((r) => (
                  <tr key={`${r.commodity_id}-${r.region_id}-${r.market_year}`} className="border-t border-line">
                    <td className="py-2 capitalize">{r.commodity_id}</td>
                    <td className="py-2">{r.region}</td>
                    <td className="py-2">{r.market_year}</td>
                    <td className="tabular py-2 text-right">{qty(r.value, r.unit_id)}</td>
                    <td className="py-2 text-right">
                      <Delta value={r.delta} digits={1} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section aria-labelledby="h-dl" className="card flex flex-wrap items-center justify-between gap-4 p-5 sm:p-6">
        <div>
          <h2 id="h-dl" className="text-lg font-semibold">
            Take the numbers with you
          </h2>
          <p className="text-sm text-muted">
            Excel workbook of this report (changes + balance sheets), per-commodity history since 2010, and the full
            dataset ({num(meta.history.rows)} rows).
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {meta.downloads[0] && (
            <a
              href={`/data/${meta.downloads[0].url}`}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
              download
            >
              Download {meta.latest.label} (.xlsx)
            </a>
          )}
          <Link href="/downloads/" className="rounded-lg border border-line px-4 py-2 text-sm hover:bg-surface-2">
            All downloads &amp; explorer
          </Link>
        </div>
      </section>
    </div>
  );
}
