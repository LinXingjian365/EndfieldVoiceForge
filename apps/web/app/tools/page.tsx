"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Play, Scissors, Waves, Mic, SlidersHorizontal } from "lucide-react";
import { api, type Job } from "@/lib/api";
import { Panel, ScanDivider } from "@/components/ef";
import { Button } from "@/components/ef/button";
import { Field, Input, Select, Slider } from "@/components/ef/form";
import { JobLog } from "@/components/job-log";

export default function ToolsPage() {
  const [jobs, setJobs] = useState<Record<string, string | null>>({});
  const setJob = (k: string, id: string) => setJobs((j) => ({ ...j, [k]: id }));

  return (
    <div className="grid h-full grid-cols-2 grid-rows-2 gap-2 p-2">
      <ToolCard k="uvr5" title="UVR5 人声分离" en="VOCAL / INST" icon={<Waves size={16} />} jobId={jobs.uvr5 ?? null}>
        <Uvr5Form onJob={(id) => setJob("uvr5", id)} />
      </ToolCard>
      <ToolCard k="slice" title="音频切片" en="SLICER" icon={<Scissors size={16} />} jobId={jobs.slice ?? null}>
        <SliceForm onJob={(id) => setJob("slice", id)} />
      </ToolCard>
      <ToolCard k="denoise" title="降噪" en="DENOISE" icon={<SlidersHorizontal size={16} />} jobId={jobs.denoise ?? null}>
        <DenoiseForm onJob={(id) => setJob("denoise", id)} />
      </ToolCard>
      <ToolCard k="asr" title="批量 ASR 打标" en="ASR · DIRECTORY" icon={<Mic size={16} />} jobId={jobs.asr ?? null}>
        <AsrForm onJob={(id) => setJob("asr", id)} />
      </ToolCard>
    </div>
  );
}

function ToolCard({ title, en, icon, jobId, children }: { k: string; title: string; en: string; icon: React.ReactNode; jobId: string | null; children: React.ReactNode }) {
  return (
    <Panel title={title} en={en} action={<span className="text-ink-2">{icon}</span>}>
      <div className="grid h-full grid-rows-[auto_minmax(0,1fr)] gap-2 p-3">
        {children}
        {jobId ? <JobLog jobId={jobId} /> : <div className="tex-grid flex items-center justify-center border border-dashed border-line-1 text-xs text-ink-3">日志</div>}
      </div>
    </Panel>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-2">{children}</div>;
}

function Uvr5Form({ onJob }: { onJob: (id: string) => void }) {
  const models = useQuery({ queryKey: ["uvr5-models"], queryFn: () => api<string[]>("/tools/uvr5/models") });
  const [f, setF] = useState({ model: "", input: "outputs/uploads", out_vocal: "outputs/uvr5/vocal", out_inst: "outputs/uvr5/inst", agg: 10 });
  const m = useMutation({ mutationFn: () => api<Job>("/tools/uvr5", { method: "POST", json: f }), onSuccess: (j) => onJob(j.id) });
  const opts = (models.data ?? []).map((v) => ({ value: v, label: v }));
  return (
    <div className="flex flex-col gap-2">
      {opts.length === 0 ? (
        <p className="text-xs text-notify">tools/uvr5/uvr5_weights/ 里没有模型。从 GPT-SoVITS 预训练包放入 HP2/HP5/roformer 权重后可用。</p>
      ) : (
        <Field label="模型"><Select value={f.model || opts[0].value} onChange={(v) => setF({ ...f, model: v })} options={opts} /></Field>
      )}
      <Row>
        <Field label="输入(文件或目录)"><Input value={f.input} onChange={(e) => setF({ ...f, input: e.target.value })} /></Field>
        <Field label="人声比例 agg" value={f.agg}><Slider value={f.agg} onChange={(v) => setF({ ...f, agg: v })} min={0} max={20} step={1} /></Field>
      </Row>
      <Row>
        <Field label="人声输出"><Input value={f.out_vocal} onChange={(e) => setF({ ...f, out_vocal: e.target.value })} /></Field>
        <Field label="伴奏输出"><Input value={f.out_inst} onChange={(e) => setF({ ...f, out_inst: e.target.value })} /></Field>
      </Row>
      <Button variant="action" icon={<Play size={14} />} onClick={() => m.mutate()} disabled={opts.length === 0} loading={m.isPending} className="self-start">运行</Button>
      {m.isError && <span className="text-xs text-danger">{(m.error as Error).message}</span>}
    </div>
  );
}

function SliceForm({ onJob }: { onJob: (id: string) => void }) {
  const [f, setF] = useState({ input: "outputs/uploads", output: "outputs/slices", threshold: -34, min_length: 4000, min_interval: 300, hop_size: 10, max_sil_kept: 500, max_amp: 0.9, alpha: 0.25 });
  const m = useMutation({ mutationFn: () => api<Job>("/tools/slice", { method: "POST", json: f }), onSuccess: (j) => onJob(j.id) });
  return (
    <div className="flex flex-col gap-2">
      <Row>
        <Field label="输入"><Input value={f.input} onChange={(e) => setF({ ...f, input: e.target.value })} /></Field>
        <Field label="输出目录"><Input value={f.output} onChange={(e) => setF({ ...f, output: e.target.value })} /></Field>
      </Row>
      <Row>
        <Field label="静音阈值 dB" value={f.threshold}><Slider value={f.threshold} onChange={(v) => setF({ ...f, threshold: v })} min={-60} max={-10} step={1} /></Field>
        <Field label="最短片段 ms" value={f.min_length}><Slider value={f.min_length} onChange={(v) => setF({ ...f, min_length: v })} min={500} max={15000} step={100} /></Field>
      </Row>
      <Row>
        <Field label="最小间隔 ms" value={f.min_interval}><Slider value={f.min_interval} onChange={(v) => setF({ ...f, min_interval: v })} min={50} max={2000} step={10} /></Field>
        <Field label="保留静音 ms" value={f.max_sil_kept}><Slider value={f.max_sil_kept} onChange={(v) => setF({ ...f, max_sil_kept: v })} min={0} max={2000} step={10} /></Field>
      </Row>
      <Button variant="action" icon={<Play size={14} />} onClick={() => m.mutate()} loading={m.isPending} className="self-start">运行</Button>
      {m.isError && <span className="text-xs text-danger">{(m.error as Error).message}</span>}
    </div>
  );
}

function DenoiseForm({ onJob }: { onJob: (id: string) => void }) {
  const [f, setF] = useState({ input: "outputs/slices", output: "outputs/denoised", precision: "float16" });
  const m = useMutation({ mutationFn: () => api<Job>("/tools/denoise", { method: "POST", json: f }), onSuccess: (j) => onJob(j.id) });
  return (
    <div className="flex flex-col gap-2">
      <Row>
        <Field label="输入目录"><Input value={f.input} onChange={(e) => setF({ ...f, input: e.target.value })} /></Field>
        <Field label="输出目录"><Input value={f.output} onChange={(e) => setF({ ...f, output: e.target.value })} /></Field>
      </Row>
      <Field label="精度"><Select value={f.precision} onChange={(v) => setF({ ...f, precision: v })} options={[{ value: "float16", label: "float16" }, { value: "float32", label: "float32" }]} className="w-32" /></Field>
      <Button variant="action" icon={<Play size={14} />} onClick={() => m.mutate()} loading={m.isPending} className="self-start">运行</Button>
      {m.isError && <span className="text-xs text-danger">{(m.error as Error).message}</span>}
    </div>
  );
}

function AsrForm({ onJob }: { onJob: (id: string) => void }) {
  const [f, setF] = useState({ input: "datasets/typhoea_train", output: "datasets/typhoea_train_asr", lang: "zh", backend: "funasr", precision: "float32" });
  const m = useMutation({ mutationFn: () => api<Job>("/tools/asr", { method: "POST", json: f }), onSuccess: (j) => onJob(j.id) });
  return (
    <div className="flex flex-col gap-2">
      <Row>
        <Field label="输入目录(wav)"><Input value={f.input} onChange={(e) => setF({ ...f, input: e.target.value })} /></Field>
        <Field label="输出目录(.list)"><Input value={f.output} onChange={(e) => setF({ ...f, output: e.target.value })} /></Field>
      </Row>
      <Row>
        <Field label="后端"><Select value={f.backend} onChange={(v) => setF({ ...f, backend: v })} options={[{ value: "funasr", label: "Fun-ASR-Nano(中文推荐)" }, { value: "whisper", label: "Faster Whisper" }]} /></Field>
        <Field label="语种"><Select value={f.lang} onChange={(v) => setF({ ...f, lang: v })} options={["zh", "en", "ja", "ko", "yue", "auto"].map((v) => ({ value: v, label: v }))} /></Field>
      </Row>
      <ScanDivider />
      <p className="micro normal-case tracking-normal">输出 <span className="text-ink">&lt;目录名&gt;.list</span>;之后在数据页运行「规范列表」。</p>
      <Button variant="action" icon={<Play size={14} />} onClick={() => m.mutate()} loading={m.isPending} className="self-start">运行</Button>
      {m.isError && <span className="text-xs text-danger">{(m.error as Error).message}</span>}
    </div>
  );
}
