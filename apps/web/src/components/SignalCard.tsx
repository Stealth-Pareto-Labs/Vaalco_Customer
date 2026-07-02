"use client";

import { MessageSquare } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import type { Priority, Signal } from "@/lib/types";

interface SignalCardProps {
  signal: Signal;
  onProbe: (probe: string) => void;
}

const priorityStyle: Record<
  Priority,
  { color: string; bg: string; labelKey: string }
> = {
  high: { color: "var(--hi)", bg: "var(--hi-bg)", labelKey: "signals.high" },
  medium: {
    color: "var(--med)",
    bg: "var(--med-bg)",
    labelKey: "signals.medium"
  },
  low: { color: "var(--lo)", bg: "var(--lo-bg)", labelKey: "signals.low" }
};

const priorityWord: Record<Priority, { en: string; fr: string }> = {
  high: { en: "HIGH", fr: "HAUTE" },
  medium: { en: "MEDIUM", fr: "MOYENNE" },
  low: { en: "LOW", fr: "BASSE" }
};

export default function SignalCard({ signal, onProbe }: SignalCardProps) {
  const { t, locale } = useI18n();
  const ps = priorityStyle[signal.priority];
  const explanation = signal.explanation ?? signal.summary ?? "";

  return (
    <article
      className="overflow-hidden rounded-xl border border-line bg-surface"
      style={{ borderLeft: `3px solid ${ps.color}` }}
    >
      <div className="p-4 sm:p-5">
        <div className="mb-2 flex items-start justify-between gap-3">
          <span
            className="mono inline-flex shrink-0 items-center rounded-md px-2 py-0.5 text-[11px] font-semibold tracking-wide"
            style={{ color: ps.color, background: ps.bg }}
          >
            {priorityWord[signal.priority][locale]}
          </span>
          {signal.category && (
            <span className="truncate text-right text-[12px] font-medium uppercase tracking-wide text-mut">
              {signal.category}
            </span>
          )}
        </div>

        <h3 className="text-[16px] font-semibold leading-snug text-ink">
          {signal.title}
        </h3>

        {explanation && (
          <p className="mt-2 whitespace-pre-wrap text-[15px] leading-relaxed text-mut">
            {explanation}
          </p>
        )}

        {signal.evidence && signal.evidence.length > 0 && (
          <div className="mt-4 rounded-lg border border-line bg-surface2 p-3">
            <h4 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-mut2">
              {t("signals.evidence")}
            </h4>
            <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
              {signal.evidence.map((ev, i) => (
                <div
                  key={i}
                  className="flex items-baseline justify-between gap-3 border-b border-line/60 pb-1 last:border-0"
                >
                  <dt className="text-[13px] text-mut">{ev.label}</dt>
                  <dd className="mono tnum shrink-0 text-[13px] font-medium text-ink">
                    {ev.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {signal.next_steps && signal.next_steps.length > 0 && (
          <div className="mt-4">
            <h4 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-mut2">
              {t("signals.nextSteps")}
            </h4>
            <ul className="space-y-1.5">
              {signal.next_steps.map((step, i) => (
                <li
                  key={i}
                  className="flex gap-2.5 text-[15px] leading-relaxed text-ink"
                >
                  <span
                    className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full"
                    style={{ background: ps.color }}
                    aria-hidden="true"
                  />
                  <span>{step}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {signal.probe && (
          <div className="mt-4">
            <button
              type="button"
              onClick={() => onProbe(signal.probe as string)}
              className="focus-ring inline-flex cursor-pointer items-center gap-2 rounded-lg border border-line2 bg-surface2 px-3 py-2 text-[14px] font-medium text-ink transition-colors duration-150 hover:border-primary hover:text-primary"
            >
              <MessageSquare size={15} aria-hidden="true" />
              {t("signals.askAbout")}
            </button>
          </div>
        )}
      </div>
    </article>
  );
}
