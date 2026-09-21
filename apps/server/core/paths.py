"""路径常量:复用仓库根目录的 config.py,并补上 server 专用目录。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config as _cfg  # noqa: E402

VERSION = "0.1.0"

ROOT = _cfg.ROOT
UNPACKER_DIR = _cfg.UNPACKER_DIR
GSV_DIR = _cfg.GSV_DIR
RVC_DIR = _cfg.RVC_DIR
INDEXTTS_DIR = _cfg.INDEXTTS_DIR
PY_TTS = _cfg.PY_TTS
PY_RVC = _cfg.PY_RVC
DATASETS_DIR = _cfg.DATASETS_DIR
OUTPUTS_DIR = _cfg.OUTPUTS_DIR
VGMSTREAM = _cfg.VGMSTREAM

# ---- 提弗洛斯 AI ----
TABLECFG_JSON_DIR = _cfg.TABLECFG_JSON_DIR
I18N_CN_JSON = _cfg.I18N_CN_JSON
CHARACTER_TABLE_JSON = _cfg.CHARACTER_TABLE_JSON
DIALOG_TEXT_JSON = _cfg.DIALOG_TEXT_JSON
SNS_DIALOG_JSON = _cfg.SNS_DIALOG_JSON
SNS_OPTION_JSON = _cfg.SNS_OPTION_JSON
LORE_DIR = _cfg.LORE_DIR
LORE_STORE = _cfg.LORE_STORE
LLM_BASE_URL = _cfg.LLM_BASE_URL
LLM_API_KEY = _cfg.LLM_API_KEY
LLM_MODEL = _cfg.LLM_MODEL
LLM_API_FORMAT = _cfg.LLM_API_FORMAT
LLM_ANTHROPIC_BETA = _cfg.LLM_ANTHROPIC_BETA
EMBED_BASE_URL = _cfg.EMBED_BASE_URL
EMBED_API_KEY = _cfg.EMBED_API_KEY
EMBED_MODEL = _cfg.EMBED_MODEL
CONTACT = _cfg.CONTACT
FEEDBACK_FILE = _cfg.FEEDBACK_FILE

ASSETS_DIR = os.path.join(ROOT, "assets")
CHARACTERS_DIR = os.path.join(ROOT, "characters")
GENERATED_DIR = os.path.join(OUTPUTS_DIR, "generated")
UPLOADS_DIR = os.path.join(OUTPUTS_DIR, "uploads")
REF_SLICES_DIR = os.path.join(OUTPUTS_DIR, "ref_slices")
LIBRARY_DB = os.path.join(OUTPUTS_DIR, "library.db")
JOBS_LOG_DIR = os.path.join(OUTPUTS_DIR, "jobs")

for d in (GENERATED_DIR, UPLOADS_DIR, REF_SLICES_DIR, JOBS_LOG_DIR):
    os.makedirs(d, exist_ok=True)

# 允许 /files 读取的根(防止任意路径读取)
SAFE_ROOTS = (ROOT, UNPACKER_DIR)


def resolve(rel_or_abs: str) -> str:
    """相对路径按仓库根解析;返回绝对路径。"""
    p = rel_or_abs if os.path.isabs(rel_or_abs) else os.path.join(ROOT, rel_or_abs)
    return os.path.normpath(p)


def is_safe(abs_path: str) -> bool:
    ap = os.path.normcase(os.path.abspath(abs_path))
    return any(ap.startswith(os.path.normcase(os.path.abspath(r)) + os.sep) for r in SAFE_ROOTS)


def rel_to_root(abs_path: str) -> str:
    try:
        return os.path.relpath(abs_path, ROOT).replace("\\", "/")
    except ValueError:
        return abs_path
