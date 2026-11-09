"use client";

import { useLang, useT } from "@/components/chrome/I18n";
import { LANGS } from "@/lib/i18n";

export default function LangToggle() {
  const { lang, setLang } = useLang();
  const t = useT();
  return (
    <div role="group" aria-label={t("lang.label")} className="flex shrink-0 items-center rounded-full border border-line bg-card p-0.5">
      {LANGS.map((l) => (
        <button
          key={l}
          type="button"
          lang={l === "pt" ? "pt-BR" : "en"}
          aria-pressed={lang === l}
          aria-label={l === "pt" ? "Português" : "English"}
          onClick={() => setLang(l)}
          className={`h-10 min-w-11 cursor-pointer rounded-full px-2.5 text-[13px] font-semibold ${
            lang === l ? "bg-[var(--pill-active)] text-white" : "text-ink"
          }`}
        >
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
