"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "./api";

/** 订阅 SSE。每条 message 事件的 data 会 JSON.parse 后回调。 */
export function useSSE<T = unknown>(path: string | null, onEvent: (e: T) => void) {
  const cb = useRef(onEvent);
  cb.current = onEvent;
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    if (!path) return;
    const es = new EventSource(`${API_BASE}${path}`);
    es.onopen = () => setConnected(true);
    es.onmessage = (ev) => {
      try {
        cb.current(JSON.parse(ev.data) as T);
      } catch {
        cb.current(ev.data as unknown as T);
      }
    };
    es.onerror = () => setConnected(false);
    return () => {
      es.close();
      setConnected(false);
    };
  }, [path]);
  return connected;
}
