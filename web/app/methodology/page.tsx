import type { Metadata } from "next";

import { T } from "@/components/chrome/I18n";
import TopBar, { CommodityPills } from "@/components/chrome/TopBar";
import MethodologyBody from "@/components/MethodologyBody";
import { commodityPills, releaseInfo } from "@/lib/dashboard";
import { getInsights, getMeta } from "@/lib/data";

export const metadata: Metadata = { title: "Methodology · USDA Reports Dashboard" };

export default function Methodology() {
  const meta = getMeta();
  const ins = getInsights();
  return (
    <>
      <TopBar title={<T k="nav.methodology" />} release={releaseInfo(meta)}>
        <CommodityPills pills={commodityPills()} />
      </TopBar>
      <MethodologyBody
        f={{
          reports: meta.history.reports,
          rows: meta.history.rows,
          first: meta.history.first_report,
          last: meta.latest.report_month,
          minN: ins?.gates.min_n ?? 5,
          pctlN: ins?.gates.percentile_min_n ?? 10,
          smallN: ins?.gates.small_sample_below ?? 10,
          f2Months: ins?.gates.f2_min_months_remaining ?? 5,
          nScreened: ins?.n_screened ?? null,
          homeHidden: ins?.gates.home_hidden_months?.crop_progress ?? [12, 1, 2, 3],
        }}
      />
    </>
  );
}
