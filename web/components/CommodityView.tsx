"use client";

import { useRef, useState } from "react";

import BalanceSheet from "@/components/BalanceSheet";
import Bar from "@/components/charts/Bar";
import { ChartTable } from "@/components/charts/common";
import MultiLine from "@/components/charts/MultiLine";
import Waterfall from "@/components/charts/Waterfall";
import { T, useLang, useT } from "@/components/chrome/I18n";
import TopBar, { CommodityPills, type Pill, type ReleaseInfo } from "@/components/chrome/TopBar";
import Delta from "@/components/Delta";
import Explore from "@/components/Explore";
import { decimals, flagLabel, monthYear, num, unitShort } from "@/lib/format";
import { revView, seriesNoun, stuView, waterfallView } from "@/lib/insights";
import { attrName, commodityName, regionName } from "@/lib/labels";
import type { CommodityIndex, Series } from "@/lib/types";

type Entry = CommodityIndex[number];

const ATTR_LABEL: Record<string, string> = {
  ending_stocks: "Ending stocks",
  production: "Production",
  stocks_to_use_pct: "Stocks-to-use %",
  exports: "Exports",
  domestic_total: "Domestic use",
  yield: "Yield",
};

const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);

function Tabs<V extends string>({ label, items, value, onChange }: { label: string; items: { id: V; label: string }[]; value: V; onChange: (v: V) => void }) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1">
      {items.map((it) => (
        <button
          key={it.id}
          type="button"
          aria-pressed={it.id === value}
          onClick={() => onChange(it.id)}
          className={`min-h-11 cursor-pointer rounded-full px-3 text-xs font-semibold ${
            it.id === value ? "bg-[var(--pill-active)] text-white" : "border border-line text-ink hover:bg-nav-active"
          }`}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}

function Stat({ title, value, children }: { title: React.ReactNode; value: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="card p-4">
      <p className="m-0 text-[13px] text-muted">{title}</p>
      <p className="mono m-0 mt-1 text-[28px] font-semibold">{value}</p>
      <p className="m-0 text-[13px]">{children}</p>
    </div>
  );
}

export default function CommodityView({
  entry,
  initial,
  release,
  pills,
}: {
  entry: Entry;
  initial: Series;
  release: ReleaseInfo;
  pills: Pill[];
}) {
  const t = useT();
  const { lang } = useLang();
  const [region, setRegion] = useState("united_states");
  const [series, setSeries] = useState<Series>(initial);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ region: string; message: string } | null>(null);
  const [attr, setAttr] = useState("ending_stocks");
  const [drvMy, setDrvMy] = useState<string | null>(null);
  const latestRequest = useRef(0);

  const selectRegion = (next: string) => {
    setRegion(next);
    if (next === series.region) return;
    const id = ++latestRequest.current; // ignore responses that arrive out of order
    setLoading(true);
    setError(null);
    fetch(`/data/commodities/${entry.id}/${next}.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<Series>;
      })
      .then((s) => {
        if (id !== latestRequest.current) return;
        setSeries(s);
        setDrvMy(null);
      })
      .catch((e: Error) => id === latestRequest.current && setError({ region: next, message: e.message }))
      .finally(() => id === latestRequest.current && setLoading(false));
  };

  const regionLabel = (id: string, fallback: string) => regionName(id, lang, fallback);
  const what = seriesNoun(entry.id, series.region_label, entry.label, lang, series.region);
  const esRow = series.balance_sheet.rows.find((r) => r.id === "ending_stocks");
  const suRow = series.balance_sheet.rows.find((r) => r.id === "stocks_to_use_pct");
  const cols = series.balance_sheet.columns;
  const n = cols.length - 1;
  const newCrop = cols[n];
  const es = esRow?.values[n];
  const su = suRow?.values[n];
  const d = decimals(series.unit, es?.value ?? 0);
  const stu = stuView(series, lang);
  const flag = (f: string | null | undefined) =>
    lang === "pt" ? (f === "proj" ? t("status.proj") : f === "est" ? t("status.est") : "") : flagLabel(f);
  const attrLabel = (a: string) => (lang === "pt" ? cap(attrName(a, "pt", ATTR_LABEL[a])) : ATTR_LABEL[a]);

  const attrs = Object.keys(ATTR_LABEL).filter((a) => series.revisions[a]?.length);
  const activeAttr = attrs.includes(attr) ? attr : attrs[0];
  const rev = activeAttr ? revView(series, activeAttr, 5, 23, lang) : null;
  const unitLong = lang === "en" ? (series.unit_label ?? "") : unitShort(series.unit, lang);
  const revUnit = activeAttr === "stocks_to_use_pct" ? "%" : activeAttr === "yield" ? "" : unitLong;

  const drvYears = series.drivers.map((x) => x.market_year);
  const activeMy = drvMy && drvYears.includes(drvMy) ? drvMy : drvYears[drvYears.length - 1];
  const wf = waterfallView(series, activeMy, series.previous_report_month, lang);
  const dim = loading ? "opacity-60" : "";
  const stuRank = stu.now !== null && stu.n >= 5 ? t("tight.rank", { k: stu.k, n: stu.n, from: stu.finalFrom, to: stu.finalTo }) : null;
  const isWorld = series.region === "world" || series.region === "world_less_china";

  return (
    <>
      <TopBar
        title={
          <>
            {commodityName(entry.id, lang, entry.label)}{" "}
            <span className="text-muted">· {regionLabel(series.region, series.region_label)}</span>
          </>
        }
        release={release}
      >
        <CommodityPills pills={pills} active={entry.id} />
      </TopBar>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="m-0 text-[13px] text-muted">{t("cv.sub", { month: monthYear(series.report_month, lang), unit: unitLong })}</p>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted">
            <T k="commodity.region" />
          </span>
          <select
            value={region}
            onChange={(e) => selectRegion(e.target.value)}
            className="min-h-11 rounded-lg border border-line bg-card px-3 text-ink"
          >
            {entry.regions.map((r) => (
              <option key={r.id} value={r.id}>
                {regionLabel(r.id, r.label)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error && (
        <p role="alert" className="card m-0 p-3 text-sm text-down">
          {t("cv.loadError", { region: error.region, error: error.message })}
        </p>
      )}

      <section aria-label={t("home.kpis")} className={`grid-fit-220 ${dim}`}>
        <Stat title={t("cv.es", { my: newCrop?.market_year ?? "", flag: flag(newCrop?.flag) })} value={num(es?.value, d)}>
          <Delta value={es?.delta} digits={d} />{" "}
          <span className="text-muted">
            {t("cv.vsLast")} · {unitShort(series.unit, lang)}
          </span>
        </Stat>
        <Stat title={t("cv.stu", { my: newCrop?.market_year ?? "" })} value={`${num(su?.value, 1)}%`}>
          <Delta value={su?.delta} digits={1} suffix=" pt" /> <span className="text-muted">{t("cv.vsLast")}</span>
        </Stat>
        <Stat title={t("cv.hist")} value={stuRank ? t("cv.kofn", { k: stu.k, n: stu.n }) : "—"}>
          <span className="text-muted">{stuRank ? t("cv.histNote") : t("cv.histNeed")}</span>
        </Stat>
        <Stat title={t("cv.old", { my: cols[n - 1]?.market_year ?? "" })} value={num(esRow?.values[n - 1]?.value, d)}>
          <Delta value={esRow?.values[n - 1]?.delta} digits={d} /> <span className="text-muted">{t("cv.oldNote")}</span>
        </Stat>
      </section>

      <div className={`grid-fit-380 items-start ${dim}`}>
        <section className="card min-w-0 p-5" aria-labelledby="h-bs">
          <div className="eyebrow">{t("cv.bsEyebrow")}</div>
          <h2 id="h-bs" className="m-0 text-[17px] font-bold">
            <T k="commodity.bs" />
          </h2>
          <p className="mb-4 mt-1 text-[13px] text-muted">
            {t("cv.bsNote", {
              unit: unitLong,
              month: series.previous_report_month ? monthYear(series.previous_report_month, lang) : t("cv.prevReport"),
            })}
          </p>
          <BalanceSheet series={series} />
        </section>

        <section className="card flex min-w-0 flex-col gap-2 p-5" aria-labelledby="h-drv">
          <div>
            <div className="eyebrow">
              <T k="wf.eyebrow" />
            </div>
            <h2 id="h-drv" className="m-0 text-[17px] font-bold">
              <T k="commodity.drivers" />
            </h2>
          </div>
          {drvYears.length > 0 && (
            <Tabs label={t("stu.head.my")} items={drvYears.map((y) => ({ id: y, label: y }))} value={activeMy} onChange={setDrvMy} />
          )}
          {wf ? (
            <>
              <Waterfall steps={wf.steps} ariaLabel={`${what}. ${wf.aria}`} format={(v) => num(v, wf.digits)} />
              <p className="m-0 text-xs text-muted">{t("cv.wfNote")}</p>
              <ChartTable
                caption={wf.aria}
                head={[t("wf.head.step"), t("wf.head.effect", { unit: unitShort(series.unit, lang) })]}
                rows={wf.rows}
              />
            </>
          ) : (
            <p className="py-12 text-center text-sm text-muted">
              <T k="wf.none" />
            </p>
          )}
        </section>
      </div>

      <section className={`card flex flex-col gap-2 p-5 ${dim}`} aria-labelledby="h-rev">
        <div>
          <div className="eyebrow">
            <T k="rev.eyebrow" />
          </div>
          <h2 id="h-rev" className="m-0 text-[17px] font-bold">
            <T k="commodity.revisions" />
          </h2>
        </div>
        {attrs.length > 0 && (
          <Tabs label={t("cv.line")} items={attrs.map((a) => ({ id: a, label: attrLabel(a) }))} value={activeAttr} onChange={setAttr} />
        )}
        {rev ? (
          <>
            <MultiLine
              lines={rev.lines}
              xMax={rev.xMax}
              xTicks={rev.xTicks}
              height={260}
              ariaLabel={t("cv.revAria", {
                what,
                attr: attrLabel(activeAttr).toLowerCase(),
                first: rev.firstMy,
                last: rev.lastMy,
                min: num(rev.curMin, rev.digits),
                max: num(rev.curMax, rev.digits),
                since: rev.since,
              })}
              format={(v) => num(v, rev.digits > 1 ? 1 : rev.digits)}
            />
            <p className="m-0 text-xs text-muted">
              {revUnit ? `${revUnit}. ` : ""}
              {t("cv.revNote", { last: rev.lastMy, from: rev.greyFrom, to: rev.greyTo })}
            </p>
            <ChartTable
              caption={t("cv.revCaption", { what, attr: attrLabel(activeAttr).toLowerCase() })}
              head={rev.head}
              rows={rev.rows}
            />
          </>
        ) : (
          <p className="text-sm text-muted">{t("cv.revNone")}</p>
        )}
      </section>

      <section className={`card flex flex-col gap-2 p-5 ${dim}`} aria-labelledby="h-su">
        <div className="flex flex-wrap justify-between gap-2">
          <div>
            <div className="eyebrow">
              <T k="tight.eyebrow" />
            </div>
            <h2 id="h-su" className="m-0 text-[17px] font-bold">
              <T k="commodity.stu" />
            </h2>
          </div>
          {stu.now !== null && (
            <div className="text-right">
              <div className="mono text-xl font-semibold">{num(stu.now, 1)}%</div>
              {stuRank && <div className="text-xs text-muted">{stuRank}</div>}
            </div>
          )}
        </div>
        {stu.bars.length ? (
          <>
            <Bar
              items={stu.bars}
              ariaLabel={t("stu.aria", {
                what,
                from: stu.from,
                to: stu.to,
                my: stu.nowMy ?? "",
                now: `${num(stu.now, 1)}%`,
                rank: stuRank ? `; ${stuRank}` : "",
              })}
              format={(v) => `${num(v, 0)}%`}
            />
            <p className="m-0 text-xs text-muted">
              {t("cv.stuNote", {
                my: stu.nowMy ?? "",
                est: stu.estMy ? t("cv.stuNoteEst", { my: stu.estMy }) : "",
                n: stu.n,
              })}
              {isWorld ? t("cv.stuWorld") : t("cv.stuUs")}
            </p>
            <ChartTable
              caption={t("cv.stuCaption", { what })}
              head={[t("stu.head.my"), t("stu.head.stu"), t("stu.head.es"), t("stu.head.status")]}
              rows={stu.rows}
            />
          </>
        ) : (
          <p className="text-sm text-muted">{t("cv.stuNone")}</p>
        )}
      </section>

      <Explore series={series} />
    </>
  );
}
