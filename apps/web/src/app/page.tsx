"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, clearToken, getToken } from "@/lib/api";
import Header from "@/components/Header";
import Tabs, { type TabKey } from "@/components/Tabs";
import Ask, { type AskHandle } from "@/components/Ask";
import Signals from "@/components/Signals";

export default function DashboardPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [tab, setTab] = useState<TabKey>("ask");
  const [days, setDays] = useState(0);
  const [connected, setConnected] = useState(true);
  const [highCount, setHighCount] = useState(0);
  const askRef = useRef<AskHandle>(null);

  // Auth guard
  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
    } else {
      setReady(true);
    }
  }, [router]);

  // Poll status every 15s
  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    const controllerRef: { current: AbortController | null } = { current: null };

    const poll = async () => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      try {
        const status = await api.status(controller.signal);
        if (!cancelled) {
          setDays(status.days ?? 0);
          setConnected(true);
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        if (!cancelled) setConnected(false);
      }
    };

    void poll();
    const interval = setInterval(() => void poll(), 15000);

    return () => {
      cancelled = true;
      clearInterval(interval);
      controllerRef.current?.abort();
    };
  }, [ready]);

  const handleLogout = useCallback(() => {
    clearToken();
    router.replace("/login");
  }, [router]);

  const handleProbe = useCallback((probe: string) => {
    setTab("ask");
    // Allow the Ask panel to become visible before sending.
    setTimeout(() => {
      askRef.current?.sendProbe(probe);
    }, 60);
  }, []);

  if (!ready) {
    return <div className="min-h-screen bg-bg" aria-hidden="true" />;
  }

  return (
    <div className="min-h-screen bg-bg">
      <Header days={days} connected={connected} onLogout={handleLogout} />

      <main className="mx-auto max-w-6xl px-4 sm:px-6">
        <Tabs active={tab} onChange={setTab} highCount={highCount} />

        {/* Ask stays mounted to preserve the conversation thread. */}
        <div
          role="tabpanel"
          hidden={tab !== "ask"}
          aria-hidden={tab !== "ask"}
        >
          <Ask ref={askRef} />
        </div>

        <div
          role="tabpanel"
          hidden={tab !== "signals"}
          aria-hidden={tab !== "signals"}
        >
          <Signals
            active={tab === "signals"}
            onProbe={handleProbe}
            onHighCount={setHighCount}
          />
        </div>
      </main>
    </div>
  );
}
