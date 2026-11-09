"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import { T } from "@/components/chrome/I18n";
import type { Series } from "@/lib/types";

// ECharts is only downloaded when a reader opens the Explore section.
const RevisionChart = dynamic(() => import("@/components/RevisionChart"), {
  ssr: false,
  loading: () => <p className="py-8 text-center text-sm text-muted">Loading the interactive chart…</p>,
});

export default function Explore({ series }: { series: Series }) {
  const [open, setOpen] = useState(false);
  return (
    <details className="card p-5" onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary className="flex min-h-11 items-center text-[15px] font-semibold">
        <T k="explore.title" />
      </summary>
      {open && (
        <div className="pt-3">
          <RevisionChart series={series} />
        </div>
      )}
    </details>
  );
}
