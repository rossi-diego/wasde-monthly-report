import type { Metadata } from "next";

import { EnglishOnlyNote, T } from "@/components/chrome/I18n";
import TopBar, { CommodityPills } from "@/components/chrome/TopBar";
import { commodityPills, releaseInfo } from "@/lib/dashboard";
import { getInsights, getMeta } from "@/lib/data";
import { monthLabel, num } from "@/lib/format";

export const metadata: Metadata = { title: "Methodology · USDA Reports Dashboard" };

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="card max-w-3xl space-y-3 p-5 sm:p-6">
      <h2 className="m-0 text-[17px] font-bold">{title}</h2>
      <div className="space-y-3 leading-relaxed">{children}</div>
    </section>
  );
}

export default function Methodology() {
  const meta = getMeta();
  const ins = getInsights();
  return (
    <>
      <TopBar title={<T k="nav.methodology" />} release={releaseInfo(meta)}>
        <CommodityPills pills={commodityPills()} />
      </TopBar>
      {/* Long-form copy is English only (by design, see lib/i18n.ts): PT readers get a notice, and
          the block is marked lang="en" so screen readers keep EN pronunciation. */}
      <EnglishOnlyNote />
      <div lang="en" className="flex flex-col gap-5">
      <p className="m-0 max-w-3xl text-muted">
        How the numbers on this site are collected, harmonized and turned into insight. Everything is open source and
        rebuilt from the raw USDA files on every run.
      </p>

      <Block title="Sources">
        <p>
          <strong className="text-ink">2021 onwards:</strong> USDA&apos;s official machine-readable WASDE CSV, one file per
          report. <strong className="text-ink">July 2010 – 2020</strong> (and any month without a CSV): the XML edition
          archived by ESMIS (Cornell / USDA National Agricultural Library), discovered through its public API. Earlier
          reports exist only as PDF/text and are out of scope.
        </p>
        <p>
          The dataset currently holds {num(meta.history.reports)} reports ({monthLabel(meta.history.first_report)} –{" "}
          {meta.latest.label}) and {num(meta.history.rows)} values. Months without a WASDE (e.g. the October 2013 and
          October 2025 government shutdowns) are simply absent.
        </p>
      </Block>

      <Block title="Harmonization">
        <p>
          The XML edition does not label commodities or units for most tables. Its layout was learned from the 53 months
          (2021–2025) published in both formats: 97% of CSV values are reproduced exactly from the XML, and 100% of the
          grain and oilseed balance sheets. Older releases map to the same layout; label variants (e.g. &quot;Hard
          Winter&quot; vs &quot;Hard Red Winter&quot;) are aliased in versioned configuration files.
        </p>
        <p>
          Every table, commodity, line and unit gets a canonical id (e.g. &quot;Ending Stocks, Total&quot; and
          &quot;Ending stocks&quot; → <code>ending_stocks</code>). A label never seen before stops the monthly run until it is
          mapped, so nothing is silently dropped.
        </p>
        <p>
          Continuity choices: &quot;EU-27&quot; (2010–2013), &quot;European Union&quot; and &quot;EU-27+UK&quot; (Jan–Apr 2021)
          form one European Union series (membership changed over time, including Brexit in 2020). Older reports publish
          projected farm prices as ranges (e.g. 7.50–8.90); these are stored as the midpoint. Units follow the official CSV
          for every series, and labels that are wrong at the source (cotton farm price tagged as bales) are corrected.
        </p>
        <p>
          Known gaps in the pre-2021 history: WASDE&apos;s projection-reliability tables, some quarterly livestock lines,
          and the U.S. milk table, whose fat- and skim-solids blocks share labels in the XML and are not fully separated.
          Footnoted &quot;negligible&quot; cells in old cotton tables are stored as missing rather than zero.
        </p>
      </Block>

      <Block title="Definitions">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <strong className="text-ink">Stocks-to-use</strong>: ending stocks ÷ use. For World and World ex-China, use =
            domestic use (exports and imports net out globally). For the U.S. and individual countries, use = domestic use
            + exports. Where a table publishes no domestic total (U.S. soybeans), it is derived as total use − exports.
          </li>
          <li>
            <strong className="text-ink">Revision path</strong>: the value USDA published for one marketing year in each
            successive report. Month 0 is the first projection in May of the marketing-year start; month 12 is when the
            projection becomes an estimate.
          </li>
          <li>
            <strong className="text-ink">Drivers</strong>: Δ ending stocks = Δ beginning stocks + Δ production + Δ imports −
            Δ domestic use − Δ exports + other (residual lines and rounding). For U.S. tables production splits into an
            area effect (Δ area × previous yield) and a yield effect (the rest).
          </li>
          <li>
            <strong className="text-ink">Percentile</strong>: where the current stocks-to-use projection ranks among the
            final values of all completed marketing years in the dataset (shown once at least 10 years are complete).
          </li>
        </ul>
      </Block>

      <Block title="How headlines are chosen">
        <ol className="list-decimal space-y-2 pl-5">
          <li>Candidates: ending stocks, production, yield, area, exports, crush and farm price of the focus commodities, for the new- and old-crop marketing years.</li>
          <li>Each change must clear an absolute materiality floor (e.g. 50 mil. bu for U.S. corn ending stocks, 0.3 bu/acre for soybean yield, 2 MMT for world stocks).</li>
          <li>Score = half &quot;size&quot; (percent change) and half &quot;surprise&quot; (change ÷ the median change of the same line in the same calendar month of past years), weighted towards ending stocks and the U.S./World aggregates.</li>
          <li>One headline per commodity, region and marketing year, at most two per commodity, six in total. Ending-stocks headlines carry their drivers and the change in stocks-to-use.</li>
        </ol>
      </Block>

      <Block title="Export Sales (USDA FAS)">
        <p>
          Weekly Export Sales Reporting (ESR) data from the FAS API (<code>api.fas.usda.gov</code>), published Thursdays at
          8:30 ET for the week ending the previous Thursday. Quantities are metric tonnes for the current marketing year;
          next-marketing-year sales are kept separate and never added to the current year. Commitments = accumulated
          exports + outstanding sales. ESR commitments are not Census exports.
        </p>
        <p>
          <strong className="text-ink">Pace vs USDA (E1)</strong>: commitments ÷ the U.S. export projection of the latest
          WASDE released before that ESR (an as-of join on release timestamps, so no look-ahead), converted to metric
          tonnes (bushels by commodity weight; soybean meal from thousand short tons; soybean oil from million pounds). Each
          of the 5 previous marketing years is measured the same way, at the same week, against the WASDE public at the time.
          Five years is a small sample: it is shown as a mean and a min–max range, never as a percentile.
        </p>
        <p>
          <strong className="text-ink">Required weekly sales (E2)</strong>: (as-of target − commitments) ÷ weeks left in the
          marketing year, compared with the 4-week average of net sales; not shown with fewer than 6 weeks left.{" "}
          <strong className="text-ink">China share (E3)</strong>: China&apos;s commitments ÷ all commitments, always shown next
          to the share of unknown destinations, which can hide China.
        </p>
        <p>
          Vintages: the API serves only the latest revision of past weeks, so history before the first capture is
          latest-only; every pull is stored as an immutable snapshot from then on (silver keeps every vintage, the
          published datasets show the latest revision).
        </p>
        <p>
          Release times: the newest week of each pull carries the API&apos;s own release timestamp. Backfilled history is
          dated with the Thursday 8:30 ET rule (holidays move it to Friday), except for the weeks published late after the
          2013, 2018–19 and 2025 government shutdowns, which are pinned to their actual FAS catch-up release dates. A week
          is therefore always compared with the WASDE that was public when FAS actually released it.
        </p>
      </Block>

      <Block title="Insight rules and honesty gates">
        <ul className="list-disc space-y-2 pl-5">
          <li>Insights are computed in Python as typed parameters (ranks, shares, n); the site only turns them into words, and a test checks that the page matches the JSON.</li>
          <li>Ranks read &quot;k of n&quot;. A percentile appears only when n ≥ {ins?.gates.percentile_min_n ?? 10}. n is always shown, with a &quot;small sample&quot; chip below {ins?.gates.small_sample_below ?? 10}.</li>
          <li>An insight is not shown when n &lt; {ins?.gates.min_n ?? 5}, when an input report is older than its cadence plus grace, or when no USDA projection was public at the time.</li>
          {ins && (
            <li>
              Multiple comparisons: this build screened{" "}
              {Object.entries(ins.n_screened)
                .map(([k, v]) => `${k} ${num(v)}`)
                .join(", ")}{" "}
              series or candidates; the home page shows at most one card per report plus one cross-report card.
            </li>
          )}
        </ul>
      </Block>

      <Block title="Automation">
        <p>
          A scheduled GitHub Actions workflow runs every 30 minutes on weekdays. A light gate checks the release
          calendars first and stops in seconds when nothing is due. WASDE is polled from 12:00 ET on release day; Export
          Sales from 8:30 ET every Thursday (Friday after a holiday week). When a new report appears it rebuilds bronze →
          silver → gold (dbt + DuckDB, with data tests such as the U.S. balance-sheet identity and a no-look-ahead check),
          redeploys this site, verifies it live and only then publishes the versioned GitHub release.
        </p>
        <p>
          A new WASDE becomes the <code>data-YYYY-MM</code> release, always marked Latest. A week with only new Export
          Sales data publishes an immutable prerelease <code>weekly-YYYY-MM-DD</code> that is never marked Latest. Export
          Sales is isolated from WASDE: a failed or invalid ESR pull keeps the last good ESR data, is flagged on the
          Reports page and never blocks the WASDE release. An external heartbeat and an auto-updated GitHub issue alert the
          maintainer if a report is late or a check fails.
        </p>
      </Block>
      </div>
    </>
  );
}
