"use client";

import Bar from "@/components/charts/Bar";
import { ChartTable } from "@/components/charts/common";
import PaceChart from "@/components/charts/PaceChart";
import { useLang, useT } from "@/components/chrome/I18n";
import TopBar, { type ReleaseInfo } from "@/components/chrome/TopBar";
import { Chapter, DataTable, ExploreDetails, InsightMeta, PickPills, Stat, Suppressed, Swatch, TakeSection, useSelection } from "@/components/report/Parts";
import type { CropProgressCrop, CropProgressIndex, Insight, InsightsDoc, TakeFile } from "@/lib/data-contract";
import { ciText, num, pctInt, points, shortDate } from "@/lib/format";
import type { Key } from "@/lib/i18n";
import { byId, cropName, cropTitle, stageName } from "@/lib/insight-text";
import { cropProgressText, finalRatings } from "@/lib/report-views";

const GREEN = "var(--r-progress)";
const ok = (i: Insight | undefined) => (i && i.suppressed_reason === null ? i : undefined);

/** Week index (1 …) with a date label every ~4 weeks, ending on the newest week. */
function weekTicks(weeks: string[], lang: "en" | "pt") {
  const every = Math.max(1, Math.ceil(weeks.length / 6));
  return weeks
    .map((w, i) => ({ x: i + 1, label: shortDate(w, false, lang) ?? w }))
    .filter((_, i) => (weeks.length - 1 - i) % every === 0);
}

export default function CropProgressView({
  index,
  crops,
  insights,
  take,
  release,
}: {
  index: CropProgressIndex;
  crops: CropProgressCrop[];
  insights: InsightsDoc | null;
  take: TakeFile[];
  release: ReleaseInfo;
}) {
  const t = useT();
  const { lang } = useLang();
  const ids = crops.map((c) => c.crop);
  const [sel, pick] = useSelection(ids, ids[0] ?? "corn");
  const d = crops.find((c) => c.crop === sel) ?? crops[0];
  if (!d) return null;
  const crop = d.crop;
  const lastScheduled = index.season?.last_scheduled ?? null;
  const v = cropProgressText(d, insights, lang, lastScheduled);
  const c1 = byId(insights, `C1:${crop}`);
  const c2 = byId(insights, `C2:${crop}`);
  const c3 = byId(insights, `C3:${crop}`);
  const c1ok = ok(c1);
  const c2ok = ok(c2);
  const c3ok = ok(c3);
  const cname = cropName(crop, lang);
  const season = String(d.season);

  // ---- chapter 1: good/excellent by week vs NASS last year and the own 5-yr band
  const ge = d.ge.series;
  const geWeeks = ge.map((r) => r[0]);
  const geLines = [
    { id: "prev", current: false, points: ge.map((r, i) => [i + 1, r[2]] as [number, number | null]) },
    { id: season, current: true, points: ge.map((r, i) => [i + 1, r[1]] as [number, number | null]) },
  ];
  // The 5-season band and mean are drawn only for weeks where all min_n seasons were rated
  // (n per week is in the table); a week with fewer is a gap, never a "5-season" comparison.
  const minN = v.minN;
  const full = (r: (typeof ge)[number]) => r[6] >= minN;
  const geBand = ge.map((r, i) => (full(r) ? { x: i + 1, mean: r[3], min: r[4], max: r[5] } : { x: i + 1, mean: null, min: null, max: null }));
  const bandWeeks = ge.filter(full).length;
  const thinWeeks = ge.length - bandWeeks;
  const geHasPrev = ge.some((r) => r[2] !== null);
  const lastGe = [...ge].reverse().find((r) => r[1] !== null);
  const geAriaVars = {
    crop: cname,
    season,
    v: pctInt(lastGe?.[1]),
    date: shortDate(lastGe?.[0], true, lang) ?? "—",
    min: pctInt(lastGe?.[4]),
    max: pctInt(lastGe?.[5]),
  };
  const geAria = lastGe && full(lastGe) ? t("cp.c1.aria", geAriaVars) : t("cp.c1.ariaNoBand", { ...geAriaVars, min: minN });
  const geRows = ge.map((r) => [shortDate(r[0], true, lang) ?? r[0], pctInt(r[1]), pctInt(r[2]), r[3] === null ? "—" : `${num(r[3], 1)}%`, pctInt(r[4]), pctInt(r[5]), r[6]]);

  // ---- chapter 2: stage in progress vs NASS's published 5-yr average
  const sp = d.stage_pace;
  const spWeeks = sp.series.map((r) => r[0]);
  const spLines = [
    { id: "prev", current: false, points: sp.series.map((r, i) => [i + 1, r[3]] as [number, number | null]) },
    { id: season, current: true, points: sp.series.map((r, i) => [i + 1, r[1]] as [number, number | null]) },
  ];
  const spBand = sp.series.map((r, i) => ({ x: i + 1, mean: r[2], min: null, max: null }));
  const spHasPrev = sp.series.some((r) => r[3] !== null);
  const stagePrevNull = d.stages.some((s) => s.nass_prev_year_pct === null);
  const spStage = sp.stage ? stageName(sp.stage, lang) : "";
  const lastSp = [...sp.series].reverse().find((r) => r[1] !== null);
  const spAria = t("cp.c2.aria", { crop: cname, stage: spStage, season, v: pctInt(lastSp?.[1]), avg: pctInt(lastSp?.[2]) });
  const spRows = sp.series.map((r) => [shortDate(r[0], true, lang) ?? r[0], pctInt(r[1]), pctInt(r[2]), pctInt(r[3])]);

  // ---- chapter 3: season state
  const finals = finalRatings(c1);

  return (
    <>
      <TopBar title={t("cp.title")} release={release} sub={v.sub}>
        <PickPills label={t("cp.crop")} items={crops.map((c) => ({ id: c.crop, label: cropTitle(c.crop, lang) }))} active={crop} onPick={pick} />
      </TopBar>

      <section aria-label={t("cp.k.ge")} className="flex flex-col gap-3">
        <p className="m-0 max-w-[720px] text-[17px] leading-snug" data-testid="cp-lead">
          {v.lead}
        </p>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
          {v.closed && (
            <span className="rounded-full px-2.5 py-[2px] font-semibold text-white" style={{ background: "var(--pill-active)" }} data-testid="season-closed">
              {v.cropDone ? t("cp.pill.cropDone") : t("card.eb.cpClosed")}
            </span>
          )}
          {d.n_states !== null && <span>{t("caveat.nass_selected_states_aggregate")} ({d.n_states})</span>}
        </div>
        <div className="grid-fit-220">
          <Stat color={GREEN} label={v.stats.stageLabel} value={v.stats.stage} sub={v.stats.stageSub} testid="cp-stage" />
          <Stat color={GREEN} label={t("cp.k.ge")} value={v.stats.ge} sub={v.stats.geSub} testid="cp-ge" />
          <Stat color={GREEN} label={t("cp.k.ci")} value={v.stats.ci} sub={v.stats.ciSub} testid="cp-ci" />
          <Stat color={GREEN} label={t("cp.k.next")} value={v.stats.next} sub={v.stats.nextSub} testid="cp-next" />
        </div>
      </section>

      <Chapter n={1} color={GREEN} eyebrow="cp.c1.eb" title="cp.c1">
        {v.nBelowLine ? (
          <p className="m-0 rounded-xl bg-bg px-3 py-2 text-[13px] text-muted" data-testid="suppressed" data-suppressed={c1?.suppressed_reason === "n_below_min" ? c1.id : c3?.id}>
            {v.nBelowLine}
          </p>
        ) : (
          c1 && c1.suppressed_reason !== null && <Suppressed i={c1} />
        )}
        {v.geLine ? (
          <>
            <p className="m-0 text-[15px] leading-snug" data-testid="cp-ge-line">
              {v.geLine} {v.prevLine}
            </p>
            {v.dist && <p className="m-0 text-xs text-muted">{v.dist}</p>}
          </>
        ) : (
          <p className="m-0 text-[13px] text-muted">{t("cp.c1.none")}</p>
        )}
        {ge.length > 1 && (
          <>
            <PaceChart
              lines={geLines}
              band={geBand}
              xMax={ge.length}
              xTicks={weekTicks(geWeeks, lang)}
              color={GREEN}
              ariaLabel={geAria}
              targetLabel=""
              reference={null}
              domain="data"
              format={(x) => `${num(x, 0)}%`}
            />
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" data-testid="cp-ge-legend">
              <span className="flex items-center gap-1.5">
                <Swatch kind="line" color={GREEN} />
                {t("cp.c1.cur", { season })}
              </span>
              {geHasPrev && (
                <span className="flex items-center gap-1.5">
                  <Swatch kind="thin" />
                  {t("cp.c1.prevLine")}
                </span>
              )}
              {bandWeeks > 0 && (
                <>
                  <span className="flex items-center gap-1.5">
                    <Swatch kind="band" color={GREEN} />
                    {t("cp.c1.band")}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Swatch kind="dashed" />
                    {t("cp.c1.mean")}
                  </span>
                </>
              )}
            </div>
            {thinWeeks > 0 && (
              <p className="m-0 text-xs text-muted" data-testid="cp-band-gap">
                {t("cp.c1.bandGap", { k: thinWeeks, min: minN })}
              </p>
            )}
            <ChartTable
              caption={geAria}
              head={[t("cp.h.week"), t("cp.h.ge"), t("cp.h.prevYear"), t("esr.h.mean"), t("esr.h.min"), t("esr.h.max"), "n"]}
              rows={geRows}
            />
          </>
        )}
        {c1ok && !v.closed && <InsightMeta i={c1ok} chip={c1ok.params.position ? t(`pos.${c1ok.params.position as string}` as Key) : null} />}
        {v.ciLine && (
          <p className="m-0 text-[13px]" data-testid="cp-ci-line">
            {v.ciLine}
          </p>
        )}
        {c3 && c3.suppressed_reason !== null && !v.closed && !(v.nBelowLine && c3.suppressed_reason === "n_below_min") && <Suppressed i={c3} />}
        {c3ok && <InsightMeta i={c3ok} chip={c3ok.params.position ? t(`pos.${c3ok.params.position as string}` as Key) : null} />}
      </Chapter>

      <div className="grid-fit-380">
        <Chapter n={2} color={GREEN} eyebrow="cp.c2.eb" title="cp.c2">
          {v.stageDoneLine ? (
            <p className="m-0 rounded-xl bg-bg px-3 py-2 text-[13px] text-muted" data-testid="suppressed" data-suppressed={c2?.id}>
              {v.stageDoneLine}
            </p>
          ) : (
            c2 && c2.suppressed_reason !== null && <Suppressed i={c2} />
          )}
          {v.stageLine && (
            <p className="m-0 text-[15px] leading-snug" data-testid="cp-stage-line">
              {v.stageLine}
            </p>
          )}
          {sp.series.length > 1 ? (
            <>
              <PaceChart
                lines={spLines}
                band={spBand}
                xMax={sp.series.length}
                xTicks={weekTicks(spWeeks, lang)}
                color={GREEN}
                ariaLabel={spAria}
                targetLabel=""
                reference={null}
                height={220}
                format={(x) => `${num(x, 0)}%`}
              />
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" data-testid="cp-stage-legend">
                <span className="flex items-center gap-1.5">
                  <Swatch kind="line" color={GREEN} />
                  {t("cp.c2.cur", { season })} · {spStage}
                </span>
                <span className="flex items-center gap-1.5">
                  <Swatch kind="dashed" />
                  {t("cp.c2.avg")}
                </span>
                {spHasPrev && (
                  <span className="flex items-center gap-1.5">
                    <Swatch kind="thin" />
                    {t("cp.c2.prev")}
                  </span>
                )}
              </div>
              <ChartTable caption={spAria} head={[t("cp.h.week"), season, t("cp.h.avg5"), t("cp.h.lastYear")]} rows={spRows} />
            </>
          ) : (
            !v.stageLine && <p className="m-0 text-[13px] text-muted">{t("cp.c2.none")}</p>
          )}
          {c2ok && <InsightMeta i={c2ok} chip={c2ok.params.position ? t(`pos.${c2ok.params.position as string}` as Key) : null} />}
          {d.stages.length > 0 && (
            <DataTable
              id="h-cp-stages"
              title={t("cp.c2.table")}
              head={[t("cp.h.stage"), t("cp.h.thisWeek"), t("cp.h.lastWeek"), t("cp.h.lastYear"), t("cp.h.avg5"), t("cp.h.vsAvg")]}
              rows={d.stages.map((s) => [stageName(s.stage, lang), pctInt(s.value_pct), pctInt(s.nass_prev_week_pct), pctInt(s.nass_prev_year_pct), pctInt(s.nass_5yr_avg_pct), points(s.vs_5yr_avg_pp)])}
            />
          )}
          {d.stages.length > 0 && stagePrevNull && (
            <p className="m-0 text-xs text-muted" data-testid="cp-prev-none">
              {t("cp.c2.prevNoneNote", { y: d.season - 1 })}
            </p>
          )}
        </Chapter>

        <Chapter n={3} color={GREEN} eyebrow="cp.c3.eb" title="cp.c3">
          <p className="m-0 text-[15px] leading-snug" data-testid="cp-season-line">
            {v.seasonLine}
          </p>
          {v.closed && finals.length > 0 && (
            <>
              <Bar
                items={finals.map((f) => ({ label: String(f.season), value: f.ge, kind: f.current ? "current" : "past" }))}
                ariaLabel={t("cp.c3.finalAria", { crop: cname, season, v: pctInt(finals.at(-1)?.ge) })}
                currentColor={GREEN}
                height={180}
                minTop={10}
                format={(x) => `${num(x, 0)}%`}
              />
              {c1ok && <InsightMeta i={c1ok} chip={c1ok.params.position ? t(`pos.${c1ok.params.position as string}` as Key) : null} />}
            </>
          )}
          <DataTable
            id="h-cp-crops"
            title={t("cp.c3.crops")}
            head={[t("cp.h.crop"), t("cp.h.week"), t("cp.h.stage"), t("cp.h.thisWeek"), t("cp.h.vsAvg"), t("cp.h.ge"), t("cp.h.ci")]}
            rows={crops.map((c) => {
              const s = c.stages.find((x) => x.stage === c.stage_pace.stage) ?? c.stages.at(-1);
              const cw = c.condition?.week_ending ?? null;
              // A rating from an older week than the row's stage table names its own week.
              const dated = (txt: string) => (c.condition && cw && cw !== c.week_ending ? t("cp.c3.condWeek", { v: txt, date: shortDate(cw, false, lang) ?? cw }) : txt);
              return [
                cropTitle(c.crop, lang),
                shortDate(c.week_ending ?? c.latest.week_ending, false, lang) ?? "—",
                s ? stageName(s.stage, lang) : "—",
                pctInt(s?.value_pct),
                points(s?.vs_5yr_avg_pp),
                c.condition ? dated(pctInt(c.condition.ge_pct)) : "—",
                c.condition ? dated(ciText(c.condition.ci)) : "—",
              ];
            })}
          />
        </Chapter>
      </div>

      <ExploreDetails title="cp.explore" testid="cp-explore">
        <DataTable
          id="h-cp-ex-cond"
          title={t("cp.ex.cond", { season })}
          head={[t("cp.h.week"), t("cp.h.ge"), t("cp.h.prevYear"), t("cp.h.ci"), t("esr.h.mean"), "n"]}
          rows={[...ge].reverse().map((r) => {
            const ci = d.ci.series.find((x) => x[0] === r[0]);
            return [shortDate(r[0], true, lang) ?? r[0], pctInt(r[1]), pctInt(r[2]), ciText(ci?.[1]), r[3] === null ? "—" : `${num(r[3], 1)}%`, r[6]];
          })}
        />
        {sp.series.length > 0 && (
          <DataTable
            id="h-cp-ex-stage"
            title={t("cp.ex.stage", { stage: spStage, season })}
            head={[t("cp.h.week"), season, t("cp.h.avg5"), t("cp.h.lastYear")]}
            rows={[...spRows].reverse()}
          />
        )}
      </ExploreDetails>

      <TakeSection title="cp.take" testid="cp-take" files={take} reportId="crop_progress" methodAnchor="crop-progress">
        <p className="m-0 text-xs text-muted" data-testid="cp-window">
          {t("cp.window", { start: shortDate(index.history_start, true, lang) ?? index.history_start })}
        </p>
      </TakeSection>
    </>
  );
}
