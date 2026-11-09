import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import { I18nProvider, T } from "@/components/chrome/I18n";
import Sidebar from "@/components/chrome/Sidebar";
import { themeBootScript } from "@/components/chrome/ThemeToggle";
import { getMeta, getReportsMeta } from "@/lib/data";

import "./globals.css";

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex-sans",
  display: "swap",
});
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "USDA Reports Dashboard",
  description:
    "Five USDA reports (WASDE, Export Sales, NASS crush, Crop Progress, Grain Stocks), harmonized point-in-time since 2010 and updated automatically on release day, in English and Portuguese.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const meta = getMeta();
  const reports = getReportsMeta();
  return (
    <html lang="en" suppressHydrationWarning className={`${plexSans.variable} ${plexMono.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body>
        <I18nProvider>
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2"
          >
            <T k="skip" />
          </a>
          <div className="flex min-h-screen flex-wrap">
            <Sidebar
              reports={meta.history.reports}
              rows={meta.history.rows}
              esrReleases={reports.export_sales?.releases ?? null}
              crushReleases={reports.oilseed_crush?.releases ?? null}
              cpReleases={reports.crop_progress?.releases ?? null}
              gsReleases={reports.grain_stocks?.releases ?? null}
            />
            <main
              id="main"
              className="box-border flex min-w-0 flex-[999_1_560px] flex-col gap-5 px-4 pb-10 pt-6 sm:px-7"
            >
              {children}
              <footer className="mt-auto flex flex-wrap gap-x-5 gap-y-2 pt-4 text-xs text-muted">
                <span>
                  <T k="footer.built" /> ·{" "}
                  <a className="inline-flex min-h-11 items-center underline" href="https://github.com/rossi-diego/usda-reports-dashboard">
                    <T k="footer.code" />
                  </a>
                </span>
                <span className="inline-flex items-center">
                  <T k="footer.source" />
                </span>
                <span className="inline-flex items-center">
                  <T
                    k="footer.data"
                    v={{
                      ...(meta.data_release_tag ? { tag: meta.data_release_tag } : {}),
                      at: new Date(meta.generated_at).toISOString().slice(0, 16).replace("T", " "),
                    }}
                    keys={meta.data_release_tag ? undefined : { tag: "footer.local" }}
                  />
                </span>
              </footer>
            </main>
          </div>
        </I18nProvider>
      </body>
    </html>
  );
}
