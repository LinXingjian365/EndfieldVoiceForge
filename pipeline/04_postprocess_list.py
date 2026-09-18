"""步骤 4：把 GPT-SoVITS ASR 工具输出的 .list 规范成训练用格式（speaker=typhoea, lang=zh），剔除空文本。

输入：datasets/typhoea_train_asr/typhoea_train.list（ASR 原始输出）
产物：datasets/typhoea_train_asr/typhoea.list
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

src = os.path.join(config.TRAIN_LIST_DIR, 'typhoea_train.list')
out = config.TRAIN_LIST

lines = []
empty = 0
with open(src, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parts = line.split('|')
        if len(parts) < 4:
            continue
        path = parts[0]
        text = '|'.join(parts[3:]).strip()
        if not text:
            empty += 1
            continue
        lines.append('%s|%s|zh|%s' % (path, config.SPEAKER, text))

with open(out, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')
print('valid:', len(lines), 'empty filtered:', empty)
print('out:', out)
