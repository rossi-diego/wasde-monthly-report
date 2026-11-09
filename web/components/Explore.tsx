"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import { Chevron } from "@/components/charts/common";
import { T } from "@/components/chrome/I18n";
import type { Series } from "@/lib/types";

function Loading() {
  return (
    <p className="py-8 text-center text-sm text-muted">
      <T k="explore.loading" />
    </p>
  );
}

// ECharts is only downloaded when a reader opens the Explore section.
const RevisionChart = dynamic(() => import("@/components/RevisionChart"), {
  ssr: false,
  loading: () => <Loading />,
});

export default function Explore({ series }: { series: Series }) {
  const [open, setOpen] = useState(false);
  return (
    <details className="card group p-5" onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary className="flex min-h-11 items-center justify-between gap-3 text-[15px] font-semibold">
        <T k="explore.title" />
        {/* Visible affordance: a flex summary has no native disclosure triangle. */}
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-line text-link group-hover:bg-nav-active">
          <Chevron size={16} />
        </span>
      </summary>
      {open && (
        <div className="pt-3">
          <RevisionChart series={series} />
        </div>
      )}
    </details>
  );
}
