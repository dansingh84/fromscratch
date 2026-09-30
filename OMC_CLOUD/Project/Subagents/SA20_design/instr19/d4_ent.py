# D4b: how far are the static tables' class bits from the frame's own empirical conditional entropy (same contexts)?
# Also: share of bits in class symbols vs raw mantissa+sign bits, per plane, inter frames 2..N-1.
import numpy as np, sys, yuv, ent, seq
cell, bpp = sys.argv[1], float(sys.argv[2]); N = int(sys.argv[3]) if len(sys.argv) > 3 else 6; HOLD = int(sys.argv[4]) if len(sys.argv) > 4 else 1
p, W, H = yuv.CELLS[cell] if cell in yuv.CELLS else yuv.TRAIN[cell]
tabs = ent.Tables(sys.argv[5] if len(sys.argv) > 5 else '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/tab_eb_r2.pkl')
s = seq.Seq(W, H, bpp, tabs, tilt=0.25, rho=0.35, bx=64, lam=4, refresh=False, still_hold=HOLD, S=4 if H == 720 else 8)
for f in range(N):
    x = yuv.read_frame(p, W, H, f)
    s.c.collect = f >= 2
    o, b, info = s.encode(x)
# the emission bits of the collected symbols: table cost vs empirical entropy per key+context
tot_t = 0; tot_e = 0; rows = []
for k, a in tabs.cnt.items():
    ln = tabs.len.get(k)
    if ln is None: continue
    tb = (a * ln).sum(); n = a.sum(1, keepdims=True); em = -(a * np.log2(np.where(a > 0, a / np.maximum(n, 1), 1))).sum()
    tot_t += tb; tot_e += em; rows.append((k, a.sum(), tb, em))
print(cell, bpp, 'hold', HOLD, 'class-symbol bits: table %.0f  empirical %.0f  ratio %.3f' % (tot_t, tot_e, tot_t / tot_e))
for k, n, tb, em in sorted(rows, key=lambda r: -r[2])[:12]:
    print('  key', k, 'n %d table %.0f emp %.0f ratio %.3f' % (n, tb, em, tb / max(em, 1)))
