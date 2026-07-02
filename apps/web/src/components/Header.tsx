"use client";

import { Ship, LogOut } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import LangToggle from "@/components/LangToggle";

interface HeaderProps {
  days: number;
  connected: boolean;
  onLogout: () => void;
}

export default function Header({ days, connected, onLogout }: HeaderProps) {
  const { t } = useI18n();

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-3 px-4 py-3 sm:px-6">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <div
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-line2"
            style={{
              background:
                "linear-gradient(140deg, var(--navy), var(--primary-strong))"
            }}
            aria-hidden="true"
          >
            <Ship size={22} className="text-white" />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-[17px] font-semibold leading-tight text-ink">
              {t("app.title")}
            </h1>
            <p className="truncate text-[13px] text-mut">{t("app.subtitle")}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <StatusPill days={days} connected={connected} />
          <LangToggle />
          <button
            type="button"
            onClick={onLogout}
            className="focus-ring flex cursor-pointer items-center gap-1.5 rounded-lg border border-line bg-surface2 px-2.5 py-1.5 text-[13px] font-medium text-mut transition-colors duration-150 hover:border-line2 hover:text-ink"
          >
            <LogOut size={15} aria-hidden="true" />
            <span className="hidden sm:inline">{t("header.logout")}</span>
          </button>
        </div>
      </div>
    </header>
  );
}

function StatusPill({ days, connected }: { days: number; connected: boolean }) {
  const { t } = useI18n();
  return (
    <div
      className="flex items-center gap-2 rounded-full border border-line bg-surface2 px-3 py-1.5"
      role="status"
    >
      <span
        className={`inline-block h-2 w-2 shrink-0 rounded-full ${
          connected ? "pulse-dot" : ""
        }`}
        style={{ background: connected ? "var(--lo)" : "var(--hi)" }}
        aria-hidden="true"
      />
      <span className="whitespace-nowrap text-[13px] font-medium text-ink">
        {connected ? (
          <>
            <span className="mono tnum">{days}</span>{" "}
            <span className="text-mut">{t("status.reportsLoaded")}</span>
          </>
        ) : (
          <span className="text-mut">{t("status.disconnected")}</span>
        )}
      </span>
    </div>
  );
}
