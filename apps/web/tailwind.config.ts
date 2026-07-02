import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        surface2: "var(--surface2)",
        line: "var(--line)",
        line2: "var(--line2)",
        ink: "var(--ink)",
        mut: "var(--mut)",
        mut2: "var(--mut2)",
        primary: "var(--primary)",
        "primary-strong": "var(--primary-strong)",
        navy: "var(--navy)",
        accent: "var(--accent)",
        orange: "var(--orange)",
        hi: "var(--hi)",
        med: "var(--med)",
        lo: "var(--lo)"
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"]
      }
    }
  },
  plugins: []
};

export default config;
