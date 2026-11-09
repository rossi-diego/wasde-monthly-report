import type { Metadata } from "next";

import Explorer from "@/components/Explorer";
import { getCatalog, getMeta } from "@/lib/data";
import { bytes, monthLabel, num } from "@/lib/format";

export const metadata: Metadata = { title: "Data & downloads · USDA Reports Dashboard" };

export default function DownloadsPage() {
  const meta = getMeta();
  const catalog = getCatalog();
  return (
    <div className="space-y-10">
      <section className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight">Data &amp; downloads</h1>
        <p className="max-w-3xl text-ink-2">
          Every value of every WASDE report from {monthLabel(meta.history.first_report)} to {meta.latest.label} —{" "}
          {num(meta.history.reports)} reports, {num(meta.history.rows)} values — harmonized into one table. Updated
          automatically on release day.
        </p>
      </section>

      <section aria-labelledby="h-files" className="space-y-3">
        <h2 id="h-files" className="text-lg font-semibold">
          Ready-made files
        </h2>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {meta.downloads.map((d) => (
            <li key={d.file} className="card flex flex-col gap-2 p-4">
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-medium">{d.label}</h3>
                <span className="shrink-0 rounded-full bg-surface-2 px-2 py-0.5 text-xs text-muted">{bytes(d.bytes)}</span>
              </div>
              <p className="flex-1 text-sm text-muted">{d.description}</p>
              <div className="flex flex-wrap gap-3 text-sm">
                <a className="font-medium text-accent hover:underline" href={`/data/${d.url}`} download>
                  Download {d.file.split(".").slice(1).join(".")}
                </a>
                {d.release_url && (
                  <a className="text-muted hover:underline" href={d.release_url}>
                    Versioned copy ({meta.data_release_tag})
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="h-explore" className="card space-y-4 p-5 sm:p-6">
        <div>
          <h2 id="h-explore" className="text-lg font-semibold">
            Explore and export a slice
          </h2>
          <p className="text-sm text-muted">
            Pick a WASDE table and filter it; the data loads in your browser and exports exactly what you see.
          </p>
        </div>
        <Explorer catalog={catalog} defaultTable="us_feed_grains_corn" />
      </section>
    </div>
  );
}
