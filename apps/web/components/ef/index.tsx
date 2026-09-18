import { cn } from "@/lib/utils";

/* ---------- Panel:直角面板,可选切角与区段头 ---------- */
export function Panel({
  title,
  en,
  action,
  className,
  cut,
  children,
}: {
  title?: string;
  en?: string;
  action?: React.ReactNode;
  className?: string;
  cut?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className={cn("relative flex min-h-0 flex-col border border-line-1 bg-surface-1", cut && "cut-corner", className)}>
      {(title || action) && (
        <header className="flex h-10 shrink-0 items-center gap-3 border-b border-line-1 px-3">
          {title && <h2 className="section-head whitespace-nowrap text-ink">{title}</h2>}
          {en && <span className="micro min-w-0 truncate">{en}</span>}
          <div className="ml-auto flex shrink-0 items-center gap-2">{action}</div>
        </header>
      )}
      <div className="min-h-0 flex-1">{children}</div>
    </section>
  );
}

/* ---------- ScanDivider ---------- */
export function ScanDivider({ label, className }: { label?: string; className?: string }) {
  return (
    <div className={cn("flex items-center gap-3 py-1", className)} role="separator">
      <span className="h-px flex-1 bg-gradient-to-r from-transparent via-line-2 to-transparent" />
      {label && <span className="micro">{label}</span>}
      <span className="h-px flex-1 bg-gradient-to-r from-transparent via-line-2 to-transparent" />
    </div>
  );
}

/* ---------- CoordinateTag:label | value | unit ---------- */
export function CoordinateTag({
  label,
  value,
  unit,
  tone = "default",
  className,
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  tone?: "default" | "action" | "data" | "danger" | "success" | "notify";
  className?: string;
}) {
  const toneCls = {
    default: "text-ink",
    action: "text-action-text",
    data: "text-data",
    danger: "text-danger",
    success: "text-success",
    notify: "text-notify",
  }[tone];
  return (
    <div className={cn("inline-flex items-stretch border border-line-1 bg-surface-0 font-mono text-xs", className)}>
      <span className="border-r border-line-1 bg-surface-2 px-2 py-1 text-[10px] uppercase tracking-widest text-ink-2">{label}</span>
      <span className={cn("px-2 py-1 font-bold tabular-nums", toneCls)}>{value}</span>
      {unit && <span className="pr-2 py-1 text-[10px] text-ink-3">{unit}</span>}
    </div>
  );
}

/* ---------- FrequencyBars:播放/活动态 ---------- */
export function FrequencyBars({
  bars = 12,
  height = 24,
  paused = false,
  tone = "action",
  className,
}: {
  bars?: number;
  height?: number;
  paused?: boolean;
  tone?: "action" | "data" | "operator" | "muted";
  className?: string;
}) {
  const color = { action: "bg-action", data: "bg-data", operator: "bg-operator", muted: "bg-ink-3" }[tone];
  return (
    <div aria-hidden className={cn("flex items-end gap-px", paused && "freq-paused", className)} style={{ height }}>
      {Array.from({ length: bars }, (_, i) => (
        <span
          key={i}
          className={cn("freq-bar w-[3px] h-full", color)}
          style={{ animationDelay: `${((i * 0.13) % 0.9).toFixed(2)}s`, ["--freq-dur" as string]: `${0.6 + (i % 3) * 0.15}s` }}
        />
      ))}
    </div>
  );
}

/* ---------- GhostWord:幽灵描边字 ---------- */
export function GhostWord({ children, className, size = 120 }: { children: string; className?: string; size?: number }) {
  return (
    <span aria-hidden className={cn("ghost-word font-display", className)} style={{ fontSize: size }}>
      {children}
    </span>
  );
}

/* ---------- WarningBand ---------- */
export function WarningBand({ children, tone = "danger", className }: { children: React.ReactNode; tone?: "danger" | "notify"; className?: string }) {
  const c = tone === "danger" ? "border-danger text-danger" : "border-notify text-notify";
  return (
    <div role="alert" className={cn("flex items-center gap-3 border-l-4 bg-surface-2 px-3 py-2 text-sm", c, className)}>
      <span className="tex-hatch h-4 w-6 shrink-0 opacity-70" aria-hidden />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

/* ---------- Chip:胶囊短状态 ---------- */
export function Chip({ children, tone = "default", className }: { children: React.ReactNode; tone?: "default" | "action" | "gain" | "notify" | "danger" | "success" | "special" | "data"; className?: string }) {
  const t = {
    default: "bg-surface-2 text-ink-2 border-line-1",
    action: "bg-action text-on-action border-action",
    gain: "bg-gain text-on-action border-gain",
    notify: "bg-notify text-on-action border-notify",
    danger: "bg-danger/15 text-danger border-danger/40",
    success: "bg-success/15 text-success border-success/40",
    special: "bg-special/15 text-special border-special/40",
    data: "bg-data/15 text-data border-data/40",
  }[tone];
  return <span className={cn("rounded-capsule inline-flex items-center border px-2 py-0.5 font-mono text-[11px] tabular-nums", t, className)}>{children}</span>;
}

/* ---------- Progress:灰轨 + 黄填充 ---------- */
export function Progress({ value, max = 100, tone = "action", className, label }: { value: number; max?: number; tone?: "action" | "data" | "danger" | "operator"; className?: string; label?: string }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  const c = { action: "bg-action", data: "bg-data", danger: "bg-danger", operator: "bg-operator" }[tone];
  return (
    <div className={cn("relative h-1.5 w-full bg-surface-3", className)} role="progressbar" aria-valuenow={value} aria-valuemax={max} aria-label={label}>
      <div className={cn("h-full transition-[width] duration-[var(--dur-normal)]", c)} style={{ width: `${pct}%` }} />
    </div>
  );
}
