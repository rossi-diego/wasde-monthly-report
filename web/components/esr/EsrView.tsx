"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import Bar from "@/components/charts/Bar";
import { ChartTable, Chevron } from "@/components/charts/common";
import PaceChart from "@/components/charts/PaceChart";
import WeeklyBars from "@/components/charts/WeeklyBars";
import { T, useLang, useT } from "@/components/chrome/I18n";
import TopBar, { CommodityPills, type ReleaseInfo } from "@/components/chrome/TopBar";
import { SmallChip } from "@/components/home/InsightCards";
import type { EsrCommodity, EsrIndex, Insight, InsightsDoc } from "@/lib/data-contract";
import { bytes, monthYear, num, share, shortDate, tonnes, tonnesAxis, unitShort } from "@/lib/format";
import { byId, cap, caveatText, finding, noun, suppressedText } from "@/lib/insight-text";
import type { Key } from "@/lib/i18n";
import { commodityName, regionName } from "@/lib/labels";

export type TakeFile = { file: string; dataset: string; format: string; href: string; bytes: number; rows: number };

const TEAL = "var(--r-esr)";

function Chapter({ n, id, eyebrow, title, children }: { n: number; id: string; eyebrow: Key; title: Key; children: React.ReactNode }) {
  return (
    <article aria-labelledby={id} className="card flex min-w-0 flex-col gap-3 p-5" data-testid={`chapter-${n}`}>
      <div>
        <div className="eyebrow" style={{ color: TEAL }}>
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
    <div className="card flex min-w-0 flex-col gap-0.5 p-4" style={{ borderTop: `4px solid ${TEAL}` }}>
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

/** Horizontal bars as an HTML list (labels never collide on a phone). */
function HBars({ rows, color, ariaLabel }: { rows: { key: string; label: string; value: number; text: string; strong?: boolean }[]; color: string; ariaLabel: string }) {
  const max = Math.max(...rows.map((r) => Math.abs(r.value)), 1);
  return (
    <ul aria-label={ariaLabel} className="m-0 flex list-none flex-col gap-1.5 p-0">
      {rows.map((r) => (
        <li key={r.key} className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)_10rem] items-center gap-2 text-[13px]">
          <span className={`truncate ${r.strong ? "font-semibold" : ""}`}>{r.label}</span>
          <span aria-hidden="true" className="h-3 overflow-hidden rounded-[3px] bg-grid">
            <span className="block h-3 rounded-[3px]" style={{ width: `${(Math.max(r.value, 0) / max) * 100}%`, background: r.strong ? color : "var(--bar-est)" }} />
          </span>
          <span className="mono text-right">{r.text}</span>
        </li>
      ))}
    </ul>
  );
}

export default function EsrView({
  index,
  commodities,
  insights,
  take,
  release,
}: {
  index: EsrIndex;
  commodities: EsrCommodity[];
  insights: InsightsDoc | null;
  take: TakeFile[];
  release: ReleaseInfo;
}) {
  const t = useT();
  const { lang } = useLang();
  const [sel, setSel] = useState(commodities[0]?.commodity_id ?? "");

  // Deep links from the home cards: /reports/export-sales/?c=corn
  useEffect(() => {
    const c = new URLSearchParams(window.location.search).get("c");
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time sync from the URL after hydration
    if (c && commodities.some((x) => x.commodity_id === c)) setSel(c);
  }, [commodities]);

  const pick = (id: string) => {
    setSel(id);
    try {
      const u = new URL(window.location.href);
      u.searchParams.set("c", id);
      window.history.replaceState(null, "", u);
    } catch {
      /* ignore */
    }
  };

  const d = commodities.find((c) => c.commodity_id === sel) ?? commodities[0];
  if (!d) return null;
  const c = d.commodity_id;
  const what = commodityName(c, lang, d.label);
  const whatLower = noun(c, lang);
  const leadWhat = lang === "pt" ? whatLower : cap(whatLower);
  const k = d.kpis;
  const e1 = byId(insights, `E1:${c}`);
  const e2 = byId(insights, `E2:${c}`);
  const e3 = finding(insights, `E3:${c}`);
  const e1ok = e1 && e1.suppressed_reason === null ? e1 : undefined;
  const wk = t("unit.perWeek");
  const pills = commodities.map((x) => ({ id: x.commodity_id, label: x.label }));
  const targetMonth = monthYear(d.target.wasde_release_key, lang);

  // ---- chapter 1: pace
  const cur = d.pace.series.find((s) => s.current);
  const hasPace = d.pace.series.some((s) => s.points.some((p) => p[1] !== null));
  const lines = d.pace.series.map((s) => ({ id: s.market_year, current: s.current, points: s.points.map((p) => [p[0], p[1]] as [number, number | null]) }));
  const band = d.pace.band.map((b) => ({ x: b[0], mean: b[1], min: b[2], max: b[3] }));
  const lastBand = d.pace.band.find((b) => b[0] === d.latest.week_of_my);
  const paceAria = t("esr.c1.aria", {
    what: whatLower,
    my: d.market_year,
    w: d.latest.week_of_my,
    pct: share(k.pct_of_target),
    min: share(lastBand?.[2]),
    max: share(lastBand?.[3]),
  });
  const priorYears = d.pace.series.filter((s) => !s.current).map((s) => s.market_year);
  const paceRows = d.pace.band.map((b) => {
    const p = cur?.points.find((x) => x[0] === b[0]);
    return [b[0], share(p?.[1]), share(b[1]), share(b[2]), share(b[3]), b[4]];
  });

  // ---- chapter 2: destinations
  const country = (id: string, label: string) => (id === "unknown" ? t("esr.unknown") : regionName(id, lang, label));
  const dest = d.destinations;
  const china = dest.rows.find((r) => r.country_id === "china");
  const unknown = dest.rows.find((r) => r.country_id === "unknown");
  const hist = dest.china_unknown_history.filter((h) => h.china_share !== null);
  // China absent from the destination rows while there are commitments = a 0% share.
  const chinaShare = china?.share ?? ((dest.total_commitment_mt ?? 0) > 0 ? 0 : null);
  const shareBars = [
    ...hist.map((h) => ({ label: h.market_year, value: (h.china_share ?? 0) * 100, kind: "past" as const })),
    ...(chinaShare !== null ? [{ label: d.market_year, value: chinaShare * 100, kind: "current" as const }] : []),
  ];
  const noChina = shareBars.length > 0 && shareBars.every((b) => b.value === 0);
  const nOther = Math.max(dest.n_destinations - dest.rows.length, 0);
  const unk = dest.china_unknown_history.map((h) => h.unknown_share).filter((v): v is number => v !== null);
  const destRows = [
    ...dest.rows.map((r) => ({
      key: r.country_id,
      label: country(r.country_id, r.country_label),
      value: r.total_commitment_mt ?? 0,
      text: `${tonnes(r.total_commitment_mt, lang)} · ${share(r.share, 0)}`,
      strong: r.country_id === "china" || r.country_id === "unknown",
    })),
    ...(dest.other_mt > 0
      ? [
          {
            key: "other",
            label: t(nOther === 1 ? "esr.c2.other1" : "esr.c2.other", { n: nOther }),
            value: dest.other_mt,
            text: `${tonnes(dest.other_mt, lang)} · ${share(dest.other_mt / (dest.total_commitment_mt || 1), 0)}`,
          },
        ]
      : []),
  ];
  const weekDate = shortDate(dest.week_ending, true, lang) ?? "";

  // ---- chapter 3: still needed
  const req = e2?.suppressed_reason === null ? (e2.params.required_weekly_mt as number) : null;
  const avg = e2?.suppressed_reason === null ? (e2.params.net_sales_4wk_avg_mt as number) : null;

  return (
    <>
      <TopBar
        title={t("esr.title", { what: lang === "pt" ? `${what} (EUA)` : `U.S. ${what}` })}
        release={release}
        sub={t("esr.sub", {
          week: shortDate(d.latest.week_ending, true, lang) ?? "",
          date: shortDate(d.latest.release_key, true, lang) ?? "",
          next: shortDate(d.next_release, false, lang) ?? "—",
        })}
      >
        <CommodityPills pills={pills} active={c} onPick={pick} />
      </TopBar>

      <section aria-label={t("esr.k.commit")} className="flex flex-col gap-3">
        <p className="m-0 max-w-[720px] text-[17px] leading-snug" data-testid="esr-lead">
          {e1ok && e1ok.params.pct !== null
            ? e1ok.params.position
              ? t("esr.lead", {
                  what: leadWhat,
                  pct: share(e1ok.params.pct as number),
                  my: d.market_year,
                  pos: t(`pos.${e1ok.params.position as string}` as Key),
                  min: share(e1ok.params.hist_min as number),
                  max: share(e1ok.params.hist_max as number),
                  n: e1ok.n ?? 0,
                })
              : t("esr.leadPlain", { what: leadWhat, pct: share(e1ok.params.pct as number), my: d.market_year })
            : k.pct_of_target !== null
              ? t("esr.leadPlain", { what: leadWhat, pct: share(k.pct_of_target), my: d.market_year })
              : t("esr.leadNoTarget", { what: leadWhat, total: tonnes(k.total_commitment_mt, lang) })}
        </p>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          {d.target.wasde_release_key && <span>{t("esr.target", { month: targetMonth })}</span>}
          {e1 && e1.suppressed_reason !== null && <Suppressed i={e1} />}
          {e1ok && (
            <>
              <span className="font-semibold text-ink" data-testid="n">
                {t("card.n", { n: e1ok.n ?? "—" })}
              </span>
              {e1ok.caveats.includes("small_sample") && <SmallChip />}
            </>
          )}
        </div>
        <div className="grid-fit-220">
          <Stat
            label={<T k="esr.k.commit" />}
            value={tonnes(k.total_commitment_mt, lang)}
            testid="esr-commitments"
            sub={t("esr.k.commitSub", { acc: tonnes(k.accumulated_exports_mt, lang), out: tonnes(k.outstanding_sales_mt, lang) })}
          />
          <Stat
            label={<T k="esr.k.target" />}
            value={tonnes(d.target.exports_mt, lang)}
            testid="esr-target"
            sub={
              d.target.exports_native !== null
                ? t("esr.k.targetSub", { native: `${num(d.target.exports_native, 0)} ${unitShort(d.target.unit_id, lang)}`, month: targetMonth })
                : undefined
            }
          />
          <Stat
            label={<T k="esr.k.net" />}
            value={tonnes(k.net_sales_mt, lang)}
            sub={t("esr.k.netSub", { x: tonnes(k.weekly_exports_mt, lang) })}
          />
          <Stat label={<T k="esr.k.next" />} value={shortDate(d.next_release, true, lang) ?? "—"} sub={<T k="esr.k.nextSub" />} testid="esr-next" />
        </div>
      </section>

      <Chapter n={1} id="h-esr-pace" eyebrow="esr.c1.eb" title="esr.c1">
        {hasPace ? (
          <>
            <PaceChart
              lines={lines}
              band={band}
              xMax={Math.max(52, ...d.pace.series.flatMap((s) => s.points.map((p) => p[0])))}
              color={TEAL}
              ariaLabel={paceAria}
              targetLabel={t("esr.c1.target")}
              format={(v) => share(v, 0)}
            />
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true" className="inline-block h-1 w-5 rounded" style={{ background: TEAL }} />
                {t("esr.c1.cur", { my: d.market_year })}
              </span>
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true" className="inline-block h-2.5 w-5 rounded" style={{ background: TEAL, opacity: 0.18 }} />
                {t("esr.c1.band")}
              </span>
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true" className="inline-block w-5 border-t-2 border-dashed" style={{ borderColor: "var(--muted)" }} />
                {t("esr.c1.mean")}
              </span>
              <span className="flex items-center gap-1.5">
                <span aria-hidden="true" className="inline-block h-0.5 w-5" style={{ background: "var(--bar-past)" }} />
                {t("esr.c1.prior")} ({priorYears.join(", ")})
              </span>
              <span>{t("esr.axis.week")}</span>
            </div>
            <p className="m-0 text-xs text-muted" data-testid="pace-legend">
              <strong className="text-ink">{t("caveat.history_point_in_time")}:</strong> {t("esr.c1.note")}
            </p>
            <ChartTable
              caption={paceAria}
              head={[t("esr.h.week"), d.market_year, t("esr.h.mean"), t("esr.h.min"), t("esr.h.max"), "n"]}
              rows={paceRows}
            />
          </>
        ) : (
          <p className="m-0 text-[13px] text-muted">{t("esr.c1.none")}</p>
        )}
      </Chapter>

      <div className="grid-fit-380">
        <Chapter n={2} id="h-esr-buyers" eyebrow="esr.c2.eb" title="esr.c2">
          {noChina && (
            <p className="m-0 rounded-xl bg-bg px-3 py-2 text-[13px] text-muted" data-testid="no-china">
              {t("esr.c2.noChina", { n: hist.length })}
            </p>
          )}
          {shareBars.length > 0 && !noChina && (
            <>
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-[13px] font-semibold">{t("esr.c2.share")}</span>
                <span className="mono text-xl font-semibold" data-testid="china-share">
                  {share(chinaShare)}
                </span>
              </div>
              <Bar
                items={shareBars}
                height={170}
                currentColor={TEAL}
                minTop={10}
                format={(v) => `${num(v, 0)}%`}
                ariaLabel={t("esr.c2.aria", {
                  what: whatLower,
                  w: d.latest.week_of_my,
                  list: shareBars.map((b) => `${b.label} ${num(b.value, 1)}%`).join(", "),
                })}
              />
              <p className="m-0 text-xs text-muted">
                {t("esr.c2.unknownLine", {
                  u: share(unknown?.share ?? 0),
                  lo: share(unk.length ? Math.min(...unk) : null),
                  hi: share(unk.length ? Math.max(...unk) : null),
                })}
              </p>
              {e3 && (
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                  {e3.params.position ? (
                    <span className="rounded-full bg-nav-active px-2 py-[1px] font-semibold text-ink">{t(`pos.${e3.params.position as string}` as Key)}</span>
                  ) : null}
                  <span className="font-semibold text-ink">{t("card.n", { n: e3.n ?? "—" })}</span>
                  {e3.caveats.includes("small_sample") && <SmallChip />}
                  {e3.caveats
                    .filter((x) => x !== "small_sample")
                    .map((x) => (
                      <span key={x}>· {caveatText(x, lang)}</span>
                    ))}
                </div>
              )}
            </>
          )}
          <h3 className="m-0 text-[14px] font-semibold">{t("esr.c2.top", { date: weekDate })}</h3>
          <HBars rows={destRows} color={TEAL} ariaLabel={t("esr.c2.topAria", { date: weekDate })} />
          <p className="m-0 text-xs text-muted">{t("caveat.unknown_may_hide_china")}</p>
        </Chapter>

        <Chapter n={3} id="h-esr-needed" eyebrow="esr.c3.eb" title="esr.c3">
          {e2 && e2.suppressed_reason !== null ? (
            <Suppressed i={e2} />
          ) : req !== null && avg !== null && e2 ? (
            req <= 0 ? (
              <p className="m-0">{t("esr.c3.met")}</p>
            ) : (
              <>
                <p className="m-0 text-[15px] leading-snug" data-testid="esr-needed">
                  {t("esr.c3.sentence", {
                    req: tonnes(req, lang),
                    weeks: e2.params.weeks_remaining as number,
                    ratio: num(e2.params.ratio_required_to_avg as number, 2),
                    avg: tonnes(avg, lang),
                  })}
                </p>
                <HBars
                  color={TEAL}
                  ariaLabel={t("esr.c3.aria", { req: `${tonnes(req, lang)}${wk}`, avg: `${tonnes(avg, lang)}${wk}` })}
                  rows={[
                    { key: "req", label: t("esr.c3.req"), value: req, text: `${tonnes(req, lang)}${wk}`, strong: true },
                    { key: "avg", label: t("esr.c3.avg"), value: avg, text: `${tonnes(avg, lang)}${wk}` },
                  ]}
                />
                <h3 className="m-0 text-[14px] font-semibold">{t("esr.c3.weekly", { my: d.market_year })}</h3>
                <WeeklyBars
                  items={d.weekly.map((w) => ({ label: String(w.week_of_my), value: w.net_sales_mt }))}
                  reference={req}
                  referenceLabel={t("esr.c3.ref", { v: tonnes(req, lang) })}
                  color={TEAL}
                  format={(v) => tonnesAxis(v, lang)}
                  ariaLabel={t("esr.c3.weeklyAria", {
                    my: d.market_year,
                    req: tonnes(req, lang),
                    list: d.weekly.map((w) => `${w.week_of_my}: ${tonnes(w.net_sales_mt, lang)}`).join(", "),
                  })}
                />
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                  <span className="font-semibold text-ink">{t("card.n", { n: e2.n ?? "—" })}</span>
                  {e2.caveats.includes("small_sample") && <SmallChip />}
                  <span>· {caveatText("esr_not_census", lang)}</span>
                </div>
              </>
            )
          ) : (
            <p className="m-0 text-[13px] text-muted">{t("supp.asof_missing")}</p>
          )}
          {d.target.unit_id && <p className="m-0 text-xs text-muted">{t("esr.units", { unit: unitShort(d.target.unit_id, lang) })}</p>}
        </Chapter>
      </div>

      <details className="card group p-5" data-testid="esr-explore">
        <summary className="flex min-h-11 items-center justify-between gap-3 text-[15px] font-semibold">
          <T k="esr.explore" />
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line text-link group-hover:bg-nav-active">
            <Chevron size={16} />
          </span>
        </summary>
        <div className="flex flex-col gap-4 pt-3">
          <section aria-labelledby="h-ex-weekly">
            <h3 id="h-ex-weekly" className="m-0 text-[14px] font-semibold">
              {t("esr.ex.weekly", { my: d.market_year })}
            </h3>
            <div tabIndex={0} role="region" aria-labelledby="h-ex-weekly" className="max-h-80 overflow-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    {[t("esr.h.weekEnding"), t("esr.h.week"), t("esr.h.net"), t("esr.h.exports"), t("esr.h.nextMy"), t("esr.h.avg4")].map((h) => (
                      <th key={h} scope="col">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...d.weekly].reverse().map((w) => (
                    <tr key={w.week_ending}>
                      <th scope="row" className="font-normal">
                        {shortDate(w.week_ending, true, lang)}
                      </th>
                      <td className="tabular">{w.week_of_my}</td>
                      <td className="tabular">{tonnes(w.net_sales_mt, lang)}</td>
                      <td className="tabular">{tonnes(w.weekly_exports_mt, lang)}</td>
                      <td className="tabular">{tonnes(w.next_my_net_sales_mt, lang)}</td>
                      <td className="tabular">{tonnes(w.net_sales_4wk_avg_mt, lang)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section aria-labelledby="h-ex-dest">
            <h3 id="h-ex-dest" className="m-0 text-[14px] font-semibold">
              {t("esr.ex.dest", { date: weekDate })}
            </h3>
            <div tabIndex={0} role="region" aria-labelledby="h-ex-dest" className="max-h-80 overflow-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    {[t("esr.h.country"), t("esr.h.commit"), t("esr.h.exports"), t("esr.h.out"), t("esr.h.net"), t("esr.h.share")].map((h) => (
                      <th key={h} scope="col">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {dest.rows.map((r) => (
                    <tr key={r.country_id}>
                      <th scope="row" className="font-normal">
                        {country(r.country_id, r.country_label)}
                      </th>
                      <td className="tabular">{tonnes(r.total_commitment_mt, lang)}</td>
                      <td className="tabular">{tonnes(r.accumulated_exports_mt, lang)}</td>
                      <td className="tabular">{tonnes(r.outstanding_sales_mt, lang)}</td>
                      <td className="tabular">{tonnes(r.net_sales_mt, lang)}</td>
                      <td className="tabular">{share(r.share)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section aria-labelledby="h-ex-hist">
            <h3 id="h-ex-hist" className="m-0 text-[14px] font-semibold">
              {t("esr.h.china")} / {t("esr.h.unknown")}
            </h3>
            <table className="data-table">
              <thead>
                <tr>
                  {[t("wasde.h.my"), t("esr.h.china"), t("esr.h.unknown")].map((h) => (
                    <th key={h} scope="col">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dest.china_unknown_history.map((h) => (
                  <tr key={h.market_year}>
                    <th scope="row" className="font-normal">
                      {h.market_year}
                    </th>
                    <td className="tabular">{share(h.china_share)}</td>
                    <td className="tabular">{share(h.unknown_share)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      </details>

      <section aria-labelledby="h-take" className="card flex flex-col gap-2 p-5" data-testid="esr-take">
        <h2 id="h-take" className="m-0 text-[17px] font-bold">
          <T k="esr.take" />
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
        <div className="flex flex-wrap gap-x-5 text-[13px]">
          <Link href="/data/#report-export_sales" className="inline-flex min-h-11 items-center text-link">
            <T k="esr.take.all" />
          </Link>
          <Link href="/methodology/" className="inline-flex min-h-11 items-center text-link">
            <T k="esr.take.method" />
          </Link>
        </div>
      </section>
    </>
  );
}
