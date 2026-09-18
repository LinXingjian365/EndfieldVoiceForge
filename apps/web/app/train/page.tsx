"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Check, Upload, FlaskConical } from "lucide-react";
import { api, type Job, type WeightEntry } from "@/lib/api";
import { useStudio } from "@/lib/store";
import { Panel, Chip, CoordinateTag, GhostWord, ScanDivider } from "@/components/ef";
import { Button } from "@/components/ef/button";
import { Field, Input, Select, Slider, Switch } from "@/components/ef/form";
import { JobLog } from "@/components/job-log";
import { AreaChart } from "@/components/area-chart";
import { cn, fmtBytes } from "@/lib/utils";

interface TrainStatus { exp: string; version: string; format: Record<string, boolean>; running: Record<string, string>; weights: WeightEntry[]; expDir: string }
interface Curves { s2: Record<string, [number, number][]>; s1: Record<string, [number, number][]> }

const VERSIONS = ["v2", "v2Pro", "v2ProPlus", "v4", "v3", "v1"];
const FORMAT_ORDER: Record<string, string[]> = { default: ["1a", "1b", "1c"], pro: ["1a", "1b", "1sv", "1c"] };
const STAGE_LABEL: Record<string, string> = { "1a": "文本 · BERT", "1b": "HuBERT · 32k", "1sv": "说话人向量", "1c": "语义 token" };

export default function TrainPage() {
  const { characterId, character } = useStudio();
  const qc = useQueryClient();
  const [exp, setExp] = useState(character?.weights.exp ?? "typhoea");
  const [version, setVersion] = useState(character?.weights.version ?? "v2");
  useEffect(() => { if (character) { setExp(character.weights.exp); setVersion(character.weights.version); } }, [character?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const status = useQuery({ queryKey: ["train-status", exp, version], queryFn: () => api<TrainStatus>(`/training/${exp}/status?version=${version}`), refetchInterval: 4000 });
  const curves = useQuery({ queryKey: ["curves", exp, version], queryFn: () => api<Curves>(`/training/${exp}/curves?version=${version}`), refetchInterval: 8000 });
  const [jobId, setJobId] = useState<string | null>(null);
  const [s2, setS2] = useState({ batch_size: 1, epochs: 8, save_every: 1, text_low_lr_rate: 0.4, grad_ckpt: true, lora_rank: 0, resume: true });
  const [s1, setS1] = useState({ batch_size: 1, epochs: 15, save_every: 1, if_dpo: false });

  const stages = FORMAT_ORDER[version.startsWith("v2Pro") ? "pro" : "default"];
  const fmt = status.data?.format ?? {};
  const running = status.data?.running ?? {};
  const anyRunning = Object.keys(running).length > 0;

  const runFormat = useMutation({
    mutationFn: (stage: string) => api<Job>("/training/format", { method: "POST", json: { character: characterId, exp, version, stages: [stage] } }),
    onSuccess: (j) => { setJobId(j.id); qc.invalidateQueries({ queryKey: ["train-status"] }); },
  });
  const merge = useMutation({ mutationFn: (stage: string) => api(`/training/format/${stage}/merge?exp=${exp}`, { method: "POST" }), onSuccess: () => qc.invalidateQueries({ queryKey: ["train-status"] }) });
  const runS2 = useMutation({ mutationFn: () => api<Job>("/training/s2", { method: "POST", json: { exp, version, ...s2 } }), onSuccess: (j) => { setJobId(j.id); qc.invalidateQueries({ queryKey: ["train-status"] }); } });
  const runS1 = useMutation({ mutationFn: () => api<Job>("/training/s1", { method: "POST", json: { exp, version, ...s1 } }), onSuccess: (j) => { setJobId(j.id); qc.invalidateQueries({ queryKey: ["train-status"] }); } });
  const load = useMutation({ mutationFn: (b: { gpt: string; sovits: string }) => api("/models/load", { method: "POST", json: { ...b, version, character: characterId } }), onSuccess: () => qc.invalidateQueries({ queryKey: ["status"] }) });

  // 阶段完成后自动 merge 分片文件
  const onJobDone = (j: Job) => {
    if (j.status === "done" && j.kind.startsWith("train:format:")) merge.mutate(j.meta.stage as string);
  };

  const s2Curve = useMemo(() => curves.data?.s2["loss/g/total"] ?? [], [curves.data]);
  const s2D = useMemo(() => curves.data?.s2["loss/d/total"] ?? [], [curves.data]);
  const s1Curve = useMemo(() => curves.data?.s1["total_loss_step"] ?? curves.data?.s1["total_loss_epoch"] ?? [], [curves.data]);
  const s1Acc = useMemo(() => curves.data?.s1["top_3_acc_step"] ?? [], [curves.data]);
  const gpts = (status.data?.weights ?? []).filter((w) => w.kind === "gpt");
  const sovs = (status.data?.weights ?? []).filter((w) => w.kind === "sovits");
  const allDone = stages.every((s) => fmt[s]);

  return (
    <div className="grid h-full grid-cols-[minmax(280px,0.8fr)_minmax(0,1.6fr)] grid-rows-[minmax(0,1fr)_minmax(0,0.8fr)] gap-2 p-2">
      {/* 左上:实验配置 */}
      <Panel title="实验" en="EXPERIMENT" className="row-span-2">
        <div className="flex h-full flex-col gap-3 overflow-auto p-3">
          <div className="grid grid-cols-[1fr_auto] gap-2">
            <Field label="实验名 exp"><Input value={exp} onChange={(e) => setExp(e.target.value)} /></Field>
            <Field label="版本"><Select value={version} onChange={setVersion} options={VERSIONS.map((v) => ({ value: v, label: v }))} className="w-28" /></Field>
          </div>
          <p className="micro normal-case tracking-normal">数据:{character?.dataset.list}</p>

          <ScanDivider label="1 · FORMAT" />
          <ol className="flex flex-col gap-1">
            {stages.map((s) => {
              const r = Object.entries(running).find(([k]) => k === `train:format:${s}`)?.[1];
              return (
                <li key={s} className={cn("flex items-center gap-2 border border-line-1 bg-surface-0 px-2 py-1.5", r && "border-action")}>
                  <span className={cn("flex h-5 w-5 items-center justify-center text-[10px] font-bold", fmt[s] ? "bg-ink text-canvas" : "bg-surface-2 text-ink-3")}>{fmt[s] ? <Check size={12} /> : s}</span>
                  <span className="text-xs text-ink">{STAGE_LABEL[s]}</span>
                  {r ? <Button size="sm" variant="ghost" className="ml-auto" onClick={() => setJobId(r)}>日志</Button>
                    : <Button size="sm" variant={fmt[s] ? "ghost" : "action"} className="ml-auto" icon={<Play size={10} />} disabled={anyRunning} onClick={() => runFormat.mutate(s)}>{fmt[s] ? "重跑" : "运行"}</Button>}
                </li>
              );
            })}
          </ol>

          <ScanDivider label="2 · SoVITS (s2)" />
          <Field label="epochs" value={s2.epochs}><Slider value={s2.epochs} onChange={(v) => setS2({ ...s2, epochs: v })} min={1} max={50} step={1} /></Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="batch" value={s2.batch_size}><Slider value={s2.batch_size} onChange={(v) => setS2({ ...s2, batch_size: v })} min={1} max={8} step={1} /></Field>
            <Field label="save every" value={s2.save_every}><Slider value={s2.save_every} onChange={(v) => setS2({ ...s2, save_every: v })} min={1} max={10} step={1} /></Field>
          </div>
          <Field label="text_low_lr_rate" value={s2.text_low_lr_rate.toFixed(2)}><Slider value={s2.text_low_lr_rate} onChange={(v) => setS2({ ...s2, text_low_lr_rate: v })} min={0.2} max={0.6} step={0.05} /></Field>
          <div className="flex items-center justify-between text-xs text-ink-2"><span>梯度检查点(省显存)</span><Switch checked={s2.grad_ckpt} onChange={(v) => setS2({ ...s2, grad_ckpt: v })} /></div>
          <div className="flex items-center justify-between text-xs text-ink-2"><span>从上次断点续训</span><Switch checked={s2.resume} onChange={(v) => setS2({ ...s2, resume: v })} /></div>
          {(version === "v3" || version === "v4") && <Field label="LoRA rank" value={s2.lora_rank}><Slider value={s2.lora_rank} onChange={(v) => setS2({ ...s2, lora_rank: v })} min={0} max={128} step={16} /></Field>}
          <Button variant="action" icon={<FlaskConical size={14} />} disabled={!allDone || anyRunning} loading={runS2.isPending} onClick={() => runS2.mutate()}>开始 SoVITS 训练</Button>

          <ScanDivider label="3 · GPT (s1)" />
          <Field label="epochs" value={s1.epochs}><Slider value={s1.epochs} onChange={(v) => setS1({ ...s1, epochs: v })} min={1} max={50} step={1} /></Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="batch" value={s1.batch_size}><Slider value={s1.batch_size} onChange={(v) => setS1({ ...s1, batch_size: v })} min={1} max={8} step={1} /></Field>
            <Field label="save every" value={s1.save_every}><Slider value={s1.save_every} onChange={(v) => setS1({ ...s1, save_every: v })} min={1} max={10} step={1} /></Field>
          </div>
          <div className="flex items-center justify-between text-xs text-ink-2"><span>DPO 训练(更吃显存)</span><Switch checked={s1.if_dpo} onChange={(v) => setS1({ ...s1, if_dpo: v })} /></div>
          <Button variant="action" icon={<FlaskConical size={14} />} disabled={!allDone || anyRunning} loading={runS1.isPending} onClick={() => runS1.mutate()}>开始 GPT 训练</Button>
          {(runS1.isError || runS2.isError || runFormat.isError) && <span className="text-xs text-danger">{((runS1.error ?? runS2.error ?? runFormat.error) as Error).message}</span>}
        </div>
      </Panel>

      {/* 右上:阶段带 + 曲线 */}
      <Panel title="曲线" en="LOSS CURVES" action={<span className="micro">{curves.isFetching ? "refreshing" : "auto 8s"}</span>}>
        <div className="relative grid h-full grid-rows-2 gap-2 overflow-hidden p-3">
          {!anyRunning && s2Curve.length > 0 && <GhostWord size={96} className="right-4 top-2">TRAINED</GhostWord>}
          <StageRow title="SoVITS · s2" tag="loss/g/total" last={s2Curve.at(-1)} running={!!running["train:s2"]} onLog={() => setJobId(running["train:s2"])}>
            <AreaChart height={90} series={[{ name: "G", points: s2Curve, tone: "data" }, { name: "D", points: s2D, tone: "muted" }]} />
          </StageRow>
          <StageRow title="GPT · s1" tag="total_loss" last={s1Curve.at(-1)} extra={s1Acc.at(-1) ? `top3 acc ${(s1Acc.at(-1)![1] * 100).toFixed(1)}%` : undefined} running={!!running["train:s1"]} onLog={() => setJobId(running["train:s1"])}>
            <AreaChart height={90} series={[{ name: "loss", points: s1Curve, tone: "data" }]} />
          </StageRow>
        </div>
      </Panel>

      {/* 右下:日志 + 检查点 */}
      <div className="grid min-h-0 grid-cols-[minmax(0,1fr)_minmax(320px,0.9fr)] gap-2">
        <Panel title="日志" en="JOB LOG">
          {jobId ? <JobLog jobId={jobId} onDone={onJobDone} className="h-full border-0" /> : <div className="flex h-full items-center justify-center text-xs text-ink-3">运行任意阶段后在此显示实时输出</div>}
        </Panel>
        <Panel title="检查点" en="CHECKPOINTS" action={<span className="micro">{gpts.length} gpt · {sovs.length} sovits</span>}>
          <div className="h-full overflow-auto">
            <CkptList title="SoVITS" rows={sovs} onLoad={(w) => load.mutate({ sovits: w.path, gpt: gpts.at(-1)?.path ?? "" })} />
            <CkptList title="GPT" rows={gpts} onLoad={(w) => load.mutate({ gpt: w.path, sovits: sovs.at(-1)?.path ?? "" })} />
          </div>
        </Panel>
      </div>
    </div>
  );
}

function StageRow({ title, tag, last, extra, running, onLog, children }: { title: string; tag: string; last?: [number, number]; extra?: string; running: boolean; onLog: () => void; children: React.ReactNode }) {
  return (
    <div className={cn("grid min-h-0 grid-cols-[140px_minmax(0,1fr)] gap-3 border border-line-1 bg-surface-0", running && "border-action")}>
      <div className="flex flex-col justify-between border-r border-line-1 p-2">
        <div>
          <div className="text-sm text-ink">{title}</div>
          <div className="micro">{tag}</div>
        </div>
        <div className="flex flex-col gap-1">
          {last && <CoordinateTag label="step" value={last[0]} />}
          {last && <CoordinateTag label="loss" value={last[1].toFixed(3)} tone="data" />}
          {extra && <span className="micro text-gain">{extra}</span>}
          {running ? <Chip tone="action" className="w-fit cursor-pointer" >RUNNING</Chip> : null}
          {running && <button type="button" onClick={onLog} className="micro text-left hover:text-ink">查看日志 →</button>}
        </div>
      </div>
      <div className="min-h-0 p-2">{children}</div>
    </div>
  );
}

function CkptList({ title, rows, onLoad }: { title: string; rows: WeightEntry[]; onLoad: (w: WeightEntry) => void }) {
  return (
    <div>
      <div className="section-head sticky top-0 bg-surface-1 px-3 py-1.5 text-ink">{title}</div>
      <ul>
        {rows.slice().reverse().map((w) => (
          <li key={w.path} className="flex items-center gap-2 border-b border-line-1 px-3 py-1.5 text-xs">
            <span className="font-mono text-ink">e{w.epoch}{w.step ? ` · s${w.step}` : ""}</span>
            <span className="micro">{fmtBytes(w.size)}</span>
            <span className="micro ml-auto">{new Date(w.mtime * 1000).toLocaleTimeString()}</span>
            <Button size="sm" variant="ghost" icon={<Upload size={11} />} onClick={() => onLoad(w)}>加载</Button>
          </li>
        ))}
        {rows.length === 0 && <li className="px-3 py-2 text-xs text-ink-3">无</li>}
      </ul>
    </div>
  );
}
