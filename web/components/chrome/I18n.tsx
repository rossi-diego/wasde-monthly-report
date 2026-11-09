"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { monthYear, shortDate } from "@/lib/format";
import { LANG_KEY, translate, type Key, type Lang, type Vars } from "@/lib/i18n";
import { commodityName } from "@/lib/labels";

type Ctx = { lang: Lang; setLang: (l: Lang) => void };
const LangContext = createContext<Ctx>({ lang: "en", setLang: () => {} });

/** Server and first client render are EN; a stored PT choice is applied after hydration. */
export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(LANG_KEY);
    } catch {
      /* storage unavailable (private mode, blocked site data) */
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time sync from storage after hydration
    if (stored === "pt") setLangState("pt");
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang === "pt" ? "pt-BR" : "en";
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(LANG_KEY, l);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(() => ({ lang, setLang }), [lang, setLang]);
  return <LangContext.Provider value={value}>{children}</LangContext.Provider>;
}

export const useLang = () => useContext(LangContext);

export function useT() {
  const { lang } = useLang();
  return useCallback((key: Key, vars?: Vars) => translate(lang, key, vars), [lang]);
}

/** Translated text, usable from server components. `months` are "YYYY-MM" values that are
 *  formatted as "October 2026" / "outubro de 2026" in the active language. */
export function T({ k, v, months }: { k: Key; v?: Vars; months?: Record<string, string | null | undefined> }) {
  const { lang } = useLang();
  const vars: Vars = { ...v };
  for (const [name, m] of Object.entries(months ?? {})) vars[name] = monthYear(m, lang);
  return <>{translate(lang, k, v || months ? vars : undefined)}</>;
}

/** "2026-10" -> "October 2026" / "outubro de 2026", usable from server components. */
export function MonthYear({ m }: { m: string | null | undefined }) {
  const { lang } = useLang();
  return <>{monthYear(m, lang)}</>;
}

/** "2026-10-09" -> "Oct 9, 2026" / "9 out 2026", usable from server components. */
export function DateText({ iso, withYear = true }: { iso: string | null | undefined; withYear?: boolean }) {
  const { lang } = useLang();
  return <>{shortDate(iso, withYear, lang) ?? "—"}</>;
}

/** Commodity name in the active language (the JSON label is the EN fallback). */
export function CommodityName({ id, fallback }: { id: string; fallback: string }) {
  const { lang } = useLang();
  return <>{commodityName(id, lang, fallback)}</>;
}
