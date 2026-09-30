# D2: never-away kill test. Intra frame 0 coded (SA17 bench). For every away sample (legal output farther from source
# than the SAME leaves + plain clip), find its 'case' = the level-1 quad; try ONE re-choice (+-1 index) of each
# coarse coefficient covering it (HL1/LH1/HH1 at the quad, and HL2/LH2/HH2 at the level-2 quad, LL-side via H-bands
# not tried). A case is FIXABLE if some single re-choice leaves 0 away samples in a 16x16 window around it and does
# not raise the plane's away total. Prints the share of fixable cases per cell.
import numpy as np, sys, yuv, ent, seq, pyr, codec
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
C = {'cut24': (SA7 + 'cut24.yuv', 256, 64, 0, 1023), 'ext10': (SA7 + 'ext_10_422_l0.yuv', 512, 128, 0, 1023),
     'gfx': (yuv.ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256, 4, 1019), 'dng720': (yuv.CELLS['dng720'][0], 1280, 720, 4, 1019)}
tabs = ent.Tables('/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/tab_eb_r2.pkl')
cell = sys.argv[1]; bpp = float(sys.argv[2]); maxcases = int(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 9
path, W, H, lo, hi = C[cell]
g = seq.Seq(W, H, bpp, tabs, lo=lo, hi=hi, tilt=0.25, rho=0.35, S=4 if H <= 720 else 8)
x = yuv.read_frame(path, W, H, 0); o, b, info = g.encode(x)
def away_map(V, s):
    yl, _, _ = pyr.synthesis(V, lo, hi); yu, _, _ = pyr.synthesis(V, lo, hi, legal=False); yc = np.clip(yu, lo, hi)
    return (np.abs(yl - s) > np.abs(yc - s))
rng = np.random.default_rng(1)
tot_cases = 0; fixable = 0; per_opt = {}
for p in range(3):
    V0 = {k: v.copy() for k, v in info['V0'][p].items()}; s = x[p]
    A = away_map(V0, s); A0 = int(A.sum())
    # steps per band row
    plans = info['plans']; nS = len(plans)
    def step(bn, r):
        return 1 << g.c.E[plans[min(nS - 1, r * codec.ROWDIV[bn] // g.S)]][(p, bn)]
    ys, xs = np.nonzero(A)
    quads = sorted(set(zip(ys // 4, xs // 4)))          # level-2 quads (4x4 pixel blocks) containing away samples
    if len(quads) > maxcases: quads = [quads[i] for i in rng.choice(len(quads), maxcases, replace=False)]
    for (qy, qx) in quads:
        tot_cases += 1
        y0, y1, x0, x1 = max(0, 4 * qy - 6), 4 * qy + 10, max(0, 4 * qx - 6), 4 * qx + 10
        loc0 = int(A[y0:y1, x0:x1].sum()); ok = False
        opts = []
        for bn, (ry, rx) in [('HL1', (2 * qy, 2 * qx)), ('HL1', (2 * qy, 2 * qx + 1)), ('HL1', (2 * qy + 1, 2 * qx)), ('HL1', (2 * qy + 1, 2 * qx + 1)),
                             ('LH1', (2 * qy, 2 * qx)), ('LH1', (2 * qy + 1, 2 * qx)), ('HL2', (qy, qx)), ('LH2', (qy, qx)), ('HH2', (qy, qx))]:
            if ry >= V0[bn].shape[0] or rx >= V0[bn].shape[1]: continue
            for sg in (-1, 1):
                opts.append((bn, ry, rx, sg))
        for (bn, ry, rx, sg) in opts:
            V = dict(V0); V[bn] = V0[bn].copy(); V[bn][ry, rx] += sg * step(bn, ry)
            A2 = away_map(V, s)
            if A2[y0:y1, x0:x1].sum() == 0 and A2.sum() <= A0 - loc0:
                ok = True; per_opt[bn] = per_opt.get(bn, 0) + 1; break
        fixable += ok
    print(cell, bpp, 'plane', p, 'away samples', A0, 'cases so far', tot_cases, 'fixable', fixable, flush=True)
print('RESULT', cell, bpp, 'cases', tot_cases, 'fixable by one +-1 re-choice', fixable, '(%.1f%%)' % (100 * fixable / max(1, tot_cases)), per_opt)
