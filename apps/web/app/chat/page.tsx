"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Send, Volume2, VolumeX, Bot, User, Database, Plus, Pencil, Trash2, MessageSquare } from "lucide-react";
import { API_BASE, api, apiBlob, assetUrl, type Character } from "@/lib/api";
import { Chip } from "@/components/ef";
import { Button } from "@/components/ef/button";
import { Textarea, Switch } from "@/components/ef/form";
import { cn } from "@/lib/utils";

interface Source {
  text: string;
  source: string;
  speaker: string;
  score: number;
}

interface Msg {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  audioUrl?: string;
  streaming?: boolean;
}

interface ChatStatus {
  llm: boolean;
  embed: boolean;
  llm_model: string;
  embed_model: string;
  rag_chunks: number;
  rag_ready: boolean;
}

interface SessionRow {
  id: string;
  title: string;
  updated: number;
  count: number;
}

const CHARACTER = "typhoea";

const SOURCE_LABEL: Record<string, string> = {
  archive: "档案",
  sns: "SNS 对话",
  sim: "台词",
  meta: "基础",
};

export default function ChatPage() {
  const char = useQuery({ queryKey: ["character", "typhoea"], queryFn: () => api<Character>("/characters/typhoea") });
  const status = useQuery({ queryKey: ["chat-status"], queryFn: () => api<ChatStatus>("/chat/status") });
  const qc = useQueryClient();
  const sessionsQ = useQuery({ queryKey: ["chat-sessions", CHARACTER], queryFn: () => api<{ sessions: SessionRow[] }>(`/chat/sessions?character=${CHARACTER}`) });
  const [sid, setSid] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [renaming, setRenaming] = useState<{ id: string; title: string } | null>(null);
  const [input, setInput] = useState("");
  const [voice, setVoice] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const s = status.data;
  const c = char.data;
  const voiceRef = useRef(voice);
  voiceRef.current = voice;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs]);

  const [busy, setBusy] = useState(false);

  async function ensureSession(): Promise<string> {
    if (sid) return sid;
    const sess = await api<{ id: string }>("/chat/sessions", { method: "POST", json: { character: CHARACTER } });
    setSid(sess.id);
    qc.invalidateQueries({ queryKey: ["chat-sessions", CHARACTER] });
    return sess.id;
  }

  async function saveSession(id: string, messages: Msg[]) {
    await api(`/chat/sessions/${id}`, { method: "PUT", json: { character: CHARACTER, messages } }).catch(() => {});
    qc.invalidateQueries({ queryKey: ["chat-sessions", CHARACTER] });
  }

  async function send(text: string) {
    const history = msgs.slice(-20).map((m) => ({ role: m.role, content: m.content }));
    let id: string;
    try {
      id = await ensureSession();
    } catch (e) {
      setMsgs((m) => [...m, { role: "user", content: text }, { role: "assistant", content: `（回复失败）无法创建会话: ${(e as Error).message}` }]);
      return;
    }
    setMsgs((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "", streaming: true }]);
    setInput("");
    setBusy(true);

    let reply = "";
    let sources: Source[] = [];

    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history, character: "typhoea" }),
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          const l = line.trim();
          if (!l.startsWith("data:")) continue;
          const data = l.slice(5).trim();
          if (data === "[DONE]") continue;
          let evt: { type?: string; sources?: Source[]; text?: string; error?: string };
          try {
            evt = JSON.parse(data);
          } catch {
            continue;
          }
          if (evt.type === "meta") {
            sources = evt.sources ?? [];
            setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, sources } : x)));
          } else if (evt.type === "delta") {
            reply += evt.text ?? "";
            setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, content: x.content + (evt.text ?? "") } : x)));
          } else if (evt.type === "error") {
            throw new Error(evt.error ?? "未知错误");
          }
        }
      }
    } catch (e) {
      setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, content: `（回复失败）${(e as Error).message}`, streaming: false } : x)));
      setBusy(false);
      return;
    }

    const finalMsgs = [...msgs, { role: "user" as const, content: text }, { role: "assistant" as const, content: reply, sources }];
    setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, streaming: false } : x)));
    setBusy(false);
    saveSession(id, finalMsgs);

    if (voiceRef.current && reply) {
      try {
        const blob = await apiBlob("/chat/tts", { method: "POST", json: { text: reply, character: "typhoea" } });
        const url = URL.createObjectURL(blob);
        setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, audioUrl: url } : x)));
      } catch {
        /* 语音合成失败不阻断对话 */
      }
    }
  }

  function onSubmit() {
    const text = input.trim();
    if (!text || busy) return;
    send(text);
  }

  // 首次进入自动打开最近一个会话
  const sessions = sessionsQ.data?.sessions ?? [];
  const autoOpened = useRef(false);
  useEffect(() => {
    if (autoOpened.current || !sessionsQ.data) return;
    autoOpened.current = true;
    if (sessions.length > 0) openSession(sessions[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionsQ.data]);

  async function openSession(id: string) {
    if (busy) return;
    try {
      const sess = await api<{ id: string; messages: Msg[] }>(`/chat/sessions/${id}?character=${CHARACTER}`);
      setSid(sess.id);
      setMsgs(sess.messages);
    } catch {
      qc.invalidateQueries({ queryKey: ["chat-sessions", CHARACTER] });
    }
  }

  function newChat() {
    if (busy) return;
    setSid(null);
    setMsgs([]);
  }

  async function deleteSession(id: string) {
    if (!window.confirm("删除这个会话？记录不可恢复。")) return;
    await api(`/chat/sessions/${id}?character=${CHARACTER}`, { method: "DELETE" }).catch(() => {});
    if (id === sid) newChat();
    qc.invalidateQueries({ queryKey: ["chat-sessions", CHARACTER] });
  }

  async function commitRename() {
    if (!renaming) return;
    const { id, title } = renaming;
    setRenaming(null);
    const sess = await api<{ messages: Msg[] }>(`/chat/sessions/${id}?character=${CHARACTER}`).catch(() => null);
    if (!sess) return;
    await api(`/chat/sessions/${id}`, { method: "PUT", json: { character: CHARACTER, messages: sess.messages, title } }).catch(() => {});
    qc.invalidateQueries({ queryKey: ["chat-sessions", CHARACTER] });
  }

  const avatar = c?.art.avatarSquare ?? c?.art.avatar;

  return (
    <div className="relative flex h-full flex-col overflow-hidden">
      {/* Baker 字体注入（Bender=UI 字体，Endfield Belt=游戏腰封/Logo 字体） */}
      <style>{`
        @font-face {
          font-family: 'Bender';
          src: url('${API_BASE}/assets/baker/fonts/bender.otf') format('opentype');
          font-weight: normal;
          font-style: normal;
        }
        @font-face {
          font-family: 'Endfield Belt';
          src: url('${API_BASE}/assets/baker/fonts/EndfieldBelt-Bold.ttf') format('truetype');
          font-weight: 700;
          font-style: normal;
        }
        .font-bender { font-family: 'Bender', 'Noto Sans SC', sans-serif; }
        .font-belt { font-family: 'Endfield Belt', 'Bender', sans-serif; }
      `}</style>

      {/* Baker 聊天背景 */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.14]"
        style={{
          backgroundImage: `url(${assetUrl("baker/extracted/bg/deco_sns_chat_bg.png")})`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      />

      {/* 顶栏：Baker 名牌 */}
      <header className="relative z-10 flex items-center gap-3 border-b border-line-1 bg-surface-0/80 py-2 pl-4 pr-28 backdrop-blur">
        <div className="flex flex-col gap-0.5 leading-none">
          <span className="font-belt text-xl tracking-[0.18em] text-ink">BAKER</span>
          <img
            src="/brand/endfield-logo-en.svg"
            alt="Endfield Industries"
            className="h-3.5 w-[85px] object-contain object-left"
            style={{ filter: "invert(1)" }}
          />
        </div>
        <div className="mx-2 h-6 w-px bg-line-2" />
        {c && avatar ? (
          <img src={assetUrl(avatar)} alt={c.name} className="h-9 w-9 object-cover" />
        ) : (
          <span className="h-9 w-9 bg-surface-2" />
        )}
        <div className="flex min-w-0 flex-col">
          <span className="truncate text-sm font-medium text-ink">{c?.name ?? "提弗洛斯"}</span>
          <span className="micro truncate">{c?.nameEn ?? "TYPHOEUS"}</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {s && (
            <>
              <Chip tone={s.llm ? "success" : "notify"}>{s.llm ? "LLM 已连接" : "LLM 未配置"}</Chip>
              <Chip tone={s.rag_ready ? "data" : "notify"}>{s.rag_ready ? `资料 ${s.rag_chunks}` : "资料未入库"}</Chip>
            </>
          )}
          <Button variant="ghost" size="sm" icon={<Plus size={12} />} onClick={newChat} disabled={busy}>新对话</Button>
        </div>
      </header>

      <div className="relative z-10 flex min-h-0 flex-1">
      {/* 会话列表 */}
      <aside className="flex w-52 shrink-0 flex-col border-r border-line-1 bg-surface-0/80 backdrop-blur">
        <div className="micro flex items-center justify-between px-3 py-2">
          <span>会话 · {sessions.length}</span>
          <button type="button" aria-label="新对话" title="新对话" onClick={newChat} disabled={busy} className="text-ink-3 hover:text-action-text disabled:opacity-40"><Plus size={13} /></button>
        </div>
        <ul className="min-h-0 flex-1 overflow-y-auto">
          {sessions.map((row) => (
            <li key={row.id} className={cn("group flex items-center gap-1 border-l-2 px-2 py-1.5 text-xs", row.id === sid ? "border-action bg-surface-2/80 text-ink" : "border-transparent text-ink-2 hover:bg-surface-1")}>
              {renaming?.id === row.id ? (
                <input
                  autoFocus
                  value={renaming.title}
                  onChange={(e) => setRenaming({ id: row.id, title: e.target.value })}
                  onBlur={commitRename}
                  onKeyDown={(e) => { if (e.key === "Enter") commitRename(); if (e.key === "Escape") setRenaming(null); }}
                  className="min-w-0 flex-1 border border-line-2 bg-surface-0 px-1 py-0.5 text-xs text-ink outline-none"
                  aria-label="会话名称"
                />
              ) : (
                <button type="button" onClick={() => openSession(row.id)} className="flex min-w-0 flex-1 items-center gap-1.5 text-left" title={row.title}>
                  <MessageSquare size={12} className="shrink-0 opacity-60" />
                  <span className="truncate">{row.title}</span>
                </button>
              )}
              <button type="button" aria-label="重命名" title="重命名" onClick={() => setRenaming({ id: row.id, title: row.title })} className="shrink-0 text-ink-3 opacity-0 hover:text-ink group-hover:opacity-100"><Pencil size={11} /></button>
              <button type="button" aria-label="删除会话" title="删除会话" onClick={() => deleteSession(row.id)} className="shrink-0 text-ink-3 opacity-0 hover:text-danger group-hover:opacity-100"><Trash2 size={11} /></button>
            </li>
          ))}
          {sessions.length === 0 && <li className="px-3 py-2 text-xs text-ink-3">还没有会话，发一句话就会自动建一个。</li>}
        </ul>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
      {/* 消息区 */}
      <div ref={scrollRef} className="relative min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {msgs.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            {avatar && <img src={assetUrl(avatar)} alt={c?.name} className="h-24 w-24 object-cover opacity-90" />}
            <p className="max-w-sm text-sm leading-relaxed text-ink-2">和提弗洛斯聊聊吧。她会依据游戏里的档案、台词与 SNS 对话来回应。</p>
            {s && !s.rag_ready && (
              <p className="micro normal-case tracking-normal text-notify">
                资料库为空：先运行 <span className="text-ink">scripts/ingest_lore.py</span> 入库。
              </p>
            )}
            {s && !s.llm && (
              <p className="micro normal-case tracking-normal text-notify">
                未配置云端 LLM：复制 <span className="text-ink">.env.example</span> 为 <span className="text-ink">.env</span> 填 key 后重启 server。
              </p>
            )}
          </div>
        ) : (
          <ul className="flex flex-col gap-3">
            {msgs.map((m, i) => (
              <li key={i} className={cn("flex gap-2", m.role === "user" ? "justify-end" : "justify-start")}>
                {m.role === "assistant" && (
                  <span className="mt-1 shrink-0">
                    {avatar ? <img src={assetUrl(avatar)} alt={c?.name} className="h-8 w-8 object-cover" /> : <Bot size={20} className="text-action-text" />}
                  </span>
                )}
                <div className={cn("max-w-[74%] min-w-0", m.role === "user" && "order-1")}>
                  <div className={cn("mb-1 flex items-center gap-1 text-xs", m.role === "user" ? "justify-end text-ink-2" : "text-action-text")}>
                    {m.role === "user" ? (
                      <>
                        <span className="truncate">管理员</span>
                        <User size={12} />
                      </>
                    ) : (
                      <>
                        <span className="truncate">{c?.name ?? "提弗洛斯"}</span>
                      </>
                    )}
                  </div>
                  <div
                    className={cn(
                      "cut-corner whitespace-pre-wrap border px-3 py-2 text-sm leading-relaxed",
                      m.role === "user" ? "border-line-2 bg-surface-2/90 text-ink" : "border-action/30 bg-surface-0/95 text-ink",
                    )}
                  >
                    {m.content}
                    {m.streaming && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-action align-middle" />}
                  </div>
                  {m.audioUrl && <audio controls autoPlay src={m.audioUrl} className="mt-2 h-8 w-full" />}
                  {m.sources && m.sources.length > 0 && (
                    <details className="mt-2 border border-line-1 bg-surface-0">
                      <summary className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-xs text-ink-2 hover:text-ink">
                        <Database size={12} /> 参考资料（{m.sources.length}）
                      </summary>
                      <ul className="flex flex-col gap-2 border-t border-line-1 p-3">
                        {m.sources.map((src, j) => (
                          <li key={j} className="text-xs leading-relaxed text-ink-2">
                            <span className="mr-2 font-mono text-[10px] uppercase text-ink-3">{SOURCE_LABEL[src.source] ?? src.source} · {(src.score * 100).toFixed(0)}%</span>
                            <span className="text-ink-2">{src.text.slice(0, 200)}</span>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* 输入区 */}
      <div className="relative flex items-end gap-2 border-t border-line-1 bg-surface-0/80 p-2 backdrop-blur">
        <label className="flex shrink-0 cursor-pointer items-center gap-2 px-2 py-2 text-xs text-ink-2">
          <Switch checked={voice} onChange={setVoice} ariaLabel="语音回复" />
          {voice ? <Volume2 size={14} /> : <VolumeX size={14} />}
        </label>
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSubmit();
            }
          }}
          placeholder="和提弗洛斯说点什么…（Enter 发送，Shift+Enter 换行）"
          className="max-h-28 min-h-[44px] flex-1"
          rows={1}
        />
        <Button variant="action" icon={<Send size={14} />} onClick={onSubmit} disabled={!input.trim() || busy} loading={busy}>
          发送
        </Button>
      </div>
      </div>
      </div>
    </div>
  );
}
