# -*- coding: utf-8 -*-
"""
提弗洛斯 GPT-SoVITS v2 微调模型推理
用法（用 index-tts 的 venv）：
  third_party/index-tts/.venv/Scripts/python.exe gsv_infer.py
输出：
  outputs/gsv_typhoea_ft.wav / .mp3
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as paths

GSV = paths.GSV_DIR
os.chdir(GSV)
sys.path.append(GSV)
sys.path.append(os.path.join(GSV, 'GPT_SoVITS'))

import numpy as np
import soundfile as sf

from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config

# 微调后的权重
GPT_CKPT = os.path.join(GSV, 'GPT_weights_v2', 'typhoea-e20.ckpt')
SOVITS_PTH = os.path.join(GSV, 'SoVITS_weights_v2', 'typhoea_e20_s5000.pth')
CNHUBERT = os.path.join(GSV, 'GPT_SoVITS', 'pretrained_models', 'chinese-hubert-base')
BERT = os.path.join(GSV, 'GPT_SoVITS', 'pretrained_models', 'chinese-roberta-wwm-ext-large')

# 参考音频（提弗洛斯自然台词，3~10s，含“很高兴”的积极语气）
REF_AUDIO = os.path.join(paths.TRAIN_WAV_DIR, 'typhoea_18645.wav')
REF_TEXT = '好吧，很高兴你能把我当做合格的伙伴。'
TARGET_TEXT = '我是提弗洛斯，很高兴认识你。'


def main():
    config = TTS_Config({
        'custom': {
            'device': 'cuda:0',
            'is_half': True,
            'version': 'v2',
            't2s_weights_path': GPT_CKPT,
            'vits_weights_path': SOVITS_PTH,
            'bert_base_path': BERT,
            'cnhuhbert_base_path': CNHUBERT,
        }
    })
    print(config)
    tts = TTS(config)

    gen = tts.run({
        'text': TARGET_TEXT,
        'text_lang': 'zh',
        'ref_audio_path': REF_AUDIO,
        'prompt_text': REF_TEXT,
        'prompt_lang': 'zh',
        'top_k': 15,
        'top_p': 1.0,
        'temperature': 1.0,
        'text_split_method': 'cut5',
        'batch_size': 1,
        'seed': -1,
    })
    sr, audio = next(gen)

    audio = np.asarray(audio)
    if audio.dtype != np.int16:
        audio = np.clip(audio, -1.0, 1.0)
        audio = (audio * 32767).astype(np.int16)

    os.makedirs(paths.OUTPUTS_DIR, exist_ok=True)
    out_wav = os.path.join(paths.OUTPUTS_DIR, 'gsv_typhoea_ft.wav')
    sf.write(out_wav, audio, sr)
    print('已保存 WAV:', out_wav, '采样率', sr, '时长 %.2fs' % (len(audio) / sr))

    # 转 MP3 便于手机播放
    out_mp3 = os.path.join(paths.OUTPUTS_DIR, 'gsv_typhoea_ft.mp3')
    try:
        import subprocess
        subprocess.run(['ffmpeg', '-y', '-i', out_wav, '-codec:a', 'libmp3lame', '-b:a', '192k', out_mp3],
                       check=True, capture_output=True)
        print('已保存 MP3:', out_mp3)
    except Exception as e:
        print('MP3 转换失败(忽略):', e)


if __name__ == '__main__':
    main()
