# -*- coding: utf-8 -*-
"""EndfieldVoiceForge 路径配置。

所有脚本从这里取路径，不再硬编码绝对路径。
唯一的外部依赖是 EndfieldUnpacker（解包工具 + 解包产物 + vgmstream），
默认认为它与本仓库同级；否则设置环境变量 ENDFIELD_UNPACKER_DIR。
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

UNPACKER_DIR = os.path.abspath(
    os.environ.get("ENDFIELD_UNPACKER_DIR")
    or os.path.join(os.path.dirname(ROOT), "EndfieldUnpacker")
)
DECRYPT_OUT = os.path.join(UNPACKER_DIR, "DecryptOutput")
PCK_CHINESE_STREAM = os.path.join(
    DECRYPT_OUT, "Audio", "PCK", "Windows", "Chinese", "default_chinese_stream.pck"
)
AUDIO_DIALOG_JSON = os.path.join(DECRYPT_OUT, "TableCfg_json", "AudioDialog.json")
WEM_ALL_DIR = os.path.join(DECRYPT_OUT, "Audio_wem_all")
VGMSTREAM = os.path.join(UNPACKER_DIR, "vgmstream-win64", "vgmstream-cli.exe")

THIRD_PARTY = os.path.join(ROOT, "third_party")
GSV_DIR = os.path.join(THIRD_PARTY, "gpt-sovits")
RVC_DIR = os.path.join(THIRD_PARTY, "RVC")
INDEXTTS_DIR = os.path.join(THIRD_PARTY, "index-tts")

# index-tts 的 venv 同时被 GPT-SoVITS 复用（Python 3.11 + torch 2.8 cu128）
PY_TTS = os.path.join(INDEXTTS_DIR, ".venv", "Scripts", "python.exe")
PY_RVC = os.path.join(RVC_DIR, ".venv", "Scripts", "python.exe")

DATASETS_DIR = os.path.join(ROOT, "datasets")
CACHE_DIR = os.path.join(DATASETS_DIR, "cache")
TRAIN_WAV_DIR = os.path.join(DATASETS_DIR, "typhoea_train")
TRAIN_LIST_DIR = os.path.join(DATASETS_DIR, "typhoea_train_asr")
TRAIN_LIST = os.path.join(TRAIN_LIST_DIR, "typhoea.list")
SPEECH_POOL_DIR = os.path.join(DATASETS_DIR, "typhoea_speech2")
VAD_REF_DIR = os.path.join(DATASETS_DIR, "typhoea_ref_vad")

OUTPUTS_DIR = os.path.join(ROOT, "outputs")
REF_EXPERIMENTS_DIR = os.path.join(OUTPUTS_DIR, "ref_experiments")

SPEAKER = "typhoea"  # 提弗洛斯 = chr_0034_typhoea

# ---- 提弗洛斯 AI（资料接入）----
# 解包产物里的表格 JSON：剧情/对话/档案文本都走 TextId 间接引用，
# 实际中文文本在 I18nTextTable_CN.json 里（textId -> 中文）。
TABLECFG_JSON_DIR = os.path.join(DECRYPT_OUT, "TableCfg_json")
I18N_CN_JSON = os.path.join(TABLECFG_JSON_DIR, "I18nTextTable_CN.json")
CHARACTER_TABLE_JSON = os.path.join(TABLECFG_JSON_DIR, "CharacterTable.json")
DIALOG_TEXT_JSON = os.path.join(TABLECFG_JSON_DIR, "DialogTextTable.json")
SNS_DIALOG_JSON = os.path.join(TABLECFG_JSON_DIR, "SNSDialogTable.json")
SNS_OPTION_JSON = os.path.join(TABLECFG_JSON_DIR, "SNSDialogOptionTable.json")

# 资料入库后的分块 + 向量存储（scripts/ingest_lore.py 生成）
LORE_DIR = os.path.join(ROOT, "lore")
LORE_STORE = os.path.join(LORE_DIR, "typhoea_chunks.json")

# 云端 LLM / embedding（OpenAI 兼容协议）。6GB 显存已被语音模型占用，故走云端 API。
# 配置写在项目根目录 .env（已 gitignore，不上传 GitHub），也可用环境变量覆盖。
# 不做任何默认值：不配置就用不了 LLM/embedding（对应 /chat 会显示「未配置」）。

def _load_dotenv(path):
    """极简 .env 加载器（无第三方依赖）。已存在的环境变量优先于 .env。"""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("\"'")
            if k and k not in os.environ:
                os.environ[k] = v


_load_dotenv(os.path.join(ROOT, ".env"))

LLM_BASE_URL = os.environ.get("ENDFIELD_LLM_BASE_URL", "")
LLM_API_KEY = os.environ.get("ENDFIELD_LLM_API_KEY", "")
LLM_MODEL = os.environ.get("ENDFIELD_LLM_MODEL", "")
# 上游协议格式：openai（Chat Completions）| anthropic（Anthropic Messages 原生，直连不转换）
LLM_API_FORMAT = os.environ.get("ENDFIELD_LLM_API_FORMAT", "openai").lower()
# Anthropic 格式需要的 beta 头（anyrouter 等 1M 上下文模型需要 context-1m-2025-08-07）
LLM_ANTHROPIC_BETA = os.environ.get("ENDFIELD_LLM_ANTHROPIC_BETA", "context-1m-2025-08-07")
EMBED_BASE_URL = os.environ.get("ENDFIELD_EMBED_BASE_URL", "") or LLM_BASE_URL
EMBED_API_KEY = os.environ.get("ENDFIELD_EMBED_API_KEY", "") or LLM_API_KEY
EMBED_MODEL = os.environ.get("ENDFIELD_EMBED_MODEL", "")


# 反馈联系方式（「设置 → 系统」页展示，供用户联系开发者反馈问题/建议）
CONTACT = {
    "wechat": "Z2Z2S2S2",
    "qq": "2163645230",
    "bilibili": "易谦国学文化",
    "email": "linyuxin5211314@gmail.com",
}
# 用户在网页提交的反馈追加写入这里（本地收集，正式发布可改为 GitHub Issues）
FEEDBACK_FILE = os.path.join(ROOT, "outputs", "feedback.jsonl")


def import_unpacker():
    """让脚本能 `from extract_akpk import ...`（AKPK 解密逻辑在 EndfieldUnpacker 里）。"""
    if UNPACKER_DIR not in sys.path:
        sys.path.insert(0, UNPACKER_DIR)
