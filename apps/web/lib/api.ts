export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:9890";

export function assetUrl(rel: string) {
  return `${API_BASE}/assets/${rel}`;
}

export function fileUrl(absOrRel: string) {
  return `${API_BASE}/files?path=${encodeURIComponent(absOrRel)}`;
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(typeof body === "string" ? body : (body as { detail?: string })?.detail ?? `HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

export async function api<T = unknown>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: {
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(rest.headers ?? {}),
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  const ct = res.headers.get("content-type") ?? "";
  const body = ct.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) throw new ApiError(res.status, body);
  return body as T;
}

export async function apiBlob(path: string, init?: RequestInit & { json?: unknown }): Promise<Blob> {
  const { json, ...rest } = init ?? {};
  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: { ...(json !== undefined ? { "Content-Type": "application/json" } : {}), ...(rest.headers ?? {}) },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.blob();
}

/* ---------- 类型 ---------- */

export interface Character {
  id: string;
  code: string;
  name: string;
  nameEn: string;
  accent: string;
  accentDeep: string;
  art: {
    full: string; half: string; poster: string; avatar: string; avatarSquare: string;
    silhouette: string; scene: string; card: string; skillIcons: string[];
  };
  speakerChannel: string;
  dataset: { wavDir: string; list: string };
  weights: { exp: string; version: string; gpt: string; sovits: string };
  defaultRef: { audio: string; text: string; lang: string };
}

export interface Status {
  gpu: { name: string; total: number; used: number; free: number } | null;
  engine: { loaded: boolean; gpt: string | null; sovits: string | null; version: string | null; device: string; busy: boolean };
  character: string | null;
  jobs: { running: number; total: number };
  version: string;
}

export interface WeightEntry {
  kind: "gpt" | "sovits";
  path: string;
  file: string;
  exp: string;
  epoch: number | null;
  step: number | null;
  version: string;
  size: number;
  mtime: number;
}

export interface TtsParams {
  text: string;
  text_lang: string;
  ref_audio_path: string;
  prompt_text: string;
  prompt_lang: string;
  aux_ref_audio_paths?: string[];
  top_k: number;
  top_p: number;
  temperature: number;
  text_split_method: string;
  batch_size: number;
  batch_threshold: number;
  split_bucket: boolean;
  speed_factor: number;
  fragment_interval: number;
  seed: number;
  parallel_infer: boolean;
  repetition_penalty: number;
  sample_steps: number;
  super_sampling: boolean;
}

export const DEFAULT_TTS: Omit<TtsParams, "text" | "ref_audio_path" | "prompt_text"> = {
  text_lang: "zh",
  prompt_lang: "zh",
  top_k: 15,
  top_p: 1,
  temperature: 1,
  text_split_method: "cut5",
  batch_size: 1,
  batch_threshold: 0.75,
  split_bucket: true,
  speed_factor: 1,
  fragment_interval: 0.3,
  seed: -1,
  parallel_infer: true,
  repetition_penalty: 1.35,
  sample_steps: 32,
  super_sampling: false,
};

export interface LibraryItem {
  id: number;
  character: string;
  text: string;
  ref_audio: string;
  prompt_text: string;
  gpt: string;
  sovits: string;
  params: Record<string, unknown>;
  wav: string;
  duration: number;
  seed: number;
  elapsed: number;
  favorite: boolean;
  tags: string[];
  created_at: string;
}

export interface Job {
  id: string;
  kind: string;
  title: string;
  status: "queued" | "running" | "done" | "failed" | "cancelled";
  cmd: string[];
  started_at: number | null;
  ended_at: number | null;
  exit_code: number | null;
  meta: Record<string, unknown>;
  tail: string[];
}

export interface Sample {
  idx: number;
  wav: string;
  path: string;
  dur: number;
  f0: number;
  voiced: number;
  vt: number;
  text: string | null;
  inList: boolean;
}
