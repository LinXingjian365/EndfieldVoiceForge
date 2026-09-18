import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmtBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`;
  return `${(n / 1024 ** 3).toFixed(2)} GB`;
}

export function fmtSec(s: number) {
  if (!Number.isFinite(s)) return "--";
  const m = Math.floor(s / 60);
  const r = s - m * 60;
  return m > 0 ? `${m}m ${r.toFixed(1)}s` : `${r.toFixed(2)}s`;
}
