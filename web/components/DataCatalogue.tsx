import { T } from "@/components/chrome/I18n";
import TopBar, { CommodityPills } from "@/components/chrome/TopBar";
import Explorer from "@/components/Explorer";
import ReleaseCatalogue, { type CatCommodity, type CatFile, type Workbook } from "@/components/ReleaseCatalogue";
import { commodityPills, releaseInfo } from "@/lib/dashboard";
import { getCatalog, getCrushIndex, getEsrIndex, getIndex, getMeta, getReleaseCatalog, servedPath } from "@/lib/data";
import { bytes, monthLabel, num } from "@/lib/format";

/** Shared by /data/ (catalogue) and /downloads/ (kept for existing links). */
export default function DataCatalogue() {
  const meta = getMeta();
  const catalog = getCatalog();
  const rc = getReleaseCatalog();
  const esr = getEsrIndex();

  // Links resolved at build time: the site copy when this build serves it, else the release asset.
  const files: CatFile[] = (rc?.files ?? []).map((f) => {
    const served = servedPath(f.site_url);
    return { ...f, href: served ?? f.release_url, served: Boolean(served) };
  });
  const workbooks: Workbook[] = meta.downloads
    .filter((d) => d.file.endsWith(".xlsx"))
    .map((d) => ({
      file: d.file,
      label: d.label,
      href: `/data/${d.url}`,
      bytes: d.bytes,
      commodity: /^wasde_history_(.+)\.xlsx$/.exec(d.file)?.[1] ?? null,
    }));
  const esrIds = new Set(esr?.commodities.map((c) => c.id) ?? []);
  // NASS crush covers soybeans and its products (crude oil, meal).
  const crushIds = new Set(getCrushIndex() ? ["soybeans", "soybean_oil", "soybean_meal"] : []);
  const commodities: CatCommodity[] = [
    ...getIndex().map((c) => ({
      id: c.id,
      label: c.label,
      reports: ["wasde", ...(esrIds.has(c.id) ? ["export_sales"] : []), ...(crushIds.has(c.id) ? ["oilseed_crush"] : [])],
    })),
    ...(esr?.commodities ?? [])
      .filter((c) => !getIndex().some((x) => x.id === c.id))
      .map((c) => ({ id: c.id, label: c.label, reports: ["export_sales"] })),
  ];

  return (
    <>
      <TopBar title={<T k="data.page" />} release={releaseInfo(meta)}>
        <CommodityPills pills={commodityPills()} />
      </TopBar>

      {rc ? (
        <>
          <p className="m-0 max-w-3xl text-muted">
            <T k="cat.lead" v={{ files: num(rc.files.length), reports: Object.keys(rc.reports).length, tag: rc.data_tag ?? "local build" }} />
          </p>
          <ReleaseCatalogue
            catalog={rc}
            files={files}
            workbooks={workbooks}
            datapackageHref={servedPath(rc.datapackage.site_url) ?? rc.datapackage.release_url}
            commodities={commodities}
            vintageQuality={esr?.latest.vintage_quality ?? null}
          />
        </>
      ) : (
        <p className="m-0 max-w-3xl text-muted" lang="en">
          Every value of every WASDE report from {monthLabel(meta.history.first_report)} to {meta.latest.label}:{" "}
          {num(meta.history.reports)} reports, {num(meta.history.rows)} values, harmonized into one table. Public domain (USDA).
        </p>
      )}

      <section aria-labelledby="h-files" className="flex flex-col gap-3">
        <h2 id="h-files" className="m-0 text-[17px] font-bold">
          <T k="cat.files" />
        </h2>
        {/* File descriptions come from the publisher in English (lang marks them for screen readers). */}
        <ul className="grid-fit-240 m-0 list-none p-0" lang="en">
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
            <T k="cat.slice" />
          </h2>
          <p className="m-0 text-[13px] text-muted">
            <T k="cat.sliceNote" />
          </p>
        </div>
        {/* The explorer's controls are English only for now. */}
        <div lang="en">
          <Explorer catalog={catalog} defaultTable="us_feed_grains_corn" />
        </div>
      </section>
    </>
  );
}
