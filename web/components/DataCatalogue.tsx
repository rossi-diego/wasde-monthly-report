import { T } from "@/components/chrome/I18n";
import TopBar, { CommodityPills } from "@/components/chrome/TopBar";
import Explorer from "@/components/Explorer";
import FileCards from "@/components/FileCards";
import ReleaseCatalogue, { type CatCommodity, type CatFile, type Workbook } from "@/components/ReleaseCatalogue";
import { commodityPills, releaseInfo } from "@/lib/dashboard";
import { getCatalog, getCropProgressIndex, getCrushIndex, getEsrIndex, getGrainStocksIndex, getIndex, getMeta, getReleaseCatalog, servedPath } from "@/lib/data";
import { num } from "@/lib/format";

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
  const cpIds = new Set(getCropProgressIndex()?.crops.map((c) => c.commodity_id) ?? []);
  const gsIds = new Set<string>(getGrainStocksIndex()?.commodities.map((c) => c.id) ?? []);
  const commodities: CatCommodity[] = [
    ...getIndex().map((c) => ({
      id: c.id,
      label: c.label,
      reports: [
        "wasde",
        ...(esrIds.has(c.id) ? ["export_sales"] : []),
        ...(crushIds.has(c.id) ? ["oilseed_crush"] : []),
        ...(cpIds.has(c.id) ? ["crop_progress"] : []),
        ...(gsIds.has(c.id) ? ["grain_stocks"] : []),
      ],
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
            <T k="cat.lead" v={{ files: num(rc.files.length), reports: Object.keys(rc.reports).length, ...(rc.data_tag ? { tag: rc.data_tag } : {}) }} keys={rc.data_tag ? undefined : { tag: "footer.local" }} />
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
        <p className="m-0 max-w-3xl text-muted">
          <T k="cat.legacyLead" v={{ reports: num(meta.history.reports), rows: num(meta.history.rows) }} months={{ first: meta.history.first_report, last: meta.latest.report_month }} />
        </p>
      )}

      <section aria-labelledby="h-files" className="flex flex-col gap-3">
        <h2 id="h-files" className="m-0 text-[17px] font-bold">
          <T k="cat.files" />
        </h2>
        <FileCards downloads={meta.downloads} tag={meta.data_release_tag} />
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
        <Explorer catalog={catalog} defaultTable="us_feed_grains_corn" />
      </section>
    </>
  );
}
