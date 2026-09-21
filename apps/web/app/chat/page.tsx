"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Send, Volume2, VolumeX, Bot, User, Database } from "lucide-react";
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

const SOURCE_LABEL: Record<string, string> = {
  archive: "档案",
  sns: "SNS 对话",
  sim: "台词",
  meta: "基础",
};

export default function ChatPage() {
  const char = useQuery({ queryKey: ["character", "typhoea"], queryFn: () => api<Character>("/characters/typhoea") });
  const status = useQuery({ queryKey: ["chat-status"], queryFn: () => api<ChatStatus>("/chat/status") });
  const historyQ = useQuery({ queryKey: ["chat-history", "typhoea"], queryFn: () => api<{ messages: Msg[] }>("/chat/history?character=typhoea") });
  const [msgs, setMsgs] = useState<Msg[]>([]);
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

  async function send(text: string) {
    const history = msgs.slice(-20).map((m) => ({ role: m.role, content: m.content }));
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

    setMsgs((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, streaming: false } : x)));
    setBusy(false);

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

  // 对话记录留存：启动时加载历史
  useEffect(() => {
    if (historyQ.data?.messages?.length) setMsgs(historyQ.data.messages);
  }, [historyQ.data]);

  // 每完成一轮对话就保存（busy 从 true -> false 时触发一次）
  const prevBusyRef = useRef(false);
  useEffect(() => {
    if (prevBusyRef.current && !busy && msgs.length > 0) {
      api("/chat/history", { method: "POST", json: { character: "typhoea", messages: msgs } }).catch(() => {});
    }
    prevBusyRef.current = busy;
  }, [busy, msgs]);

  function clearChat() {
    setMsgs([]);
    api("/chat/history?character=typhoea", { method: "DELETE" }).catch(() => {});
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
      <header className="relative z-10 flex items-center gap-3 border-b border-line-1 bg-surface-0/80 px-4 py-2 backdrop-blur">
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
          {msgs.length > 0 && (
            <Button variant="ghost" size="sm" onClick={clearChat}>清空</Button>
          )}
        </div>
      </header>

      {/* 消息区 */}
      <div ref={scrollRef} className="relative z-10 min-h-0 flex-1 overflow-y-auto px-4 py-4">
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
      <div className="relative z-10 flex items-end gap-2 border-t border-line-1 bg-surface-0/80 p-2 backdrop-blur">
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
  );
}
