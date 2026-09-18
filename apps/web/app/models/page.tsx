"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload, Trash2, Sparkles, Cpu, Wand2, ListTree } from "lucide-react";
import { api, fileUrl, type WeightEntry, type Status, type RvcModels } from "@/lib/api";
import { useStudio } from "@/lib/store";
import { Panel, Chip, CoordinateTag, ScanDivider } from "@/components/ef";
import { Button } from "@/components/ef/button";
import { Input, Textarea } from "@/components/ef/form";
import { Waveform } from "@/components/audio/waveform";
import { JobLog } from "@/components/job-log";
import { cn, fmtBytes } from "@/lib/utils";

export default function ModelsPage() {
  const { characterId, character } = useStudio();
  const qc = useQueryClient();
  const models = useQuery({ queryKey: ["models"], queryFn: () => api<{ weights: WeightEntry[] }>("/models") });
  const status = useQuery({ queryKey: ["status"], queryFn: () => api<Status>("/status"), refetchInterval: 4000 });
  const eng = status.data?.engine;
  const [pickG, setPickG] = useState<string | null>(null);
  const [pickS, setPickS] = useState<string | null>(null);
  const [abText, setAbText] = useState("好吧，很高兴你能把我当做合格的伙伴。");
  const [ab, setAb] = useState<{ label: string; wav: string; elapsed: number }[]>([]);

  const weights = models.data?.weights ?? [];
  const byExp = useMemo(() => {
    const m: Record<string, { gpt: WeightEntry[]; sovits: WeightEntry[] }> = {};
    for (const w of weights) {
      m[w.exp] ??= { gpt: [], sovits: [] };
      m[w.exp][w.kind].push(w);
    }
    return m;
  }, [weights]);

  const load = useMutation({
    mutationFn: (b: { gpt: string; sovits: string }) => api("/models/load", { method: "POST", json: { ...b, version: "v2", character: characterId } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["status"] }); qc.invalidateQueries({ queryKey: ["models"] }); },
  });
  const del = useMutation({
    mutationFn: (path: string) => api(`/training/weights?path=${encodeURIComponent(path)}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["models"] }),
  });

  const abRun = useMutation({
    mutationFn: async (pairs: { label: string; gpt: string; sovits: string }[]) => {
      const out: typeof ab = [];
      for (const p of pairs) {
        await api("/models/load", { method: "POST", json: { gpt: p.gpt, sovits: p.sovits, version: "v2", character: characterId } });
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:9890"}/tts`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ character: characterId, text: abText, ref_audio_path: character?.defaultRef.audio, prompt_text: character?.defaultRef.text, prompt_lang: "zh", text_lang: "zh", seed: 1234, save: true }),
        });
        if (!res.ok) throw new Error(await res.text());
        out.push({ label: p.label, wav: res.headers.get("X-Wav-Path") ?? "", elapsed: Number(res.headers.get("X-Elapsed")) });
        setAb([...out]);
      }
      qc.invalidateQueries({ queryKey: ["status"] });
      return out;
    },
  });

  const curG = pickG ?? eng?.gpt ?? null;
  const curS = pickS ?? eng?.sovits ?? null;

  return (
    <div className="grid h-full grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)] gap-2 p-2">
      <Panel title="权重矩阵" en="WEIGHTS · exp × epoch" action={
        <div className="flex items-center gap-2">
          <CoordinateTag label="loaded" value={eng?.loaded ? `${eng.gpt?.split("/").pop()} + ${eng.sovits?.split("/").pop()}` : "—"} tone={eng?.loaded ? "success" : "default"} className="max-w-[420px] [&>span:nth-child(2)]:truncate" />
        </div>
      }>
        <div className="h-full overflow-auto p-3">
          {Object.entries(byExp).map(([exp, g]) => (
            <section key={exp} className="mb-6">
              <div className="mb-2 flex items-center gap-3">
                <span className="section-head text-ink">{exp}</span>
                <Chip>{g.gpt.length} GPT</Chip>
                <Chip>{g.sovits.length} SoVITS</Chip>
              </div>
              <Grid title="GPT" rows={g.gpt} cur={curG} loaded={eng?.gpt ?? null} onPick={setPickG} onDel={(p) => del.mutate(p)} />
              <Grid title="SoVITS" rows={g.sovits} cur={curS} loaded={eng?.sovits ?? null} onPick={setPickS} onDel={(p) => del.mutate(p)} />
            </section>
          ))}
          {weights.length === 0 && <p className="text-sm text-ink-3">没有微调权重。去训练页跑 s1/s2。</p>}
          <ScanDivider label="RVC · POST-PROCESS" className="my-4" />
          <RvcSection />
        </div>
      </Panel>

      <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-2">
        <Panel title="加载" en="LOAD PAIR">
          <div className="flex flex-col gap-2 p-3">
            <CoordinateTag label="gpt" value={curG?.split("/").pop() ?? "—"} className="[&>span:nth-child(2)]:truncate" />
            <CoordinateTag label="sovits" value={curS?.split("/").pop() ?? "—"} className="[&>span:nth-child(2)]:truncate" />
            <Button variant="action" icon={<Cpu size={14} />} disabled={!curG || !curS || (curG === eng?.gpt && curS === eng?.sovits)} loading={load.isPending} onClick={() => curG && curS && load.mutate({ gpt: curG, sovits: curS })}>
              {curG === eng?.gpt && curS === eng?.sovits ? "已加载" : "加载到引擎"}
            </Button>
            {load.isError && <span className="text-xs text-danger">{(load.error as Error).message}</span>}
          </div>
        </Panel>

        <Panel title="A / B 试听" en="COMPARE EPOCHS" action={<span className="micro">seed 1234 · 默认参考</span>}>
          <div className="flex h-full flex-col gap-2 p-3">
            <Textarea rows={2} value={abText} onChange={(e) => setAbText(e.target.value)} />
            <AbPicker weights={weights} onRun={(pairs) => abRun.mutate(pairs)} busy={abRun.isPending} />
            {abRun.isError && <span className="text-xs text-danger">{(abRun.error as Error).message}</span>}
            <ScanDivider label="RESULTS" />
            <ul className="min-h-0 flex-1 overflow-auto">
              {ab.map((r) => (
                <li key={r.wav} className="mb-2 border border-line-1 bg-surface-0 p-2">
                  <div className="mb-1 flex items-center gap-2"><Chip tone="special">{r.label}</Chip><span className="micro ml-auto">{r.elapsed.toFixed(1)}s</span></div>
                  <Waveform url={fileUrl(r.wav)} height={28} compact />
                </li>
              ))}
              {ab.length === 0 && !abRun.isPending && <li className="text-xs text-ink-3">选两组 epoch 后运行,结果会并排列出便于试听。</li>}
            </ul>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Grid({ title, rows, cur, loaded, onPick, onDel }: { title: string; rows: WeightEntry[]; cur: string | null; loaded: string | null; onPick: (p: string) => void; onDel: (p: string) => void }) {
  return (
    <div className="mb-3">
      <div className="micro mb-1">{title}</div>
      <div className="flex flex-wrap gap-1">
        {rows.map((w) => {
          const isLoaded = w.path === loaded;
          const isCur = w.path === cur;
          return (
            <div key={w.path} className={cn("group relative flex h-14 w-[72px] flex-col items-center justify-center border text-xs", isCur ? "corner-bracket border-line-2 bg-surface-2" : "border-line-1 bg-surface-0 hover:bg-surface-hover", isLoaded && "border-action")} title={`${w.file} · ${fmtBytes(w.size)}`}>
              <button type="button" onClick={() => onPick(w.path)} className="absolute inset-0" aria-label={w.file} />
              <span className="pointer-events-none font-mono font-bold text-ink">e{w.epoch ?? "?"}</span>
              <span className="pointer-events-none micro">{w.step ? `s${w.step}` : fmtBytes(w.size)}</span>
              {isLoaded && <span aria-hidden className="pointer-events-none absolute left-0 top-0 h-full w-[3px] bg-action" />}
              {!isLoaded && <button type="button" aria-label="删除" onClick={(e) => { e.stopPropagation(); if (confirm(`删除 ${w.file}?`)) onDel(w.path); }} className="absolute right-0.5 top-0.5 hidden text-ink-3 hover:text-danger group-hover:block"><Trash2 size={10} /></button>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AbPicker({ weights, onRun, busy }: { weights: WeightEntry[]; onRun: (pairs: { label: string; gpt: string; sovits: string }[]) => void; busy: boolean }) {
  const [a, setA] = useState(""), [b, setB] = useState("");
  const sov = weights.filter((w) => w.kind === "sovits");
  const gpt = weights.filter((w) => w.kind === "gpt");
  const parse = (v: string) => {
    const e = Number(v);
    const s = sov.find((w) => w.epoch === e), g = gpt.find((w) => w.epoch === e) ?? gpt.at(-1);
    return s && g ? { label: `e${e}`, gpt: g.path, sovits: s.path } : null;
  };
  const pa = parse(a), pb = parse(b);
  return (
    <div className="flex items-center gap-2">
      <Input placeholder="epoch A" value={a} onChange={(e) => setA(e.target.value)} className="w-24 font-mono" />
      <span className="micro">vs</span>
      <Input placeholder="epoch B" value={b} onChange={(e) => setB(e.target.value)} className="w-24 font-mono" />
      <Button variant="primary" icon={<Sparkles size={14} />} className="ml-auto h-9" disabled={!pa || !pb} loading={busy} onClick={() => pa && pb && onRun([pa, pb])}>对比</Button>
      <span className="sr-only"><Upload /></span>
    </div>
  );
}

function RvcSection() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["rvc-models"], queryFn: () => api<RvcModels>("/rvc/models") });
  const [jobId, setJobId] = useState<string | null>(null);
  const exp = useMutation({
    mutationFn: (b: { exp: string; ckpt: string; name: string }) => api<{ file: string }>("/rvc/export", { method: "POST", json: { ...b, info: `${b.exp} ${b.ckpt}` } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["rvc-models"] }),
  });
  const idx = useMutation({
    mutationFn: (exp: string) => api<{ id: string }>(`/rvc/index?exp=${encodeURIComponent(exp)}`, { method: "POST" }),
    onSuccess: (j) => setJobId(j.id),
  });
  const d = q.data;
  if (!d) return null;
  return (
    <section>
      <div className="mb-2 flex items-center gap-3">
        <span className="section-head text-ink">RVC 音色模型</span>
        <Chip tone="special">{d.models.length} 模型</Chip>
        <Chip>{d.indices.length} 索引</Chip>
      </div>
      <div className="mb-3 flex flex-wrap gap-1">
        {d.models.map((m) => (
          <div key={m.file} className="flex h-14 min-w-[110px] flex-col items-center justify-center border border-line-1 bg-surface-0 px-2 text-xs" title={m.file}>
            <span className="font-mono font-bold text-ink">{m.name}</span>
            <span className="micro">{fmtBytes(m.size)}</span>
          </div>
        ))}
        {d.models.length === 0 && <span className="text-xs text-ink-3">还没有导出的 RVC 模型。从下面的训练 checkpoint 导出。</span>}
      </div>
      {d.experiments.map((e) => (
        <div key={e.exp} className="mb-2 border border-line-1 bg-surface-0 p-2">
          <div className="mb-1 flex items-center gap-2">
            <span className="font-mono text-xs text-ink">{e.exp}</span>
            <Chip tone={e.has_index ? "success" : "default"}>{e.has_index ? "索引已建" : "无索引"}</Chip>
            <Button variant="ghost" size="sm" icon={<ListTree size={12} />} className="ml-auto" disabled={!e.has_features} loading={idx.isPending} onClick={() => idx.mutate(e.exp)}>{e.has_index ? "重建索引" : "建索引"}</Button>
          </div>
          <div className="flex flex-wrap gap-1">
            {e.checkpoints.map((c) => (
              <Button key={c.file} variant="secondary" size="sm" icon={<Wand2 size={12} />} loading={exp.isPending && exp.variables?.ckpt === c.file} onClick={() => exp.mutate({ exp: e.exp, ckpt: c.file, name: e.exp })}>
                导出 s{c.step} → {e.exp}.pth
              </Button>
            ))}
            {e.checkpoints.length === 0 && <span className="micro">没有 G_*.pth checkpoint</span>}
          </div>
          {exp.isError && <span className="text-xs text-danger">{(exp.error as Error).message}</span>}
        </div>
      ))}
      {jobId && <JobLog jobId={jobId} compact className="mt-2 max-h-40" onDone={() => qc.invalidateQueries({ queryKey: ["rvc-models"] })} />}
    </section>
  );
}
