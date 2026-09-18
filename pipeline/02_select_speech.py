"""步骤 2：对提弗洛斯每条台词（voType 0/4/5）按时长找最近邻 wem，解码后用 pyin 量 F0 / 有声比。

产物：datasets/typhoea_speech2/*.wav（候选池）、datasets/cache/select_speech2.txt（含 F0 统计）
"""
import os, struct, sys, json, subprocess
import numpy as np, librosa, soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
config.import_unpacker()
from extract_akpk import decrypt_vfs, decrypt_wem, read_u32

PCK = config.PCK_CHINESE_STREAM
AD = config.AUDIO_DIALOG_JSON
CACHE = os.path.join(config.CACHE_DIR, 'ext_durations.json')
VGS = config.VGMSTREAM
OUTDIR = config.SPEECH_POOL_DIR
OUT = os.path.join(config.CACHE_DIR, 'select_speech2.txt')
os.makedirs(OUTDIR, exist_ok=True)

data = bytearray(open(PCK, 'rb').read())
hs = read_u32(data, 4)
decrypt_vfs(data, 12, hs - 4, hs, 0)
data[0:4] = b'AKPK'
struct.pack_into('<I', data, 8, 1)

pos = 4
pos += 4; pos += 4
langs = read_u32(data, pos); pos += 4
banks = read_u32(data, pos); pos += 4
sounds = read_u32(data, pos); pos += 4
externals = read_u32(data, pos); pos += 4
pos += langs + banks + sounds
ext_start = pos
cnt = read_u32(data, ext_start)
entry_size = (externals - 4) // cnt

entries = {}
for i in range(cnt):
    e = ext_start + 4 + i * entry_size
    low = read_u32(data, e)
    blk = read_u32(data, e+8)
    sz = read_u32(data, e+12)
    off = read_u32(data, e+16)
    if blk != 0:
        off *= blk
    entries[i] = (low, off, sz)

durations = {int(k): v for k, v in json.load(open(CACHE)).items()}
ad = json.load(open(AD, encoding='utf-8'))
def u32(k):
    n = int(k); return n + 4294967296 if n < 0 else n

typhoea = [(k, v) for k, v in ad.items() if 'typhoea' in str(v.get('speakerChannel','')).lower()]

# 对每个 vt=0/4/5 目标找最近邻
targets = []
for k, v in typhoea:
    vt = v.get('voType')
    if vt not in (0, 4, 5):
        continue
    dur = v.get('wavDuration', 0.0)
    if dur <= 0:
        continue
    best_idx = min(durations, key=lambda i: abs(durations[i] - dur))
    delta = durations[best_idx] - dur
    targets.append((vt, dur, os.path.basename(v.get('path','')), best_idx, delta))

lines = []
lines.append('typhoea vt0/4/5 targets: %d' % len(targets))

# 提取 + 解码 + F0，对 delta < 0.01 的
rows = []
for vt, dur, path, idx, delta in targets:
    if abs(delta) > 0.01:
        continue
    low, off, sz = entries[idx]
    wem = bytearray(data[off:off+sz])
    if len(wem) < 4 or wem[:4] not in (b'RIFF', b'RIFX'):
        decrypt_wem(wem, low & 0xFFFFFFFF)
    wav = os.path.join(OUTDIR, '%d_%d.wav' % (idx, int(dur*1000)))
    with open(os.path.join(OUTDIR, 'tmp.wem'), 'wb') as f:
        f.write(bytes(wem))
    subprocess.run([VGS, '-o', wav, '-2', '1', os.path.join(OUTDIR, 'tmp.wem')], capture_output=True)
    if not os.path.exists(wav):
        continue
    try:
        y, sr = librosa.load(wav, sr=48000)
        y = librosa.effects.trim(y, top_db=40)[0]
        if len(y) < int(0.3 * sr):
            continue
        f0, voiced, _ = librosa.pyin(y, fmin=80, fmax=600, sr=sr, frame_length=2048)
        f0v = f0[voiced] if voiced is not None else np.array([])
        vr = float(np.mean(voiced)) if voiced is not None else 0.0
        med = float(np.median(f0v)) if len(f0v) > 0 else 0.0
        rows.append((idx, len(y)/sr, med, vr, path))
        lines.append('vt=%d idx=%d dur=%.2f delta=%+.3f F0=%.0f voiced=%.2f %s' % (vt, idx, len(y)/sr, delta, med, vr, path))
    except Exception as ex:
        lines.append('idx=%d ERROR %s' % (idx, ex))

# 女声说话筛选：F0 300~550, voiced>0.15
lines.append('')
lines.append('=== female speech (F0 300-550, voiced>0.15) ===')
sel = [r for r in rows if 300 < r[2] < 550 and r[3] > 0.15]
for idx, d, med, vr, path in sorted(sel, key=lambda x: -x[1]):
    lines.append('idx=%d dur=%.2f F0=%.0f voiced=%.2f %s' % (idx, d, med, vr, path))

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
sys.stderr.write('DONE rows=%d sel=%d\n' % (len(rows), len(sel)))
