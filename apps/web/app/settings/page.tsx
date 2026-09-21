"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Eye, EyeOff, PlugZap } from "lucide-react";
import { Panel, Chip, ScanDivider, CoordinateTag } from "@/components/ef";
import { Button } from "@/components/ef/button";
import { Field, Input, Textarea, Select } from "@/components/ef/form";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useToast } from "@/components/toast";

interface Config {
  llm_base_url: string;
  llm_api_key: string;
  llm_has_key: boolean;
  llm_model: string;
  llm_api_format: string;
  embed_base_url: string;
  embed_api_key: string;
  embed_has_key: boolean;
  embed_model: string;
  env_file: string;
}

interface Provider {
  id: string;
  name: string;
  short?: string;
  color?: string;
  base_url: string;
  models: string[];
  embeds: string[];
  default_model: string;
  default_embed: string;
}

interface Contact {
  wechat: string;
  qq: string;
  bilibili: string;
  email: string;
}

interface SavedProvider {
  id?: string;
  name: string;
  base_url: string;
  api_key: string;
  model: string;
  format: string;
  color: string;
}

type FormState = {
  llm_base_url: string;
  llm_api_key: string;
  llm_model: string;
  llm_api_format: string;
  embed_base_url: string;
  embed_api_key: string;
  embed_model: string;
};

const EMPTY: FormState = {
  llm_base_url: "",
  llm_api_key: "",
  llm_model: "",
  llm_api_format: "openai",
  embed_base_url: "",
  embed_api_key: "",
  embed_model: "",
};

type ParsedProvider = { name: string; base_url: string; api_key: string; models: string[]; format?: string };

const URL_KEYS = ["base_url", "baseUrl", "baseURL", "api_base", "apiBase", "endpoint", "url", "base"];
const KEY_KEYS = ["api_key", "apiKey", "auth_token", "authToken", "token", "key"];

function clean(v: string): string {
  return v.replace(/`/g, "").replace(/^["']|["']$/g, "").trim();
}

function stripTrailingSlash(s: string): string {
  return s.replace(/\/+$/, "");
}

function pickFirst(o: Record<string, unknown>, keys: string[]): string {
  for (const k of keys) {
    const v = o[k];
    if (typeof v === "string" && clean(v)) return clean(v);
  }
  return "";
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return "";
  }
}

function b64decode(s: string): string {
  const b = s.trim().replace(/-/g, "+").replace(/_/g, "/");
  try {
    return atob(b);
  } catch {
    return "";
  }
}

// Claude Code settings.json / cc-switch 的 settingsConfig.env：
// { env: { ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN, ANTHROPIC_MODEL, ANTHROPIC_DEFAULT_*_MODEL } }
function parseClaudeEnv(env: Record<string, unknown>): ParsedProvider | null {
  const base_url = stripTrailingSlash(
    pickFirst(env, ["ANTHROPIC_BASE_URL", "ANTHROPIC_API_URL", "ANTHROPIC_BASEURL"]),
  );
  const api_key = pickFirst(env, [
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "GOOGLE_API_KEY",
  ]);
  if (!base_url && !api_key) return null;
  const models = new Set<string>();
  for (const [k, v] of Object.entries(env)) {
    if (typeof v === "string" && /^ANTHROPIC.*MODEL/.test(k) && clean(v)) models.add(clean(v));
  }
  return { name: hostOf(base_url), base_url, api_key, models: [...models], format: "anthropic" };
}

function pickAny(o: Record<string, unknown>, keys: string[]): string {
  for (const k of keys) {
    const v = o[k];
    if (typeof v === "string" && clean(v)) return clean(v);
  }
  for (const sub of ["settingsConfig", "settings", "config", "options", "env", "claude"]) {
    const s = o[sub];
    if (s && typeof s === "object") {
      const v = pickAny(s as Record<string, unknown>, keys);
      if (v) return v;
    }
  }
  return "";
}

function parseProviders(text: string): ParsedProvider[] {
  let data: unknown = null;
  try {
    data = JSON.parse(text);
  } catch {
    /* not direct json */
  }
  if (data === null || data === undefined) {
    // cc-switch 深链：ccswitch://import-provider?...&data=<base64>
    const m = text.match(/[?&]data=([^&]+)/);
    const raw = m ? m[1] : text;
    const decoded = b64decode(raw);
    if (decoded) {
      try {
        data = JSON.parse(decoded);
      } catch {
        /* ignore */
      }
    }
  }
  if (data === null || data === undefined) return [];

  const root = data as Record<string, unknown>;

  // 1) Claude Code settings.json（顶层 env.ANTHROPIC_*）
  if (root.env && typeof root.env === "object") {
    const c = parseClaudeEnv(root.env as Record<string, unknown>);
    if (c) return [c];
  }

  // 2) provider 数组 / 对象
  const arr: unknown[] = Array.isArray(data)
    ? data
    : Array.isArray(root.providers)
      ? (root.providers as unknown[])
      : Array.isArray(root.configs)
        ? (root.configs as unknown[])
        : [data];

  const out: ParsedProvider[] = [];
  for (const item of arr) {
    if (!item || typeof item !== "object") continue;
    const o = item as Record<string, unknown>;
    // cc-switch Provider：settingsConfig.env.{ANTHROPIC_*}
    const sc = o.settingsConfig;
    if (sc && typeof sc === "object") {
      const scObj = sc as Record<string, unknown>;
      if (scObj.env && typeof scObj.env === "object") {
        const c = parseClaudeEnv(scObj.env as Record<string, unknown>);
        if (c) {
          out.push({ ...c, name: String(o.name ?? o.label ?? c.name) });
          continue;
        }
      }
    }
    const base_url = stripTrailingSlash(pickAny(o, URL_KEYS));
    const api_key = pickAny(o, KEY_KEYS);
    const name = String(o.name ?? o.label ?? "");
    let models: string[] = [];
    if (Array.isArray(o.models)) models = o.models.map((m) => clean(String(m)));
    else if (o.model_mapping && typeof o.model_mapping === "object") models = Object.keys(o.model_mapping as object);
    else if (typeof o.model === "string") models = [clean(o.model)];
    if (base_url || name || api_key) out.push({ name, base_url, api_key, models });
  }
  return out;
}

function ProviderBadge({ name, color }: { name: string; color?: string }) {
  const letter = (name || "?").trim().charAt(0).toUpperCase();
  return (
    <span
      className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-[3px] text-[10px] font-bold leading-none text-white"
      style={{ background: color ?? "#888" }}
    >
      {letter}
    </span>
  );
}

function ModelCombo({
  value,
  onChange,
  options,
  onFetch,
  fetching,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
  onFetch: () => void;
  fetching: boolean;
  placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDown(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  function toggle() {
    setOpen((o) => {
      if (!o) setQuery("");
      return !o;
    });
  }

  const filtered = options.filter((o) => !query || o.toLowerCase().includes(query.toLowerCase()));

  return (
    <div ref={wrapRef} className="relative flex gap-2">
      <div className="relative flex-1">
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => {
            setQuery("");
            setOpen(true);
          }}
          placeholder={placeholder}
          spellCheck={false}
          autoComplete="off"
          className="pr-8"
        />
        <button
          type="button"
          onClick={toggle}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-2 hover:text-ink"
          aria-label="展开模型列表"
        >
          <ChevronDown size={14} className={cn("transition-transform", open && "rotate-180")} />
        </button>
      </div>
      <Button type="button" variant="secondary" size="sm" loading={fetching} onClick={onFetch} className="shrink-0">
        拉取模型
      </Button>
      {open && (
        <div className="absolute left-0 right-0 top-full z-[60] mt-1 border border-line-2 bg-surface-1 shadow-lg">
          {options.length === 0 ? (
            <div className="px-3 py-4 text-center text-sm text-ink-3">暂无模型，先点「拉取模型」获取列表</div>
          ) : (
            <>
              <div className="border-b border-line-1 p-2">
                <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索模型…" autoComplete="off" className="h-8 text-xs" />
              </div>
              <div className="max-h-56 overflow-auto">
                {filtered.length === 0 ? (
                  <div className="px-3 py-4 text-center text-sm text-ink-3">无匹配模型</div>
                ) : (
                  filtered.map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => {
                        onChange(m);
                        setOpen(false);
                      }}
                      className={cn(
                        "block w-full px-3 py-1.5 text-left text-sm text-ink hover:bg-surface-hover",
                        m === value && "bg-surface-2",
                      )}
                    >
                      {m}
                    </button>
                  ))
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { data } = useQuery({ queryKey: ["config"], queryFn: () => api<Config>("/config") });
  const providersQ = useQuery({ queryKey: ["providers"], queryFn: () => api<{ providers: Provider[] }>("/config/providers") });
  const contact = useQuery({ queryKey: ["contact"], queryFn: () => api<Contact>("/system/contact") });

  const providers = providersQ.data?.providers ?? [];
  const llmProviders = providers;
  const embedProviders = providers.filter((p) => p.embeds.length > 0);

  const [form, setForm] = useState<FormState>(EMPTY);
  const [llmModels, setLlmModels] = useState<string[]>([]);
  const [embedModels, setEmbedModels] = useState<string[]>([]);
  const [activeLlm, setActiveLlm] = useState("");
  const [activeEmbed, setActiveEmbed] = useState("");
  const [fetching, setFetching] = useState<"" | "llm" | "embed">("");
  const [showLlmKey, setShowLlmKey] = useState(false);
  const [showEmbedKey, setShowEmbedKey] = useState(false);
  const [testing, setTesting] = useState(false);
  const [savedName, setSavedName] = useState("");
  const [importText, setImportText] = useState("");
  const [imported, setImported] = useState<ParsedProvider[]>([]);
  const [saved, setSaved] = useState(false);
  const [fbContact, setFbContact] = useState("");
  const [fbContent, setFbContent] = useState("");

  useEffect(() => {
    if (data) {
      setForm({
        llm_base_url: data.llm_base_url,
        llm_api_key: "",
        llm_model: data.llm_model,
        llm_api_format: data.llm_api_format || "openai",
        embed_base_url: data.embed_base_url,
        embed_api_key: "",
        embed_model: data.embed_model,
      });
    }
  }, [data]);

  const save = useMutation({
    mutationFn: (body: Record<string, string | null>) => api("/config", { method: "POST", json: body }),
    onSuccess: () => {
      setSaved(true);
      toast("success", "配置已保存并生效");
      qc.invalidateQueries({ queryKey: ["config"] });
      setTimeout(() => setSaved(false), 2500);
    },
    onError: (e) => toast("danger", `保存失败：${(e as Error).message}`),
  });

  const feedback = useMutation({
    mutationFn: (body: { contact: string; content: string }) => api("/system/feedback", { method: "POST", json: body }),
    onSuccess: () => {
      setFbContent("");
      setFbContact("");
      toast("success", "反馈已提交，感谢！");
    },
  });

  const savedQ = useQuery({
    queryKey: ["saved-providers"],
    queryFn: () => api<{ providers: SavedProvider[] }>("/config/saved"),
  });

  const saveProvider = useMutation({
    mutationFn: (body: SavedProvider) => api("/config/saved", { method: "POST", json: body }),
    onSuccess: () => {
      toast("success", "已保存为供应商");
      setSavedName("");
      qc.invalidateQueries({ queryKey: ["saved-providers"] });
    },
    onError: (e) => toast("danger", `保存失败：${(e as Error).message}`),
  });

  const activateProvider = useMutation({
    mutationFn: (id: string) => api(`/config/saved/${id}/activate`, { method: "POST" }),
    onSuccess: () => {
      toast("success", "已切换供应商");
      qc.invalidateQueries({ queryKey: ["config"] });
    },
    onError: (e) => toast("danger", `切换失败：${(e as Error).message}`),
  });

  const deleteProvider = useMutation({
    mutationFn: (id: string) => api(`/config/saved/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast("success", "已删除");
      qc.invalidateQueries({ queryKey: ["saved-providers"] });
    },
  });

  function saveCurrent() {
    const name = savedName.trim() || hostOf(form.llm_base_url) || "未命名";
    saveProvider.mutate({
      name,
      base_url: form.llm_base_url,
      api_key: form.llm_api_key,
      model: form.llm_model,
      format: form.llm_api_format,
      color: "#888888",
    });
  }

  function set(k: keyof FormState) {
    return (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));
  }

  function applyLlm(p: Provider) {
    setActiveLlm(p.id);
    setLlmModels(p.models);
    setForm((f) => ({ ...f, llm_base_url: p.base_url, llm_model: p.default_model }));
  }

  function applyEmbed(p: Provider) {
    setActiveEmbed(p.id);
    setEmbedModels(p.embeds);
    setForm((f) => ({ ...f, embed_base_url: p.base_url, embed_model: p.default_embed }));
  }

  async function fetchModels(kind: "llm" | "embed") {
    const base = kind === "llm" ? form.llm_base_url : form.embed_base_url || form.llm_base_url;
    if (!base) {
      toast("danger", "请先填接口地址");
      return;
    }
    const key = kind === "llm" ? form.llm_api_key : form.embed_api_key || form.llm_api_key;
    const fmt = kind === "llm" ? form.llm_api_format : "openai";
    setFetching(kind);
    try {
      const res = await api<{ models: string[]; error?: string }>(
        `/config/models?base_url=${encodeURIComponent(base)}&format=${fmt}${key ? `&api_key=${encodeURIComponent(key)}` : ""}`,
      );
      if (res.error) {
        toast("danger", res.error);
      } else if (res.models?.length) {
        if (kind === "llm") setLlmModels(res.models);
        else setEmbedModels(res.models);
        toast("success", `已拉取 ${res.models.length} 个模型`);
      } else {
        toast("danger", "未拉取到模型，请检查地址/Key");
      }
    } catch (e) {
      toast("danger", `拉取失败：${(e as Error).message}`);
    }
    setFetching("");
  }

  async function testConnection() {
    const base = form.llm_base_url;
    if (!base) {
      toast("danger", "请先填接口地址");
      return;
    }
    setTesting(true);
    try {
      const key = form.llm_api_key;
      const res = await api<{ ok: boolean; latency_ms?: number; status?: number; error?: string }>(
        `/config/test?base_url=${encodeURIComponent(base)}&format=${form.llm_api_format}${key ? `&api_key=${encodeURIComponent(key)}` : ""}`,
      );
      if (res.ok) {
        toast("success", `连接正常 · ${res.latency_ms}ms`);
      } else {
        toast("danger", `连接失败：${res.error ?? res.status}`);
      }
    } catch (e) {
      toast("danger", `测试失败：${(e as Error).message}`);
    }
    setTesting(false);
  }

  function doImport() {
    const list = parseProviders(importText);
    if (!list.length) {
      toast("danger", "没识别到有效配置（请确认是 JSON 或 cc-switch 深链）");
      setImported([]);
      return;
    }
    setImported(list);
    toast("info", `识别到 ${list.length} 个提供商，点「填入 LLM」应用`);
  }

  function applyImported(p: ParsedProvider) {
    setForm((f) => ({
      ...f,
      llm_base_url: p.base_url,
      llm_model: p.models[0] ?? f.llm_model,
      llm_api_key: p.api_key,
      llm_api_format: p.format ?? f.llm_api_format,
    }));
    if (p.models.length) setLlmModels(p.models);
    setActiveLlm("custom");
    toast("success", `已导入「${p.name || p.base_url}」到 LLM`);
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    save.mutate({
      llm_base_url: form.llm_base_url,
      llm_api_key: form.llm_api_key === "" ? null : form.llm_api_key,
      llm_model: form.llm_model,
      llm_api_format: form.llm_api_format,
      embed_base_url: form.embed_base_url,
      embed_api_key: form.embed_api_key === "" ? null : form.embed_api_key,
      embed_model: form.embed_model,
    });
  }

  function onSubmitFeedback(e: React.FormEvent) {
    e.preventDefault();
    feedback.mutate({ contact: fbContact, content: fbContent });
  }

  const status = <Chip tone={data?.llm_has_key ? "success" : "notify"}>{data?.llm_has_key ? "LLM 已配置" : "LLM 未配置"}</Chip>;

  function chipCls(active: boolean) {
    return cn(
      "inline-flex items-center gap-1.5 rounded-capsule border px-3 py-1.5 text-xs transition-colors",
      active ? "border-action bg-action text-on-action" : "border-line-2 bg-surface-2 text-ink-2 hover:bg-surface-hover hover:text-ink",
    );
  }

  return (
    <div className="h-full space-y-2 overflow-auto p-2">
      <Panel title="AI 配置" en="LLM / EMBED" action={status}>
        <form onSubmit={onSubmit} className="mx-auto max-w-2xl space-y-5 px-6 py-5">
          {/* LLM */}
          <ScanDivider label="LLM · 对话生成" />
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex flex-wrap gap-2">
              {llmProviders.map((p) => (
                <button key={p.id} type="button" onClick={() => applyLlm(p)} className={chipCls(activeLlm === p.id)}>
                  <ProviderBadge name={p.short ?? p.name} color={p.color} />
                  {p.short ?? p.name}
                </button>
              ))}
              <button type="button" onClick={() => setActiveLlm("custom")} className={chipCls(activeLlm === "custom")}>自定义</button>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <CoordinateTag label="格式" value={form.llm_api_format === "anthropic" ? "ANTHROPIC" : "OPENAI"} tone="data" />
              <CoordinateTag label="模型" value={form.llm_model || "—"} tone="action" />
            </div>
          </div>

          <Field label="上游格式" hint="Anthropic Messages 原生（如 anyrouter）选 Anthropic，直连不转格式">
            <Select
              value={form.llm_api_format}
              onChange={(v) => setForm((f) => ({ ...f, llm_api_format: v }))}
              options={[
                { value: "openai", label: "OpenAI Chat Completions" },
                { value: "anthropic", label: "Anthropic Messages（原生）" },
              ]}
            />
          </Field>

          <Field label="接口地址 Base URL" hint="OpenAI 填 .../v1；Anthropic 填 origin（如 https://anyrouter.top）">
            <div className="flex gap-2">
              <Input value={form.llm_base_url} onChange={set("llm_base_url")} placeholder="https://api.siliconflow.cn/v1" spellCheck={false} autoComplete="off" className="flex-1" />
              <Button type="button" variant="secondary" size="sm" onClick={testConnection} loading={testing} className="shrink-0">
                <PlugZap size={14} /> 测试
              </Button>
            </div>
          </Field>

          <Field label="模型" hint="点右侧箭头展开列表，也可直接输入">
            <ModelCombo
              value={form.llm_model}
              onChange={(v) => setForm((f) => ({ ...f, llm_model: v }))}
              options={llmModels}
              onFetch={() => fetchModels("llm")}
              fetching={fetching === "llm"}
              placeholder="选择或输入模型名"
            />
          </Field>

          <Field label="API Key" hint={data?.llm_has_key ? "已设置（留空保持不变）" : "未设置"}>
            <div className="relative">
              <Input type={showLlmKey ? "text" : "password"} value={form.llm_api_key} onChange={set("llm_api_key")} placeholder={data?.llm_has_key ? "已设置，留空不改" : "sk-..."} spellCheck={false} autoComplete="new-password" className="pr-9" />
              <button type="button" onClick={() => setShowLlmKey((s) => !s)} className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-2 hover:text-ink" aria-label="显示/隐藏 key">
                {showLlmKey ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </Field>

          {/* Embedding */}
          <ScanDivider label="EMBEDDING · 资料检索" />
          <div className="mb-1 flex flex-wrap gap-2">
            {embedProviders.map((p) => (
              <button key={p.id} type="button" onClick={() => applyEmbed(p)} className={chipCls(activeEmbed === p.id)}>
                <span className="h-2 w-2 rounded-full" style={{ background: p.color ?? "#888" }} />
                {p.short ?? p.name}
              </button>
            ))}
            <button type="button" onClick={() => setActiveEmbed("custom")} className={chipCls(activeEmbed === "custom")}>自定义</button>
          </div>

          <Field label="接口地址 Base URL" hint="留空则复用上面的 LLM 地址">
            <Input value={form.embed_base_url} onChange={set("embed_base_url")} placeholder="留空复用 LLM 地址" spellCheck={false} autoComplete="off" />
          </Field>

          <Field label="模型" hint="改了模型需重新入库（数据页 → 资料入库）">
            <ModelCombo
              value={form.embed_model}
              onChange={(v) => setForm((f) => ({ ...f, embed_model: v }))}
              options={embedModels}
              onFetch={() => fetchModels("embed")}
              fetching={fetching === "embed"}
              placeholder="选择或输入模型名"
            />
          </Field>

          <Field label="API Key" hint="留空则复用上面的 LLM Key">
            <div className="relative">
              <Input type={showEmbedKey ? "text" : "password"} value={form.embed_api_key} onChange={set("embed_api_key")} placeholder="留空复用 LLM Key" spellCheck={false} autoComplete="new-password" className="pr-9" />
              <button type="button" onClick={() => setShowEmbedKey((s) => !s)} className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-2 hover:text-ink" aria-label="显示/隐藏 key">
                {showEmbedKey ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </Field>

          <div className="flex items-center gap-3 pt-1">
            <Button type="submit" variant="action" loading={save.isPending}>保存并生效</Button>
            {saved && <Chip tone="success">已保存</Chip>}
          </div>
        </form>
      </Panel>

      <Panel title="供应商" en="PROVIDERS">
        <div className="mx-auto max-w-2xl space-y-4 px-6 py-5">
          <div className="flex gap-2">
            <Input value={savedName} onChange={(e) => setSavedName(e.target.value)} placeholder="名称（留空自动取域名）" spellCheck={false} autoComplete="off" />
            <Button type="button" variant="secondary" onClick={saveCurrent} loading={saveProvider.isPending} className="shrink-0">保存当前配置</Button>
          </div>

          {savedQ.data?.providers?.length ? (
            <div className="space-y-2">
              {savedQ.data.providers.map((p) => (
                <div key={p.id} className="flex items-center gap-3 border border-line-1 bg-surface-0 px-3 py-2">
                  <ProviderBadge name={p.name} color={p.color} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm text-ink">{p.name}</span>
                      <Chip tone={p.format === "anthropic" ? "data" : "default"}>{p.format === "anthropic" ? "ANTHROPIC" : "OPENAI"}</Chip>
                    </div>
                    <div className="micro normal-case tracking-normal truncate">{p.base_url}{p.model ? ` · ${p.model}` : ""}</div>
                  </div>
                  <Button type="button" variant="action" size="sm" onClick={() => p.id && activateProvider.mutate(p.id)} loading={activateProvider.isPending}>启用</Button>
                  <Button type="button" variant="ghost" size="sm" onClick={() => p.id && deleteProvider.mutate(p.id)}>删除</Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-ink-3">还没有保存的供应商。填好上面的 LLM 配置后点「保存当前配置」，以后一键切换。</p>
          )}
        </div>
      </Panel>

      <Panel title="导入配置" en="IMPORT">
        <div className="mx-auto max-w-2xl space-y-3 px-6 py-5">
          <p className="text-sm leading-relaxed text-ink-2">
            粘贴 cc-switch / OpenAI 兼容的配置 JSON（对象、数组、<span className="font-mono text-ink">providers</span> 字段），
            或 cc-switch 深链（<span className="font-mono text-ink">ccswitch://...&data=base64</span>），识别后一键填入 LLM。
          </p>
          <Textarea value={importText} onChange={(e) => setImportText(e.target.value)} rows={5} placeholder='例如 {"name":"anyrouter","base_url":"https://...","api_key":"sk-...","models":["..."]}' spellCheck={false} />
          <div className="flex items-center gap-3">
            <Button type="button" variant="secondary" onClick={doImport}>识别配置</Button>
            {imported.length > 0 && <Chip tone="data">{imported.length} 个提供商</Chip>}
          </div>
          {imported.length > 0 && (
            <div className="space-y-2">
              {imported.map((p, i) => (
                <div key={i} className="flex items-center gap-3 border border-line-1 bg-surface-0 px-3 py-2">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm text-ink">{p.name || p.base_url}</div>
                    <div className="micro normal-case tracking-normal truncate">{p.base_url}{p.models.length ? ` · ${p.models.length} 模型` : ""}</div>
                  </div>
                  <Button type="button" variant="action" size="sm" onClick={() => applyImported(p)}>填入 LLM</Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Panel>

      <Panel title="反馈" en="FEEDBACK">
        <div className="mx-auto max-w-2xl space-y-4 px-6 py-5">
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5 text-sm">
            {(
              [
                ["微信", contact.data?.wechat],
                ["QQ", contact.data?.qq],
                ["B站", contact.data?.bilibili],
                ["邮箱", contact.data?.email],
              ] as const
            ).map(([label, val]) => (
              <div key={label} className="flex items-baseline gap-2">
                <span className="micro w-8 shrink-0">{label}</span>
                <span className="truncate font-mono text-xs text-ink">{val || "—"}</span>
              </div>
            ))}
          </div>
          <form onSubmit={onSubmitFeedback} className="space-y-3">
            <Field label="你的联系方式（选填）" hint="方便我回复你，可留空">
              <Input value={fbContact} onChange={(e) => setFbContact(e.target.value)} placeholder="QQ / 微信 / 邮箱…" spellCheck={false} autoComplete="off" />
            </Field>
            <Field label="反馈内容">
              <Textarea value={fbContent} onChange={(e) => setFbContent(e.target.value)} rows={4} placeholder="遇到什么问题、想要什么功能，都可以写在这里…" />
            </Field>
            <div className="flex items-center gap-3">
              <Button type="submit" variant="secondary" loading={feedback.isPending}>提交反馈</Button>
              {feedback.isError && <Chip tone="danger">提交失败</Chip>}
            </div>
          </form>
        </div>
      </Panel>
    </div>
  );
}
