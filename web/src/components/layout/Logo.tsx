/** Условный знак архива (демонстрационный, не официальная символика учреждения). */
export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true" focusable="false">
      <rect width="48" height="48" rx="10" fill="rgb(var(--c-primary))" />
      <path d="M8 18 24 9l16 9v3H8z" fill="rgb(var(--c-primary-ink))" />
      <path d="M11 23h4v13h-4zM19 23h4v13h-4zM27 23h4v13h-4zM35 23h2v13h-2z" fill="rgb(var(--c-primary-ink))" opacity=".9" />
      <path d="M8 38h32v3H8z" fill="rgb(var(--c-accent))" />
    </svg>
  );
}
