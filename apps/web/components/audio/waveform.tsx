"use client";

import { useEffect, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import { Pause, Play } from "lucide-react";
import { cn } from "@/lib/utils";

/** 波形 + 播放。url 为完整可访问地址。 */
export function Waveform({
  url,
  height = 48,
  accent = "var(--operator-accent)",
  className,
  compact,
  onReady,
}: {
  url: string;
  height?: number;
  accent?: string;
  className?: string;
  compact?: boolean;
  onReady?: (durationSec: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const ws = useRef<WaveSurfer | null>(null);
  const [playing, setPlaying] = useState(false);
  const [dur, setDur] = useState(0);
  const [cur, setCur] = useState(0);

  useEffect(() => {
    if (!ref.current) return;
    const w = WaveSurfer.create({
      container: ref.current,
      url,
      height,
      waveColor: "rgba(137,141,137,.55)",
      progressColor: accent,
      cursorColor: "var(--action)",
      cursorWidth: 1,
      barWidth: 2,
      barGap: 1,
      barRadius: 0,
      normalize: true,
    });
    ws.current = w;
    w.on("ready", (d) => {
      setDur(d);
      onReady?.(d);
    });
    w.on("play", () => setPlaying(true));
    w.on("pause", () => setPlaying(false));
    w.on("finish", () => setPlaying(false));
    w.on("timeupdate", (t) => setCur(t));
    return () => {
      w.destroy();
      ws.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, height, accent]);

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <button
        type="button"
        onClick={() => ws.current?.playPause()}
        aria-label={playing ? "暂停" : "播放"}
        className={cn(
          "rounded-full flex shrink-0 items-center justify-center bg-ink text-canvas hover:bg-action hover:text-on-action",
          compact ? "h-7 w-7" : "h-9 w-9",
        )}
      >
        {playing ? <Pause size={compact ? 12 : 14} /> : <Play size={compact ? 12 : 14} className="ml-0.5" />}
      </button>
      <div ref={ref} className="min-w-0 flex-1" />
      <span className="micro w-[86px] shrink-0 text-right tabular-nums">
        {cur.toFixed(1)} / {dur.toFixed(1)}s
      </span>
    </div>
  );
}
