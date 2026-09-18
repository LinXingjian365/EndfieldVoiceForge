"""步骤 3：从候选池里按 F0 180-350Hz、有声比 >=0.30、时长 0.5-40s 筛出训练集并解码为 wav。

产物：datasets/typhoea_train/typhoea_<idx>.wav + manifest.json
"""
import os, struct, sys, json, subprocess, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
config.import_unpacker()
from extract_akpk import decrypt_vfs, decrypt_wem, read_u32

PCK = config.PCK_CHINESE_STREAM
VGS = config.VGMSTREAM
SEL = os.path.join(config.CACHE_DIR, 'select_speech2.txt')
OUTDIR = config.TRAIN_WAV_DIR
os.makedirs(OUTDIR, exist_ok=True)

print('>> reading PCK...')
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
print('>> externals count=%d entry_size=%d' % (cnt, entry_size))

entries = {}
for i in range(cnt):
    e = ext_start + 4 + i * entry_size
    low = read_u32(data, e)
    blk = read_u32(data, e + 8)
    sz = read_u32(data, e + 12)
    off = read_u32(data, e + 16)
    if blk != 0:
        off *= blk
    entries[i] = (low, off, sz)

pat = re.compile(r'^vt=(\d+) idx=(\d+) dur=([\d.]+) delta=[-+][\d.]+ F0=([\d.]+) voiced=([\d.]+) (\S+)$')
rows = []
with open(SEL, encoding='utf-8') as f:
    for line in f:
        m = pat.match(line.strip())
        if not m:
            continue
        vt, idx, dur, f0, voiced, path = int(m.group(1)), int(m.group(2)), float(m.group(3)), float(m.group(4)), float(m.group(5)), m.group(6)
        if vt in (0, 4):
            rows.append((idx, dur, f0, voiced, path, vt))

sel = []
for idx, dur, f0, voiced, path, vt in rows:
    if voiced < 0.30:
        continue
    if not (180 <= f0 <= 350):
        continue
    if not (0.5 <= dur <= 40):
        continue
    sel.append((idx, dur, f0, voiced, path, vt))

seen, uniq = set(), []
for r in sel:
    if r[0] not in seen:
        seen.add(r[0])
        uniq.append(r)

print('>> rows=%d selected=%d unique=%d' % (len(rows), len(sel), len(uniq)))

manifest = []
for idx, dur, f0, voiced, path, vt in uniq:
    low, off, sz = entries[idx]
    wem = bytearray(data[off:off + sz])
    if len(wem) < 4 or wem[:4] not in (b'RIFF', b'RIFX'):
        decrypt_wem(wem, low & 0xFFFFFFFF)
    tmp = os.path.join(OUTDIR, '_tmp.wem')
    out_wav = os.path.join(OUTDIR, 'typhoea_%d.wav' % idx)
    open(tmp, 'wb').write(bytes(wem))
    subprocess.run([VGS, '-o', out_wav, '-2', '1', tmp], capture_output=True)
    if os.path.exists(out_wav):
        manifest.append({'idx': idx, 'wav': 'typhoea_%d.wav' % idx, 'dur': dur, 'f0': f0, 'voiced': voiced, 'path': path, 'vt': vt})
    else:
        print('FAIL decode idx=%d' % idx)

with open(os.path.join(OUTDIR, 'manifest.json'), 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print('>> decoded=%d -> %s' % (len(manifest), OUTDIR))
