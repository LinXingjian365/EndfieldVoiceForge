"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions.js";
import { Film, Scissors, Upload, Play, Pause, Trash2, Layers, Wand2, Repeat2 } from "lucide-react";
import { api, fileUrl, ApiError } from "@/lib/api";
import { Button } from "@/components/ef/button";
import { Chip } from "@/components/ef";
import { Input } from "@/components/ef/form";

type Seg = { path: string; name: string; duration: number };

type StampedSegment = Seg & {
  id: string;
  start: number;
  end: number;
  label: string;
};

/** 视频 -> 音频 -> 波形拖选区间选起止 -> 截取 -> 命名标记 -> 组合 -> 交 RVC。 */
export function VideoCutter({
  onCut,
  accent = "var(--action)",
}: {
  onCut: (seg: Seg) => void;
  accent?: string;
}) {
  const [video, setVideo] = useState<{ path: string; name: string } | null>(null);
  const [audio, setAudio] = useState<Seg | null>(null);
  const [busy, setBusy] = useState<"upload" | "extract" | "cut" | "concat" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [region, setRegion] = useState<{ start: number; end: number } | null>(null);
  const [playing, setPlaying] = useState(false);
  const [looping, setLooping] = useState(false);
  const [segments, setSegments] = useState<StampedSegment[]>([]);
  const [checked, setChecked] = useState<Set<string>>(new Set());

  const waveRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);
  const regionsRef = useRef<ReturnType<typeof RegionsPlugin.create> | null>(null);
  const currentRegionRef = useRef<{ start: number; end: number } | null>(null);
  const loopingRef = useRef(false);

  async function uploadVideo(file: File) {
    setErr(null);
    setBusy("upload");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const up = await api<{ path: string; name: string }>("/upload", { method: "POST", body: fd });
      setVideo(up);
      return up;
    } catch (e) {
      setErr((e as ApiError).message);
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function extractAudio(v: { path: string; name: string }) {
    setErr(null);
    setBusy("extract");
    setAudio(null);
    setRegion(null);
    try {
      const a = await api<Seg>("/tools/extract_audio", { method: "POST", json: { path: v.path } });
      setAudio(a);
      return a;
    } catch (e) {
      setErr((e as ApiError).message);
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    const up = await uploadVideo(f);
    if (up) await extractAudio(up);
    e.target.value = "";
  }

  // 波形加载 + 默认选区(前 3~8 秒)
  useEffect(() => {
    if (!audio || !waveRef.current) return;
    const ws = WaveSurfer.create({
      container: waveRef.current,
      url: fileUrl(audio.path),
      height: 64,
      waveColor: "rgba(137,141,137,.55)",
      progressColor: accent,
      cursorColor: "var(--action)",
      cursorWidth: 1,
      barWidth: 2,
      barGap: 1,
      barRadius: 0,
      normalize: true,
    });
    const regions = ws.registerPlugin(RegionsPlugin.create());
    wsRef.current = ws;
    regionsRef.current = regions;
    ws.on("ready", (dur) => {
      const start = 0;
      const end = Math.min(8, dur);
      const r = regions.addRegion({
        start,
        end,
        color: "rgba(255, 245, 0, 0.22)",
        drag: true,
        resize: true,
      });
      const sync = () => {
        currentRegionRef.current = { start: r.start, end: r.end };
        setRegion({ start: r.start, end: r.end });
      };
      r.on("update", sync);
      r.on("update-end", sync);
      sync();
    });
    return () => {
      ws.destroy();
      wsRef.current = null;
      regionsRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audio?.path]);

  // 视频是唯一播放器:维护播放状态 + 波形游标跟随 + 循环回跳 + 波形点击跳转(单向,不反向 seek,所以不卡)
  useEffect(() => {
    const ws = wsRef.current;
    const videoEl = videoRef.current;
    if (!videoEl || !ws) return;
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onTime = () => {
      const t = videoEl.currentTime;
      ws.setTime(t);
      const r = currentRegionRef.current;
      if (loopingRef.current && r && t >= r.end) videoEl.currentTime = r.start;
    };
    const onInteract = (t: number) => {
      if (Number.isFinite(t)) videoEl.currentTime = t;
    };
    videoEl.addEventListener("play", onPlay);
    videoEl.addEventListener("pause", onPause);
    videoEl.addEventListener("timeupdate", onTime);
    videoEl.addEventListener("seeked", onTime);
    const unsubInteract = ws.on("interaction", onInteract);
    return () => {
      videoEl.removeEventListener("play", onPlay);
      videoEl.removeEventListener("pause", onPause);
      videoEl.removeEventListener("timeupdate", onTime);
      videoEl.removeEventListener("seeked", onTime);
      unsubInteract?.();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [video?.path, audio?.path]);

  // 播放/暂停(视频原生,带声音)
  function togglePlay() {
    const videoEl = videoRef.current;
    if (!videoEl) return;
    if (videoEl.paused) {
      loopingRef.current = false;
      setLooping(false);
      void videoEl.play();
    } else {
      videoEl.pause();
    }
  }

  // 循环预览当前选区(视频原生,带声音,播到末尾回跳)
  function toggleLoopPreview() {
    const videoEl = videoRef.current;
    const r = currentRegionRef.current;
    if (!videoEl || !r) return;
    if (looping) {
      loopingRef.current = false;
      setLooping(false);
      videoEl.pause();
      return;
    }
    loopingRef.current = true;
    setLooping(true);
    videoEl.currentTime = r.start;
    void videoEl.play();
  }

  async function cut() {
    if (!audio || !region || region.end - region.start <= 0) return;
    setErr(null);
    setBusy("cut");
    try {
      const seg = await api<Seg>("/tools/cut", {
        method: "POST",
        json: { path: audio.path, start: region.start, end: region.end },
      });
      setSegments((prev) => [
        ...prev,
        {
          ...seg,
          id: `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
          start: region.start,
          end: region.end,
          label: `片段${prev.length + 1} ${region.start.toFixed(1)}–${region.end.toFixed(1)}s`,
        },
      ]);
      onCut(seg);
    } catch (e) {
      setErr((e as ApiError).message);
    } finally {
      setBusy(null);
    }
  }

  function toggleChecked(id: string) {
    setChecked((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }

  async function combine() {
    const chosen = segments.filter((s) => checked.has(s.id));
    if (chosen.length < 2) return;
    setErr(null);
    setBusy("concat");
    try {
      const seg = await api<Seg>("/tools/concat", { method: "POST", json: { paths: chosen.map((s) => s.path) } });
      setSegments((prev) => [
        ...prev,
        {
          ...seg,
          id: `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
          start: chosen[0].start,
          end: chosen[chosen.length - 1].end,
          label: `组合 ${chosen.map((s) => s.label).join(" + ")}`,
        },
      ]);
      setChecked(new Set());
    } catch (e) {
      setErr((e as ApiError).message);
    } finally {
      setBusy(null);
    }
  }

  function rename(id: string, label: string) {
    setSegments((prev) => prev.map((s) => (s.id === id ? { ...s, label } : s)));
  }

  function remove(id: string) {
    setSegments((prev) => prev.filter((s) => s.id !== id));
    setChecked((prev) => {
      const n = new Set(prev);
      n.delete(id);
      return n;
    });
  }

  const checkedCount = useMemo(() => segments.filter((s) => checked.has(s.id)).length, [segments, checked]);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <input type="file" accept="video/*" className="sr-only" id="vc-video" onChange={onPick} />
        <Button variant="secondary" size="sm" icon={<Upload size={14} />} loading={busy === "upload"} onClick={() => document.getElementById("vc-video")?.click()}>
          上传视频
        </Button>
        <Button variant="secondary" size="sm" icon={<Film size={14} />} disabled={!video} loading={busy === "extract"} onClick={() => video && extractAudio(video)}>
          提取音频
        </Button>
        <span className="min-w-0 flex-1 truncate text-xs text-ink-2">{video?.name ?? "mp4 / mov / mkv / webm…"}</span>
      </div>
      {err && <span className="text-xs text-danger">{err}</span>}

      {/* 视频画面预览:固定高度 + object-contain 完整显示(不裁切不拉伸),标准播放器做法 + 终末地工业描框 */}
      {video && (
        <div className="group relative">
          <div className="cut-corner relative border border-line-1 bg-surface-1 p-1.5">
            <div className="corner-bracket-action relative h-60 w-full overflow-hidden bg-black">
              <video ref={videoRef} src={fileUrl(video.path)} controls playsInline className="h-full w-full object-contain" />
            </div>
          </div>
          {/* 底部技术标签条 */}
          <div className="mt-1 flex items-center gap-2 px-0.5">
            <span className="micro">VIDEO / REF</span>
            <span className="h-px flex-1 bg-line-1" aria-hidden />
            <span className="micro">{video.name}</span>
          </div>
        </div>
      )}

      {audio && (
        <>
          <div className="flex items-center gap-2">
            <Chip tone="data">{audio.duration.toFixed(1)}s</Chip>
            <span className="min-w-0 flex-1 truncate text-xs text-ink-2">{audio.name}</span>
            <button
              type="button"
              onClick={togglePlay}
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink text-canvas hover:bg-action hover:text-on-action"
              aria-label={playing ? "暂停" : "播放"}
            >
              {playing ? <Pause size={13} /> : <Play size={13} className="ml-0.5" />}
            </button>
            <button
              type="button"
              onClick={toggleLoopPreview}
              className="flex items-center gap-1.5 rounded-full border border-line-2 px-3 py-1.5 text-xs transition-colors hover:border-action hover:text-action"
              style={looping ? { color: "var(--on-action)", background: "var(--action)", borderColor: "var(--action)" } : undefined}
              aria-label="循环预览截取片段"
              title="只循环播放当前选中的截取片段"
            >
              <Repeat2 size={13} />
              {looping ? "停止预览" : "预览片段"}
            </button>
          </div>
          <div className="border border-line-1 bg-surface-0 p-1">
            <div ref={waveRef} />
          </div>
          <p className="text-[11px] leading-relaxed text-ink-3">
            拖动上方视频进度条看画面，或在波形上拖出/调两侧把手选定区间（当前 {region ? `${region.start.toFixed(1)}–${region.end.toFixed(1)}s` : "—"}）。
          </p>
          <Button variant="action" icon={<Scissors size={14} />} disabled={!region || region.end - region.start <= 0} loading={busy === "cut"} onClick={cut} className="self-start">
            截取素材
          </Button>
        </>
      )}

      {/* 标记片段管理:命名 / 试听 / 选用 / 删除 / 勾选组合 */}
      {segments.length > 0 && (
        <div className="border border-line-1 bg-surface-1">
          <div className="flex items-center gap-2 border-b border-line-1 px-2 py-1.5">
            <Chip tone="special">{segments.length} 段素材</Chip>
            <span className="micro ml-auto">勾选后命名/组合</span>
            <Button variant="secondary" size="sm" icon={<Layers size={14} />} disabled={checkedCount < 2} loading={busy === "concat"} onClick={combine}>
              组合选中 {checkedCount > 1 ? `(${checkedCount})` : ""}
            </Button>
          </div>
          <ul className="flex max-h-52 flex-col overflow-y-auto">
            {segments.map((s) => (
              <li key={s.id} className="flex items-center gap-2 border-b border-line-1 px-2 py-1.5 last:border-b-0">
                <input type="checkbox" checked={checked.has(s.id)} onChange={() => toggleChecked(s.id)} className="h-3.5 w-3.5 accent-[var(--action)]" aria-label="选择组合" />
                <Input value={s.label} onChange={(e) => rename(s.id, e.target.value)} className="h-7 min-w-0 flex-1 text-xs" aria-label="片段命名" />
                <Chip tone="data">{s.duration.toFixed(1)}s</Chip>
                <audio src={fileUrl(s.path)} controls preload="none" className="h-8 w-32" />
                <button type="button" onClick={() => onCut(s)} className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink text-canvas hover:bg-action hover:text-on-action" aria-label="用作 RVC 音色转换源" title="用这段做音色转换">
                  <Wand2 size={13} />
                </button>
                <button type="button" onClick={() => remove(s.id)} className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-ink-2 hover:bg-surface-hover hover:text-danger" aria-label="删除片段" title="删除">
                  <Trash2 size={13} />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}