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


def import_unpacker():
    """让脚本能 `from extract_akpk import ...`（AKPK 解密逻辑在 EndfieldUnpacker 里）。"""
    if UNPACKER_DIR not in sys.path:
        sys.path.insert(0, UNPACKER_DIR)
