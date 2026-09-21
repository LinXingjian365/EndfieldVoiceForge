"use client";

import { useMutation } from "@tanstack/react-query";
import { Power, RotateCw } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/toast";

export function SystemControls() {
  const toast = useToast();

  const quit = useMutation({
    mutationFn: () => api<{ message: string }>("/system/quit", { method: "POST" }),
    onSuccess: (d) => toast("info", d.message ?? "服务已停止"),
    onError: (e) => toast("danger", `退出失败：${(e as Error).message}`),
  });

  const restart = useMutation({
    mutationFn: () => api<{ message: string }>("/system/restart", { method: "POST" }),
    onSuccess: (d) => toast("info", d.message ?? "正在重启…"),
    onError: (e) => toast("danger", `重启失败：${(e as Error).message}`),
  });

  return (
    <div className="fixed right-3 top-3 z-50 flex items-center gap-2">
      <button
        type="button"
        title="重启服务"
        onClick={() => restart.mutate()}
        className="cut-corner flex h-9 w-9 items-center justify-center border border-line-1 bg-surface-1/90 text-ink-2 backdrop-blur transition-colors hover:bg-surface-hover hover:text-ink"
      >
        <RotateCw size={16} strokeWidth={1.75} />
      </button>
      <button
        type="button"
        title="关闭服务"
        onClick={() => {
          if (window.confirm("确定关闭 EndfieldVoiceForge 服务吗？")) quit.mutate();
        }}
        className="cut-corner flex h-9 w-9 items-center justify-center border border-line-1 bg-surface-1/90 text-ink-2 backdrop-blur transition-colors hover:bg-danger/20 hover:text-danger"
      >
        <Power size={16} strokeWidth={1.75} />
      </button>
    </div>
  );
}
