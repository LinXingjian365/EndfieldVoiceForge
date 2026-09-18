"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AudioWaveform, Database, FlaskConical, Layers, Wrench, ArrowRight } from "lucide-react";
import { api, assetUrl, type Status, type WeightEntry, type LibraryItem } from "@/lib/api";
import { useStudio } from "@/lib/store";
import { CoordinateTag, GhostWord, ScanDivider, Chip } from "@/components/ef";
import { fmtBytes } from "@/lib/utils";

const MODULES = [
  { href: "/synth", icon: AudioWaveform, title: "合成工作台", en: "SYNTHESIS", desc: "参考音频 · 文本 · 参数 · 生成 · 历史" },
  { href: "/data", icon: Database, title: "数据车间", en: "DATASET", desc: "解包定位 · 筛选 · ASR · 校对" },
  { href: "/train", icon: FlaskConical, title: "训练控制台", en: "TRAINING", desc: "格式化 · GPT · SoVITS · 曲线 · 检查点" },
  { href: "/models", icon: Layers, title: "模型库", en: "MODELS", desc: "权重矩阵 · 加载 · 对比" },
  { href: "/tools", icon: Wrench, title: "工具箱", en: "TOOLS", desc: "UVR5 · 切片 · 降噪 · 长音频切分" },
];

export default function HubPage() {
  const { character } = useStudio();
  const status = useQuery({ queryKey: ["status"], queryFn: () => api<Status>("/status") });
  const models = useQuery({ queryKey: ["models"], queryFn: () => api<{ weights: WeightEntry[] }>("/models") });
  const recent = useQuery({ queryKey: ["library", "recent"], queryFn: () => api<LibraryItem[]>("/library?limit=5") });

  const s = status.data;
  const weights = models.data?.weights ?? [];
  const gptCount = weights.filter((w) => w.kind === "gpt").length;
  const sovCount = weights.filter((w) => w.kind === "sovits").length;

  return (
    <div className="relative h-full overflow-hidden">
      {/* 场景层:角色场景图 + 暗角,低对比 */}
      {character && (
        <div aria-hidden className="absolute inset-0 -z-10">
          <img src={assetUrl(character.art.scene)} alt="" className="h-full w-full object-cover opacity-25" />
          <div className="absolute inset-0 bg-gradient-to-r from-canvas via-canvas/80 to-canvas/20" />
          <div className="absolute inset-0 tex-grid opacity-60" />
        </div>
      )}

      {/* 幽灵字索引 */}
      <GhostWord size={160} className="left-[var(--rail-w)] top-6 -translate-x-8">
        {character?.nameEn.toUpperCase() ?? "ENDFIELD"}
      </GhostWord>

      {/* 偏心视觉锚:全身立绘出血右下 */}
      {character && (
        <img
          src={assetUrl(character.art.full)}
          alt={character.name}
          className="pointer-events-none absolute -bottom-10 -right-24 h-[110%] max-w-none select-none object-contain drop-shadow-[0_0_40px_rgba(0,0,0,.6)]"
        />
      )}

      {/* 左侧信息栏 + 模块入口 */}
      <div className="relative z-10 flex h-full max-w-[720px] flex-col gap-6 p-10">
        <header className="flex flex-col gap-3">
          <span className="micro">// VOICE FORGE / {character?.code ?? "--"}</span>
          <h1 className="font-display text-5xl font-black tracking-tight text-ink">
            {character?.name ?? "..."}
            <span className="ml-3 align-middle text-lg font-medium text-ink-2">{character?.nameEn}</span>
          </h1>
          <div className="flex flex-wrap gap-2">
            <CoordinateTag label="engine" value={s?.engine.loaded ? "READY" : "IDLE"} tone={s?.engine.loaded ? "success" : "notify"} />
            <CoordinateTag label="vram" value={s?.gpu ? `${fmtBytes(s.gpu.used)} / ${fmtBytes(s.gpu.total)}` : "--"} tone="data" />
            <CoordinateTag label="gpt" value={gptCount} unit="ckpt" />
            <CoordinateTag label="sovits" value={sovCount} unit="pth" />
          </div>
        </header>

        <ScanDivider label="MODULES" />

        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {MODULES.map(({ href, icon: Icon, title, en, desc }, i) => (
            <li key={href} className={i === 0 ? "sm:col-span-2" : ""}>
              <Link
                href={href}
                className="group flex items-center gap-4 border border-line-1 bg-surface-1/90 p-4 backdrop-blur-sm transition-colors hover:border-line-2 hover:bg-surface-2/90 focus-visible:outline-2 focus-visible:outline-action"
              >
                <span className="flex h-11 w-11 shrink-0 items-center justify-center bg-surface-2 text-ink-2 group-hover:bg-action group-hover:text-on-action">
                  <Icon size={20} strokeWidth={1.75} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline gap-2">
                    <span className="font-medium text-ink">{title}</span>
                    <span className="micro">{en}</span>
                  </span>
                  <span className="block truncate text-xs text-ink-2">{desc}</span>
                </span>
                <ArrowRight size={16} className="text-ink-3 transition-transform group-hover:translate-x-1 group-hover:text-action" />
              </Link>
            </li>
          ))}
        </ul>

        {recent.data && recent.data.length > 0 && (
          <>
            <ScanDivider label="RECENT" />
            <ul className="flex flex-col gap-1 text-sm">
              {recent.data.map((g) => (
                <li key={g.id} className="flex items-center gap-3 border-l-2 border-line-2 pl-3 text-ink-2">
                  <span className="truncate text-ink">{g.text}</span>
                  <Chip className="ml-auto shrink-0">{g.duration.toFixed(1)}s</Chip>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
