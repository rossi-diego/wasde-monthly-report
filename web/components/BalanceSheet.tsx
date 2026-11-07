import Delta from "@/components/Delta";
import { decimals, flagLabel, num } from "@/lib/format";
import type { Series } from "@/lib/types";

const RATE_ROWS: Record<string, number> = { yield: 1, stocks_to_use_pct: 1, farm_price: 2, area_planted: 1, area_harvested: 1 };
const KEY_ROWS = new Set(["production", "ending_stocks", "total_supply", "total_use", "stocks_to_use_pct"]);

export default function BalanceSheet({ series }: { series: Series }) {
  const { columns, rows } = series.balance_sheet;
  if (!rows.length) return <p className="text-sm text-muted">No balance sheet for this region.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[420px] text-sm">
        <thead>
          <tr className="border-b border-line text-xs text-muted">
            <th scope="col" className="pb-2 text-left font-normal">
              Line
            </th>
            {columns.map((c) => (
              <th key={c.market_year} scope="col" className="pb-2 text-right font-normal">
                <span className="text-ink-2">{c.market_year}</span> {flagLabel(c.flag)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const d = RATE_ROWS[r.id] ?? decimals(series.unit, r.values[0]?.value ?? 0);
            const key = KEY_ROWS.has(r.id);
            return (
              <tr key={r.id} className={`border-b border-line last:border-0 ${key ? "font-medium" : ""}`}>
                <th scope="row" className={`py-1.5 pr-3 text-left font-normal ${key ? "text-ink" : "text-ink-2"}`}>
                  {r.label}
                  {r.unit && r.unit !== series.unit_label && (
                    <span className="block text-xs font-normal text-muted">{r.unit}</span>
                  )}
                </th>
                {r.values.map((v, i) => (
                  <td key={i} className="tabular py-1.5 text-right align-top">
                    <div>{num(v.value, d)}</div>
                    {v.delta !== null && v.delta !== 0 && (
                      <Delta value={v.delta} digits={d} className="text-xs font-normal" />
                    )}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
