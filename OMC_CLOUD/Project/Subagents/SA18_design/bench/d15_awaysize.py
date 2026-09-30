# D15: size of the never-away failure (AVG leaf-interval legality) vs the SAME leaves + plain clip, intra frame 0 and
# the first inter frame, per cell/rate: samples changed by legality, away count, max excess |e_legal|-|e_clip|, share of
# the plane's squared error contributed by the away excess, and plane MSE legal vs clip.
import numpy as np, sys, yuv, ent, seq, pyr
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
C = {'cut24': (SA7 + 'cut24.yuv', 256, 64, 0, 1023), 'ext10': (SA7 + 'ext_10_422_l0.yuv', 512, 128, 0, 1023),
     'gfx': (yuv.ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256, 4, 1019), 'dng720': (yuv.CELLS['dng720'][0], 1280, 720, 4, 1019)}
tabs = ent.Tables(sys.argv[2] if len(sys.argv) > 2 else '../out/tab_h_r1.pkl')
for cell in sys.argv[1].split(','):
    path, W, H, lo, hi = C[cell]
    for bpp in (0.5, 1.0, 2.0):
        g = seq.Seq(W, H, bpp, tabs, lo=lo, hi=hi, tilt=0.25, rho=0.35, S=4 if H <= 720 else 8, still_hold=1, refresh=False, bx=64, lam=4)
        g.c.emit_reading = False
        agg = dict(n=0, ch=0, away=0, mx=0.0, ex=0.0, se_l=0.0, se_c=0.0)
        for f in range(2):
            x = yuv.read_frame(path, W, H, f); o, b, info = g.encode(x)
            for p in range(3):
                s = x[p].astype(float); yu, _, _ = pyr.synthesis(info['V0'][p], lo, hi, legal=False); yc = np.clip(yu, lo, hi)
                el = np.abs(o[p] - s); ec = np.abs(yc - s); aw = el > ec
                agg['n'] += s.size; agg['ch'] += int((o[p] != yc).sum()); agg['away'] += int(aw.sum())
                if aw.any(): agg['mx'] = max(agg['mx'], float((el - ec)[aw].max()))
                agg['ex'] += float((el[aw] ** 2 - ec[aw] ** 2).sum()); agg['se_l'] += float((el ** 2).sum()); agg['se_c'] += float((ec ** 2).sum())
        print('%-7s @%.1f samples %d | changed by legality %d | AWAY %d (%.4f %% of samples) max excess %.0f codes | away excess = %.3f %% of plane SE | SE legal/clip %.4f' % (
            cell, bpp, agg['n'], agg['ch'], agg['away'], 100 * agg['away'] / agg['n'], agg['mx'], 100 * agg['ex'] / max(agg['se_l'], 1), agg['se_l'] / max(agg['se_c'], 1)), flush=True)
