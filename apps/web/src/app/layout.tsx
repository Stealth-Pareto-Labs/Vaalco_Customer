import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Fira_Sans, Fira_Code } from "next/font/google";
import "./globals.css";
import { I18nProvider } from "@/lib/i18n";
import { ToastProvider } from "@/components/Toast";

const firaSans = Fira_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap"
});

const firaCode = Fira_Code({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap"
});

export const metadata: Metadata = {
  title: "Navigator Z — Vessel Intelligence",
  description:
    "Fuel Intelligence dashboard for VAALCO Energy — fuel, DP efficiency, maintenance and HSE signals for the Navigator Z.",
  robots: { index: false, follow: false }
};

export const viewport: Viewport = {
  themeColor: "#0b0e10",
  width: "device-width",
  initialScale: 1
};

export default function RootLayout({
  children
}: {
  children: ReactNode;
}) {
  return (
    <html lang="en" className={`${firaSans.variable} ${firaCode.variable}`}>
      <body>
        <I18nProvider>
          <ToastProvider>{children}</ToastProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
