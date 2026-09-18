"""步骤 1：解密中文语音流 PCK 的 externals 区，用 vgmstream 量出每条 wem 的时长并缓存。

同时按 AudioDialog.wavDuration 做一次时长匹配，输出唯一匹配报告。
产物：datasets/cache/ext_durations.json、ext_match_map.json、diag_extmatch.txt
"""
import os, struct, sys, json, re, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
config.import_unpacker()
from extract_akpk import decrypt_vfs, decrypt_wem, read_u32

PCK = config.PCK_CHINESE_STREAM
AD = config.AUDIO_DIALOG_JSON
VGS = config.VGMSTREAM
CACHE = os.path.join(config.CACHE_DIR, 'ext_durations.json')
OUT = os.path.join(config.CACHE_DIR, 'diag_extmatch.txt')
os.makedirs(config.CACHE_DIR, exist_ok=True)

data = bytearray(open(PCK, 'rb').read())
hs = read_u32(data, 4)
decrypt_vfs(data, 12, hs - 4, hs, 0)
data[0:4] = b'AKPK'
struct.pack_into('<I', data, 8, 1)

pos = 4
pos += 4  # header_size
pos += 4  # flag
langs = read_u32(data, pos); pos += 4
banks = read_u32(data, pos); pos += 4
sounds = read_u32(data, pos); pos += 4
externals = read_u32(data, pos); pos += 4
pos += langs + banks + sounds
ext_start = pos
cnt = read_u32(data, ext_start)
entry_size = (externals - 4) // cnt

# 收集 externals 条目 (idx, low, off, sz)
entries = []
for i in range(cnt):
    e = ext_start + 4 + i * entry_size
    low = read_u32(data, e)
    high = read_u32(data, e+4)
    blk = read_u32(data, e+8)
    sz = read_u32(data, e+12)
    off = read_u32(data, e+16)
    if blk != 0:
        off *= blk
    entries.append((i, low, off, sz))

sys.stderr.write('externals entries: %d\n' % len(entries))

# 缓存
durations = {}
if os.path.exists(CACHE):
    durations = {int(k): v for k, v in json.load(open(CACHE)).items()}
    sys.stderr.write('cache loaded: %d\n' % len(durations))

todo = [e for e in entries if e[0] not in durations]

tmpdir = tempfile.mkdtemp(prefix='wemtmp_')

def measure(entry):
    i, low, off, sz = entry
    wem = bytearray(data[off:off+sz])
    if len(wem) < 4 or wem[:4] not in (b'RIFF', b'RIFX'):
        decrypt_wem(wem, low & 0xFFFFFFFF)
    fp = os.path.join(tmpdir, '%d.wem' % i)
    with open(fp, 'wb') as f:
        f.write(bytes(wem))
    try:
        r = subprocess.run([VGS, '-m', fp], capture_output=True, text=True, timeout=20)
        out = r.stdout
        sr = None
        samples = None
        for line in out.splitlines():
            if 'sample rate:' in line:
                m = re.search(r'(\d+)', line)
                if m: sr = int(m.group(1))
            if 'stream total samples:' in line:
                m = re.search(r'stream total samples:\s*(\d+)', line)
                if m: samples = int(m.group(1))
        if sr and samples:
            return (i, samples / sr)
    except Exception:
        pass
    finally:
        try: os.remove(fp)
        except Exception: pass
    return (i, None)

sys.stderr.write('todo: %d\n' % len(todo))

done = 0
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = [ex.submit(measure, e) for e in todo]
    for fut in as_completed(futs):
        i, d = fut.result()
        if d is not None:
            durations[i] = d
        done += 1
        if done % 1000 == 0:
            sys.stderr.write('progress %d/%d\n' % (done, len(todo)))
            json.dump(durations, open(CACHE, 'w'))

json.dump(durations, open(CACHE, 'w'))
sys.stderr.write('durations total: %d\n' % len(durations))

# 匹配 typhoea
ad = json.load(open(AD, encoding='utf-8'))
def u32(k):
    n = int(k); return n + 4294967296 if n < 0 else n
typhoea = [(k, v) for k, v in ad.items() if 'typhoea' in str(v.get('speakerChannel','')).lower()]

lines = []
lines.append('externals with duration: %d' % len(durations))
lines.append('typhoea entries: %d' % len(typhoea))

# idx -> dur 查找：对每个 typhoea 目标，找最接近的 externals 时长
# 建 dur -> list of idx
from collections import defaultdict
dur2idx = defaultdict(list)
for i, d in durations.items():
    dur2idx[round(d, 6)].append(i)

targets = [(v.get('voType'), v.get('wavDuration', 0.0), v.get('path',''), u32(k)) for k, v in typhoea if v.get('voType') in (0,4,5)]

for tol in (0.0005, 0.001, 0.002, 0.005):
    uniq = amb = 0
    for vt, dur, path, key in targets:
        cands = [i for d, il in dur2idx.items() if abs(d - dur) <= tol for i in il]
        if len(cands) == 1: uniq += 1
        elif len(cands) > 1: amb += 1
    lines.append('tol=%.4f unique=%d ambiguous=%d none=%d' % (tol, uniq, amb, len(targets)-uniq-amb))

# 输出唯一匹配 (tol=0.001)，保存 idx + low + off + sz 便于后续提取
lines.append('')
lines.append('=== unique matches (tol=0.001) ===')
matches = []
for vt, dur, path, key in sorted(targets, key=lambda x: x[1], reverse=True):
    cands = [i for d, il in dur2idx.items() if abs(d - dur) <= 0.001 for i in il]
    if len(cands) == 1:
        idx = cands[0]
        matches.append((vt, dur, idx, path))
        lines.append('vt=%d idx=%d dur=%.4f %s' % (vt, idx, dur, os.path.basename(path)))

# 保存匹配结果 (idx -> path) 供提取用
match_map = {idx: path for vt, dur, idx, path in matches}
json.dump(match_map, open(os.path.join(config.CACHE_DIR, 'ext_match_map.json'), 'w'))

with open(OUT, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
sys.stderr.write('DONE unique=%d\n' % len(matches))
