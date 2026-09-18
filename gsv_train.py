# -*- coding: utf-8 -*-
"""
提弗洛斯 GPT-SoVITS v2 训练脚本（6GB 显存适配 batch_size=1）
用法（用 index-tts 的 venv）：
  third_party/index-tts/.venv/Scripts/python.exe gsv_train.py preprocess   # 预处理（Hubert 特征 + 语义 token）
  third_party/index-tts/.venv/Scripts/python.exe gsv_train.py s1           # GPT 训练（文本->语义）
  third_party/index-tts/.venv/Scripts/python.exe gsv_train.py s2           # SoVITS 训练（语义->音频）
"""

import os, sys, json, subprocess, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

GSV = config.GSV_DIR
PY = config.PY_TTS

VERSION = 'v2'
EXP_NAME = config.SPEAKER
EXP_ROOT = os.path.join(GSV, 'logs')
OPT_DIR = os.path.join(EXP_ROOT, EXP_NAME)
INP_TEXT = config.TRAIN_LIST
INP_WAV = config.TRAIN_WAV_DIR

PM = os.path.join(GSV, 'GPT_SoVITS', 'pretrained_models')
CNHUBERT = os.path.join(PM, 'chinese-hubert-base')
BERT = os.path.join(PM, 'chinese-roberta-wwm-ext-large')
S2G = os.path.join(PM, 'gsv-v2final-pretrained', 's2G2333k.pth')
S2D = os.path.join(PM, 'gsv-v2final-pretrained', 's2D2333k.pth')
S1_CKPT = os.path.join(PM, 'gsv-v2final-pretrained', 's1bert25hz-5kh-longer-epoch=12-step=369668.ckpt')

BATCH = 1
EPOCHS = 20


def run(script, env_extra=None, args=None):
    env = os.environ.copy()
    env.update({
        'PYTHONPATH': os.pathsep.join([GSV, os.path.join(GSV, 'GPT_SoVITS')]),
        'inp_text': INP_TEXT,
        'inp_wav_dir': INP_WAV,
        'exp_name': EXP_NAME,
        'opt_dir': OPT_DIR,
        'cnhubert_base_dir': CNHUBERT,
        'bert_pretrained_dir': BERT,
        'version': VERSION,
        'hz': '25hz',
        'is_half': 'True',
        'i_part': '0',
        'all_parts': '1',
        'pretrained_s2G': S2G,
        's2config_path': os.path.join(GSV, 'GPT_SoVITS', 'configs', 's2.json'),
        '_CUDA_VISIBLE_DEVICES': '0',
    })
    if env_extra:
        env.update(env_extra)
    cmd = [PY, '-s', script] + (args or [])
    print('>>', ' '.join(cmd))
    return subprocess.run(cmd, cwd=GSV, env=env)


def preprocess():
    os.makedirs(OPT_DIR, exist_ok=True)

    # 1) 文本 -> 音素 + BERT 特征（v2 必需）
    r = run('GPT_SoVITS/prepare_datasets/1-get-text.py')
    if r.returncode != 0:
        raise SystemExit('1-get-text 失败')
    part_txt = os.path.join(OPT_DIR, '2-name2text-0.txt')
    if os.path.exists(part_txt):
        os.replace(part_txt, os.path.join(OPT_DIR, '2-name2text.txt'))

    # 2) Hubert 特征 + 32k wav
    r = run('GPT_SoVITS/prepare_datasets/2-get-hubert-wav32k.py')
    if r.returncode != 0:
        raise SystemExit('2-get-hubert-wav32k 失败')

    # 3) 语义 token（s2 编码器 latent）
    r = run('GPT_SoVITS/prepare_datasets/3-get-semantic.py')
    if r.returncode != 0:
        raise SystemExit('3-get-semantic 失败')
    part_sem = os.path.join(OPT_DIR, '6-name2semantic-0.tsv')
    if os.path.exists(part_sem):
        lines = open(part_sem, encoding='utf-8').read().strip('\n').split('\n')
        with open(os.path.join(OPT_DIR, '6-name2semantic.tsv'), 'w', encoding='utf-8') as f:
            f.write('item_name\tsemantic_audio\n')
            f.write('\n'.join(lines) + '\n')
        os.remove(part_sem)

    print('>> 预处理完成, opt_dir=', OPT_DIR)


def train_s1():
    with open(os.path.join(GSV, 'GPT_SoVITS', 'configs', 's1longer-v2.yaml'), encoding='utf-8') as f:
        import yaml
        data = yaml.safe_load(f)
    data['train']['batch_size'] = BATCH
    data['train']['epochs'] = EPOCHS
    data['train']['save_every_n_epoch'] = 1
    data['train']['if_save_every_weights'] = True
    data['train']['if_save_latest'] = True
    data['train']['if_dpo'] = False
    data['train']['half_weights_save_dir'] = 'GPT_weights_v2'
    data['train']['exp_name'] = EXP_NAME
    data['pretrained_s1'] = S1_CKPT
    data['train_semantic_path'] = os.path.join(OPT_DIR, '6-name2semantic.tsv')
    data['train_phoneme_path'] = os.path.join(OPT_DIR, '2-name2text.txt')
    data['output_dir'] = os.path.join(OPT_DIR, 'logs_s1_v2')
    os.makedirs(os.path.join(GSV, 'GPT_weights_v2'), exist_ok=True)
    # 清空旧 ckpt，避免残留 checkpoint 触发 weights_only 反序列化失败
    ckpt_dir = os.path.join(OPT_DIR, 'logs_s1_v2', 'ckpt')
    os.makedirs(ckpt_dir, exist_ok=True)
    for _f in os.listdir(ckpt_dir):
        os.remove(os.path.join(ckpt_dir, _f))
    tmp_cfg = os.path.join(GSV, 'TEMP', 'tmp_s1.yaml')
    os.makedirs(os.path.dirname(tmp_cfg), exist_ok=True)
    import yaml
    with open(tmp_cfg, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)
    run('GPT_SoVITS/s1_train.py', args=['--config_file', tmp_cfg])
    print('>> s1 训练完成')


def train_s2():
    with open(os.path.join(GSV, 'GPT_SoVITS', 'configs', 's2.json'), encoding='utf-8') as f:
        data = json.load(f)
    data['train']['batch_size'] = BATCH
    data['train']['epochs'] = EPOCHS
    data['train']['text_low_lr_rate'] = 0.4
    data['train']['pretrained_s2G'] = S2G
    data['train']['pretrained_s2D'] = S2D
    data['train']['if_save_latest'] = True
    data['train']['if_save_every_weights'] = True
    data['train']['save_every_epoch'] = 1
    data['train']['gpu_numbers'] = '0'
    data['train']['grad_ckpt'] = True
    data['train']['lora_rank'] = 0
    data['model']['version'] = VERSION
    data['data']['exp_dir'] = OPT_DIR
    data['s2_ckpt_dir'] = OPT_DIR
    data['save_weight_dir'] = 'SoVITS_weights_v2'
    data['name'] = EXP_NAME
    data['version'] = VERSION
    os.makedirs(os.path.join(GSV, 'SoVITS_weights_v2'), exist_ok=True)
    os.makedirs(os.path.join(OPT_DIR, 'logs_s2_v2'), exist_ok=True)
    tmp_cfg = os.path.join(GSV, 'TEMP', 'tmp_s2.json')
    os.makedirs(os.path.dirname(tmp_cfg), exist_ok=True)
    with open(tmp_cfg, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    run('GPT_SoVITS/s2_train.py', args=['--config', tmp_cfg])
    print('>> s2 训练完成')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('step', choices=['preprocess', 's1', 's2', 'all'])
    a = ap.parse_args()
    if a.step in ('preprocess', 'all'):
        preprocess()
    if a.step in ('s1', 'all'):
        train_s1()
    if a.step in ('s2', 'all'):
        train_s2()
