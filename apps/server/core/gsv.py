"""组装 GPT-SoVITS 各阶段(数据格式化 / s1 / s2)与工具(切片 / 降噪 / ASR)的命令与配置。

逻辑对齐上游 webui.py 的 open1a/open1b/open1c/open1Ba/open1Bb/open_slice/open_asr/open_denoise,
但不启动 Gradio,只返回 (cmd, env, cwd) 供 jobs.launch 使用。
"""
from __future__ import annotations

import json
import os

import yaml

from . import paths

PM = os.path.join("GPT_SoVITS", "pretrained_models")
PRETRAINED_SOVITS = {
    "v1": f"{PM}/s2G488k.pth",
    "v2": f"{PM}/gsv-v2final-pretrained/s2G2333k.pth",
    "v3": f"{PM}/s2Gv3.pth",
    "v4": f"{PM}/gsv-v4-pretrained/s2Gv4.pth",
    "v2Pro": f"{PM}/v2Pro/s2Gv2Pro.pth",
    "v2ProPlus": f"{PM}/v2Pro/s2Gv2ProPlus.pth",
}
PRETRAINED_GPT = {
    "v1": f"{PM}/s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt",
    "v2": f"{PM}/gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt",
    "v3": f"{PM}/s1v3.ckpt",
    "v4": f"{PM}/s1v3.ckpt",
    "v2Pro": f"{PM}/s1v3.ckpt",
    "v2ProPlus": f"{PM}/s1v3.ckpt",
}
SOVITS_ROOT = {"v1": "SoVITS_weights", "v2": "SoVITS_weights_v2", "v3": "SoVITS_weights_v3", "v4": "SoVITS_weights_v4", "v2Pro": "SoVITS_weights_v2Pro", "v2ProPlus": "SoVITS_weights_v2ProPlus"}
GPT_ROOT = {"v1": "GPT_weights", "v2": "GPT_weights_v2", "v3": "GPT_weights_v3", "v4": "GPT_weights_v4", "v2Pro": "GPT_weights_v2Pro", "v2ProPlus": "GPT_weights_v2ProPlus"}
CNHUBERT = f"{PM}/chinese-hubert-base"
BERT = f"{PM}/chinese-roberta-wwm-ext-large"
SV_PATH = f"{PM}/sv/pretrained_eres2netv2w24s4ep4.ckpt"
VERSIONS = list(SOVITS_ROOT)


def g(p: str) -> str:
    return os.path.join(paths.GSV_DIR, p)


# 6GB 显卡上桌面进程常占 ~1GB,不开 expandable_segments 首个 step 就会因碎片化 OOM。
# 上游 s2 DataLoader 默认 5 worker + pin_memory + prefetch 3,16GB 主机上再挂着 server/浏览器会把主机内存挤爆,
# 表现为首个 step "CUDA unknown error";GSV_NUM_WORKERS/GSV_PIN_MEMORY 由 patches/ 里的补丁读取。
GPU_ENV = {"PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True", "_CUDA_VISIBLE_DEVICES": "0", "GSV_NUM_WORKERS": "2", "GSV_PIN_MEMORY": "0"}
S1_NUM_WORKERS = 2


def available_versions() -> list[dict]:
    out = []
    for v in VERSIONS:
        out.append({"version": v, "sovits_pretrained": os.path.exists(g(PRETRAINED_SOVITS[v])), "gpt_pretrained": os.path.exists(g(PRETRAINED_GPT[v]))})
    return out


def exp_dir(exp: str) -> str:
    return g(os.path.join("logs", exp))


def _base_env(exp: str, inp_text: str, inp_wav: str, version: str) -> dict[str, str]:
    return {
        "PYTHONPATH": os.pathsep.join([paths.GSV_DIR, g("GPT_SoVITS")]),
        "inp_text": inp_text,
        "inp_wav_dir": inp_wav,
        "exp_name": exp,
        "opt_dir": exp_dir(exp),
        "cnhubert_base_dir": g(CNHUBERT),
        "bert_pretrained_dir": g(BERT),
        "version": version,
        "hz": "25hz",
        "is_half": "True",
        "i_part": "0",
        "all_parts": "1",
        "pretrained_s2G": g(PRETRAINED_SOVITS[version]),
        "s2config_path": g("GPT_SoVITS/configs/s2.json" if version not in ("v2Pro", "v2ProPlus") else f"GPT_SoVITS/configs/s2{version}.json"),
        "sv_path": g(SV_PATH),
        **GPU_ENV,
    }


# ---------- 数据格式化 1a/1b/1c ----------

FORMAT_STAGES = {
    "1a": ("GPT_SoVITS/prepare_datasets/1-get-text.py", "文本分词与 BERT 特征"),
    "1b": ("GPT_SoVITS/prepare_datasets/2-get-hubert-wav32k.py", "HuBERT 特征 + 32k 重采样"),
    "1sv": ("GPT_SoVITS/prepare_datasets/2-get-sv.py", "说话人向量(v2Pro)"),
    "1c": ("GPT_SoVITS/prepare_datasets/3-get-semantic.py", "语义 token"),
}


def format_stage(stage: str, exp: str, inp_text: str, inp_wav: str, version: str):
    script, _ = FORMAT_STAGES[stage]
    os.makedirs(exp_dir(exp), exist_ok=True)
    return [paths.PY_TTS, "-s", script], _base_env(exp, inp_text, inp_wav, version), paths.GSV_DIR


def merge_parts(stage: str, exp: str):
    """单卡时分片文件带 -0 后缀,合并成训练读取的名字(对齐 webui 逻辑)。"""
    d = exp_dir(exp)
    if stage == "1a":
        p = os.path.join(d, "2-name2text-0.txt")
        if os.path.exists(p):
            os.replace(p, os.path.join(d, "2-name2text.txt"))
    elif stage == "1c":
        p = os.path.join(d, "6-name2semantic-0.tsv")
        if os.path.exists(p):
            lines = open(p, encoding="utf-8").read().strip("\n").split("\n")
            with open(os.path.join(d, "6-name2semantic.tsv"), "w", encoding="utf-8") as f:
                f.write("item_name\tsemantic_audio\n" + "\n".join(lines) + "\n")
            os.remove(p)


def format_status(exp: str) -> dict:
    d = exp_dir(exp)
    return {
        "1a": os.path.exists(os.path.join(d, "2-name2text.txt")),
        "1b": os.path.isdir(os.path.join(d, "4-cnhubert")) and os.path.isdir(os.path.join(d, "5-wav32k")),
        "1sv": os.path.isdir(os.path.join(d, "7-sv_cn")),
        "1c": os.path.exists(os.path.join(d, "6-name2semantic.tsv")),
    }


# ---------- s2 (SoVITS) ----------

def s2_cmd(exp: str, version: str, batch_size: int, epochs: int, save_every: int, text_low_lr_rate: float = 0.4,
           if_save_latest: bool = True, if_save_every_weights: bool = True, grad_ckpt: bool = True, lora_rank: int = 0,
           resume: bool = True):
    cfg_path = g("GPT_SoVITS/configs/s2.json" if version not in ("v2Pro", "v2ProPlus") else f"GPT_SoVITS/configs/s2{version}.json")
    with open(cfg_path, encoding="utf-8") as f:
        data = json.load(f)
    s2_dir = exp_dir(exp)
    ckpt_dir = os.path.join(s2_dir, f"logs_s2_{version}")
    os.makedirs(ckpt_dir, exist_ok=True)
    if not resume:
        # 上游会自动从 logs_s2_<ver>/G_*.pth D_*.pth 续训;清掉即从预训练重新开始
        for fn in os.listdir(ckpt_dir):
            if fn.endswith(".pth"):
                os.remove(os.path.join(ckpt_dir, fn))
    data["train"]["batch_size"] = batch_size
    data["train"]["epochs"] = epochs
    data["train"]["text_low_lr_rate"] = text_low_lr_rate
    data["train"]["pretrained_s2G"] = g(PRETRAINED_SOVITS[version])
    data["train"]["pretrained_s2D"] = g(PRETRAINED_SOVITS[version].replace("s2G", "s2D"))
    data["train"]["if_save_latest"] = if_save_latest
    data["train"]["if_save_every_weights"] = if_save_every_weights
    data["train"]["save_every_epoch"] = save_every
    data["train"]["gpu_numbers"] = "0"
    data["train"]["grad_ckpt"] = grad_ckpt
    data["train"]["lora_rank"] = lora_rank
    data["model"]["version"] = version
    data["data"]["exp_dir"] = data["s2_ckpt_dir"] = s2_dir
    data["save_weight_dir"] = SOVITS_ROOT[version]
    data["name"] = exp
    data["version"] = version
    os.makedirs(g(SOVITS_ROOT[version]), exist_ok=True)
    tmp = g(os.path.join("TEMP", f"tmp_s2_{exp}.json"))
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    script = "GPT_SoVITS/s2_train.py" if version in ("v1", "v2", "v2Pro", "v2ProPlus") else "GPT_SoVITS/s2_train_v3_lora.py"
    env = {"PYTHONPATH": os.pathsep.join([paths.GSV_DIR, g("GPT_SoVITS")]), "version": version, **GPU_ENV}
    return [paths.PY_TTS, "-s", script, "--config", tmp], env, paths.GSV_DIR


# ---------- s1 (GPT) ----------

def s1_cmd(exp: str, version: str, batch_size: int, epochs: int, save_every: int,
           if_save_latest: bool = True, if_save_every_weights: bool = True, if_dpo: bool = False):
    cfg_path = g("GPT_SoVITS/configs/s1longer.yaml" if version == "v1" else "GPT_SoVITS/configs/s1longer-v2.yaml")
    with open(cfg_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    s1_dir = exp_dir(exp)
    data["train"]["batch_size"] = batch_size
    data["train"]["epochs"] = epochs
    data["data"]["num_workers"] = S1_NUM_WORKERS
    data["pretrained_s1"] = g(PRETRAINED_GPT[version])
    data["train"]["save_every_n_epoch"] = save_every
    data["train"]["if_save_every_weights"] = if_save_every_weights
    data["train"]["if_save_latest"] = if_save_latest
    data["train"]["if_dpo"] = if_dpo
    data["train"]["half_weights_save_dir"] = GPT_ROOT[version]
    data["train"]["exp_name"] = exp
    data["train_semantic_path"] = os.path.join(s1_dir, "6-name2semantic.tsv")
    data["train_phoneme_path"] = os.path.join(s1_dir, "2-name2text.txt")
    data["output_dir"] = os.path.join(s1_dir, f"logs_s1_{version}")
    os.makedirs(g(GPT_ROOT[version]), exist_ok=True)
    # 清空旧 ckpt,避免残留 checkpoint 触发 weights_only 反序列化失败
    ckpt_dir = os.path.join(s1_dir, f"logs_s1_{version}", "ckpt")
    os.makedirs(ckpt_dir, exist_ok=True)
    for fn in os.listdir(ckpt_dir):
        os.remove(os.path.join(ckpt_dir, fn))
    tmp = g(os.path.join("TEMP", f"tmp_s1_{exp}.yaml"))
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)
    env = {"PYTHONPATH": os.pathsep.join([paths.GSV_DIR, g("GPT_SoVITS")]), "hz": "25hz", "version": version, **GPU_ENV}
    return [paths.PY_TTS, "-s", "GPT_SoVITS/s1_train.py", "--config_file", tmp], env, paths.GSV_DIR


# ---------- 工具 ----------

def slice_cmd(inp: str, out: str, threshold=-34, min_length=4000, min_interval=300, hop_size=10, max_sil_kept=500, _max=0.9, alpha=0.25):
    return [paths.PY_TTS, "-s", "tools/slice_audio.py", inp, out, str(threshold), str(min_length), str(min_interval), str(hop_size), str(max_sil_kept), str(_max), str(alpha), "0", "1"], {}, paths.GSV_DIR


def denoise_cmd(inp: str, out: str, precision: str = "float16"):
    return [paths.PY_TTS, "-s", "tools/cmd-denoise.py", "-i", inp, "-o", out, "-p", precision], {}, paths.GSV_DIR


def asr_cmd(inp: str, out: str, lang: str = "zh", backend: str = "funasr", precision: str = "float32", model_size: str = "large"):
    script = "tools/asr/funasr_asr.py" if backend == "funasr" else "tools/asr/fasterwhisper_asr.py"
    return [paths.PY_TTS, "-s", script, "-i", inp, "-o", out, "-s", model_size, "-l", lang, "-p", precision], {}, paths.GSV_DIR


def uvr5_cmd(model_name: str, inp: str, out_vocal: str, out_inst: str, agg: int = 10, fmt: str = "wav"):
    """UVR5 上游只有 Gradio;用一段内联脚本直接调 tools/uvr5/webui.py 里的 uvr()。"""
    code = (
        "import sys,os;sys.argv=['x','cuda','True','0','False'];"
        f"os.chdir({paths.GSV_DIR!r});sys.path.insert(0,'tools/uvr5');sys.path.insert(0,'.');"
        "import webui as u;"
        f"[print(x) for x in u.uvr({model_name!r},{inp!r},{out_vocal!r},[],{out_inst!r},{agg},{fmt!r})]"
    )
    return [paths.PY_TTS, "-c", code], {}, paths.GSV_DIR


def uvr5_models() -> list[str]:
    d = g("tools/uvr5/uvr5_weights")
    if not os.path.isdir(d):
        return []
    return sorted(fn.replace(".pth", "").replace(".ckpt", "") for fn in os.listdir(d) if fn.endswith((".pth", ".ckpt")) or "onnx" in fn)
