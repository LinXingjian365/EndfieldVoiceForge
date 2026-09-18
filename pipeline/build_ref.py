"""从 PCK externals 按 idx 抠出指定台词、去静音、拼成零样本克隆用的参考音频。

产物：outputs/ref_experiments/typhoea_speech_ref3.wav
"""
import os, struct, sys, subprocess
import numpy as np, librosa, soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
config.import_unpacker()
from extract_akpk import decrypt_vfs, decrypt_wem, read_u32

PCK = config.PCK_CHINESE_STREAM
VGS = config.VGMSTREAM
REF = os.path.join(config.REF_EXPERIMENTS_DIR, 'typhoea_speech_ref3.wav')
OUTDIR = config.SPEECH_POOL_DIR
os.makedirs(OUTDIR, exist_ok=True)
os.makedirs(config.REF_EXPERIMENTS_DIR, exist_ok=True)

# 单段：自我介绍（情绪最贴「我是提弗洛斯，很高兴认识你」的欢快上扬）
# idx=9123 introduce_01, F0=268Hz voiced=0.53, 8.59s
IDX = [(9123, 'introduce_01')]

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

segs = []
for idx, name in IDX:
    e = ext_start + 4 + idx * entry_size
    low = read_u32(data, e)
    blk = read_u32(data, e+8)
    sz = read_u32(data, e+12)
    off = read_u32(data, e+16)
    if blk != 0:
        off *= blk
    wem = bytearray(data[off:off+sz])
    if len(wem) < 4 or wem[:4] not in (b'RIFF', b'RIFX'):
        decrypt_wem(wem, low & 0xFFFFFFFF)
    tmp = os.path.join(OUTDIR, '_tmp.wem')
    wav = os.path.join(OUTDIR, 'ref3_%d.wav' % idx)
    open(tmp, 'wb').write(bytes(wem))
    subprocess.run([VGS, '-o', wav, '-2', '1', tmp], capture_output=True)
    if os.path.exists(wav):
        y, sr = librosa.load(wav, sr=48000)
        y = librosa.effects.trim(y, top_db=40)[0]
        if len(y) > int(0.4 * sr):
            segs.append(y)
            print('idx=%d %s dur=%.2fs' % (idx, name, len(y)/sr))

if segs:
    merged = np.concatenate(segs)
    sf.write(REF, merged, 48000)
    f0, voiced, _ = librosa.pyin(merged, fmin=80, fmax=600, sr=48000)
    f0v = f0[voiced] if voiced is not None else np.array([])
    med = np.median(f0v) if len(f0v) > 0 else 0
    print('MERGED dur=%.1fs F0=%.0fHz n_segs=%d' % (len(merged)/48000, med, len(segs)))
    print('REF=%s' % REF)
else:
    print('NO SEGS')
