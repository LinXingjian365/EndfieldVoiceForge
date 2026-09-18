"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";

export type Series = { name: string; points: [number, number][]; tone?: "data" | "action" | "danger" | "operator" | "muted" };

const STROKE = { data: "var(--data)", action: "var(--action)", danger: "var(--danger)", operator: "var(--operator-accent)", muted: "var(--text-muted)" };

/** 行内面积图(SVG,无第三方库)。用于训练 loss:蓝=量值。 */
export function AreaChart({ series, height = 64, className, showAxis = true, logY = false }: { series: Series[]; height?: number; className?: string; showAxis?: boolean; logY?: boolean }) {
  const W = 600;
  const H = height;
  const pad = { l: showAxis ? 36 : 2, r: 4, t: 4, b: showAxis ? 14 : 2 };
  const { paths, xMin, xMax, yMin, yMax } = useMemo(() => {
    const all = series.flatMap((s) => s.points);
    if (all.length === 0) return { paths: [], xMin: 0, xMax: 1, yMin: 0, yMax: 1 };
    const xs = all.map((p) => p[0]);
    const ysRaw = all.map((p) => p[1]).filter((v) => Number.isFinite(v) && (!logY || v > 0));
    const f = (v: number) => (logY ? Math.log10(v) : v);
    const xMin = Math.min(...xs), xMax = Math.max(...xs);
    const yMin = Math.min(...ysRaw.map(f)), yMax = Math.max(...ysRaw.map(f));
    const sx = (x: number) => pad.l + ((x - xMin) / Math.max(1e-9, xMax - xMin)) * (W - pad.l - pad.r);
    const sy = (y: number) => pad.t + (1 - (f(y) - yMin) / Math.max(1e-9, yMax - yMin)) * (H - pad.t - pad.b);
    const paths = series.map((s) => {
      const pts = s.points.filter((p) => Number.isFinite(p[1]) && (!logY || p[1] > 0));
      if (pts.length === 0) return { s, line: "", area: "" };
      const line = pts.map((p, i) => `${i ? "L" : "M"}${sx(p[0]).toFixed(1)},${sy(p[1]).toFixed(1)}`).join(" ");
      const area = `${line} L${sx(pts[pts.length - 1][0]).toFixed(1)},${H - pad.b} L${sx(pts[0][0]).toFixed(1)},${H - pad.b} Z`;
      return { s, line, area };
    });
    return { paths, xMin, xMax, yMin: logY ? 10 ** yMin : yMin, yMax: logY ? 10 ** yMax : yMax };
  }, [series, H, logY, pad.l, pad.r, pad.t, pad.b]);

  if (paths.length === 0) return <div className={cn("flex items-center justify-center text-xs text-ink-3", className)} style={{ height }}>无数据</div>;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={cn("w-full", className)} style={{ height }} role="img" aria-label={series.map((s) => s.name).join(", ")}>
      {showAxis && (
        <>
          <text x={pad.l - 4} y={pad.t + 8} textAnchor="end" className="fill-ink-3" style={{ fontSize: 9, fontFamily: "var(--font-mono)" }}>{fmt(yMax)}</text>
          <text x={pad.l - 4} y={H - pad.b} textAnchor="end" className="fill-ink-3" style={{ fontSize: 9, fontFamily: "var(--font-mono)" }}>{fmt(yMin)}</text>
          <text x={pad.l} y={H - 2} className="fill-ink-3" style={{ fontSize: 9, fontFamily: "var(--font-mono)" }}>{xMin}</text>
          <text x={W - pad.r} y={H - 2} textAnchor="end" className="fill-ink-3" style={{ fontSize: 9, fontFamily: "var(--font-mono)" }}>{xMax}</text>
          <line x1={pad.l} x2={W - pad.r} y1={H - pad.b} y2={H - pad.b} stroke="var(--line-1)" />
        </>
      )}
      {paths.map(({ s, line, area }) => (
        <g key={s.name}>
          <path d={area} fill={STROKE[s.tone ?? "data"]} opacity={0.12} />
          <path d={line} fill="none" stroke={STROKE[s.tone ?? "data"]} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
        </g>
      ))}
    </svg>
  );
}

function fmt(v: number) {
  if (Math.abs(v) >= 100) return v.toFixed(0);
  if (Math.abs(v) >= 1) return v.toFixed(2);
  return v.toExponential(1);
}
