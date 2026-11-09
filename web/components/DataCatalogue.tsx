import { T } from "@/components/chrome/I18n";
import TopBar, { CommodityPills } from "@/components/chrome/TopBar";
import Explorer from "@/components/Explorer";
import { commodityPills, releaseInfo } from "@/lib/dashboard";
import { getCatalog, getMeta } from "@/lib/data";
import { bytes, monthLabel, num } from "@/lib/format";

/** Shared by /data/ (catalogue) and /downloads/ (kept for existing links). */
export default function DataCatalogue() {
  const meta = getMeta();
  const catalog = getCatalog();
  return (
    <>
      <TopBar title={<T k="data.page" />} release={releaseInfo(meta)}>
        <CommodityPills pills={commodityPills()} />
      </TopBar>

      <p className="m-0 max-w-3xl text-muted">
        Every value of every WASDE report from {monthLabel(meta.history.first_report)} to {meta.latest.label}:{" "}
        {num(meta.history.reports)} reports, {num(meta.history.rows)} values, harmonized into one table. Updated automatically on
        release day. Public domain (USDA).
      </p>

      <section aria-labelledby="h-files" className="flex flex-col gap-3">
        <h2 id="h-files" className="m-0 text-[17px] font-bold">
          Ready-made files
        </h2>
        <ul className="grid-fit-240 m-0 list-none p-0">
          {meta.downloads.map((d) => (
            <li key={d.file} className="card flex flex-col gap-2 p-4">
              <div className="flex items-start justify-between gap-2">
                <h3 className="m-0 text-[15px] font-semibold">{d.label}</h3>
                <span className="shrink-0 rounded-full bg-bg px-2 py-0.5 text-xs text-muted">{bytes(d.bytes)}</span>
              </div>
              <p className="m-0 flex-1 text-[13px] text-muted">{d.description}</p>
              <div className="flex flex-wrap gap-x-4 text-[13px]">
                <a className="inline-flex min-h-11 items-center font-semibold text-link" href={`/data/${d.url}`} download>
                  Download {d.file.split(".").slice(1).join(".")}
                </a>
                {d.release_url && (
                  <a className="inline-flex min-h-11 items-center text-muted underline" href={d.release_url}>
                    Versioned copy ({meta.data_release_tag})
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="h-explore" className="card flex flex-col gap-4 p-5">
        <div>
          <h2 id="h-explore" className="m-0 text-[17px] font-bold">
            Explore and export a slice
          </h2>
          <p className="m-0 text-[13px] text-muted">
            Pick a WASDE table and filter it; the data loads in your browser and exports exactly what you see.
          </p>
        </div>
        <Explorer catalog={catalog} defaultTable="us_feed_grains_corn" />
      </section>
    </>
  );
}
