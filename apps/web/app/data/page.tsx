"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Check, Trash2, ChevronLeft, ChevronRight, Save, RefreshCw, FileText } from "lucide-react";
import { api, fileUrl, type Sample, type Job } from "@/lib/api";
import { useStudio } from "@/lib/store";
import { Panel, Chip, CoordinateTag, ScanDivider, Progress } from "@/components/ef";
import { Button } from "@/components/ef/button";
import { Textarea } from "@/components/ef/form";
import { Waveform } from "@/components/audio/waveform";
import { JobLog } from "@/components/job-log";
import { cn } from "@/lib/utils";

interface Step { id: string; title: string; desc: string; produces: string; script: string | null; done: boolean; mtime: number | null; running: string | null }
interface SamplesRes { count: number; inList: number; totalDur: number; samples: Sample[] }

export default function DataPage() {
  const { characterId, character } = useStudio();
  const qc = useQueryClient();
  const steps = useQuery({ queryKey: ["pipeline", characterId], queryFn: () => api<Step[]>(`/datasets/${characterId}/pipeline`), refetchInterval: 5000 });
  const samples = useQuery({ queryKey: ["samples", characterId], queryFn: () => api<SamplesRes>(`/datasets/${characterId}/samples`) });
  const [jobId, setJobId] = useState<string | null>(null);
  const [sel, setSel] = useState<number>(0);
  const [filter, setFilter] = useState<"all" | "labeled" | "unlabeled">("all");
  const [q, setQ] = useState("");
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLUListElement>(null);

  const rows = useMemo(() => {
    const r = samples.data?.samples ?? [];
    return r.filter((s) => (filter === "all" || (filter === "labeled" ? s.inList : !s.inList)) && (!q || (s.text ?? "").includes(q) || s.path.includes(q)));
  }, [samples.data, filter, q]);
  const cur = rows[sel];

  useEffect(() => { setDraft(cur?.text ?? ""); }, [cur?.wav]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (sel >= rows.length) setSel(Math.max(0, rows.length - 1)); }, [rows.length, sel]);

  const run = useMutation({
    mutationFn: (id: string) => api<Job>(`/datasets/${characterId}/pipeline/${id}`, { method: "POST" }),
    onSuccess: (j) => { setJobId(j.id); qc.invalidateQueries({ queryKey: ["pipeline"] }); },
  });
  const save = useMutation({
    mutationFn: ({ wav, text }: { wav: string; text: string }) => api(`/datasets/${characterId}/samples/text?wav=${encodeURIComponent(wav)}`, { method: "PATCH", json: { text } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["samples"] }),
  });
  const del = useMutation({
    mutationFn: (wav: string) => api(`/datasets/${characterId}/samples?wav=${encodeURIComponent(wav)}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["samples"] }),
  });

  // 键盘:↑↓ 切样本,Ctrl+S 保存
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "TEXTAREA" && !(e.ctrlKey || e.metaKey)) return;
      if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(rows.length - 1, s + 1)); }
      if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); if (cur) save.mutate({ wav: cur.wav, text: draft }); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [rows.length, cur, draft, save]);

  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-i="${sel}"]`)?.scrollIntoView({ block: "nearest" });
  }, [sel]);

  const st = samples.data;
  return (
    <div className="grid h-full grid-cols-[minmax(260px,0.8fr)_minmax(0,1.4fr)_minmax(320px,1fr)] gap-2 p-2">
      {/* 左:管线步骤轨(斜轴节点) */}
      <Panel title="管线" en="PIPELINE" className="overflow-hidden">
        <div className="flex h-full flex-col">
          <ol className="relative flex-1 overflow-auto p-4">
            {steps.data?.map((s, i) => {
              const running = !!s.running;
              const canRun = !!s.script && !running;
              return (
                <li key={s.id} className="relative flex gap-3 pb-6 last:pb-0" style={{ paddingLeft: i * 10 }}>
                  {i < (steps.data?.length ?? 0) - 1 && <span aria-hidden className="absolute left-[calc(var(--x)+11px)] top-6 h-full w-px bg-line-2" style={{ ["--x" as string]: `${i * 10}px` }} />}
                  <span className={cn("relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center border text-[10px] font-bold", running ? "border-action bg-action text-on-action" : s.done ? "border-ink bg-ink text-canvas" : "border-line-2 bg-surface-2 text-ink-3")}>
                    {s.done && !running ? <Check size={12} /> : i + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className={cn("text-sm", s.done ? "text-ink" : "text-ink-2")}>{s.title}</span>
                      {running && <Chip tone="action">RUNNING</Chip>}
                      {s.done && !running && s.mtime && <span className="micro">{new Date(s.mtime * 1000).toLocaleDateString()}</span>}
                    </div>
                    <p className="mt-0.5 text-xs leading-relaxed text-ink-3">{s.desc}</p>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="micro truncate">{s.produces}</span>
                      {canRun && <Button size="sm" variant={s.done ? "ghost" : "action"} icon={s.done ? <RefreshCw size={12} /> : <Play size={12} />} onClick={() => run.mutate(s.id)}>{s.done ? "重跑" : "运行"}</Button>}
                      {running && <Button size="sm" variant="ghost" onClick={() => setJobId(s.running)}>查看日志</Button>}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
          {jobId && <JobLog jobId={jobId} compact className="m-2 max-h-56" />}
        </div>
      </Panel>

      {/* 中:样本矩阵 */}
      <Panel title="样本" en="SAMPLES" action={
        <div className="flex items-center gap-2">
          <input value={q} onChange={(e) => { setQ(e.target.value); setSel(0); }} placeholder="搜索文本/来源…" className="h-7 w-40 border border-line-2 bg-surface-2 px-2 text-xs" />
          {(["all", "labeled", "unlabeled"] as const).map((f) => (
            <button key={f} type="button" onClick={() => { setFilter(f); setSel(0); }} className={cn("micro px-2 py-1 hover:text-ink", filter === f && "bg-ink text-canvas")}>{f}</button>
          ))}
        </div>
      }>
        <div className="flex h-full flex-col">
          <div className="flex items-center gap-2 border-b border-line-1 px-3 py-2">
            <CoordinateTag label="clips" value={st?.count ?? "--"} />
            <CoordinateTag label="labeled" value={st?.inList ?? "--"} tone="success" />
            <CoordinateTag label="total" value={st ? (st.totalDur / 60).toFixed(1) : "--"} unit="min" tone="data" />
            <div className="ml-auto w-40"><Progress value={st?.inList ?? 0} max={st?.count ?? 1} label="标注进度" /></div>
          </div>
          <ul ref={listRef} className="min-h-0 flex-1 overflow-auto">
            {rows.map((s, i) => (
              <li key={s.wav} data-i={i}>
                <button type="button" onClick={() => setSel(i)} className={cn("relative grid w-full grid-cols-[56px_minmax(0,1fr)_auto] items-center gap-3 border-b border-line-1 px-3 py-1.5 text-left hover:bg-surface-hover", i === sel && "corner-bracket bg-surface-2")}>
                  <span className="micro">{s.idx ?? "—"}</span>
                  <span className={cn("truncate text-sm", s.inList ? "text-ink" : "text-ink-3 italic")}>{s.text ?? "(未标注)"}</span>
                  <span className="flex items-center gap-1">
                    <Chip>{s.dur.toFixed(1)}s</Chip>
                    {s.f0 > 0 && <Chip tone={s.f0 >= 180 && s.f0 <= 350 ? "gain" : "notify"}>{Math.round(s.f0)}Hz</Chip>}
                  </span>
                  {/* 底部按置信度(有声比)渐变 */}
                  <span aria-hidden className="absolute inset-x-0 bottom-0 h-0.5" style={{ background: `linear-gradient(90deg, var(--data) ${Math.round(s.voiced * 100)}%, transparent 0)`, opacity: 0.6 }} />
                </button>
              </li>
            ))}
            {rows.length === 0 && <li className="p-6 text-center text-sm text-ink-3">{samples.isLoading ? "加载中…" : "没有样本。先在左侧运行管线。"}</li>}
          </ul>
        </div>
      </Panel>

      {/* 右:打标编辑器 */}
      <Panel title="校对" en="LABEL EDITOR" action={<span className="micro">↑↓ 切换 · Ctrl+S 保存</span>}>
        {cur ? (
          <div className="flex h-full flex-col gap-3 p-3">
            <div className="flex items-center gap-2">
              <Button variant="icon" aria-label="上一条" onClick={() => setSel((s) => Math.max(0, s - 1))}><ChevronLeft size={16} /></Button>
              <span className="micro">{sel + 1} / {rows.length}</span>
              <Button variant="icon" aria-label="下一条" onClick={() => setSel((s) => Math.min(rows.length - 1, s + 1))}><ChevronRight size={16} /></Button>
              <span className="ml-auto truncate text-xs text-ink-2">{cur.wav.split("/").pop()}</span>
            </div>
            <Waveform url={fileUrl(cur.wav)} height={56} className="border border-line-1 bg-surface-0 px-2 py-1" />
            <div className="flex flex-wrap gap-2">
              <CoordinateTag label="src" value={cur.path.replace(".wem", "")} />
              <CoordinateTag label="f0" value={Math.round(cur.f0)} unit="Hz" tone="data" />
              <CoordinateTag label="voiced" value={(cur.voiced * 100).toFixed(0)} unit="%" />
              <CoordinateTag label="voType" value={cur.vt} />
            </div>
            <ScanDivider label="TRANSCRIPT" />
            <Textarea rows={5} value={draft} onChange={(e) => setDraft(e.target.value)} className="flex-1 text-base leading-relaxed" placeholder="这条音频的台词文本(空 = 从训练列表移除)" />
            <div className="flex items-center gap-2">
              <Button variant="action" icon={<Save size={14} />} onClick={() => save.mutate({ wav: cur.wav, text: draft })} loading={save.isPending} disabled={draft === (cur.text ?? "")}>保存</Button>
              <Button variant="ghost" size="sm" onClick={() => setDraft(cur.text ?? "")}>还原</Button>
              <Button variant="danger" size="sm" icon={<Trash2 size={12} />} className="ml-auto" onClick={() => { if (confirm("删除这条音频及其标注?")) del.mutate(cur.wav); }}>删除样本</Button>
            </div>
            {save.isSuccess && <span className="micro text-success">SAVED</span>}
          </div>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-ink-3"><FileText size={24} strokeWidth={1.25} /><span className="text-sm">选中一条样本开始校对</span></div>
        )}
      </Panel>
    </div>
  );
}
