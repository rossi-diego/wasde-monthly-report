"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { LANG_KEY, translate, type Key, type Lang, type Vars } from "@/lib/i18n";

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

/** Translated text, usable from server components. */
export function T({ k, v }: { k: Key; v?: Vars }) {
  const t = useT();
  return <>{t(k, v)}</>;
}
