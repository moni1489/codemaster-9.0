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
        sans: ["'Golos Text Variable'", "system-ui", "sans-serif"],
        serif: ["'Golos Text Variable'", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "Consolas", "monospace"],
      },
      // пожилые читатели: самый мелкий текст на сайте не меньше 16px (корень 18px)
      fontSize: {
        xs: ["0.875rem", { lineHeight: "1.4" }],
        sm: ["0.9375rem", { lineHeight: "1.5" }],
      },
      maxWidth: { content: "76rem" },
      minHeight: { 12: "3rem" },
      minWidth: { 12: "3rem" },
    },
  },
  plugins: [],
} satisfies Config;
