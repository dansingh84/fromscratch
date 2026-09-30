# E1f: cost of slice-closed vertical 5/3 (today's structure) vs continuous transforms. proxy entropy, gain-normalised.
import numpy as np, sys, xf, yuv
from exp1 import ent_bits, rowret
from bdrate import bd
cell = sys.argv[1]; S = int(sys.argv[2]); frames = [0, 6]
path, W, H = yuv.CELLS[cell]
def closed(x, D0, vf, hf):
    # transform each S-row slice separately (vertical closure), same horizontal; gains from a slice-sized plane
    G = xf.gains((S, x.shape[1]), 2, 5, vf, hf); bits = 0; out = np.zeros_like(x)
    for r in range(0, x.shape[0], S):
        T = xf.analysis(x[r:r + S] - 512, 2, 5, vf, hf); R = {}
        for b, c in T.items():
            D = max(1.0, D0 / np.sqrt(G[b])); q = np.sign(c) * np.floor(np.abs(c) / D + 0.4)
            bits += ent_bits(q.astype(np.int64)); R[b] = np.round(q * D).astype(np.int64)
        out[r:r + S] = xf.synthesis(R, 2, 5, vf, hf) + 512
    return out, bits
from exp1 import code_plane
res = {}
for name, fn in (('cont53', lambda x, D0: code_plane(x, D0, '53', '53', 0.4)),
                 ('cont26', lambda x, D0: code_plane(x, D0, '26', '53', 0.4)),
                 ('cont2626', lambda x, D0: code_plane(x, D0, '26', '26', 0.4)),
                 ('closed53_97', lambda x, D0: closed(x, D0, '53', '97m2')),
                 ('closed53', lambda x, D0: closed(x, D0, '53', '53'))):
    pts = []
    for D0 in (24, 36, 54, 80, 120):
        tot = 0; se = np.zeros(3); sp = np.zeros(3)
        for f in frames:
            for i, x in enumerate(yuv.read_frame(path, W, H, f)):
                y, b = fn(x, D0); y = np.clip(y, 0, 1023); tot += b; se[i] += np.mean((x - y.astype(float)) ** 2)
                sp[i] += rowret(x, y, S)[0]
        ps = 10 * np.log10(1023 ** 2 / (se / len(frames))); pts.append((tot / (W * H * len(frames)), *ps, *(sp / 2)))
    res[name] = np.array(pts)
    print(name, 'rowspread(S=%d) at D0=54: %.1f/%.1f/%.1f' % (S, *res[name][2, 4:7]), flush=True)
for k in res:
    if k != 'cont53': print('BD-rate %s vs cont53 on %s: %+.2f %%' % (k, cell, bd(res['cont53'], res[k])))
