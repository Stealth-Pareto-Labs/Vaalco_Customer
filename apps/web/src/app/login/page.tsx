"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Anchor, AlertTriangle } from "lucide-react";
import { api, ApiError, getToken, setToken } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import LangToggle from "@/components/LangToggle";

export default function LoginPage() {
  const router = useRouter();
  const { t } = useI18n();
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (getToken()) {
      router.replace("/");
    } else {
      setChecked(true);
    }
  }, [router]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (loading || code.trim().length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.login(code.trim());
      setToken(res.token);
      router.replace("/");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError(t("login.error"));
      } else {
        setError(t("login.error"));
      }
      setLoading(false);
    }
  };

  if (!checked) {
    return <div className="min-h-screen bg-bg" aria-hidden="true" />;
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center bg-bg px-4 py-10">
      <div
        className="pointer-events-none absolute inset-0 opacity-60"
        style={{
          background:
            "radial-gradient(60% 55% at 50% 0%, rgba(30,64,175,0.18), transparent 70%)"
        }}
        aria-hidden="true"
      />

      <div className="absolute right-4 top-4">
        <LangToggle />
      </div>

      <div className="relative w-full max-w-sm">
        <div className="rounded-2xl border border-line bg-surface p-6 shadow-2xl sm:p-8">
          <div className="mb-6 flex flex-col items-center text-center">
            <div
              className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-line2"
              style={{
                background:
                  "linear-gradient(140deg, var(--navy), var(--primary-strong))"
              }}
              aria-hidden="true"
            >
              <Anchor size={26} className="text-white" />
            </div>
            <h1 className="text-[20px] font-semibold text-ink">
              {t("login.title")}
            </h1>
            <p className="mt-1 text-[14px] text-mut">{t("login.subtitle")}</p>
          </div>

          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="access-code"
                className="text-[13px] font-medium text-mut"
              >
                {t("login.codeLabel")}
              </label>
              <input
                id="access-code"
                type="password"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder={t("login.codePlaceholder")}
                autoComplete="off"
                autoFocus
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? "login-error" : undefined}
                className="focus-ring rounded-lg border border-line bg-surface2 px-3.5 py-2.5 text-[15px] text-ink placeholder:text-mut2 focus:border-line2"
              />
            </div>

            {error && (
              <p
                id="login-error"
                role="alert"
                className="flex items-center gap-2 text-[14px]"
                style={{ color: "var(--hi)" }}
              >
                <AlertTriangle size={15} aria-hidden="true" />
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading || code.trim().length === 0}
              className="focus-ring mt-1 flex cursor-pointer items-center justify-center rounded-lg bg-primary px-4 py-2.5 text-[15px] font-semibold text-white transition-colors duration-150 hover:bg-primary-strong disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? t("login.loading") : t("login.submit")}
            </button>
          </form>
        </div>

        <p className="mt-5 text-center text-[12px] text-mut2">
          {t("login.footer")}
        </p>
      </div>
    </main>
  );
}
