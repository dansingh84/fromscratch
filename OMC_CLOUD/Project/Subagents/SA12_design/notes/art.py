#!/usr/bin/env python3
"""Artifact battery next to efficiency (owner rule): one frame, intra only (this is a STRUCTURE test, not a codec:
no temporal prediction, rate = zeroth-order entropy estimate).  Today's structure = SA11 struct_s TODAY model
(5/3 + 9/7-like, 2V x 5H, mirrored 16-row slices); HF-B5 = SA12 legal pyramid.  Matched rate by quarter-step Qf
search.  Per cell/rate/codec: VMAF-NEG (negscore.sh), PSNR Y/Cb/Cr, smudgegroups (owner method), flatplane,
texstat, grid statistic, slice-edge rows; colour render + |diff| map (unmarked + _grid).
usage: art.py tag path W H frame target_bpp outdir"""
import sys, os, math, json, subprocess, re, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grid, hf
from PIL import Image
T = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools'
SCR = os.environ.get('SCR', '/tmp')
tag, path, W, H, fr, tgt, outd = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), float(sys.argv[6]), sys.argv[7]
os.makedirs(outd, exist_ok=True)
src = hf.load(path, W, H, fr, '422')
def match(fn, planes):
    lo, hi = 1.0, 12.0; best = None
    for _ in range(7):                      # bisection on Qf (quarter steps)
        q = round((lo + hi) / 2 * 4) / 4; r, b = fn(planes, 16, q)
        if best is None or abs(math.log2(b / tgt)) < abs(math.log2(best[2] / tgt)): best = (q, r, b)
        if b > tgt: lo = q
        else: hi = q
    return best
def wr(planes, p):
    np.concatenate([np.clip(np.rint(x), 0, 1023).astype('<u2').ravel() for x in planes]).tofile(p)
def rgb(y, cb, cr):
    cb = np.repeat(cb, 2, axis=1)[:, :W]; cr = np.repeat(cr, 2, axis=1)[:, :W]
    yy = (y / 1023 * 255 - 16 * 255 / 256) * (255 / 219); c1 = (cb / 1023 - .5) * 255 * (255 / 224); c2 = (cr / 1023 - .5) * 255 * (255 / 224)
    return np.clip(np.stack([yy + 1.5748 * c2, yy - .1873 * c1 - .4681 * c2, yy + 1.8556 * c1], -1), 0, 255).astype(np.uint8)
def grid_png(a, p, bw=32, bh=16):
    Image.fromarray(a).save(p); g = a.copy()
    if g.ndim == 2: g = np.stack([g] * 3, -1)
    g[:, ::bw] = (255, 0, 0); g[::bh, :] = (255, 0, 0); Image.fromarray(g).save(p.replace('.png', '_grid.png'))
sp = os.path.join(SCR, '%s_src.yuv' % tag); wr(src, sp)
res = {}
for name, fn in (('today', grid.base_decode), ('hfB5', grid.hf_decode)):
    Qf, recs, b = match(fn, [p.astype(np.int64) if name == 'hfB5' else p.astype(float) for p in src])
    dp = os.path.join(SCR, '%s_%s.yuv' % (tag, name)); wr(recs, dp)
    r = dict(bpp_est=b, Qf=Qf)
    out = subprocess.run(['bash', T + '/negscore.sh', sp, dp, str(W), str(H), '422', '10', '1'], capture_output=True, text=True)
    m = re.findall(r'[-+]?\d+\.\d+', out.stdout.strip().splitlines()[-1] if out.stdout.strip() else '')
    r['neg'] = float(m[-1]) if m else None; r['neg_raw'] = out.stdout.strip().splitlines()[-1:] if out.stdout else out.stderr[-200:]
    r['psnr'] = [10 * math.log10(1023 ** 2 / float(((np.clip(np.rint(a), 0, 1023) - s) ** 2).mean())) for a, s in zip(recs, src)]
    pref = os.path.join(outd, '%s_%s' % (tag, name))
    sg = subprocess.run(['python3', T + '/smudgegroups.py', sp, dp, str(W), str(H), '0', pref + '_smudge', '--sh', '16', '--fmt', '422'], capture_output=True, text=True, cwd=T)
    r['smudge'] = [l for l in sg.stdout.splitlines() if 'groups' in l]
    fp = subprocess.run(['python3', T + '/flatplane.py', sp, dp, str(W), str(H), '0', '--fmt', '422'], capture_output=True, text=True, cwd=T)
    r['flatplane'] = fp.stdout.strip().splitlines()[-1:]
    ts = subprocess.run(['python3', T + '/texstat.py', sp, dp, str(W), str(H), '0', '--fmt', '422'], capture_output=True, text=True, cwd=T)
    r['texstat'] = [l for l in ts.stdout.splitlines() if 'TEXSTAT' in l]
    gs = []
    for pi, (a, s) in enumerate(zip(recs, src)):
        e = np.clip(np.rint(a), 0, 1023) - s; st = grid.stats(e); ph = [float(np.abs(e[j::16]).mean()) for j in range(16)]
        gs.append(dict(v16=st['v16'], h32=st['h32'], h16=st['h16'], first=ph[0] / np.mean(ph), last=ph[-1] / np.mean(ph)))
    r['grid'] = gs
    grid_png(rgb(*[np.clip(np.rint(x), 0, 1023) for x in recs]), pref + '_decode.png')
    grid_png(np.clip(np.abs(np.clip(np.rint(recs[0]), 0, 1023) - src[0]) * 16, 0, 255).astype(np.uint8), pref + '_absdiffY.png')
    grid_png(np.clip(np.abs(np.clip(np.rint(recs[2]), 0, 1023) - src[2]) * 16, 0, 255).astype(np.uint8), pref + '_absdiffCr.png', 16, 16)
    os.remove(dp); res[name] = r
    print(tag, tgt, name, json.dumps(r), flush=True)
grid_png(rgb(*[s.astype(float) for s in src]), os.path.join(outd, '%s_source.png' % tag))
os.remove(sp)
json.dump(res, open(os.path.join(outd, '%s_%g.json' % (tag, tgt)), 'w'), indent=1)
