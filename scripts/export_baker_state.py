# -*- coding: utf-8 -*-
"""把提弗洛斯的 SNS 对话导出成 baker-dx 的 v1 状态文件，让 Baker 复刻能直接显示。

用法（用 server 的 venv 跑，保证 numpy 可用）：
    third_party/index-tts/.venv/Scripts/python.exe scripts/export_baker_state.py [--to-baker]

产物：
    outputs/baker/baker_dx_state.json
    --to-baker 时同时覆盖 D:\\baker-dx-1.4.0\\baker_dx_state.json（桌面版读取它）

数据来源：EndfieldUnpacker 解包的 SNSDialogTable / SNSDialogOptionTable / I18nTextTable_CN。
"""
import base64
import json
import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from apps.server.core import paths  # noqa: E402

BAKER_DX_DIR = os.environ.get("BAKER_DX_DIR", r"D:\baker-dx-1.4.0")


def load_json(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def resolve_text(obj, i18n: dict) -> str:
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


def png_data_url(path: str) -> str:
    """本地 PNG -> data URL（找不到则空串）。"""
    if not os.path.isfile(path):
        return ""
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")


def find_avatar(*candidates: str) -> str:
    for p in candidates:
        url = png_data_url(p)
        if url:
            return url
    return ""


def collect_typhoea_transcript(i18n: dict, options: dict) -> list[dict]:
    """合并 7 棵提弗洛斯 SNS 聊天树，返回 [{sender: 'typhoea'|'user'|'status', text, image?}, ...]。

    speaker 映射：sns_chr_0034_typhoea -> typhoea，endmin -> user，空 -> status。
    contentType=1 为文本，2 为图片。
    """
    table = load_json(paths.SNS_DIALOG_JSON)
    out: list[dict] = []
    for _key, dialog in table.items():
        if dialog.get("chatId") != "sns_chr_0034_typhoea":
            continue
        content = dialog.get("dialogContentData", {}) or {}
        nodes = sorted(content.items(), key=lambda kv: int(kv[0]) if str(kv[0]).lstrip("-").isdigit() else 0)
        for _cid, node in nodes:
            speaker = node.get("speaker", "")
            if speaker == "sns_chr_0034_typhoea":
                who = "typhoea"
            elif speaker == "endmin":
                who = "user"
            else:
                who = "status"
            ctype = node.get("contentType", 1)
            if ctype == 2:
                # 图片节点：记录图片资产名
                imgs = node.get("contentParam", []) or []
                out.append({"sender": "typhoea", "image": imgs[0] if imgs else "", "text": ""})
                continue
            text = resolve_text(node.get("content"), i18n)
            if text:
                out.append({"sender": who, "text": text, "image": ""})
            for opt_id in node.get("dialogOptionIds", []) or []:
                opt = options.get(opt_id)
                if not opt:
                    continue
                opt_text = resolve_text(opt.get("optionDesc"), i18n)
                if opt_text:
                    out.append({"sender": "user", "text": opt_text, "image": ""})
    return out


def build_state(transcript: list[dict]) -> dict:
    user_id = str(uuid.uuid4())
    typhoea_id = str(uuid.uuid4())

    typhoea_avatar = find_avatar(
        os.path.join(paths.ROOT, "assets", "characters", "typhoea", "icon_round_chr_0034_typhoea.png"),
        os.path.join(paths.ROOT, "characters", "typhoea", "icon_round_chr_0034_typhoea.png"),
        os.path.join(paths.ROOT, "assets", "characters", "typhoea", "icon_chr_0034_typhoea.png"),
    )
    user_avatar = find_avatar(
        os.path.join(BAKER_DX_DIR, "assets", "avatar", "endministrator.png"),
    )

    messages = []
    for item in transcript:
        if item.get("image"):
            # v1 图片消息：用资产名占位（未提取 typhoea 图片时退化为状态行）
            messages.append(
                {"id": str(uuid.uuid4()), "sender_id": typhoea_id, "content": f"[图片 {item['image']}]", "kind": "Status", "reactions": []}
            )
            continue
        if not item.get("text"):
            continue
        sender = typhoea_id if item["sender"] == "typhoea" else user_id
        kind = "Status" if item["sender"] == "status" else "Normal"
        messages.append(
            {"id": str(uuid.uuid4()), "sender_id": sender, "content": item["text"], "kind": kind, "reactions": []}
        )

    return {
        "user_profile": {"id": user_id, "name": "Endministrator", "avatar_url": user_avatar},
        "operators": [{"id": typhoea_id, "name": "提弗洛斯", "avatar_url": typhoea_avatar}],
        "contacts": [
            {
                "id": typhoea_id,
                "unread_count": 0,
                "chat_head_style": "Alt",
                "name": "提弗洛斯",
                "avatar_url": typhoea_avatar,
                "participant_ids": [typhoea_id],
                "is_group": False,
            }
        ],
        "messages": {typhoea_id: messages},
        "stickers": [],
        "background": {"mode": "DotDark", "custom_color": "#1a1a1a", "custom_image": ""},
        "update_snooze_date": None,
        "hide_tutorial": True,
        "show_tip_saving_image_problem_on_web": False,
    }


def main() -> None:
    i18n = load_json(paths.I18N_CN_JSON)
    options = load_json(paths.SNS_OPTION_JSON)
    if not i18n:
        print("[!] 未找到 I18nTextTable_CN.json")
        sys.exit(1)

    transcript = collect_typhoea_transcript(i18n, options)
    if not transcript:
        print("[!] 没有提取到提弗洛斯 SNS 对话")
        sys.exit(1)

    state = build_state(transcript)
    n_msg = len(state["messages"][next(iter(state["messages"]))])

    out_dir = os.path.join(paths.ROOT, "outputs", "baker")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "baker_dx_state.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"[+] 已生成 {out_file}（1 个联系人「提弗洛斯」，{n_msg} 条消息）")
    print(f"    头像：提弗洛斯={'有' if state['operators'][0]['avatar_url'] else '无'}，管理员={'有' if state['user_profile']['avatar_url'] else '无'}")

    if "--to-baker" in sys.argv:
        target = os.path.join(BAKER_DX_DIR, "baker_dx_state.json")
        with open(target, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print(f"[+] 已覆盖 {target}")
    else:
        print(f"    提示：加 --to-baker 可直接覆盖 {BAKER_DX_DIR}\\baker_dx_state.json")


if __name__ == "__main__":
    main()
