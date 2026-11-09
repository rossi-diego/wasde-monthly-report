"use client";

import { T, useT } from "@/components/chrome/I18n";
import { UPCOMING } from "@/lib/reports";

// Deterministic decorative bars (no data): the placeholder shows the layout, never numbers.
const ghost = (seed: number) =>
  Array.from({ length: 12 }, (_, i) => {
    const h = 14 + ((i * 37 + seed * 11) % 40);
    return { x: 4 + i * 18, y: 58 - h, h };
  });

export default function Upcoming({ headingLevel = 2 }: { headingLevel?: 2 | 3 }) {
  const t = useT();
  const H = `h${headingLevel}` as "h2" | "h3";
  return (
    <section aria-labelledby="h-upcoming" className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-baseline gap-2.5">
        <H id="h-upcoming" className="m-0 text-[17px] font-bold">
          <T k="up.title" />
        </H>
        <span className="text-xs text-muted">
          <T k="up.note" />
        </span>
      </div>
      <div className="grid-fit-240">
        {UPCOMING.map((u, i) => (
          <article
            key={u.id}
            id={`report-${u.id}`}
            className="box-border flex min-h-[180px] flex-col gap-2 rounded-2xl border border-dashed bg-card p-[18px]"
            style={{ borderColor: u.color }}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-bold uppercase tracking-[0.04em]" style={{ color: u.color }}>
                {t(u.name)}
              </span>
              <span className="text-[11px] text-muted">{t(u.cadenceDetail)}</span>
            </div>
            {u.insight && <div className="font-semibold">{t(u.insight)}</div>}
            <svg aria-hidden="true" viewBox="0 0 220 60" preserveAspectRatio="none" className="h-[60px] w-full">
              {ghost(i + 1).map((g) => (
                <rect key={g.x} x={g.x} y={g.y} width={14} height={g.h} rx={3} style={{ fill: "var(--grid)" }} />
              ))}
            </svg>
            {u.arrives && <div className="mt-auto text-xs text-muted">{t(u.arrives)}</div>}
          </article>
        ))}
      </div>
    </section>
  );
}
