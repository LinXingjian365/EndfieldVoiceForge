"""IndexTTS-2.5 零样本克隆（无需训练，给一段参考音频直接合成）。

用 third_party/index-tts/.venv 运行：
  third_party/index-tts/.venv/Scripts/python.exe indextts_clone.py
实测 RTX 3060 6GB 上 RTF≈87（合成 3s 要 270s），仅用于快速试听，不适合批量。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

SCRIPT = config.INDEXTTS_DIR
sys.path.insert(0, SCRIPT)

# 辅助模型强制走 ModelScope（绕开 HF/SSL 限制），缓存放在 index-tts 目录内
os.environ["USE_MODELSCOPE"] = "true"
os.environ["USERPROFILE"] = SCRIPT
os.environ["HOME"] = SCRIPT
os.environ["MODELSCOPE_CACHE"] = os.path.join(SCRIPT, ".modelscope_cache")
os.environ["HF_HUB_CACHE"] = os.path.join(SCRIPT, "checkpoints", "hf_cache")

from indextts.infer_v2_5 import IndexTTS2

PROMPT = os.path.join(config.REF_EXPERIMENTS_DIR, "typhoea_speech_ref3.wav")
TEXT = "我是提弗洛斯，很高兴认识你。"
OUTPUT = os.path.join(config.OUTPUTS_DIR, "indextts_clone.wav")

CFG = os.path.join(SCRIPT, "checkpoints", "config.yaml")
MODEL_DIR = os.path.join(SCRIPT, "checkpoints")

tts = IndexTTS2(
    cfg_path=CFG,
    model_dir=MODEL_DIR,
    use_bf16=True,
    use_cuda_kernel=False,
    use_torch_compile=False,
    use_qwen_emo=False,  # 先不加载情绪模型，节省显存
)

print(">> 开始零样本克隆合成...")
tts.infer(
    spk_audio_prompt=PROMPT,
    text=TEXT,
    lang="ZH",
    output_path=OUTPUT,
    verbose=True,
    # 情绪向量：[高兴, 愤怒, 悲伤, 恐惧, 反感, 低落, 惊讶, 自然]
    # 温和档：大部分「自然」+ 少量「高兴/惊讶」，轻微抬升开头不改变性格
    emo_vector=[0.35, 0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.5],
    emo_alpha=1.0,
)
print(">> 完成:", OUTPUT, "存在:", os.path.exists(OUTPUT))
