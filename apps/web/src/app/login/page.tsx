"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { api, ApiError, getToken, setToken } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import LangToggle from "@/components/LangToggle";
import VesselHero from "@/components/VesselHero";

export default function LoginPage() {
  const router = useRouter();
  const { t } = useI18n();
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (getToken()) router.replace("/");
    else setChecked(true);
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
      // Distinguish a wrong code (401) from a connectivity/server problem.
      if (err instanceof ApiError && err.status === 401) {
        setError(t("login.error"));
      } else {
        setError(t("login.errorNetwork"));
      }
      setLoading(false);
    }
  };

  if (!checked) return <div className="min-h-dvh bg-bg" aria-hidden="true" />;

  return (
    <main className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-bg px-4 py-10">
      {/* cinematic offshore backdrop */}
      <VesselHero />

      {/* ambient depth blobs */}
      <div
        className="float-slow pointer-events-none absolute -left-24 top-1/4 h-72 w-72 rounded-full opacity-30 blur-3xl"
        style={{ background: "radial-gradient(circle, rgba(59,130,246,0.5), transparent 70%)" }}
        aria-hidden="true"
      />
      <div
        className="float-slower pointer-events-none absolute -right-20 bottom-16 h-72 w-72 rounded-full opacity-25 blur-3xl"
        style={{ background: "radial-gradient(circle, rgba(232,86,63,0.45), transparent 70%)" }}
        aria-hidden="true"
      />

      <div className="absolute right-4 top-4 z-10">
        <LangToggle />
      </div>

      <div className="relative z-10 w-full max-w-[400px]">
        {/* brand logo */}
        <div className="mb-7 flex justify-center">
          <Image
            src="/vaalco-logo-light.png"
            alt="VAALCO Energy"
            width={188}
            height={145}
            priority
            className="h-auto w-[168px] drop-shadow-[0_8px_24px_rgba(0,0,0,0.55)]"
          />
        </div>

        {/* glass card */}
        <div className="glass hairline-top rounded-2xl p-6 shadow-2xl sm:p-8">
          <div className="mb-6 text-center">
            <h1 className="text-[21px] font-semibold text-ink">{t("login.title")}</h1>
            <p className="mt-1.5 text-[13.5px] text-mut">{t("login.subtitle")}</p>
          </div>

          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="access-code" className="text-[13px] font-medium text-mut">
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
                className="focus-ring rounded-lg border border-line bg-black/25 px-3.5 py-2.5 text-[15px] text-ink placeholder:text-mut2 focus:border-primary"
              />
            </div>

            {error && (
              <p
                id="login-error"
                role="alert"
                className="flex items-center gap-2 text-[13.5px]"
                style={{ color: "var(--hi)" }}
              >
                <AlertTriangle size={15} aria-hidden="true" />
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading || code.trim().length === 0}
              className="glow-primary focus-ring mt-1 flex cursor-pointer items-center justify-center rounded-lg bg-primary px-4 py-2.5 text-[15px] font-semibold text-white transition-all duration-150 hover:bg-primary-strong disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none"
            >
              {loading ? t("login.loading") : t("login.submit")}
            </button>
          </form>

          <div className="mt-5 flex items-center justify-center gap-1.5 text-[12px] text-mut2">
            <ShieldCheck size={13} aria-hidden="true" />
            {t("login.footer")}
          </div>
        </div>
      </div>
    </main>
  );
}
