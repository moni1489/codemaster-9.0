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
        sans: ["'Libre Franklin Variable'", "system-ui", "sans-serif"],
        serif: ["'Source Serif 4 Variable'", "Georgia", "serif"],
        mono: ["'JetBrains Mono'", "Consolas", "monospace"],
      },
      maxWidth: { content: "80rem" },
      minHeight: { 12: "3rem" },
      minWidth: { 12: "3rem" },
    },
  },
  plugins: [],
} satisfies Config;
