import type { Config } from "tailwindcss";

const v = (name: string) => `rgb(var(--c-${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: v("bg"),
        surface: v("surface"),
        "surface-2": v("surface-2"),
        line: v("line"),
        ink: v("ink"),
        muted: v("muted"),
        primary: v("primary"),
        "primary-ink": v("primary-ink"),
        accent: v("accent"),
        danger: v("danger"),
        ok: v("ok"),
        warn: v("warn"),
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "Roboto", "Arial", "sans-serif"],
        serif: ["'PT Serif'", "Georgia", "'Times New Roman'", "serif"],
        mono: ["'JetBrains Mono'", "Consolas", "monospace"],
      },
      maxWidth: { content: "76rem" },
    },
  },
  plugins: [],
} satisfies Config;
