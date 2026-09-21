"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AudioWaveform, Database, FlaskConical, Home, Layers, Wrench, Sun, Moon, BookOpen, MessageSquare, Settings, ScrollText } from "lucide-react";
import { api, assetUrl, type Status } from "@/lib/api";
import { useStudio } from "@/lib/store";
import { cn, fmtBytes } from "@/lib/utils";
import { SystemControls } from "@/components/system-controls";

const NAV = [
  { href: "/", label: "枢纽", en: "HUB", icon: Home },
  { href: "/synth", label: "合成", en: "SYNTH", icon: AudioWaveform },
  { href: "/data", label: "数据", en: "DATA", icon: Database },
  { href: "/train", label: "训练", en: "TRAIN", icon: FlaskConical },
  { href: "/models", label: "模型", en: "MODELS", icon: Layers },
  { href: "/chat", label: "对话", en: "CHAT", icon: MessageSquare },
  { href: "/tools", label: "工具", en: "TOOLS", icon: Wrench },
  { href: "/guide", label: "指南", en: "GUIDE", icon: BookOpen },
  { href: "/logs", label: "日志", en: "LOGS", icon: ScrollText },
  { href: "/settings", label: "设置", en: "SETTINGS", icon: Settings },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { character, surface, setSurface } = useStudio();
  const status = useQuery({ queryKey: ["status"], queryFn: () => api<Status>("/status"), refetchInterval: 4000 });
  const s = status.data;

  return (
    <div className="grid h-full grid-cols-[var(--rail-w)_minmax(0,1fr)] grid-rows-[minmax(0,1fr)_var(--status-h)]">
      <SystemControls />
      {/* 左缘竖排图标导航轨 */}
      <nav aria-label="主导航" className="row-span-1 flex flex-col border-r border-line-1 bg-surface-0">
        <Link href="/" className="flex h-[var(--header-h)] items-center justify-center border-b border-line-1">
          {character ? (
            <img src={assetUrl(character.art.avatarSquare)} alt={character.name} className="h-9 w-9 object-cover" />
          ) : (
            <span className="h-9 w-9 bg-surface-2" />
          )}
        </Link>
        <ul className="flex flex-1 flex-col py-2">
          {NAV.map(({ href, label, en, icon: Icon }) => {
            const active = href === "/" ? path === "/" : path.startsWith(href);
            return (
              <li key={href}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "group relative flex h-16 flex-col items-center justify-center gap-1 text-ink-2 transition-colors duration-[var(--dur-fast)]",
                    "hover:bg-surface-hover hover:text-ink",
                    active && "bg-surface-2 text-ink",
                  )}
                >
                  {active && <span aria-hidden className="absolute left-0 top-0 h-full w-[3px] bg-action" />}
                  <Icon size={18} strokeWidth={1.75} />
                  <span className="text-[10px] tracking-wider">{label}</span>
                  <span className="micro sr-only">{en}</span>
                </Link>
              </li>
            );
          })}
        </ul>
        <button
          type="button"
          onClick={() => setSurface(surface === "smoke" ? "paper" : "smoke")}
          aria-label={surface === "smoke" ? "切换到纸色" : "切换到烟灰"}
          className="flex h-12 items-center justify-center border-t border-line-1 text-ink-2 hover:text-ink"
        >
          {surface === "smoke" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
      </nav>

      <main className="relative min-h-0 overflow-hidden">{children}</main>

      {/* 底部黑色状态带:真实运行信息 */}
      <footer className="col-span-2 flex items-center gap-6 border-t border-line-1 bg-surface-0 px-4 micro">
        <span className="flex items-center gap-2">
          <span
            aria-hidden
            className={cn("h-2 w-2", status.isError ? "bg-danger" : s?.engine.loaded ? "bg-success" : "bg-notify")}
          />
          {status.isError ? "SERVER OFFLINE" : s?.engine.loaded ? "ENGINE READY" : "ENGINE IDLE"}
        </span>
        {s?.gpu && (
          <span>
            GPU {s.gpu.name} · VRAM {fmtBytes(s.gpu.used)} / {fmtBytes(s.gpu.total)}
          </span>
        )}
        {s?.engine.loaded && (
          <span className="truncate">
            GPT {s.engine.gpt} · SoVITS {s.engine.sovits}
          </span>
        )}
        {s && s.jobs.running > 0 && <span className="text-action-text">JOBS {s.jobs.running} RUNNING</span>}
        <span className="ml-auto">
          {character ? `${character.code}` : "--"} · EVF {s?.version ?? "--"}
        </span>
      </footer>
    </div>
  );
}
