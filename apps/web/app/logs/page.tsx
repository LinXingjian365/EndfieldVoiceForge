"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Panel, Chip } from "@/components/ef";
import { Button } from "@/components/ef/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface LogEntry {
  ts: number;
  time: string;
  level: string;
  message: string;
  [key: string]: unknown;
}

const LEVEL_CLS: Record<string, string> = {
  info: "text-ink-2",
  warn: "text-notify",
  error: "text-danger",
};

const SKIP = ["ts", "time", "level", "message"];

function extras(l: LogEntry): string {
  const parts = Object.entries(l)
    .filter(([k]) => !SKIP.includes(k))
    .map(([k, v]) => `${k}=${v}`);
  return parts.length ? "  " + parts.join(" ") : "";
}

export default function LogsPage() {
  const { data, refetch, isFetching } = useQuery({
    queryKey: ["logs"],
    queryFn: () => api<{ logs: LogEntry[] }>("/logs?lines=200"),
    refetchInterval: 3000,
  });
  const [copied, setCopied] = useState(false);

  const logs = data?.logs ?? [];

  function copy() {
    const text = logs.map((l) => `${l.time} [${l.level}] ${l.message}${extras(l)}`).join("\n");
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const action = (
    <div className="flex items-center gap-2">
      <Button type="button" variant="secondary" size="sm" onClick={copy}>复制</Button>
      <Button type="button" variant="ghost" size="sm" onClick={() => refetch()} loading={isFetching}>刷新</Button>
      {copied && <Chip tone="success">已复制</Chip>}
    </div>
  );

  return (
    <div className="h-full p-2">
      <Panel title="运行日志" en="LOGS" action={action}>
        <div className="h-full overflow-auto font-mono text-xs leading-relaxed">
          {logs.length === 0 ? (
            <div className="p-8 text-center text-ink-3">暂无日志。操作对话、配置、反馈后会自动记录到这里。</div>
          ) : (
            logs.map((l, i) => (
              <div key={i} className="flex gap-3 border-b border-line-1 px-3 py-1.5 hover:bg-surface-hover">
                <span className="shrink-0 text-ink-3">{l.time}</span>
                <span className={cn("w-10 shrink-0 uppercase", LEVEL_CLS[l.level] ?? "text-ink-2")}>{l.level}</span>
                <span className="min-w-0 flex-1 whitespace-pre-wrap break-all text-ink">{l.message}<span className="text-ink-3">{extras(l)}</span></span>
              </div>
            ))
          )}
        </div>
      </Panel>
    </div>
  );
}
