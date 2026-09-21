"""数据集:管线步骤触发、样本列表、文本校对、.list 读写。"""
from __future__ import annotations

import json
import os
import subprocess

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import characters, jobs as jobmgr, paths

router = APIRouter(prefix="/datasets", tags=["datasets"])

PIPELINE = [
    {"id": "measure", "script": "pipeline/01_measure_externals.py", "title": "量时长", "desc": "解密中文语音流 PCK externals 区,vgmstream 量每条 wem 时长并缓存", "produces": "datasets/cache/ext_durations.json"},
    {"id": "select", "script": "pipeline/02_select_speech.py", "title": "定位台词", "desc": "按 AudioDialog.wavDuration 最近邻找 wem,解码后量 F0 / 有声比", "produces": "datasets/cache/select_speech2.txt"},
    {"id": "extract", "script": "pipeline/03_extract_train.py", "title": "筛训练集", "desc": "F0 180–350Hz、有声比≥0.30、0.5–40s 过滤,解码为 wav", "produces": "datasets/typhoea_train/manifest.json"},
    {"id": "asr", "script": None, "title": "ASR 打标", "desc": "用 GPT-SoVITS 的 FunASR 对训练集整目录识别(在训练页/工具页发起)", "produces": "datasets/typhoea_train_asr/typhoea_train.list"},
    {"id": "postprocess", "script": "pipeline/04_postprocess_list.py", "title": "规范列表", "desc": "把 ASR 输出规范成 path|speaker|zh|text,剔除空文本", "produces": "datasets/typhoea_train_asr/typhoea.list"},
]


def _char(cid: str) -> dict:
    c = characters.get(cid)
    if not c:
        raise HTTPException(404, f"character {cid} not found")
    return c


@router.get("/{cid}/pipeline")
def pipeline_status(cid: str):
    _char(cid)
    out = []
    for step in PIPELINE:
        p = paths.resolve(step["produces"])
        done = os.path.exists(p)
        running = None
        for j in jobmgr.all_jobs():
            if j.kind == f"pipeline:{step['id']}" and j.status == "running":
                running = j.id
        out.append({**step, "done": done, "mtime": os.path.getmtime(p) if done else None, "running": running})
    return out


@router.post("/{cid}/pipeline/{step_id}")
def run_pipeline_step(cid: str, step_id: str):
    _char(cid)
    step = next((s for s in PIPELINE if s["id"] == step_id), None)
    if not step or not step["script"]:
        raise HTTPException(400, "step not runnable here")
    if jobmgr.running_of_kind(f"pipeline:{step_id}"):
        raise HTTPException(409, "already running")
    # 管线脚本用系统 python(需要 numpy/librosa),优先 index-tts venv(已含 librosa/soundfile)
    py = paths.PY_TTS
    job = jobmgr.launch(f"pipeline:{step_id}", step["title"], [py, "-u", paths.resolve(step["script"])], cwd=paths.ROOT, meta={"character": cid})
    return job.public()


def _read_list(list_path: str) -> dict[str, str]:
    m = {}
    if os.path.isfile(list_path):
        with open(list_path, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("|")
                if len(parts) >= 4:
                    m[os.path.normcase(os.path.abspath(parts[0]))] = "|".join(parts[3:])
    return m


CATEGORIES = ["dialog", "commvo", "combat", "radio", "other"]


def _infer_category(name: str) -> str:
    """按 wem 文件名推断类别:对话/语气喘气/战斗受击/电台/其他。"""
    n = name.lower()
    if "combat" in n or "attack" in n or "hurt" in n or "remind" in n or "bark" in n:
        return "combat"
    if "commvo" in n or "laugh" in n or "sigh" in n or "sick" in n or "neutral" in n or "positive" in n or "negative" in n or "breath" in n:
        return "commvo"
    if "radio" in n:
        return "radio"
    # 其余 chr_0034_typhoea 的角色台词/独白/互动(mono/sim/interact/explore 等)与 au_dlg/au_voice 一律视为对话
    return "dialog"


@router.get("/{cid}/samples")
def samples(cid: str):
    c = _char(cid)
    wav_dir = paths.resolve(c["dataset"]["wavDir"])
    lst = paths.resolve(c["dataset"]["list"])
    texts = _read_list(lst)
    manifest_p = os.path.join(wav_dir, "manifest.json")
    rows = []
    if os.path.isfile(manifest_p):
        manifest = json.load(open(manifest_p, encoding="utf-8"))
        for m in manifest:
            ap = os.path.join(wav_dir, m["wav"])
            if not os.path.isfile(ap):
                continue
            key = os.path.normcase(os.path.abspath(ap))
            rows.append({
                "idx": m["idx"], "wav": paths.rel_to_root(ap), "path": m.get("path", ""), "dur": m.get("dur", 0),
                "f0": m.get("f0", 0), "voiced": m.get("voiced", 0), "vt": m.get("vt", -1),
                "text": texts.get(key), "inList": key in texts, "excluded": bool(m.get("excluded", False)),
                "category": m.get("category") or _infer_category(m.get("path", "")),
                "favorite": bool(m.get("favorite", False)),
            })
    else:
        for fn in sorted(os.listdir(wav_dir)) if os.path.isdir(wav_dir) else []:
            if fn.endswith(".wav"):
                ap = os.path.join(wav_dir, fn)
                key = os.path.normcase(os.path.abspath(ap))
                rows.append({"idx": None, "wav": paths.rel_to_root(ap), "path": fn, "dur": 0, "f0": 0, "voiced": 0, "vt": -1, "text": texts.get(key), "inList": key in texts, "excluded": False, "category": _infer_category(fn), "favorite": False})
    kept = [r for r in rows if not r["excluded"]]
    return {
        "count": len(kept), "inList": sum(1 for r in kept if r["inList"]),
        "totalDur": round(sum(r["dur"] for r in kept), 1),
        "excluded": sum(1 for r in rows if r["excluded"]),
        "samples": rows,
    }


class TextPatch(BaseModel):
    text: str


@router.patch("/{cid}/samples/text")
def set_text(cid: str, wav: str, body: TextPatch):
    """改一条样本的文本;text 为空则从 .list 移除。"""
    c = _char(cid)
    lst = paths.resolve(c["dataset"]["list"])
    ap = paths.resolve(wav)
    if not os.path.isfile(ap):
        raise HTTPException(404, "wav not found")
    lines = []
    found = False
    if os.path.isfile(lst):
        with open(lst, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("|")
                if len(parts) >= 4 and os.path.normcase(os.path.abspath(parts[0])) == os.path.normcase(os.path.abspath(ap)):
                    found = True
                    if body.text.strip():
                        lines.append(f"{parts[0]}|{parts[1]}|{parts[2]}|{body.text.strip()}")
                    continue
                if line.strip():
                    lines.append(line.rstrip("\n"))
    if not found and body.text.strip():
        lines.append(f"{ap}|{c['speakerChannel']}|zh|{body.text.strip()}")
    os.makedirs(os.path.dirname(lst), exist_ok=True)
    with open(lst, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return {"ok": True, "inList": bool(body.text.strip()), "count": len(lines)}


class CategoryPatch(BaseModel):
    category: str


@router.patch("/{cid}/samples/category")
def set_category(cid: str, wav: str, body: CategoryPatch):
    """手动覆盖样本类别。"""
    c = _char(cid)
    ap = paths.resolve(wav)
    if not os.path.isfile(ap):
        raise HTTPException(404, "wav not found")
    if body.category not in CATEGORIES:
        raise HTTPException(400, f"category must be one of {CATEGORIES}")
    wav_dir = paths.resolve(c["dataset"]["wavDir"])
    mp = os.path.join(wav_dir, "manifest.json")
    if not os.path.isfile(mp):
        raise HTTPException(404, "manifest not found")
    m = json.load(open(mp, encoding="utf-8"))
    name = os.path.basename(ap)
    entry = next((x for x in m if os.path.basename(x.get("wav", "")) == name), None)
    if entry is None:
        raise HTTPException(404, "sample not in manifest")
    entry["category"] = body.category
    json.dump(m, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "category": body.category}


class FavoritePatch(BaseModel):
    favorite: bool


class CategoryBatchBody(BaseModel):
    wavs: list[str]
    category: str


@router.post("/{cid}/samples/category_batch")
def set_category_batch(cid: str, body: CategoryBatchBody):
    """批量设置样本类别。"""
    if body.category not in CATEGORIES:
        raise HTTPException(400, f"category must be one of {CATEGORIES}")
    c = _char(cid)
    wav_dir = paths.resolve(c["dataset"]["wavDir"])
    mp = os.path.join(wav_dir, "manifest.json")
    if not os.path.isfile(mp):
        raise HTTPException(404, "manifest not found")
    m = json.load(open(mp, encoding="utf-8"))
    names = {os.path.basename(paths.resolve(w)) for w in body.wavs}
    changed = 0
    for entry in m:
        if os.path.basename(entry.get("wav", "")) in names:
            entry["category"] = body.category
            changed += 1
    json.dump(m, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "changed": changed}


@router.post("/{cid}/samples/autocat")
def autocat(cid: str):
    """按 wem 源文件名自动分类全部样本并持久化(对话/语气/战斗/电台), 类别不再随列表飘移。"""
    c = _char(cid)
    wav_dir = paths.resolve(c["dataset"]["wavDir"])
    mp = os.path.join(wav_dir, "manifest.json")
    if not os.path.isfile(mp):
        raise HTTPException(404, "manifest not found")
    m = json.load(open(mp, encoding="utf-8"))
    changed = 0
    for entry in m:
        cat = _infer_category(entry.get("path", ""))
        if entry.get("category") != cat:
            entry["category"] = cat
            changed += 1
    json.dump(m, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "changed": changed}


@router.patch("/{cid}/samples/favorite")
def set_favorite(cid: str, wav: str, body: FavoritePatch):
    """收藏/取消收藏样本(favorite 置顶展示用,持久化到 manifest.json)。"""
    c = _char(cid)
    ap = paths.resolve(wav)
    if not os.path.isfile(ap):
        raise HTTPException(404, "wav not found")
    wav_dir = paths.resolve(c["dataset"]["wavDir"])
    mp = os.path.join(wav_dir, "manifest.json")
    if not os.path.isfile(mp):
        raise HTTPException(404, "manifest not found")
    m = json.load(open(mp, encoding="utf-8"))
    name = os.path.basename(ap)
    entry = next((x for x in m if os.path.basename(x.get("wav", "")) == name), None)
    if entry is None:
        raise HTTPException(404, "sample not in manifest")
    if body.favorite:
        entry["favorite"] = True
    else:
        entry.pop("favorite", None)
    json.dump(m, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "favorite": body.favorite}


@router.delete("/{cid}/samples")
def delete_sample(cid: str, wav: str):
    c = _char(cid)
    ap = paths.resolve(wav)
    wav_dir = paths.resolve(c["dataset"]["wavDir"])
    if not paths.is_safe(ap) or not ap.startswith(os.path.normpath(wav_dir)):
        raise HTTPException(403)
    if os.path.isfile(ap):
        os.remove(ap)
    set_text(cid, wav, TextPatch(text=""))
    # manifest 同步
    mp = os.path.join(wav_dir, "manifest.json")
    if os.path.isfile(mp):
        m = json.load(open(mp, encoding="utf-8"))
        m = [x for x in m if os.path.join(wav_dir, x["wav"]) != ap]
        json.dump(m, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True}


EXCLUDED_DIR = "_excluded"


class WavsBody(BaseModel):
    wavs: list[str]


class PrefixBody(BaseModel):
    prefix: str


def _set_excluded(cid: str, rels: list[str], want: bool) -> dict:
    """把样本移入/移出 _excluded/ 子目录(预处理只扫顶层文件, 移入即自动退出训练), 并同步 manifest 与 .list。"""
    c = _char(cid)
    wav_dir = paths.resolve(c["dataset"]["wavDir"])
    mp = os.path.join(wav_dir, "manifest.json")
    if not os.path.isfile(mp):
        raise HTTPException(404, "manifest not found")
    m = json.load(open(mp, encoding="utf-8"))
    ex_dir = os.path.join(wav_dir, EXCLUDED_DIR)
    changed = 0
    for rel in rels:
        name = os.path.basename(paths.resolve(rel))
        entry = next((x for x in m if os.path.basename(x.get("wav", "")) == name), None)
        if entry is None or bool(entry.get("excluded", False)) == want:
            continue
        if want:
            set_text(cid, rel, TextPatch(text=""))  # 先从 .list 移除(需在移动前, set_text 要求文件存在)
            os.makedirs(ex_dir, exist_ok=True)
            src = os.path.join(wav_dir, entry["wav"])
            if os.path.isfile(src):
                os.replace(src, os.path.join(ex_dir, name))
            entry["wav"] = f"{EXCLUDED_DIR}/{name}"
            entry["excluded"] = True
        else:
            src = os.path.join(wav_dir, entry["wav"])
            if os.path.isfile(src):
                os.replace(src, os.path.join(wav_dir, name))
            entry["wav"] = name
            entry.pop("excluded", None)
        changed += 1
    json.dump(m, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"ok": True, "changed": changed}


@router.post("/{cid}/samples/exclude")
def exclude_samples(cid: str, body: WavsBody):
    return _set_excluded(cid, body.wavs, True)


@router.post("/{cid}/samples/restore")
def restore_samples(cid: str, body: WavsBody):
    return _set_excluded(cid, body.wavs, False)


@router.post("/{cid}/samples/exclude_prefix")
def exclude_prefix(cid: str, body: PrefixBody):
    """按前缀批量剔除(匹配 wav 文件名或来源 path, 如 au_radio_)。"""
    c = _char(cid)
    wav_dir = paths.resolve(c["dataset"]["wavDir"])
    mp = os.path.join(wav_dir, "manifest.json")
    if not os.path.isfile(mp) or not body.prefix.strip():
        raise HTTPException(400, "bad prefix")
    m = json.load(open(mp, encoding="utf-8"))
    rels = [
        paths.rel_to_root(os.path.join(wav_dir, x["wav"]))
        for x in m
        if not x.get("excluded")
        and (os.path.basename(x.get("wav", "")).startswith(body.prefix) or x.get("path", "").startswith(body.prefix))
    ]
    return _set_excluded(cid, rels, True)


@router.get("/{cid}/list")
def get_list(cid: str):
    c = _char(cid)
    lst = paths.resolve(c["dataset"]["list"])
    if not os.path.isfile(lst):
        return {"path": c["dataset"]["list"], "content": ""}
    return {"path": c["dataset"]["list"], "content": open(lst, encoding="utf-8").read()}


class ListBody(BaseModel):
    content: str


@router.put("/{cid}/list")
def put_list(cid: str, body: ListBody):
    c = _char(cid)
    lst = paths.resolve(c["dataset"]["list"])
    os.makedirs(os.path.dirname(lst), exist_ok=True)
    with open(lst, "w", encoding="utf-8") as f:
        f.write(body.content.rstrip("\n") + "\n")
    return {"ok": True, "lines": len([l for l in body.content.splitlines() if l.strip()])}
