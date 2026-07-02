"use client";

import { useState } from "react";
import Image from "next/image";
import { LogOut, Settings } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import LangToggle from "@/components/LangToggle";
import SettingsModal from "@/components/SettingsModal";

interface HeaderProps {
  days: number;
  connected: boolean;
  onLogout: () => void;
}

export default function Header({ days, connected, onLogout }: HeaderProps) {
  const { t } = useI18n();
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-3 px-4 py-3 sm:px-6">
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <div
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-line2 bg-surface2"
            aria-hidden="true"
          >
            <Image
              src="/vaalco-mark.png"
              alt="VAALCO"
              width={60}
              height={30}
              className="h-auto w-[30px]"
            />
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
            onClick={() => setSettingsOpen(true)}
            aria-label={t("header.settings")}
            title={t("header.settings")}
            className="focus-ring flex cursor-pointer items-center justify-center rounded-lg border border-line bg-surface2 p-1.5 text-mut transition-colors duration-150 hover:border-line2 hover:text-ink"
          >
            <Settings size={15} aria-hidden="true" />
          </button>
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
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
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
