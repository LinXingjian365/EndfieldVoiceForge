# -*- coding: utf-8 -*-
"""提弗洛斯资料入库：解析解包表格 JSON -> 文本分块 -> 云端向量化 -> lore/typhoea_chunks.json。

用法（用 server 的 venv 跑，保证 numpy 可用）：
    third_party/index-tts/.venv/Scripts/python.exe scripts/ingest_lore.py

文本来源（均在 EndfieldUnpacker/DecryptOutput/TableCfg_json/）：
  1. CharacterTable.json       -> 提弗洛斯档案（profileRecord 标题 + 描述）与基础信息
  2. DialogTextTable.json      -> sim_talk / sim_gift 等提弗洛斯台词
  3. SNSDialogTable.json       -> 提弗洛斯 SNS 聊天树（chatId = sns_chr_0034_typhoea）
  4. SNSDialogOptionTable.json -> SNS 里管理员的选项（并入聊天树）

所有文本都是 TextId 间接引用，真正中文在 I18nTextTable_CN.json。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from apps.server.core import llm, paths  # noqa: E402


def load_json(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# 说话人 -> 展示名
SPEAKER_MAP = {
    "sns_chr_0034_typhoea": "提弗洛斯",
    "endmin": "管理员",
}


def resolve_text(obj, i18n: dict) -> str:
    """{id: int, text: ""} -> 中文；纯字符串直接返回。"""
    if isinstance(obj, str):
        return obj.strip()
    if isinstance(obj, dict):
        txt = obj.get("text")
        if txt:
            return str(txt).strip()
        tid = obj.get("id")
        if tid:
            return (i18n.get(str(tid), "") or "").strip()
    return ""


def extract_character(i18n: dict) -> list[dict]:
    table = load_json(paths.CHARACTER_TABLE_JSON)
    entry = table.get("chr_0034_typhoea")
    if not entry:
        print("[!] CharacterTable 里没找到 chr_0034_typhoea")
        return []
    chunks = []

    # 基础信息
    meta_bits = []
    name = resolve_text(entry.get("name"), i18n)
    eng = entry.get("engName", "")
    if name:
        meta_bits.append(f"姓名：{name}")
    if eng:
        meta_bits.append(f"英文名：{eng}")
    dept = entry.get("department", "")
    if dept:
        meta_bits.append(f"所属：{dept}")
    ctype = entry.get("charTypeId", "")
    if ctype:
        meta_bits.append(f"战斗类型：{ctype}")
    cv = entry.get("cvName", {})
    chi_cv = resolve_text(cv.get("ChiCVName"), i18n) if isinstance(cv, dict) else ""
    if chi_cv:
        meta_bits.append(f"中文配音：{chi_cv}")
    if meta_bits:
        chunks.append({"text": "【基础信息】" + "；".join(meta_bits) + "。", "source": "meta", "speaker": "提弗洛斯"})

    # 档案（profileRecord）
    for rec in entry.get("profileRecord", []) or []:
        title = resolve_text(rec.get("recordTitle"), i18n)
        desc = resolve_text(rec.get("recordDesc"), i18n)
        if not desc:
            continue
        head = f"【档案】{title}：" if title else "【档案】"
        chunks.append({"text": head + desc, "source": "archive", "speaker": ""})

    return chunks


def extract_sim_dialog(i18n: dict) -> list[dict]:
    """sim_talk / sim_gift 等提弗洛斯台词，按 ~6 句一组聚合。"""
    table = load_json(paths.DIALOG_TEXT_JSON)
    lines = []
    for key, row in table.items():
        if "typhoea" not in key and "typhoea" not in str(row.get("audioOverride", "")):
            continue
        text = resolve_text(row.get("dialogText"), i18n)
        if not text:
            continue
        speaker = resolve_text(row.get("actorName"), i18n) or "提弗洛斯"
        lines.append(f"{speaker}：{text}")
    if not lines:
        return []
    # 聚合
    chunks, buf = [], []
    for ln in lines:
        buf.append(ln)
        if len(buf) >= 6:
            chunks.append({"text": "【台词】\n" + "\n".join(buf), "source": "sim", "speaker": "提弗洛斯"})
            buf = []
    if buf:
        chunks.append({"text": "【台词】\n" + "\n".join(buf), "source": "sim", "speaker": "提弗洛斯"})
    return chunks


def extract_sns(i18n: dict, options: dict) -> list[dict]:
    table = load_json(paths.SNS_DIALOG_JSON)
    chunks = []
    for key, dialog in table.items():
        if dialog.get("chatId") != "sns_chr_0034_typhoea":
            continue
        content = dialog.get("dialogContentData", {}) or {}
        # 按 contentId 排序
        nodes = sorted(content.items(), key=lambda kv: int(kv[0]) if str(kv[0]).lstrip("-").isdigit() else 0)
        transcript = []

        def push(line: str):
            if not transcript or transcript[-1] != line:
                transcript.append(line)

        for _cid, node in nodes:
            if node.get("contentType") == 1:
                text = resolve_text(node.get("content"), i18n)
                if text:
                    sp = SPEAKER_MAP.get(node.get("speaker", ""), node.get("speaker", ""))
                    push(f"{sp}：{text}" if sp else text)
            # 管理员选项（作为其台词并入）
            for opt_id in node.get("dialogOptionIds", []) or []:
                opt = options.get(opt_id)
                if not opt:
                    continue
                opt_text = resolve_text(opt.get("optionDesc"), i18n)
                if opt_text:
                    push(f"管理员：{opt_text}")
        if transcript:
            chunks.append({"text": "【SNS 对话】\n" + "\n".join(transcript), "source": "sns", "speaker": "提弗洛斯"})
    return chunks


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    i18n = load_json(paths.I18N_CN_JSON)
    options = load_json(paths.SNS_OPTION_JSON)
    if not i18n:
        print("[!] 未找到 I18nTextTable_CN.json，检查 ENDFIELD_UNPACKER_DIR / 解包产物")
        sys.exit(1)

    chunks = extract_character(i18n) + extract_sim_dialog(i18n) + extract_sns(i18n, options)
    if not chunks:
        print("[!] 没有提取到任何提弗洛斯文本")
        sys.exit(1)

    if dry_run:
        print(f"[*] 共提取 {len(chunks)} 个分块（dry-run，不向量化）：\n")
        for i, c in enumerate(chunks):
            print(f"--- [{i}] {c['source']} ---")
            print(c["text"][:300])
            print()
        sys.exit(0)

    print(f"[*] 共 {len(chunks)} 个分块，开始向量化（model={paths.EMBED_MODEL}）...")
    vectors = []
    BATCH = 20
    for i in range(0, len(chunks), BATCH):
        batch = [c["text"] for c in chunks[i : i + BATCH]]
        vectors.extend(llm.embed_texts(batch))
        print(f"    embedded {min(i + BATCH, len(chunks))}/{len(chunks)}")

    os.makedirs(paths.LORE_DIR, exist_ok=True)
    store = {"embed_model": paths.EMBED_MODEL, "chunks": []}
    for c, v in zip(chunks, vectors):
        store["chunks"].append({"id": f"{c['source']}_{len(store['chunks'])}", "text": c["text"], "source": c["source"], "speaker": c["speaker"], "embedding": v})

    with open(paths.LORE_STORE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False)

    print(f"[+] 已写入 {paths.LORE_STORE}（{len(store['chunks'])} chunks）")


if __name__ == "__main__":
    main()
