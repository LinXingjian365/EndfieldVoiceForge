"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Square } from "lucide-react";
import { api, type Job } from "@/lib/api";
import { useSSE } from "@/lib/sse";
import { Chip, FrequencyBars } from "@/components/ef";
import { cn } from "@/lib/utils";

type Ev = { type: "snapshot"; job: Job } | { type: "line"; line: string } | { type: "status"; status: Job["status"]; exit_code?: number } | { type: "end" };

const TONE: Record<Job["status"], "default" | "action" | "success" | "danger" | "notify"> = {
  queued: "default",
  running: "action",
  done: "success",
  failed: "danger",
  cancelled: "notify",
};

/** 订阅一个 job 的 SSE,显示状态 + 滚动日志。 */
export function JobLog({ jobId, title, className, compact, onDone }: { jobId: string | null; title?: string; className?: string; compact?: boolean; onDone?: (j: Job) => void }) {
  const [job, setJob] = useState<Job | null>(null);
  const [lines, setLines] = useState<string[]>([]);
  const box = useRef<HTMLPreElement>(null);
  const qc = useQueryClient();
  const doneRef = useRef(onDone);
  doneRef.current = onDone;

  useSSE<Ev>(jobId ? `/jobs/${jobId}/events` : null, (ev) => {
    if (ev.type === "snapshot") {
      setJob(ev.job);
      setLines(ev.job.tail);
    } else if (ev.type === "line") {
      setLines((l) => (l.length > 2000 ? [...l.slice(-1500), ev.line] : [...l, ev.line]));
    } else if (ev.type === "status") {
      setJob((j) => (j ? { ...j, status: ev.status, exit_code: ev.exit_code ?? j.exit_code } : j));
      if (ev.status !== "running") {
        qc.invalidateQueries();
        api<Job>(`/jobs/${jobId}`).then((j) => doneRef.current?.(j)).catch(() => {});
      }
    }
  });

  useEffect(() => {
    if (box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [lines]);

  useEffect(() => {
    setJob(null);
    setLines([]);
  }, [jobId]);

  if (!jobId) return null;
  const running = job?.status === "running";
  return (
    <div className={cn("flex min-h-0 flex-col border border-line-1 bg-surface-0", className)}>
      <div className="flex h-8 shrink-0 items-center gap-2 border-b border-line-1 px-2">
        {running && <FrequencyBars bars={6} height={12} tone="action" />}
        <span className="truncate text-xs text-ink">{title ?? job?.title ?? jobId}</span>
        {job && <Chip tone={TONE[job.status]}>{job.status.toUpperCase()}{job.exit_code != null && job.status !== "running" ? ` · ${job.exit_code}` : ""}</Chip>}
        <span className="micro ml-auto">{jobId}</span>
        {running && (
          <button type="button" aria-label="取消" onClick={() => api(`/jobs/${jobId}`, { method: "DELETE" })} className="text-ink-3 hover:text-danger">
            <Square size={12} />
          </button>
        )}
      </div>
      <pre ref={box} className={cn("min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-all p-2 font-mono text-[11px] leading-relaxed text-ink-2", compact ? "max-h-40" : "")}>
        {lines.join("\n")}
      </pre>
    </div>
  );
}
