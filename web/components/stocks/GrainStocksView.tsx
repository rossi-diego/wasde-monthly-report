"use client";

import { ChartTable } from "@/components/charts/common";
import RangeBar from "@/components/charts/RangeBar";
import WeeklyBars from "@/components/charts/WeeklyBars";
import { useLang, useT } from "@/components/chrome/I18n";
import TopBar, { type ReleaseInfo } from "@/components/chrome/TopBar";
import { Chapter, DataTable, ExploreDetails, InsightMeta, PickPills, Stat, Suppressed, TakeSection, useSelection } from "@/components/report/Parts";
import type { GrainStocksCommodity, GrainStocksIndex, Insight, InsightsDoc, TakeFile } from "@/lib/data-contract";
import { mbu, monthYear, num, share, shortDate, signedMbu, signedShare } from "@/lib/format";
import type { Key } from "@/lib/i18n";
import { byId } from "@/lib/insight-text";
import { commodityName } from "@/lib/labels";
import { grainStocksText } from "@/lib/report-views";

const VIOLET = "var(--r-stocks)";
const ok = (i: Insight | undefined) => (i && i.suppressed_reason === null ? i : undefined);
const shortMy = (my: string) => (my.length === 7 ? my.slice(2) : my); // "2025/26" -> "25/26"

export default function GrainStocksView({
  index,
  commodities,
  insights,
  take,
  release,
}: {
  index: GrainStocksIndex;
  commodities: GrainStocksCommodity[];
  insights: InsightsDoc | null;
  take: TakeFile[];
  release: ReleaseInfo;
}) {
  const t = useT();
  const { lang } = useLang();
  const ids = commodities.map((c) => c.commodity_id);
  const [sel, pick] = useSelection(ids, ids[0] ?? "corn");
  const d = commodities.find((c) => c.commodity_id === sel) ?? commodities[0];
  if (!d) return null;
  const c = d.commodity_id;
  const v = grainStocksText(d, insights, lang);
  const g1 = byId(insights, `G1:${c}`);
  const g2 = byId(insights, `G2:${c}`);
  const g3 = byId(insights, `G3:${c}`);
  const g1ok = ok(g1);
  const g2ok = ok(g2);
  const g3ok = ok(g3);
  const date = (iso: string | null | undefined, y = true) => shortDate(iso, y, lang) ?? "—";
  const chip = (i: Insight, key: "position" | "direction") =>
    i.params[key] ? t(`${key === "position" ? "pos" : "dir"}.${i.params[key] as string}` as Key) : null;

  // ---- chapter 1 (G1): NASS first print minus the WASDE ending stocks public at the release
  const rows1 = d.vs_wasde.rows.filter((r) => r.surprise_mbu !== null);
  const g1Date = rows1.at(-1)?.as_of_date ?? null;
  const aria1 = t("gs.c1.aria", { date: date(g1Date, false), my: rows1.at(-1)?.market_year ?? "—", v: signedMbu(rows1.at(-1)?.surprise_mbu) });

  // ---- chapter 2 (G2): implied use of the last quarters vs the same quarter of 5 prior MYs
  const dis = d.disappearance.filter((q) => q.implied_disappearance_mbu !== null);
  const lastDis = dis.at(-1);
  const aria2 = t("gs.c2.aria", { what: v.what, v: mbu(lastDis?.implied_disappearance_mbu) });
  const disRows = dis.map((q) => [
    `${date(q.prev_as_of_date, false)} → ${date(q.as_of_date)}`,
    mbu(q.prev_stocks_mbu),
    q.is_harvest_quarter ? t("gs.c2.prod", { v: mbu(q.production_mbu), month: monthYear(q.wasde_release_key, lang) }) : "0",
    mbu(q.stocks_mbu),
    mbu(q.implied_disappearance_mbu),
    mbu(q.band_mbu.mean),
    q.band_mbu.min === null ? "—" : `${num(q.band_mbu.min, 0)}–${num(q.band_mbu.max, 0)}`,
    q.band_mbu.n,
  ]);

  // ---- chapter 3 (G3): on-farm share
  const g3lo = g3ok ? (g3ok.params.hist_min as number | null) : null;
  const g3hi = g3ok ? (g3ok.params.hist_max as number | null) : null;
  const qRows = [...d.quarters].reverse().map((q) => [
    date(q.as_of_date),
    mbu(q.on_farm_mbu),
    mbu(q.off_farm_mbu),
    mbu(q.total_mbu),
    q.total_mbu && q.on_farm_mbu !== null ? share(q.on_farm_mbu / q.total_mbu) : "—",
    q.is_revised ? t("crush.revisedYes") : "—",
  ]);

  return (
    <>
      <TopBar title={t("gs.title")} release={release} sub={v.sub}>
        <PickPills
          label={t("gs.commodity")}
          items={commodities.map((x) => ({ id: x.commodity_id, label: commodityName(x.commodity_id, lang, x.label) }))}
          active={c}
          onPick={pick}
        />
      </TopBar>

      <section aria-label={v.stats.totalLabel} className="flex flex-col gap-3">
        <p className="m-0 max-w-[720px] text-[17px] leading-snug" data-testid="gs-lead">
          {v.lead}
        </p>
        <div className="grid-fit-220">
          <Stat color={VIOLET} label={v.stats.totalLabel} value={v.stats.total} sub={v.stats.totalSub} testid="gs-total" />
          <Stat color={VIOLET} label={t("gs.k.farm")} value={v.stats.farm} sub={v.stats.farmSub} testid="gs-farm" />
          <Stat color={VIOLET} label={t("gs.k.yoy")} value={v.stats.yoy} sub={t("gs.k.yoySub")} testid="gs-yoy" />
          <Stat color={VIOLET} label={t("gs.k.next")} value={v.stats.next} sub={t("gs.k.nextSub")} testid="gs-next" />
        </div>
      </section>

      <Chapter n={1} color={VIOLET} eyebrow="gs.c1.eb" title="gs.c1">
        {g1 && g1.suppressed_reason !== null && <Suppressed i={g1} />}
        {v.g1Line && (
          <p className="m-0 text-[15px] leading-snug" data-testid="gs-g1-line">
            {v.g1Line} {v.g1Pctl}
          </p>
        )}
        {rows1.length > 0 ? (
          <>
            <WeeklyBars
              items={rows1.map((r) => ({ label: shortMy(r.market_year), value: r.surprise_mbu }))}
              color={VIOLET}
              format={(x) => num(x, 0)}
              ariaLabel={aria1}
              height={200}
            />
            <p className="m-0 text-xs text-muted">
              {t("unit.mbu")} · {t("gs.c1.note")}
            </p>
            <ChartTable
              caption={aria1}
              head={[t("gs.h.my"), t("gs.h.date"), t("gs.h.nass"), t("gs.h.wasde"), t("gs.h.wasdeMonth"), t("gs.h.gap"), t("gs.h.gapPct")]}
              rows={[...rows1].reverse().map((r) => [r.market_year, date(r.as_of_date), mbu(r.nass_total_mbu), mbu(r.wasde_ending_stocks_mbu), monthYear(r.wasde_release_key, lang), signedMbu(r.surprise_mbu), signedShare(r.surprise_pct)])}
            />
          </>
        ) : (
          <p className="m-0 text-[13px] text-muted">{t("gs.c1.none")}</p>
        )}
        {g1ok && <InsightMeta i={g1ok} chip={chip(g1ok, "direction")} />}
      </Chapter>

      <div className="grid-fit-380">
        <Chapter n={2} color={VIOLET} eyebrow="gs.c2.eb" title="gs.c2">
          {g2 && g2.suppressed_reason !== null && <Suppressed i={g2} />}
          {v.g2Line && (
            <p className="m-0 text-[15px] leading-snug" data-testid="gs-g2-line">
              {v.g2Line}
            </p>
          )}
          {g2ok && g2ok.params.hist_min !== null && (
            <RangeBar
              lo={g2ok.params.hist_min as number}
              hi={g2ok.params.hist_max as number}
              mean={g2ok.params.hist_mean as number | null}
              value={g2ok.params.implied_disappearance_mbu as number}
              color={VIOLET}
              fromZero={false}
              format={(x) => num(x, 0)}
              ariaLabel={t("card.rangeAriaPlain", { min: mbu(g2ok.params.hist_min as number), max: mbu(g2ok.params.hist_max as number), v: mbu(g2ok.params.implied_disappearance_mbu as number) })}
            />
          )}
          {dis.length > 0 && (
            <WeeklyBars
              items={dis.map((q) => ({ label: `${date(q.as_of_date, false)} ’${q.as_of_date.slice(2, 4)}`, value: q.implied_disappearance_mbu }))}
              color={VIOLET}
              format={(x) => num(x, 0)}
              ariaLabel={aria2}
              height={170}
            />
          )}
          <p className="m-0 text-xs text-muted" data-testid="gs-formula">
            {t("gs.c2.formula")}
          </p>
          {g2ok && <InsightMeta i={g2ok} chip={chip(g2ok, "position")} />}
          {dis.length > 0 && (
            <ChartTable
              caption={aria2}
              head={[t("gs.h.quarter"), t("gs.h.start"), t("gs.h.prod"), t("gs.h.end"), t("gs.h.use"), t("gs.h.mean5"), t("gs.h.range5"), "n"]}
              rows={[...disRows].reverse()}
            />
          )}
        </Chapter>

        <Chapter n={3} color={VIOLET} eyebrow="gs.c3.eb" title="gs.c3">
          {g3 && g3.suppressed_reason !== null && <Suppressed i={g3} />}
          {v.g3Line && (
            <p className="m-0 text-[15px] leading-snug" data-testid="gs-g3-line">
              {v.g3Line}
            </p>
          )}
          {g3ok && g3lo !== null && g3hi !== null && (
            <RangeBar
              lo={g3lo}
              hi={g3hi}
              mean={g3ok.params.hist_mean as number | null}
              value={g3ok.params.on_farm_share as number}
              color={VIOLET}
              format={(x) => share(x, 0)}
              ariaLabel={t("gs.c3.aria", { what: v.what, date: date(g3ok.params.as_of_date as string), v: share(g3ok.params.on_farm_share as number), min: share(g3lo), max: share(g3hi) })}
            />
          )}
          {g3ok && <InsightMeta i={g3ok} chip={chip(g3ok, "position")} />}
          <DataTable
            id="h-gs-quarters"
            title={t("gs.ex.quarters", { n: Math.min(8, qRows.length) })}
            head={[t("gs.h.date"), t("gs.h.onFarm"), t("gs.h.offFarm"), t("gs.h.total"), t("gs.h.share"), t("gs.h.revised")]}
            rows={qRows.slice(0, 8)}
          />
        </Chapter>
      </div>

      <ExploreDetails title="gs.explore" testid="gs-explore">
        <DataTable
          id="h-gs-ex-q"
          title={t("gs.ex.byQuarter", { my: d.market_year })}
          head={[t("gs.h.date"), d.market_year, t("gs.h.mean5"), t("gs.h.range5"), "n"]}
          rows={d.by_quarter.map((q) => [date(q.as_of_date), mbu(q.total_mbu), mbu(q.band_mbu.mean), q.band_mbu.min === null ? "—" : `${num(q.band_mbu.min, 0)}–${num(q.band_mbu.max, 0)}`, q.band_mbu.n])}
        />
        <DataTable
          id="h-gs-ex-all"
          title={t("gs.ex.quarters", { n: qRows.length })}
          head={[t("gs.h.date"), t("gs.h.onFarm"), t("gs.h.offFarm"), t("gs.h.total"), t("gs.h.share"), t("gs.h.revised")]}
          rows={qRows}
        />
      </ExploreDetails>

      <TakeSection title="gs.take" testid="gs-take" files={take} reportId="grain_stocks" methodAnchor="grain-stocks">
        <p className="m-0 text-xs text-muted" data-testid="gs-window">
          {t("gs.window", { from: date(index.history_start) })}
        </p>
      </TakeSection>
    </>
  );
}
