"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { Upload, Scissors, ListMusic, Wand2, X } from "lucide-react";
import { api, assetUrl, fileUrl, API_BASE } from "@/lib/api";
import { useStudio } from "@/lib/store";
import { Button } from "@/components/ef/button";
import { Textarea, Field, Select } from "@/components/ef/form";
import { Chip, ScanDivider } from "@/components/ef";
import { Waveform } from "./waveform";
import { cn } from "@/lib/utils";

export interface RefState {
  path: string;
  text: string;
  lang: string;
  label?: string;
}

interface Sample { path: string; file: string; text: string }
interface Segment { file: string; path: string; duration: number; text: string }

const LANGS = [
  { value: "zh", label: "中文" },
  { value: "en", label: "English" },
  { value: "ja", label: "日本語" },
  { value: "ko", label: "한국어" },
  { value: "yue", label: "粤语" },
  { value: "all_zh", label: "全中文" },
  { value: "auto", label: "自动" },
];

/** 参考音频区:头像章 + 波形 + 来源(上传 / 数据集 / 长音频切分) + 参考文本(ASR) */
export function RefPicker({ value, onChange }: { value: RefState; onChange: (v: RefState) => void }) {
  const { character } = useStudio();
  const [busy, setBusy] = useState<"asr" | "upload" | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function upload(f: File) {
    setBusy("upload");
    setErr(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const r = await api<{ path: string; name: string }>("/upload", { method: "POST", body: fd });
      onChange({ ...value, path: r.path, label: r.name, text: "" });
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(null);
    }
  }

  async function recognize() {
    if (!value.path) return;
    setBusy("asr");
    setErr(null);
    try {
      const r = await api<{ text: string }>("/asr", { method: "POST", json: { path: value.path, lang: value.lang === "auto" ? "zh" : value.lang } });
      onChange({ ...value, text: r.text });
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex h-full flex-col gap-3 p-3">
      <div className="flex items-center gap-3">
        {character && (
          <img src={assetUrl(character.art.avatar)} alt="" className="rounded-full h-12 w-12 shrink-0 object-cover ring-2 ring-operator" />
        )}
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm text-ink">{value.label ?? value.path.split("/").pop() ?? "未选择参考音频"}</div>
          <div className="micro truncate">{value.path || "REF AUDIO · 3–10s"}</div>
        </div>
      </div>

      {value.path ? (
        <Waveform url={fileUrl(value.path)} height={40} className="border border-line-1 bg-surface-0 px-2 py-1" />
      ) : (
        <div className="tex-hatch flex h-[58px] items-center justify-center border border-dashed border-line-2 text-xs text-ink-3">
          先选一段参考音频
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <label className="contents">
          <input type="file" accept="audio/*" className="sr-only" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
          <Button variant="secondary" size="sm" icon={<Upload size={14} />} loading={busy === "upload"} type="button" onClick={(e) => (e.currentTarget.previousElementSibling as HTMLInputElement)?.click()}>
            上传
          </Button>
        </label>
        <SamplePicker onPick={(s) => onChange({ ...value, path: s.path, text: s.text, label: s.file })} />
        <SliceDialog onPick={(s) => onChange({ ...value, path: s.path, text: s.text, label: s.file })} />
      </div>

      <ScanDivider label="PROMPT TEXT" />

      <Field label="参考音频的文本" className="min-h-0 flex-1">
        <Textarea
          rows={4}
          value={value.text}
          onChange={(e) => onChange({ ...value, text: e.target.value })}
          placeholder="参考音频说了什么;可点「识别」自动填入"
          className="h-full"
        />
      </Field>
      <div className="flex items-center gap-2">
        <Select value={value.lang} onChange={(lang) => onChange({ ...value, lang })} options={LANGS} className="w-28" ariaLabel="参考语种" />
        <Button variant="secondary" size="sm" icon={<Wand2 size={14} />} onClick={recognize} loading={busy === "asr"} disabled={!value.path}>
          识别参考文本
        </Button>
      </div>
      {err && <p className="text-xs text-danger">{err}</p>}
    </div>
  );
}

/* ---------- 从数据集挑 ---------- */
function SamplePicker({ onPick }: { onPick: (s: Sample) => void }) {
  const { characterId } = useStudio();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const samples = useQuery({ queryKey: ["ref-samples", characterId], queryFn: () => api<Sample[]>(`/ref/samples/${characterId}?limit=300`), enabled: open });
  const list = (samples.data ?? []).filter((s) => !q || s.text.includes(q) || s.file.includes(q));
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button variant="secondary" size="sm" icon={<ListMusic size={14} />}>数据集</Button>
      </Dialog.Trigger>
      <DialogFrame title="从训练集选择参考" en="DATASET SAMPLES">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="搜索台词…" className="h-9 w-full border border-line-2 bg-surface-2 px-3 text-sm" />
        <ul className="mt-2 max-h-[60vh] overflow-auto">
          {list.map((s) => (
            <li key={s.path}>
              <button
                type="button"
                onClick={() => { onPick(s); setOpen(false); }}
                className="flex w-full items-start gap-3 border-b border-line-1 px-2 py-2 text-left hover:bg-surface-hover"
              >
                <span className="micro w-32 shrink-0 truncate pt-0.5">{s.file}</span>
                <span className="text-sm text-ink">{s.text}</span>
              </button>
            </li>
          ))}
          {samples.isLoading && <li className="p-3 text-xs text-ink-3">加载中…</li>}
          {!samples.isLoading && list.length === 0 && <li className="p-3 text-xs text-ink-3">没有匹配的样本</li>}
        </ul>
      </DialogFrame>
    </Dialog.Root>
  );
}

/* ---------- 长音频切分 ---------- */
function SliceDialog({ onPick }: { onPick: (s: Segment) => void }) {
  const [open, setOpen] = useState(false);
  const [segs, setSegs] = useState<Segment[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function run(f: File) {
    setBusy(true); setErr(null); setSegs([]);
    try {
      const fd = new FormData(); fd.append("file", f);
      const up = await api<{ path: string }>("/upload", { method: "POST", body: fd });
      const r = await api<{ segments: Segment[] }>("/ref/slice", { method: "POST", json: { path: up.path, max_dur: 10, min_dur: 1, asr: true } });
      setSegs(r.segments);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <Button variant="secondary" size="sm" icon={<Scissors size={14} />}>长音频切分</Button>
      </Dialog.Trigger>
      <DialogFrame title="长参考音频切分" en="SLICE ≤10s + ASR" wide>
        <p className="mb-2 text-xs text-ink-2">上传超过 10 秒的音频,按静音切成 ≤10s 片段并逐段识别文本。首次运行需加载 ASR 模型。</p>
        <label className="mb-3 flex h-14 cursor-pointer items-center justify-center border border-dashed border-line-2 text-sm text-ink-2 hover:border-action hover:text-ink">
          <input type="file" accept="audio/*" className="sr-only" onChange={(e) => e.target.files?.[0] && run(e.target.files[0])} />
          {busy ? "切分与识别中…" : "选择音频文件"}
        </label>
        {err && <p className="mb-2 text-xs text-danger">{err}</p>}
        <ul className="max-h-[55vh] overflow-auto">
          {segs.map((s, i) => (
            <li key={s.path} className="grid grid-cols-[32px_minmax(0,1.2fr)_minmax(0,1fr)_auto] items-center gap-3 border-b border-line-1 py-2">
              <span className="micro bg-ink px-1.5 py-0.5 text-center text-action">{String(i + 1).padStart(2, "0")}</span>
              <Waveform url={fileUrl(s.path)} height={28} compact />
              <span className="truncate text-sm text-ink" title={s.text}>{s.text || "—"}</span>
              <div className="flex items-center gap-2">
                <Chip>{s.duration.toFixed(1)}s</Chip>
                <Button size="sm" variant="action" onClick={() => { onPick(s); setOpen(false); }}>用作参考</Button>
              </div>
            </li>
          ))}
        </ul>
        {segs.length > 0 && <p className="micro mt-2">saved to outputs/ref_slices/</p>}
      </DialogFrame>
    </Dialog.Root>
  );
}

export function DialogFrame({ title, en, children, wide }: { title: string; en?: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60 backdrop-blur-[2px]" />
      <Dialog.Content className={cn("fixed left-1/2 top-1/2 z-50 w-[92vw] -translate-x-1/2 -translate-y-1/2 border border-line-2 bg-surface-1 p-4 shadow-2xl focus:outline-none", wide ? "max-w-4xl" : "max-w-2xl")}>
        <div className="mb-3 flex items-center gap-3">
          <Dialog.Title className="section-head text-ink">{title}</Dialog.Title>
          {en && <span className="micro">{en}</span>}
          <Dialog.Close className="ml-auto text-ink-2 hover:text-ink" aria-label="关闭"><X size={16} /></Dialog.Close>
        </div>
        {children}
      </Dialog.Content>
    </Dialog.Portal>
  );
}

export { API_BASE };
