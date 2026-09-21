"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles, Star, Download, Trash2, RefreshCw, ChevronDown, Wand2 } from "lucide-react";
import { api, apiBlob, fileUrl, DEFAULT_TTS, type LibraryItem, type TtsParams, type WeightEntry, type Status, type RvcModels, type Job } from "@/lib/api";
import { useStudio } from "@/lib/store";
import { Panel, Chip, CoordinateTag, FrequencyBars, ScanDivider, WarningBand } from "@/components/ef";
import { Button } from "@/components/ef/button";
import { Field, Slider, Switch, Select, Textarea } from "@/components/ef/form";
import { HelpTip } from "@/components/ef/help-tip";
import { RefPicker, type RefState } from "@/components/audio/ref-picker";
import { Waveform } from "@/components/audio/waveform";
import { JobLog } from "@/components/job-log";
import { cn } from "@/lib/utils";

const CUT = [
  { value: "cut0", label: "不切" },
  { value: "cut1", label: "凑四句一切" },
  { value: "cut2", label: "凑50字一切" },
  { value: "cut3", label: "按中文句号切" },
  { value: "cut4", label: "按英文句号切" },
  { value: "cut5", label: "按标点切" },
];
const LANGS = [
  { value: "zh", label: "中文" },
  { value: "en", label: "English" },
  { value: "ja", label: "日本語" },
  { value: "ko", label: "한국어" },
  { value: "yue", label: "粤语" },
  { value: "all_zh", label: "全中文" },
  { value: "auto", label: "自动" },
];

type Params = Omit<TtsParams, "text" | "ref_audio_path" | "prompt_text" | "prompt_lang">;

export default function SynthPage() {
  const { character, characterId } = useStudio();
  const qc = useQueryClient();
  const [ref, setRef] = useState<RefState>({ path: "", text: "", lang: "zh" });
  const [text, setText] = useState("");
  const [params, setParams] = useState<Params>({ ...DEFAULT_TTS });
  const [advanced, setAdvanced] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const [playingId, setPlayingId] = useState<number | null>(null);

  // 角色切换时填默认参考
  useEffect(() => {
    if (character && !ref.path) {
      setRef({ path: character.defaultRef.audio, text: character.defaultRef.text, lang: character.defaultRef.lang, label: character.defaultRef.audio.split("/").pop() });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [character?.id]);

  const status = useQuery({ queryKey: ["status"], queryFn: () => api<Status>("/status"), refetchInterval: 4000 });
  const models = useQuery({ queryKey: ["models"], queryFn: () => api<{ weights: WeightEntry[] }>("/models") });
  const library = useQuery({ queryKey: ["library", characterId], queryFn: () => api<LibraryItem[]>(`/library?character=${characterId}&limit=50`) });
  const rvcModels = useQuery({ queryKey: ["rvc-models"], queryFn: () => api<RvcModels>("/rvc/models") });
  const rvcModelList = rvcModels.data?.models ?? [];
  const [rvcModelFile, setRvcModelFile] = useState<string | null>(null);
  // 模型加载后若尚未选择,默认匹配角色或取第一个
  useEffect(() => {
    if (!rvcModelFile && rvcModelList.length > 0) {
      const def = rvcModelList.find((m) => m.name === characterId) ?? rvcModelList[0];
      setRvcModelFile(def.file);
    }
  }, [rvcModelList, rvcModelFile, characterId]);
  const rvcModel = rvcModelList.find((m) => m.file === rvcModelFile) ?? null;
  const [rvcRate, setRvcRate] = useState(0.5);
  const [convJobId, setConvJobId] = useState<string | null>(null);
  const rvc = useMutation({
    mutationFn: (id: number) => api<Job>("/rvc/convert", { method: "POST", json: { generation_id: id, model: rvcModel!.file, index_rate: rvcRate } }),
    onSuccess: (j) => setConvJobId(j.id),
    onError: (e) => setLastError((e as Error).message),
  });

  // RVC 转换 job 完成后,把结果写回 library 并刷新列表
  function onRvcDone(j: Job) {
    if (j.status !== "done") { setConvJobId(null); return; }
    api<LibraryItem>("/rvc/finalize", { method: "POST", json: { job_id: j.id } })
      .then(() => qc.invalidateQueries({ queryKey: ["library"] }))
      .catch(() => {})
      .finally(() => setConvJobId(null));
  }

  const gen = useMutation({
    mutationFn: async () => {
      setLastError(null);
      const body: TtsParams & { character: string; save: boolean } = {
        character: characterId,
        text,
        ref_audio_path: ref.path,
        prompt_text: ref.text,
        prompt_lang: ref.lang,
        ...params,
        save: true,
      };
      await apiBlob("/tts", { method: "POST", json: body });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["library"] });
      qc.invalidateQueries({ queryKey: ["status"] });
    },
    onError: (e) => setLastError((e as Error).message),
  });

  const patch = useMutation({
    mutationFn: ({ id, favorite }: { id: number; favorite: boolean }) => api(`/library/${id}`, { method: "PATCH", json: { favorite } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["library"] }),
  });
  const del = useMutation({
    mutationFn: (id: number) => api(`/library/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["library"] }),
  });

  const engine = status.data?.engine;
  const weights = models.data?.weights ?? [];
  const gptOpts = useMemo(() => weights.filter((w) => w.kind === "gpt").map((w) => ({ value: w.path, label: w.file })), [weights]);
  const sovOpts = useMemo(() => weights.filter((w) => w.kind === "sovits").map((w) => ({ value: w.path, label: w.file })), [weights]);
  const load = useMutation({
    mutationFn: (b: { gpt: string; sovits: string }) => api("/models/load", { method: "POST", json: { ...b, version: "v2", character: characterId } }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["status"] }); qc.invalidateQueries({ queryKey: ["models"] }); },
  });

  const canGen = !!ref.path && !!text.trim() && !gen.isPending && !engine?.busy;
  const set = <K extends keyof Params>(k: K, v: Params[K]) => setParams((p) => ({ ...p, [k]: v }));

  return (
    <div className="grid h-full grid-cols-[minmax(300px,0.9fr)_minmax(0,1.6fr)_minmax(280px,0.8fr)] grid-rows-[minmax(0,1fr)_auto] gap-2 p-2">
      {/* 左:参考音频 */}
      <Panel title="参考" en="REFERENCE" className="row-span-1">
        <RefPicker value={ref} onChange={setRef} />
      </Panel>

      {/* 中:文本 + 输出 */}
      <div className="grid min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)] gap-2">
        <Panel title="要合成的文本" en="TARGET TEXT" className="min-w-0" action={
          <div className="flex items-center gap-2">
            <HelpTip k="text_lang" /><Select value={params.text_lang} onChange={(v) => set("text_lang", v)} options={LANGS} className="h-7 w-24 text-xs" ariaLabel="文本语种" />
            <HelpTip k="text_split_method" /><Select value={params.text_split_method} onChange={(v) => set("text_split_method", v)} options={CUT} className="h-7 w-32 text-xs" ariaLabel="切分方式" />
          </div>
        }>
          <Textarea rows={6} value={text} onChange={(e) => setText(e.target.value)} placeholder={`让${character?.name ?? "角色"}说点什么…\n每句换行,合成时按句切分。`} className="h-full border-0 bg-transparent px-4 py-3 text-base" />
        </Panel>

        <Panel title="输出" en="GENERATED" className="min-w-0" action={<span className="micro">{library.data?.length ?? 0} items</span>}>
          <div className="h-full overflow-y-auto overflow-x-hidden">
            {lastError && <WarningBand className="m-2">{lastError}</WarningBand>}
            {convJobId && <JobLog jobId={convJobId} compact className="m-2" onDone={onRvcDone} />}
            {library.data?.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center gap-2 text-ink-3">
                <Sparkles size={24} strokeWidth={1.25} />
                <span className="text-sm">还没有生成记录。填好参考与文本,点下方生成。</span>
              </div>
            )}
            <ul>
              {library.data?.map((g) => (
                <li key={g.id} className={cn("group min-w-0 border-b border-line-1 px-3 py-2", playingId === g.id && "bg-surface-2")}>
                  <div className="mb-1 flex items-center gap-2">
                    <FrequencyBars bars={8} height={14} paused={playingId !== g.id} tone="operator" />
                    <span className="min-w-0 flex-1 truncate text-sm text-ink">{g.text}</span>
                    <span className="ml-auto flex shrink-0 items-center gap-1">
                      <Chip>{g.duration.toFixed(1)}s</Chip>
                      <Chip tone="data">{g.elapsed.toFixed(1)}s</Chip>
                      {g.tags.includes("rvc") && <Chip tone="special">RVC</Chip>}
                      <Chip>seed {g.seed}</Chip>
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Waveform url={fileUrl(g.wav)} height={28} compact className="min-w-0 flex-1" />
                    <button type="button" aria-label="收藏" onClick={() => patch.mutate({ id: g.id, favorite: !g.favorite })} className={cn("text-ink-3 hover:text-action", g.favorite && "text-action")}><Star size={14} fill={g.favorite ? "currentColor" : "none"} /></button>
                    <a href={fileUrl(g.wav)} download aria-label="下载" className="text-ink-3 hover:text-ink"><Download size={14} /></a>
                    <button type="button" aria-label="以此为参考" title="以此为参考" onClick={() => setRef({ path: g.wav, text: g.text, lang: params.text_lang, label: `gen #${g.id}` })} className="text-ink-3 hover:text-ink"><RefreshCw size={14} /></button>
                    {rvcModel && !g.tags.includes("rvc") && <button type="button" aria-label="RVC 精修" title={`RVC 精修 (${rvcModel.name})`} disabled={rvc.isPending || !!convJobId} onClick={() => rvc.mutate(g.id)} className={cn("text-ink-3 hover:text-special disabled:opacity-40", rvc.isPending && rvc.variables === g.id && "text-special animate-pulse")}><Wand2 size={14} /></button>}
                    <button type="button" aria-label="删除" onClick={() => del.mutate(g.id)} className="text-ink-3 hover:text-danger"><Trash2 size={14} /></button>
                  </div>
                  <div className="micro mt-1 truncate">{g.gpt?.split("/").pop()} · {g.sovits?.split("/").pop()} · {g.created_at}</div>
                </li>
              ))}
            </ul>
          </div>
        </Panel>
      </div>

      {/* 右:参数 */}
      <Panel title="参数" en="PARAMS" className="row-span-1">
        <div className="flex h-full flex-col gap-4 overflow-auto p-3">
          <div className="flex flex-col gap-2">
            <span className="micro flex items-center gap-1">WEIGHTS<HelpTip k="gpt_weight" /><HelpTip k="sovits_weight" /></span>
            <Select value={engine?.gpt ?? ""} onChange={(v) => load.mutate({ gpt: v, sovits: engine?.sovits ?? sovOpts[0]?.value })} options={gptOpts} ariaLabel="GPT 权重" className="text-xs" />
            <Select value={engine?.sovits ?? ""} onChange={(v) => load.mutate({ gpt: engine?.gpt ?? gptOpts[0]?.value, sovits: v })} options={sovOpts} ariaLabel="SoVITS 权重" className="text-xs" />
            {load.isPending && <span className="micro text-action-text">loading weights…</span>}
          </div>
          {rvcModelList.length > 0 && (
            <>
              <ScanDivider label="RVC" />
              <div className="flex flex-col gap-2">
                <span className="micro flex items-center gap-1">模型<HelpTip k="rvc_what" /></span>
                <Select value={rvcModel?.file ?? ""} onChange={(v) => setRvcModelFile(v)} options={rvcModelList.map((m) => ({ value: m.file, label: m.name }))} ariaLabel="RVC 模型" className="text-xs" />
              </div>
              <Field label={`索引率 index_rate`} help="rvc_index_rate" hint="输出列表里的魔杖按钮用此模型做音色精修" value={rvcRate.toFixed(2)}><Slider value={rvcRate} onChange={setRvcRate} min={0} max={1} step={0.05} ariaLabel="rvc index rate" /></Field>
            </>
          )}
          <ScanDivider label="SAMPLING" />
          <Field label="top_k" help="top_k" value={params.top_k}><Slider value={params.top_k} onChange={(v) => set("top_k", v)} min={1} max={100} step={1} ariaLabel="top_k" /></Field>
          <Field label="top_p" help="top_p" value={params.top_p.toFixed(2)}><Slider value={params.top_p} onChange={(v) => set("top_p", v)} min={0} max={1} step={0.05} ariaLabel="top_p" /></Field>
          <Field label="temperature" help="temperature" value={params.temperature.toFixed(2)}><Slider value={params.temperature} onChange={(v) => set("temperature", v)} min={0} max={1} step={0.05} ariaLabel="temperature" /></Field>
          <Field label="语速 speed" help="speed_factor" value={params.speed_factor.toFixed(2)}><Slider value={params.speed_factor} onChange={(v) => set("speed_factor", v)} min={0.6} max={1.65} step={0.05} ariaLabel="speed" /></Field>
          <Field label="重复惩罚" help="repetition_penalty" value={params.repetition_penalty.toFixed(2)}><Slider value={params.repetition_penalty} onChange={(v) => set("repetition_penalty", v)} min={0} max={2} step={0.05} ariaLabel="repetition penalty" /></Field>
          <Field label="seed(-1 随机)" help="seed"><input type="number" value={params.seed} onChange={(e) => set("seed", Number(e.target.value))} className="h-8 w-full border border-line-2 bg-surface-2 px-2 font-mono text-xs" /></Field>

          <button type="button" onClick={() => setAdvanced((a) => !a)} className="flex items-center gap-2 text-left micro hover:text-ink">
            <ChevronDown size={12} className={cn("transition-transform", advanced && "rotate-180")} /> ADVANCED
          </button>
          {advanced && (
            <div className="flex flex-col gap-4 border-l-2 border-line-1 pl-3">
              <Field label="句间停顿 fragment_interval" help="fragment_interval" value={params.fragment_interval.toFixed(2)}><Slider value={params.fragment_interval} onChange={(v) => set("fragment_interval", v)} min={0.01} max={1} step={0.01} ariaLabel="fragment interval" /></Field>
              <Field label="batch_size" help="batch_size" value={params.batch_size}><Slider value={params.batch_size} onChange={(v) => set("batch_size", v)} min={1} max={20} step={1} ariaLabel="batch size" /></Field>
              <Field label="batch_threshold" help="batch_threshold" value={params.batch_threshold.toFixed(2)}><Slider value={params.batch_threshold} onChange={(v) => set("batch_threshold", v)} min={0} max={1} step={0.05} ariaLabel="batch threshold" /></Field>
              <div className="flex items-center justify-between text-xs text-ink-2"><span className="flex items-center gap-1">并行推理 parallel_infer<HelpTip k="parallel_infer" /></span><Switch checked={params.parallel_infer} onChange={(v) => set("parallel_infer", v)} ariaLabel="parallel infer" /></div>
              <div className="flex items-center justify-between text-xs text-ink-2"><span className="flex items-center gap-1">分桶 split_bucket<HelpTip k="split_bucket" /></span><Switch checked={params.split_bucket} onChange={(v) => set("split_bucket", v)} ariaLabel="split bucket" /></div>
              <Field label="sample_steps (v3/v4)" help="sample_steps" value={params.sample_steps}><Slider value={params.sample_steps} onChange={(v) => set("sample_steps", v)} min={4} max={64} step={4} ariaLabel="sample steps" /></Field>
              <div className="flex items-center justify-between text-xs text-ink-2"><span className="flex items-center gap-1">超采样 super_sampling (v3)<HelpTip k="super_sampling" /></span><Switch checked={params.super_sampling} onChange={(v) => set("super_sampling", v)} ariaLabel="super sampling" /></div>
            </div>
          )}
        </div>
      </Panel>

      {/* 底部生成条 */}
      <div className="col-span-3 flex items-center gap-4 border border-line-1 bg-surface-1 px-4 py-2">
        <CoordinateTag label="engine" value={engine?.loaded ? (engine.busy ? "BUSY" : "READY") : "IDLE"} tone={engine?.loaded ? (engine.busy ? "notify" : "success") : "default"} />
        <CoordinateTag label="chars" value={text.length} />
        <CoordinateTag label="ref" value={ref.path ? "SET" : "—"} tone={ref.path ? "success" : "danger"} />
        {gen.isPending && <FrequencyBars bars={16} height={20} tone="action" />}
        <div className="ml-auto flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => setParams({ ...DEFAULT_TTS })}>重置参数</Button>
          <Button variant="primary" icon={<Sparkles size={16} />} onClick={() => gen.mutate()} disabled={!canGen} loading={gen.isPending}>
            {gen.isPending ? "合成中…" : "生成语音"}
          </Button>
        </div>
      </div>
      <PlaybackTracker onChange={setPlayingId} />
    </div>
  );
}

/** 监听页面内 audio 播放,标记当前播放项(wavesurfer 用 media element) */
function PlaybackTracker({ onChange }: { onChange: (id: number | null) => void }) {
  useEffect(() => {
    const h = (e: Event) => {
      const el = e.target as HTMLMediaElement;
      if (!el?.src) return;
      const m = el.src.match(/generated%2F[^%]+_(\w{6})\.wav|generated\/[^/]+_(\w{6})\.wav/);
      void m;
      onChange(null);
    };
    document.addEventListener("play", h, true);
    return () => document.removeEventListener("play", h, true);
  }, [onChange]);
  return null;
}
