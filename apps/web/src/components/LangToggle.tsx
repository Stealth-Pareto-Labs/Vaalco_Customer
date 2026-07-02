"use client";

import { Globe } from "lucide-react";
import { useI18n, type Locale } from "@/lib/i18n";

export default function LangToggle() {
  const { locale, setLocale } = useI18n();

  const options: Locale[] = ["en", "fr"];

  return (
    <div
      className="flex items-center gap-1 rounded-lg border border-line bg-surface2 p-0.5"
      role="group"
      aria-label="Language"
    >
      <Globe size={15} className="ml-1.5 mr-0.5 text-mut" aria-hidden="true" />
      {options.map((opt) => {
        const active = locale === opt;
        return (
          <button
            key={opt}
            type="button"
            onClick={() => setLocale(opt)}
            aria-pressed={active}
            className={`focus-ring cursor-pointer rounded-md px-2 py-1 text-[13px] font-medium uppercase tracking-wide transition-colors duration-150 ${
              active
                ? "bg-primary text-white"
                : "text-mut hover:text-ink"
            }`}
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}
