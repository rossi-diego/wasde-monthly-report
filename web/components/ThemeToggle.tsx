"use client";

import { useState } from "react";

type Mode = "system" | "light" | "dark";
const KEY = "wasde-theme";

function apply(mode: Mode) {
  const el = document.documentElement;
  if (mode === "system") el.removeAttribute("data-theme");
  else el.setAttribute("data-theme", mode);
}

/** Runs before paint (inlined in <head>) so there is no theme flash. */
export const themeBootScript = `try{var m=localStorage.getItem("${KEY}");if(m==="light"||m==="dark")document.documentElement.setAttribute("data-theme",m)}catch(e){}`;

export default function ThemeToggle() {
  const [mode, setMode] = useState<Mode>(() => {
    if (typeof window === "undefined") return "system";
    try {
      const m = localStorage.getItem(KEY);
      return m === "light" || m === "dark" ? m : "system";
    } catch {
      return "system"; // storage unavailable
    }
  });

  const next = () => {
    const order: Mode[] = ["system", "light", "dark"];
    const m = order[(order.indexOf(mode) + 1) % order.length];
    setMode(m);
    apply(m);
    try {
      if (m === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, m);
    } catch {
      /* ignore */
    }
  };

  const icon = mode === "dark" ? "☾" : mode === "light" ? "☀" : "◐";
  return (
    <button
      type="button"
      onClick={next}
      className="h-8 w-8 rounded-full border border-line text-ink-2 hover:bg-surface-2"
      aria-label={`Theme: ${mode}. Click to change.`}
      title={`Theme: ${mode}`}
    >
      <span aria-hidden suppressHydrationWarning>
        {icon}
      </span>
    </button>
  );
}
