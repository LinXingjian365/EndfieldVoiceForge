# -*- coding: utf-8 -*-
"""RVC 声音转换：提弗洛斯音色微调训练编排脚本。

用法（在项目根目录执行）：
  python rvc_train.py preprocess    # 数据切分
  python rvc_train.py f0            # RMVPE 音高提取
  python rvc_train.py hubert        # HuBERT 特征提取
  python rvc_train.py files         # 生成 filelist.txt + config.json
  python rvc_train.py train         # 训练
  python rvc_train.py all           # 依次执行以上全部
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

RVC = config.RVC_DIR
PY = config.PY_RVC

EXP = config.SPEAKER
INPUT = config.TRAIN_WAV_DIR
LOG_DIR = os.path.join(RVC, "logs", EXP)
SR = "40k"
VERSION = "v2"
BATCH = 1
EPOCHS = 200
SAVE_EVERY = 20
PRETRAIN_G = "assets/pretrained_v2/f0G40k.pth"
PRETRAIN_D = "assets/pretrained_v2/f0D40k.pth"


def run(args):
    env = os.environ.copy()
    env["PYTHONPATH"] = RVC + os.pathsep + env.get("PYTHONPATH", "")
    print(">>>", " ".join(args))
    return subprocess.run([PY, *args], cwd=RVC, env=env).returncode


def preprocess():
    # 用 -m 以模块方式运行，避免 sys.path[0]=train/ 把包名 train 解析成 train.py
    return run(
        ["-m", "train.preprocess", INPUT, "40000", "8", f"logs/{EXP}", "False", "3.7"]
    )


def extract_f0():
    return run(
        ["-m", "train.dataset.extract_f0", "cuda", "1", "0", "0", f"logs/{EXP}", "true"]
    )


def extract_hubert():
    return run(
        [
            "-m", "train.dataset.extract_hubert_feature",
            "cuda:0", "1", "0", "0", f"logs/{EXP}", VERSION, "true",
        ]
    )


def gen_files():
    gt = os.path.join(LOG_DIR, "0_gt_wavs")
    feat = os.path.join(
        LOG_DIR, "3_feature768" if VERSION == "v2" else "3_feature256"
    )
    f0 = os.path.join(LOG_DIR, "2a_f0")
    f0nsf = os.path.join(LOG_DIR, "2b-f0nsf")

    def base(d):
        # 与 WebUI 一致：取第一个点之前的名字，兼容 "0_0.wav.npy"
        return {n.split(".")[0] for n in os.listdir(d)}

    names = sorted(base(gt) & base(feat) & base(f0) & base(f0nsf))
    if not names:
        print("没有可用于训练的有效音频，请先完成切分与特征提取")
        return 1
    lines = [
        f"{gt}/{n}.wav|{feat}/{n}.npy|{f0}/{n}.wav.npy|{f0nsf}/{n}.wav.npy|0"
        for n in names
    ]
    with open(os.path.join(LOG_DIR, "filelist.txt"), "w", encoding="utf8") as f:
        f.write("\n".join(lines) + "\n")

    # 40k 采样率无论 v1/v2 都用 v1/40k.json（与 WebUI 逻辑一致）
    with open(os.path.join(RVC, "configs", "v1", "40k.json"), "r", encoding="utf8") as f:
        cfg = json.load(f)
    cfg.pop("speaker_info", None)
    with open(os.path.join(LOG_DIR, "config.json"), "w", encoding="utf8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4, sort_keys=True)
        f.write("\n")
    print(f"filelist.txt: {len(lines)} 行")
    return 0


def train():
    return run(
        [
            "-m", "train.train", "-e", EXP, "-sr", SR, "-f0", "1",
            "-bs", str(BATCH), "-g", "0", "-te", str(EPOCHS), "-se", str(SAVE_EVERY),
            "-pg", PRETRAIN_G, "-pd", PRETRAIN_D,
            "-l", "0", "-c", "0", "-sw", "1", "-v", VERSION,
        ]
    )


def main():
    cmds = {
        "preprocess": preprocess,
        "f0": extract_f0,
        "hubert": extract_hubert,
        "files": gen_files,
        "train": train,
    }
    if len(sys.argv) < 2:
        print("用法: python rvc_train.py [preprocess|f0|hubert|files|train|all]")
        return 1
    arg = sys.argv[1]
    os.makedirs(LOG_DIR, exist_ok=True)
    if arg == "all":
        for fn in (preprocess, extract_f0, extract_hubert, gen_files, train):
            if fn() != 0:
                print("FAILED:", fn.__name__)
                return 1
        return 0
    if arg not in cmds:
        print("未知子命令:", arg)
        return 1
    return cmds[arg]()


if __name__ == "__main__":
    sys.exit(main())
