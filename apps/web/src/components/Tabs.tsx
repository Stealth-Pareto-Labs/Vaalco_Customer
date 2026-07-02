"use client";

import type { ReactNode } from "react";
import { MessageSquare, Activity } from "lucide-react";
import { useI18n } from "@/lib/i18n";

export type TabKey = "ask" | "signals";

interface TabsProps {
  active: TabKey;
  onChange: (tab: TabKey) => void;
  highCount: number;
}

export default function Tabs({ active, onChange, highCount }: TabsProps) {
  const { t } = useI18n();

  const tabs: { key: TabKey; label: string; icon: ReactNode }[] = [
    { key: "signals", label: t("tab.signals"), icon: <Activity size={16} /> },
    { key: "ask", label: t("tab.ask"), icon: <MessageSquare size={16} /> }
  ];

  return (
    <div
      className="flex items-center gap-1 border-b border-line"
      role="tablist"
      aria-label="Views"
    >
      {tabs.map((tab) => {
        const isActive = active === tab.key;
        const showBadge = tab.key === "signals" && highCount > 0;
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.key)}
            className={`focus-ring relative -mb-px flex cursor-pointer items-center gap-2 border-b-2 px-4 py-3 text-[15px] font-medium transition-colors duration-150 ${
              isActive
                ? "border-primary text-ink"
                : "border-transparent text-mut hover:text-ink"
            }`}
          >
            <span
              aria-hidden="true"
              className={isActive ? "text-primary" : "text-mut"}
            >
              {tab.icon}
            </span>
            {tab.label}
            {showBadge && (
              <span
                className="mono tnum ml-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[11px] font-semibold text-white"
                style={{ background: "var(--hi)" }}
                aria-label={`${highCount} high priority`}
              >
                {highCount}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
