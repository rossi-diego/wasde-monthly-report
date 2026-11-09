"use client";

import Link from "next/link";

import { ChartTable, Chevron } from "@/components/charts/common";
import PaceChart from "@/components/charts/PaceChart";
import WeeklyBars from "@/components/charts/WeeklyBars";
import { T, useLang, useT } from "@/components/chrome/I18n";
import TopBar, { type ReleaseInfo } from "@/components/chrome/TopBar";
import { SmallChip } from "@/components/home/InsightCards";
import type { CrushCommodity, Insight, InsightsDoc } from "@/lib/data-contract";
import { bushels, bushelsAxis, bytes, lbPerBu, monthOf, monthYear, num, share, shortDate, shortTonsToMt, signed, tonnes } from "@/lib/format";
import { byId, caveatText, suppressedText } from "@/lib/insight-text";
import type { Key } from "@/lib/i18n";
import { NOPA_URL } from "@/lib/nopa";

export type TakeFile = { file: string; dataset: string; format: string; href: string; bytes: number; rows: number };

const AMBER = "var(--r-crush)";

/** Marketing-year month 1..12 → calendar month (1 = September). */
const calMonth = (m: number) => ((m + 7) % 12) + 1;

/** A share difference (0.0042) in percentage points: "+0.4", "−0.6", "0". */
const pp = (v: number | null | undefined, d = 1) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : Math.abs(v) < 1e-12 ? "0" : signed(v * 100, d);

function Chapter({ n, id, eyebrow, title, children }: { n: number; id: string; eyebrow: Key; title: Key; children: React.ReactNode }) {
  return (
    <article aria-labelledby={id} className="card flex min-w-0 flex-col gap-3 p-5" data-testid={`chapter-${n}`}>
      <div>
        <div className="eyebrow" style={{ color: AMBER }}>
          <T k="esr.ch" v={{ n: `0${n}` }} /> · <T k={eyebrow} />
        </div>
        <h2 id={id} className="m-0 mt-0.5 text-[17px] font-bold">
          <T k={title} />
        </h2>
      </div>
      {children}
    </article>
  );
}

function Stat({ label, value, sub, testid }: { label: React.ReactNode; value: React.ReactNode; sub?: React.ReactNode; testid?: string }) {
  return (
    <div className="card flex min-w-0 flex-col gap-0.5 p-4" style={{ borderTop: `4px solid ${AMBER}` }}>
      <div className="text-xs font-semibold text-muted">{label}</div>
      <div className="mono text-[22px] font-semibold" data-testid={testid}>
        {value}
      </div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  );
}

function Suppressed({ i }: { i: Insight }) {
  const { lang } = useLang();
  return (
    <p className="m-0 rounded-xl bg-bg px-3 py-2 text-[13px] text-muted" data-testid="suppressed">
      {suppressedText(i.suppressed_reason!, lang)}
    </p>
  );
}

function Meta({ i }: { i: Insight }) {
  const t = useT();
  const { lang } = useLang();
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
      {i.params.position ? (
        <span className="rounded-full bg-nav-active px-2 py-[1px] font-semibold text-ink">{t(`pos.${i.params.position as string}` as Key)}</span>
      ) : null}
      <span className="font-semibold text-ink" data-testid="n">
        {t("card.n", { n: i.n ?? "—" })}
      </span>
      {i.caveats.includes("small_sample") && <SmallChip />}
      {i.caveats
        .filter((x) => x !== "small_sample")
        .map((x) => (
          <span key={x}>· {caveatText(x, lang)}</span>
        ))}
    </div>
  );
}

export default function CrushView({
  d,
  insights,
  take,
  release,
}: {
  d: CrushCommodity;
  insights: InsightsDoc | null;
  take: TakeFile[];
  release: ReleaseInfo;
}) {
  const t = useT();
  const { lang } = useLang();
  const k = d.kpis;
  const f1 = byId(insights, "F1:soybeans");
  const f2 = byId(insights, "F2:soybeans");
  const f3 = byId(insights, "F3:soybeans");
  const ok = (i: Insight | undefined) => (i && i.suppressed_reason === null ? i : undefined);
  const f1ok = ok(f1);
  const f3ok = ok(f3);
  const monthLong = monthOf(Number(d.latest.month.slice(5, 7)), "long", lang);
  const dataMonth = monthYear(d.latest.month.slice(0, 7), lang);
  const targetMonth = monthYear(d.target.wasde_release_key, lang);
  const xTicks = [1, 3, 5, 7, 9, 11].map((m) => ({ x: m, label: monthOf(calMonth(m), "short", lang) }));
  const mo = t("unit.perMonth");

  // ---- chapter 1: pace vs USDA
  const cur = d.pace.series.find((s) => s.current);
  const hasPace = d.pace.series.some((s) => s.points.some((p) => p[1] !== null));
  // Cumulative crush is almost linear, so on a 0–100% axis the band, the mean and every year
  // overlap as one diagonal. The chart plots each year's share minus the 5-yr mean at that
  // month (percentage points): the band becomes min−mean … max−mean around a zero line.
  const meanAt = new Map(d.pace.band.map((b) => [b[0], b[1]] as [number, number | null]));
  const dev = (m: number, v: number | null) => {
    const mu = meanAt.get(m);
    return v === null || mu === null || mu === undefined ? null : v - mu;
  };
  const lines = d.pace.series.map((s) => ({ id: s.market_year, current: s.current, points: s.points.map((p) => [p[0], dev(p[0], p[1])] as [number, number | null]) }));
  const band = d.pace.band.map((b) => ({
    x: b[0],
    mean: b[1] === null ? null : 0,
    min: b[1] === null || b[2] === null ? null : b[2] - b[1],
    max: b[1] === null || b[3] === null ? null : b[3] - b[1],
  }));
  const priorYears = d.pace.series.filter((s) => !s.current).map((s) => s.market_year);
  const paceAria = t("crush.c1.aria", {
    my: d.market_year,
    month: monthLong,
    pct: share(k.pct_of_target),
    min: share(k.pct_5yr_min),
    max: share(k.pct_5yr_max),
  });
  const paceRows = d.pace.band.map((b) => {
    const p = cur?.points.find((x) => x[0] === b[0]);
    return [monthOf(calMonth(b[0]), "short", lang), share(p?.[1]), share(b[1]), share(b[2]), share(b[3]), pp(dev(b[0], p?.[1] ?? null)), b[4]];
  });

  // ---- chapter 2: still needed (F2)
  const req = f2?.suppressed_reason === null ? (f2.params.required_monthly_bu as number) : null;
  const last = f2?.suppressed_reason === null ? (f2.params.last_my_remaining_mean_bu as number) : null;
  const lastMonths = d.remaining.last_my_months;

  // ---- chapter 3: oil yield (F3)
  const yLines = d.pace.series.map((s) => ({ id: s.market_year, current: s.current, points: s.yield.map((p) => [p[0], p[1]] as [number, number | null]) }));
  const yBand = d.yield.band.map((b) => ({ x: b[0], mean: b[1], min: b[2], max: b[3] }));
  const implied = d.yield.wasde_implied_lb_bu;
  const yieldAria = t("crush.c3.aria", {
    month: monthLong,
    v: lbPerBu(k.oil_yield_lb_bu),
    min: lbPerBu(k.yield_5yr_min),
    max: lbPerBu(k.yield_5yr_max),
    w: lbPerBu(implied),
  });
  const yieldRows = d.yield.band.map((b) => {
    const p = d.pace.series.find((s) => s.current)?.yield.find((x) => x[0] === b[0]);
    return [monthOf(calMonth(b[0]), "short", lang), lbPerBu(p?.[1] ?? null), lbPerBu(b[1]), lbPerBu(b[2]), lbPerBu(b[3]), b[4]];
  });

  return (
    <>
      <TopBar
        title={t("crush.title")}
        release={release}
        sub={t("crush.sub", {
          month: dataMonth,
          date: shortDate(d.latest.release_key, true, lang) ?? "",
          next: shortDate(d.next_release, false, lang) ?? "—",
        })}
      />

      <section aria-label={t("crush.k.month", { month: monthLong })} className="flex flex-col gap-3">
        <p className="m-0 max-w-[720px] text-[17px] leading-snug" data-testid="crush-lead">
          {f1ok && f1ok.params.position
            ? t("crush.lead", {
                month: monthLong,
                pct: share(f1ok.params.pct as number),
                my: d.market_year,
                pos: t(`pos.${f1ok.params.position as string}` as Key),
                min: share(f1ok.params.hist_min as number),
                max: share(f1ok.params.hist_max as number),
                n: f1ok.n ?? 0,
              })
            : k.pct_of_target !== null
              ? t("crush.leadPlain", { month: monthLong, pct: share(k.pct_of_target), my: d.market_year })
              : t("crush.leadNoTarget", { month: monthLong, total: bushels(k.cum_bu, lang) })}
        </p>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          {d.target.wasde_release_key && <span>{t("crush.target", { month: targetMonth })}</span>}
          {d.latest.first_printed_as === "previous" && <span>· {t("crush.shutdown")}</span>}
          {f1 && f1.suppressed_reason !== null && <Suppressed i={f1} />}
          {f1ok && (
            <>
              <span className="font-semibold text-ink" data-testid="n">
                {t("card.n", { n: f1ok.n ?? "—" })}
              </span>
              {f1ok.caveats.includes("small_sample") && <SmallChip />}
            </>
          )}
        </div>
        <div className="grid-fit-220">
          <Stat
            label={t("crush.k.month", { month: monthLong })}
            value={bushels(k.month_crushed_bu, lang)}
            testid="crush-month"
            sub={t("crush.k.monthSub", { st: num((k.month_crushed_st ?? 0) / 1e6, 2), mt: tonnes(shortTonsToMt(k.month_crushed_st), lang) })}
          />
          <Stat
            label={t("crush.k.mytd", { my: d.market_year })}
            value={bushels(k.cum_bu, lang)}
            testid="crush-mytd"
            sub={
              d.target.crush_bu !== null ? (
                <span data-testid="crush-target">{t("crush.k.mytdSub", { target: bushels(d.target.crush_bu, lang), month: targetMonth, pct: share(k.pct_of_target) })}</span>
              ) : (
                t("supp.asof_missing")
              )
            }
          />
          <Stat
            label={<T k="crush.k.yield" />}
            value={lbPerBu(k.oil_yield_lb_bu)}
            testid="crush-yield"
            sub={t("crush.k.yieldSub", { oil: num((k.month_oil_klb ?? 0) / 1e6, 2) })}
          />
          <Stat label={<T k="crush.k.next" />} value={shortDate(d.next_release, true, lang) ?? "—"} sub={<T k="crush.k.nextSub" />} testid="crush-next" />
        </div>
      </section>

      <Chapter n={1} id="h-crush-pace" eyebrow="crush.c1.eb" title="crush.c1">
        {hasPace ? (
          <>
            <PaceChart
              lines={lines}
              band={band}
              xMax={12}
              xTicks={xTicks}
              color={AMBER}
              ariaLabel={paceAria}
              targetLabel=""
              reference={null}
              domain="data"
              yUnit={t("crush.c1.yUnit")}
              format={(v) => pp(v)}
            />
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true" className="inline-block h-1 w-5 rounded" style={{ background: AMBER }} />
                {t("esr.c1.cur", { my: d.market_year })}
              </span>
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true" className="inline-block h-2.5 w-5 rounded" style={{ background: AMBER, opacity: 0.18 }} />
                {t("esr.c1.band")}
              </span>
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true" className="inline-block w-5 border-t-2 border-dashed" style={{ borderColor: "var(--muted)" }} />
                {t("crush.c1.mean0")}
              </span>
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true" className="inline-block h-0.5 w-5" style={{ background: "var(--bar-past)" }} />
                {t("esr.c1.prior")} ({priorYears.join(", ")})
              </span>
              <span>{t("crush.axis.month")}</span>
            </div>
            <p className="m-0 text-xs text-muted" data-testid="pace-deviation">
              {t("crush.c1.dev")}
            </p>
            <p className="m-0 text-xs text-muted" data-testid="pace-legend">
              <strong className="text-ink">{t("caveat.history_point_in_time")}:</strong> {t("crush.c1.note")}
            </p>
            {f1ok && <Meta i={f1ok} />}
            <ChartTable caption={paceAria} head={[t("crush.h.month"), d.market_year, t("esr.h.mean"), t("esr.h.min"), t("esr.h.max"), t("crush.h.vsMean"), "n"]} rows={paceRows} />
          </>
        ) : (
          <p className="m-0 text-[13px] text-muted">{t("crush.c1.none")}</p>
        )}
      </Chapter>

      <div className="grid-fit-380">
        <Chapter n={2} id="h-crush-needed" eyebrow="crush.c2.eb" title="crush.c2">
          {f2 && f2.suppressed_reason !== null ? (
            <Suppressed i={f2} />
          ) : req !== null && f2 ? (
            req <= 0 ? (
              <p className="m-0">{t("crush.c2.met")}</p>
            ) : (
              <>
                <p className="m-0 text-[15px] leading-snug" data-testid="crush-needed">
                  {t("crush.c2.sentence", {
                    target: bushels(f2.params.target_bu as number, lang),
                    req: bushels(req, lang),
                    months: f2.params.months_remaining as number,
                    ratio: num(f2.params.ratio_required_to_last_my as number, 2),
                    avg: bushels(last, lang),
                    my: d.remaining.market_year,
                  })}
                </p>
                <h3 className="m-0 text-[14px] font-semibold">{t("crush.c2.bars", { my: d.remaining.market_year })}</h3>
                <WeeklyBars
                  items={lastMonths.map((m) => ({ label: monthOf(calMonth(m.month_of_my), "short", lang), value: m.crushed_bu }))}
                  reference={req}
                  referenceLabel={t("crush.c2.ref", { v: `${bushels(req, lang)}${mo}` })}
                  color={AMBER}
                  format={(v) => bushelsAxis(v, lang)}
                  ariaLabel={t("crush.c2.aria", {
                    my: d.remaining.market_year,
                    req: bushels(req, lang),
                    list: lastMonths.map((m) => `${monthOf(calMonth(m.month_of_my), "short", lang)}: ${bushels(m.crushed_bu, lang)}`).join(", "),
                  })}
                />
                <Meta i={f2} />
              </>
            )
          ) : (
            <p className="m-0 text-[13px] text-muted">{t("supp.asof_missing")}</p>
          )}
        </Chapter>

        <Chapter n={3} id="h-crush-yield" eyebrow="crush.c3.eb" title="crush.c3">
          {f3 && f3.suppressed_reason !== null && <Suppressed i={f3} />}
          {k.oil_yield_lb_bu !== null && (
            <p className="m-0 text-[15px] leading-snug" data-testid="crush-yield-line">
              {f3ok && f3ok.params.position
                ? t("crush.c3.sentence", {
                    month: monthLong,
                    v: lbPerBu(k.oil_yield_lb_bu),
                    pos: t(`pos.${f3ok.params.position as string}` as Key),
                    min: lbPerBu(f3ok.params.hist_min as number),
                    max: lbPerBu(f3ok.params.hist_max as number),
                    n: f3ok.n ?? 0,
                  })
                : t("crush.c3.plain", { month: monthLong, v: lbPerBu(k.oil_yield_lb_bu) })}
              {implied !== null ? ` ${t("crush.c3.wasde", { month: monthYear(d.target.oil_release_key, lang), w: lbPerBu(implied) })}` : ""}
            </p>
          )}
          <PaceChart
            lines={yLines}
            band={yBand}
            xMax={12}
            xTicks={xTicks}
            color={AMBER}
            ariaLabel={yieldAria}
            targetLabel=""
            reference={implied}
            domain="data"
            height={220}
            format={(v) => num(v, 1)}
          />
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" data-testid="yield-legend">
            <span className="flex items-center gap-1.5">
              <span aria-hidden="true" className="inline-block h-1 w-5 rounded" style={{ background: AMBER }} />
              {t("esr.c1.cur", { my: d.market_year })}
            </span>
            <span className="flex items-center gap-1.5">
              <span aria-hidden="true" className="inline-block h-2.5 w-5 rounded" style={{ background: AMBER, opacity: 0.18 }} />
              {t("esr.c1.band")}
            </span>
            <span className="flex items-center gap-1.5">
              <span aria-hidden="true" className="inline-block w-5 border-t-2 border-dashed" style={{ borderColor: "var(--muted)" }} />
              {t("esr.c1.mean")}
            </span>
            {implied !== null && (
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true" className="inline-block w-5 border-t-2 border-dotted" style={{ borderColor: "var(--muted)" }} />
                {t("crush.c3.ref", { w: lbPerBu(implied) })}
              </span>
            )}
          </div>
          <p className="m-0 text-xs text-muted">
            {t("crush.c3.note")} {t("crush.c3.axis")}
          </p>
          {f3ok && <Meta i={f3ok} />}
          <ChartTable caption={yieldAria} head={[t("crush.h.month"), d.market_year, t("esr.h.mean"), t("esr.h.min"), t("esr.h.max"), "n"]} rows={yieldRows} />
        </Chapter>
      </div>

      <details className="card group p-5" data-testid="crush-explore">
        <summary className="flex min-h-11 items-center justify-between gap-3 text-[15px] font-semibold">
          <T k="crush.explore" />
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line text-link group-hover:bg-nav-active">
            <Chevron size={16} />
          </span>
        </summary>
        <div className="flex flex-col gap-2 pt-3">
          <h3 id="h-crush-monthly" className="m-0 text-[14px] font-semibold">
            {t("crush.ex.monthly", { n: d.monthly.length })}
          </h3>
          <div tabIndex={0} role="region" aria-labelledby="h-crush-monthly" className="max-h-96 overflow-auto">
            <table className="data-table">
              <thead>
                <tr>
                  {[t("crush.h.month"), t("wasde.h.my"), t("crush.h.crushedSt"), t("crush.h.crushedBu"), t("crush.h.oil"), t("crush.h.meal"), t("crush.h.yield"), t("crush.h.revised")].map((h) => (
                    <th key={h} scope="col">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...d.monthly].reverse().map((m) => (
                  <tr key={m.month}>
                    <th scope="row" className="font-normal">
                      {monthYear(m.month.slice(0, 7), lang)}
                    </th>
                    <td>{m.market_year}</td>
                    <td className="tabular">{num(m.crushed_st)}</td>
                    <td className="tabular">{bushels(m.crushed_bu, lang)}</td>
                    <td className="tabular">{num(m.oil_klb)}</td>
                    <td className="tabular">{num(m.meal_st)}</td>
                    <td className="tabular">{lbPerBu(m.oil_yield_lb_bu)}</td>
                    <td>{m.is_revised ? t("crush.revisedYes") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="m-0 text-xs text-muted">{t("crush.ex.units")}</p>
        </div>
      </details>

      <section aria-labelledby="h-take" className="card flex flex-col gap-2 p-5" data-testid="crush-take">
        <h2 id="h-take" className="m-0 text-[17px] font-bold">
          <T k="crush.take" />
        </h2>
        <ul className="m-0 flex list-none flex-wrap gap-x-5 gap-y-1 p-0 text-[13px]">
          {take.map((f) => (
            <li key={f.file}>
              <a href={f.href} className="inline-flex min-h-11 items-center gap-1.5 font-semibold text-link" download={f.href.startsWith("/") ? "" : undefined}>
                {t(`ds.${f.dataset}` as Key)} · {f.format === "csv" ? (f.file.endsWith(".gz") ? "CSV.gz" : "CSV") : "Parquet"}
                <span className="font-normal text-muted">({bytes(f.bytes)})</span>
              </a>
            </li>
          ))}
        </ul>
        <p className="m-0 text-xs text-muted" data-testid="crush-window">
          {t("crush.window", { from: monthYear(d.history_start, lang) })}
        </p>
        <div className="flex flex-wrap gap-x-5 text-[13px]">
          <Link href="/data/#report-oilseed_crush" className="inline-flex min-h-11 items-center text-link">
            <T k="esr.take.all" />
          </Link>
          <Link href="/methodology/#crush" className="inline-flex min-h-11 items-center text-link">
            <T k="esr.take.method" />
          </Link>
        </div>
      </section>

      <aside aria-labelledby="h-nopa" className="card flex flex-col gap-1.5 p-5 text-[13px]" data-testid="nopa-note">
        <h2 id="h-nopa" className="m-0 text-[15px] font-bold">
          <T k="crush.nopa.title" />
        </h2>
        <p className="m-0">
          <T k="crush.nopa.note" />
        </p>
        <a href={NOPA_URL} rel="noopener noreferrer" className="inline-flex min-h-11 items-center self-start text-link">
          <T k="crush.nopa.link" />
        </a>
      </aside>
    </>
  );
}
