"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Check, Trash2, ChevronLeft, ChevronRight, Save, RefreshCw, FileText, Ban, RotateCcw, Star } from "lucide-react";
import { api, fileUrl, type Sample, type Job } from "@/lib/api";
import { useStudio } from "@/lib/store";
import { Panel, Chip, CoordinateTag, ScanDivider, Progress } from "@/components/ef";
import { Button } from "@/components/ef/button";
import { Textarea } from "@/components/ef/form";
import { Waveform } from "@/components/audio/waveform";
import { JobLog } from "@/components/job-log";
import { cn } from "@/lib/utils";

interface Step { id: string; title: string; desc: string; produces: string; script: string | null; done: boolean; mtime: number | null; running: string | null }
interface SamplesRes { count: number; inList: number; totalDur: number; excluded: number; samples: Sample[] }

const CATS: Record<string, { label: string; tone: "success" | "danger" | "gain" | "notify" | undefined }> = {
  dialog: { label: "对话", tone: "success" },
  combat: { label: "战斗", tone: "danger" },
  commvo: { label: "语气", tone: "gain" },
  radio: { label: "电台", tone: "notify" },
  other: { label: "其他", tone: undefined },
};
const CAT_ORDER = ["dialog", "combat", "commvo", "radio", "other"] as const;

export default function DataPage() {
  const { characterId, character } = useStudio();
  const qc = useQueryClient();
  const steps = useQuery({ queryKey: ["pipeline", characterId], queryFn: () => api<Step[]>(`/datasets/${characterId}/pipeline`), refetchInterval: 5000 });
  const samples = useQuery({ queryKey: ["samples", characterId], queryFn: () => api<SamplesRes>(`/datasets/${characterId}/samples`) });
  const [jobId, setJobId] = useState<string | null>(null);
  const [selWav, setSelWav] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "labeled" | "unlabeled" | "excluded">("all");
  const [cat, setCat] = useState<string>("all");
  const [q, setQ] = useState("");
  const [draft, setDraft] = useState("");
  const [prefix, setPrefix] = useState("");
  const [selSet, setSelSet] = useState<Set<string>>(new Set());
  const listRef = useRef<HTMLUListElement>(null);

  const rows = useMemo(() => {
    const r = samples.data?.samples ?? [];
    return r.filter((s) => {
      if (filter === "excluded") return !!s.excluded;
      if (s.excluded) return false;
      if (filter === "labeled") return s.inList;
      if (filter === "unlabeled") return !s.inList;
      return true;
    }).filter((s) => cat === "all" || (s.category ?? "other") === cat)
      .filter((s) => !q || (s.text ?? "").includes(q) || s.path.includes(q) || s.wav.includes(q))
      .slice()
      .sort((a, b) => (a.favorite ? 0 : 1) - (b.favorite ? 0 : 1));
  }, [samples.data, filter, cat, q]);
  const selIdx = useMemo(() => (selWav ? rows.findIndex((s) => s.wav === selWav) : -1), [rows, selWav]);
  const cur = selIdx >= 0 ? rows[selIdx] : rows[0];

  const catCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const s of samples.data?.samples ?? []) if (!s.excluded) c[s.category ?? "other"] = (c[s.category ?? "other"] ?? 0) + 1;
    return c;
  }, [samples.data]);

  useEffect(() => { setDraft(cur?.text ?? ""); }, [cur?.wav]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (selWav === null && rows.length > 0) setSelWav(rows[0].wav); }, [selWav, rows]);

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
  const excludeM = useMutation({
    mutationFn: (wavs: string[]) => api(`/datasets/${characterId}/samples/exclude`, { method: "POST", json: { wavs } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["samples"] }),
  });
  const restoreM = useMutation({
    mutationFn: (wavs: string[]) => api(`/datasets/${characterId}/samples/restore`, { method: "POST", json: { wavs } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["samples"] }),
  });
  const prefixM = useMutation({
    mutationFn: (p: string) => api(`/datasets/${characterId}/samples/exclude_prefix`, { method: "POST", json: { prefix: p } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["samples"] }); setPrefix(""); },
  });
  const catM = useMutation({
    mutationFn: ({ wav, category }: { wav: string; category: string }) => api(`/datasets/${characterId}/samples/category?wav=${encodeURIComponent(wav)}`, { method: "PATCH", json: { category } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["samples"] }),
  });
  const favM = useMutation({
    mutationFn: ({ wav, favorite }: { wav: string; favorite: boolean }) => api(`/datasets/${characterId}/samples/favorite?wav=${encodeURIComponent(wav)}`, { method: "PATCH", json: { favorite } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["samples"] }),
  });
  const catBatchM = useMutation({
    mutationFn: ({ wavs, category }: { wavs: string[]; category: string }) => api(`/datasets/${characterId}/samples/category_batch`, { method: "POST", json: { wavs, category } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["samples"] }); setSelSet(new Set()); },
  });
  const autocatM = useMutation({
    mutationFn: () => api(`/datasets/${characterId}/samples/autocat`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["samples"] }),
  });

  // 批量选择(仅作用于当前可见行, exclude/restore 后 wav 路径会变, 需清空选择)
  const visibleSel = rows.filter((s) => selSet.has(s.wav));
  const toRestore = visibleSel.filter((s) => s.excluded);
  const toExclude = visibleSel.filter((s) => !s.excluded);
  const allSel = rows.length > 0 && rows.every((s) => selSet.has(s.wav));
  const toggleAll = () => setSelSet(allSel ? new Set() : new Set(rows.map((s) => s.wav)));

  // 键盘:↑↓ 切样本,Ctrl+S 保存,X 剔除/恢复
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "TEXTAREA" || (e.target as HTMLElement)?.tagName === "INPUT") {
        if (!((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s")) return;
      }
      if (e.key === "ArrowDown") { e.preventDefault(); const base = selIdx < 0 ? 0 : selIdx; const next = Math.min(rows.length - 1, base + 1); if (rows[next]) setSelWav(rows[next].wav); }
      if (e.key === "ArrowUp") { e.preventDefault(); const base = selIdx < 0 ? 0 : selIdx; const next = Math.max(0, base - 1); if (rows[next]) setSelWav(rows[next].wav); }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); if (cur) save.mutate({ wav: cur.wav, text: draft }); }
      if (e.key.toLowerCase() === "x" && cur) { e.preventDefault(); (cur.excluded ? restoreM : excludeM).mutate([cur.wav]); }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [rows, selIdx, cur, draft, save, excludeM, restoreM]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-i="${selIdx}"]`)?.scrollIntoView({ block: "nearest" });
  }, [selIdx]);

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
          <input value={q} onChange={(e) => { setQ(e.target.value); setSelWav(null); }} placeholder="搜索文本/来源…" className="h-7 w-40 border border-line-2 bg-surface-2 px-2 text-xs" />
          {([["all", "全部"], ["labeled", "已标注"], ["unlabeled", "未标注"], ["excluded", "已剔除"]] as const).map(([f, lbl]) => (
            <button key={f} type="button" onClick={() => { setFilter(f); setSelWav(null); }} className={cn("micro px-2 py-1 hover:text-ink", filter === f && "bg-ink text-canvas")}>{lbl}</button>
          ))}
        </div>
      }>
        <div className="flex h-full flex-col">
          <div className="flex items-center gap-2 border-b border-line-1 px-3 py-2">
            <CoordinateTag label="clips" value={st?.count ?? "--"} />
            <CoordinateTag label="labeled" value={st?.inList ?? "--"} tone="success" />
            <CoordinateTag label="excluded" value={st?.excluded ?? 0} tone="danger" />
            <CoordinateTag label="total" value={st ? (st.totalDur / 60).toFixed(1) : "--"} unit="min" tone="data" />
            <div className="ml-auto w-40"><Progress value={st?.inList ?? 0} max={st?.count ?? 1} label="标注进度" /></div>
          </div>
          <div className="flex items-center gap-1.5 overflow-x-auto border-b border-line-1 px-3 py-1.5">
            <button type="button" onClick={() => { setCat("all"); setSelWav(null); }} className={cn("micro shrink-0 px-2 py-1 hover:text-ink", cat === "all" && "bg-ink text-canvas")}>全部</button>
            {CAT_ORDER.map((c) => (
              <button key={c} type="button" onClick={() => { setCat(c); setSelWav(null); }} className={cn("micro shrink-0 px-2 py-1 hover:text-ink", cat === c && "bg-ink text-canvas")}>
                {CATS[c].label}<span className="ml-1 opacity-60">{catCounts[c] ?? 0}</span>
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 border-b border-line-1 px-3 py-1.5">
            <label className="flex shrink-0 cursor-pointer items-center gap-1.5 micro hover:text-ink">
              <input type="checkbox" checked={allSel} onChange={toggleAll} className="h-3.5 w-3.5 accent-[var(--action)]" />
              全选
            </label>
            <span className="micro shrink-0 text-ink-3">已选 {visibleSel.length}</span>
            <Button size="sm" variant="secondary" icon={<RotateCcw size={12} />} disabled={!toRestore.length} loading={restoreM.isPending} onClick={() => { restoreM.mutate(toRestore.map((s) => s.wav)); setSelSet(new Set()); }}>接入训练集</Button>
            <Button size="sm" variant="danger" icon={<Ban size={12} />} disabled={!toExclude.length} loading={excludeM.isPending} onClick={() => { excludeM.mutate(toExclude.map((s) => s.wav)); setSelSet(new Set()); }}>移出训练集</Button>
            <select defaultValue="" onChange={(e) => { if (e.target.value) { catBatchM.mutate({ wavs: visibleSel.map((s) => s.wav), category: e.target.value }); e.target.value = ""; } }} disabled={!visibleSel.length} className="h-7 border border-line-2 bg-surface-2 px-1 text-xs" title="批量设类别">
              <option value="" disabled>批量设类别…</option>
              {CAT_ORDER.map((c) => <option key={c} value={c}>{CATS[c].label}</option>)}
            </select>
            <Button size="sm" variant="ghost" icon={<RefreshCw size={12} />} loading={autocatM.isPending} onClick={() => autocatM.mutate()}>自动分类全部</Button>
          </div>
          <div className="flex items-center gap-2 border-b border-line-1 px-3 py-1.5">
            <input value={prefix} onChange={(e) => setPrefix(e.target.value)} placeholder="前缀批量剔除，如 au_radio_c34(电台杂音，保留 continue_self 语音)" className="h-7 flex-1 border border-line-2 bg-surface-2 px-2 text-xs" />
            <Button size="sm" variant="danger" icon={<Ban size={12} />} disabled={!prefix.trim()} loading={prefixM.isPending} onClick={() => prefixM.mutate(prefix.trim())}>按前缀剔除</Button>
            {(st?.excluded ?? 0) > 0 && (
              <Button size="sm" variant="secondary" icon={<RotateCcw size={12} />} loading={restoreM.isPending} onClick={() => restoreM.mutate((samples.data?.samples ?? []).filter((s) => s.excluded).map((s) => s.wav))}>全部恢复</Button>
            )}
          </div>
          <ul ref={listRef} className="min-h-0 flex-1 overflow-auto">
            {rows.map((s, i) => (
              <li key={s.wav} data-i={i} className={cn("relative flex items-center border-b border-line-1 hover:bg-surface-hover", i === selIdx && "corner-bracket bg-surface-2")}>
                <input type="checkbox" checked={selSet.has(s.wav)} onClick={(e) => e.stopPropagation()} onChange={() => setSelSet((prev) => { const n = new Set(prev); if (n.has(s.wav)) n.delete(s.wav); else n.add(s.wav); return n; })} className="ml-3 h-3.5 w-3.5 shrink-0 accent-[var(--action)]" aria-label="多选" />
                <button type="button" onClick={() => setSelWav(s.wav)} className="relative grid min-w-0 flex-1 grid-cols-[56px_minmax(0,1fr)_auto] items-center gap-3 px-3 py-1.5 text-left">
                  <span className="micro">{s.idx ?? "—"}</span>
                  <span className={cn("truncate text-sm", s.excluded ? "text-ink-3 line-through" : s.inList ? "text-ink" : "text-ink-3 italic")}>{s.text ?? "(未标注)"}</span>
                  <span className="flex items-center gap-1">
                    {s.excluded && <Chip tone="danger">剔除</Chip>}
                    {s.category && CATS[s.category] && <Chip tone={CATS[s.category].tone}>{CATS[s.category].label}</Chip>}
                    <Chip>{s.dur.toFixed(1)}s</Chip>
                    {s.f0 > 0 && <Chip tone={s.f0 >= 180 && s.f0 <= 350 ? "gain" : "notify"}>{Math.round(s.f0)}Hz</Chip>}
                  </span>
                  {/* 底部按置信度(有声比)渐变 */}
                  <span aria-hidden className="absolute inset-x-0 bottom-0 h-0.5" style={{ background: `linear-gradient(90deg, var(--data) ${Math.round(s.voiced * 100)}%, transparent 0)`, opacity: 0.6 }} />
                </button>
                <button type="button" aria-label={s.favorite ? "取消收藏" : "收藏置顶"} title={s.favorite ? "取消收藏" : "收藏置顶"} onClick={() => favM.mutate({ wav: s.wav, favorite: !s.favorite })} className={cn("mr-2 flex h-6 w-6 shrink-0 items-center justify-center", s.favorite ? "text-action" : "text-ink-3 hover:text-ink")}>
                  <Star size={13} fill={s.favorite ? "currentColor" : "none"} />
                </button>
              </li>
            ))}
            {rows.length === 0 && <li className="p-6 text-center text-sm text-ink-3">{samples.isLoading ? "加载中…" : "没有样本。先在左侧运行管线。"}</li>}
          </ul>
        </div>
      </Panel>

      {/* 右:打标编辑器 */}
      <Panel title="校对" en="LABEL EDITOR" action={<span className="micro">↑↓ 切换 · Ctrl+S 保存 · X 剔除/恢复</span>}>
        {cur ? (
          <div className="flex h-full flex-col gap-3 p-3">
            <div className="flex items-center gap-2">
              <Button variant="icon" aria-label="上一条" onClick={() => { const n = Math.max(0, selIdx - 1); if (rows[n]) setSelWav(rows[n].wav); }}><ChevronLeft size={16} /></Button>
              <span className="micro">{selIdx + 1} / {rows.length}</span>
              <Button variant="icon" aria-label="下一条" onClick={() => { const n = Math.min(rows.length - 1, selIdx + 1); if (rows[n]) setSelWav(rows[n].wav); }}><ChevronRight size={16} /></Button>
              <Button variant="icon" aria-label={cur.favorite ? "取消收藏" : "收藏置顶"} title={cur.favorite ? "取消收藏" : "收藏置顶"} onClick={() => favM.mutate({ wav: cur.wav, favorite: !cur.favorite })} className={cur.favorite ? "text-action" : undefined}><Star size={16} fill={cur.favorite ? "currentColor" : "none"} /></Button>
              <span className="ml-auto truncate text-xs text-ink-2">{cur.wav.split("/").pop()}</span>
            </div>
            <Waveform url={fileUrl(cur.wav)} height={56} className="border border-line-1 bg-surface-0 px-2 py-1" />
            <div className="flex flex-wrap gap-2">
              <CoordinateTag label="src" value={cur.path.replace(".wem", "")} />
              <CoordinateTag label="f0" value={Math.round(cur.f0)} unit="Hz" tone="data" />
              <CoordinateTag label="voiced" value={(cur.voiced * 100).toFixed(0)} unit="%" />
              <CoordinateTag label="voType" value={cur.vt} />
            </div>
            <div className="flex items-center gap-1.5">
              <span className="micro text-ink-3">类别</span>
              {CAT_ORDER.map((c) => (
                <button key={c} type="button" onClick={() => catM.mutate({ wav: cur.wav, category: c })} className={cn("micro border px-2 py-0.5 transition-colors", (cur.category ?? "other") === c ? "border-ink bg-ink text-canvas" : "border-line-2 hover:border-ink")}>
                  {CATS[c].label}
                </button>
              ))}
            </div>
            <ScanDivider label="TRANSCRIPT" />
            <Textarea rows={5} value={draft} onChange={(e) => setDraft(e.target.value)} className="flex-1 text-base leading-relaxed" placeholder="这条音频的台词文本(空 = 从训练列表移除)" />
            <div className="flex items-center gap-2">
              <Button variant="action" icon={<Save size={14} />} onClick={() => save.mutate({ wav: cur.wav, text: draft })} loading={save.isPending} disabled={draft === (cur.text ?? "")}>保存</Button>
              <Button variant="ghost" size="sm" onClick={() => setDraft(cur.text ?? "")}>还原</Button>
              <Button variant={cur.excluded ? "secondary" : "danger"} size="sm" icon={cur.excluded ? <RotateCcw size={12} /> : <Ban size={12} />} onClick={() => (cur.excluded ? restoreM : excludeM).mutate([cur.wav])} loading={excludeM.isPending || restoreM.isPending}>{cur.excluded ? "恢复" : "剔除"}</Button>
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
