"""（早期路线）在全量 wem 里用 Silero VAD + 时长匹配筛提弗洛斯人声。

已被 pipeline/01-03 的 externals 路线取代，保留用于对照。需要 torch/torchaudio。
产物：datasets/typhoea_ref_vad/<fid>_p<prob>.wav + manifest.json
"""
import os, struct, sys, glob, json, subprocess, tempfile, warnings, shutil
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

OUT = config.WEM_ALL_DIR
VGS = config.VGMSTREAM
JIT = os.path.join(os.path.expanduser("~"), ".cache", "torch", "hub", "snakers4_silero-vad_master",
                   "src", "silero_vad", "data", "silero_vad.jit")
AD = config.AUDIO_DIALOG_JSON
REF = config.VAD_REF_DIR
os.makedirs(REF, exist_ok=True)

import torch, torchaudio
warnings.filterwarnings("ignore")
model = torch.jit.load(JIT, map_location="cpu"); model.eval()

def r16(b,o): return struct.unpack_from("<H", b, o)[0]
def r32(b,o): return struct.unpack_from("<I", b, o)[0]

def wem_info(fp):
    with open(fp, "rb") as f:
        d = f.read(64)
    if d[:4] != b"RIFF": return None
    pos = 12
    while pos + 8 <= len(d):
        tag = d[pos:pos+4]; sz = r32(d, pos+4)
        if tag == b"fmt ":
            body = d[pos+8:pos+8+sz]
            return r16(body,0), r32(body,4), r32(body,0x18) if len(body)>=0x1c else None
        pos += 8 + sz + (sz & 1)
    return None

# build 48kHz index: total_samples -> [fid]
idx48 = defaultdict(list)
for fp in glob.glob(os.path.join(OUT, "*.wem")):
    info = wem_info(fp)
    if not info: continue
    afmt, sr, total = info
    if sr == 48000 and total is not None:
        idx48[total].append(int(os.path.splitext(os.path.basename(fp))[0]))

data = json.load(open(AD, encoding="utf-8"))
typhoea = [(v["wavDuration"], v.get("path","")) for v in data.values()
           if v.get("speakerChannel","") in ("typhoea","chr_0034_typhoea") and v["wavDuration"] > 0]

def speech_prob(wav):
    w, sr = torchaudio.load(wav)
    if w.ndim > 1: w = w.mean(dim=0, keepdim=True)
    w = w.squeeze(0)
    if sr != 16000: w = torchaudio.transforms.Resample(sr, 16000)(w)
    if w.numel() < 512: return None
    model.reset_states()
    ps = []
    with torch.no_grad():
        for i in range(0, len(w), 512):
            c = w[i:i+512]
            if len(c) < 512: c = torch.nn.functional.pad(c, (0,512-len(c)))
            ps.append(model(c,16000).item())
    return max(ps)

tmp = tempfile.mkdtemp()
results = []  # (dur, path, fid, prob)
seen_fids = set()

for dur, path in typhoea:
    exp = round(dur * 48000)
    cands = set()
    for delta in range(-5, 6):
        for fid in idx48.get(exp + delta, []):
            cands.add(fid)
    for fid in cands:
        if fid in seen_fids:
            continue
        seen_fids.add(fid)
        fp = os.path.join(OUT, f"{fid}.wem")
        wav = os.path.join(tmp, f"{fid}.wav")
        subprocess.run([VGS, "-o", wav, "-2", "1", fp], capture_output=True)
        if not (os.path.exists(wav) and os.path.getsize(wav) > 0):
            continue
        p = speech_prob(wav)
        if p is not None and p >= 0.5:
            dst = os.path.join(REF, f"{fid}_p{int(p*100)}.wav")
            shutil.copy(wav, dst)
            results.append((dur, path, fid, p))
        os.remove(wav)

results.sort(key=lambda x: -x[3])
print(f"typhoea lines: {len(typhoea)}, candidates checked: {len(seen_fids)}")
print(f"confirmed voice (>=0.5): {len(results)} -> {REF}\n")
for dur, path, fid, p in results:
    print(f"  fid={fid} prob={p:.3f} dur={dur:.3f}s path={os.path.basename(path)}")

# save manifest
with open(os.path.join(REF, "manifest.json"), "w", encoding="utf-8") as f:
    json.dump([{"fid": fid, "prob": round(p,3), "duration": dur, "path": path}
               for dur, path, fid, p in results], f, ensure_ascii=False, indent=2)
print(f"\nmanifest saved: {os.path.join(REF, 'manifest.json')}")
