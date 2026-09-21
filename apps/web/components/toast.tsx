"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import { cn } from "@/lib/utils";

type Tone = "success" | "danger" | "info";
type ToastItem = { id: number; tone: Tone; msg: string };

const ToastCtx = createContext<(tone: Tone, msg: string) => void>(() => {});

export function useToast() {
  return useContext(ToastCtx);
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const idRef = useRef(0);

  const push = useCallback((tone: Tone, msg: string) => {
    const id = ++idRef.current;
    setToasts((t) => [...t, { id, tone, msg }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3400);
  }, []);

  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed right-3 top-16 z-[70] flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "pointer-events-auto rounded-capsule border px-4 py-2 text-sm shadow-lg backdrop-blur",
              t.tone === "success" && "border-success/40 bg-success/15 text-success",
              t.tone === "danger" && "border-danger/40 bg-danger/15 text-danger",
              t.tone === "info" && "border-action bg-action text-on-action",
            )}
          >
            {t.msg}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
