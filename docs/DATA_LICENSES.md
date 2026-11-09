# Data licences and sources

What this project ingests, under which terms, and what it deliberately does **not** ingest.

## Ingested (all US Government works, public domain)

Works of the U.S. federal government are not subject to copyright in the United States
(17 U.S.C. § 105). Each published file names the agency to cite (`licence` in
`config/reports.yaml`, `datapackage.json` → `licenses`).

| Report | Agency | Access | Key | Cite as |
|---|---|---|---|---|
| WASDE | USDA OCE / WAOB | `www.usda.gov` CSV (2021+), ESMIS XML (2010-07 → 2020) | none | USDA OCE/WAOB, *World Agricultural Supply and Demand Estimates* |
| Export Sales (ESR) | USDA FAS | `api.fas.usda.gov` (api.data.gov key, `FAS_API_KEY` / `USDA_PSD_KEY`) | yes (free) | USDA FAS, Export Sales Reporting Program |
| Fats & Oils: Oilseed Crushings, Production, Consumption and Stocks | USDA NASS | ESMIS `findByIdentifier/FatsOils` → release zip from `files[]` → `cafo_all_tables.csv` | none | USDA NASS, *Fats and Oils: Oilseed Crushings, Production, Consumption and Stocks* |
| Crop Progress | USDA NASS | ESMIS `findByIdentifier/CropProg` → release zip from `files[]` → `prog_all_tables.csv` | none | USDA NASS, *Crop Progress* |
| Grain Stocks | USDA NASS | ESMIS `findByIdentifier/GraiStoc` → release zip from `files[]` → `grst_all_tables.csv` (table 1) | none | USDA NASS, *Grain Stocks* |

Notes on the NASS files (spike of 2026-11-09):

* ESMIS (Cornell University / USDA National Agricultural Library) lists 134 FatsOils releases,
  2015-10-01 → 2026-11-02; 133 carry a zip. The exception (2019-01-02) is a reschedule notice.
  History used here therefore starts with the **2015-10-01** release ("2015-10+").
* CropProg: 1,116 releases (1995-04-03 → 2026-11-02), zips from 2001-05-14 but the
  `prog_all_tables.csv` layout only from 2010-05-24; history used here starts with the
  **2010-06-07** release (the 2010-05-24 file is a one-off layout). National ("<N> States")
  rows only.
* GraiStoc: 221 releases back to 1973-10-24, zips on 105 of them from 2001-06-29, the
  `grst_all_tables.csv` layout from **2010-06-30**, where the history used here starts.
* No NASS API key is used. The NASS Quick Stats API (which would reach further back) is a v2
  item; if it is ever used, the README and the site footer must carry NASS's required notice
  ("This product uses the NASS API but is not endorsed or certified by NASS").
* Values are redistributed exactly as printed (short tons, 1,000 lb), plus derived columns
  (bushels at 33.3333 bu per short ton, yields) that are documented in the dbt schema.

## Not ingested: NOPA

The National Oilseed Processors Association (NOPA) is a private, members-only trade
association, not part of USDA. Its monthly crush report is proprietary.

**Policy.** NOPA data is never ingested, displayed or redistributed by this project. The public
crush page carries only this note and an outbound link to <https://www.nopa.org/>:

> NOPA members represent roughly 95% of US soybean crush and publish about two weeks earlier;
> NOPA data is proprietary and not redistributed here. This site uses the public-domain NASS
> Fats & Oils series, which covers all reporting facilities.

**Distribution and pricing evidence** (kept here only, never on the public page):

| Item | Evidence | Access date |
|---|---|---|
| Distributor | nopa.org names Refinitiv / LSEG as the distributor of the NOPA monthly crush data | 2026-11-08 (project plan source review) |
| Price | about US$1,200 per year (subscription via the distributor) as of 2026-11 | 2026-11-08 (same source review) |
| Page | <https://www.nopa.org/resources/nopa-monthly-crush-report/> answered HTTP 200 on 2026-11-09; its body is rendered client-side, so the distributor and price lines were not re-read by a script on that date | 2026-11-09 |

If the distributor, price or terms change, update this table with the new access date; the
public page never changes because it carries no NOPA numbers.
