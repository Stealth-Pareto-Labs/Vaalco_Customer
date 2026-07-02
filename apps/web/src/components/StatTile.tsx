"use client";

import type { Priority } from "@/lib/types";

interface StatTileProps {
  label: string;
  value: number;
  severity: Priority;
}

const severityStyles: Record<
  Priority,
  { color: string; bg: string; border: string }
> = {
  high: { color: "var(--hi)", bg: "var(--hi-bg)", border: "var(--hi)" },
  medium: { color: "var(--med)", bg: "var(--med-bg)", border: "var(--med)" },
  low: { color: "var(--lo)", bg: "var(--lo-bg)", border: "var(--lo)" }
};

export default function StatTile({ label, value, severity }: StatTileProps) {
  const s = severityStyles[severity];
  return (
    <div
      className="relative flex flex-col justify-between overflow-hidden rounded-xl border border-line bg-surface p-4"
      style={{ minHeight: 108 }}
    >
      <span
        className="absolute inset-y-0 left-0 w-1"
        style={{ background: s.color }}
        aria-hidden="true"
      />
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium uppercase tracking-wide text-mut">
          {label}
        </span>
        <span
          className="inline-block h-2.5 w-2.5 rounded-full"
          style={{ background: s.color }}
          aria-hidden="true"
        />
      </div>
      <div
        className="mono tnum mt-2 text-4xl font-semibold leading-none"
        style={{ color: s.color }}
      >
        {value}
      </div>
    </div>
  );
}
