# D6: split AVG's away moves by the SOURCE of the overshooting sample: at a rail exactly (plates / clipped highlights:
# removable by a rail-excluded structure) vs not at a rail ("case 3": needs another root). Intra frame 0.
import numpy as np, sys, yuv, ent, seq, pyr
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
C = {'cut24': (SA7 + 'cut24.yuv', 256, 64, 0, 1023), 'ext10': (SA7 + 'ext_10_422_l0.yuv', 512, 128, 0, 1023),
     'gfx': (yuv.ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256, 4, 1019), 'dng720': (yuv.CELLS['dng720'][0], 1280, 720, 4, 1019),
     'dng720fr': (yuv.CELLS['dng720'][0], 1280, 720, 0, 1023)}
tabs = ent.Tables('/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/tab_eb_r2.pkl')
for cell in sys.argv[1].split(','):
    path, W, H, lo, hi = C[cell]
    for bpp in (0.5, 1.0, 2.0):
        g = seq.Seq(W, H, bpp, tabs, lo=lo, hi=hi, tilt=0.25, rho=0.35, S=4 if H <= 720 else 8)
        x = yuv.read_frame(path, W, H, 0); o, b, info = g.encode(x)
        tot = dict(rail_src=0, away=0, away_railpair=0, away_case3=0, srcoob=0)
        for p in range(3):
            s = x[p]; tot['rail_src'] += int(((s <= lo) | (s >= hi)).sum()); tot['srcoob'] += int(((s < lo) | (s > hi)).sum())
            yu, _, _ = pyr.synthesis(info['V0'][p], lo, hi, legal=False); yc = np.clip(yu, lo, hi)
            away = np.abs(o[p] - s) > np.abs(yc - s)
            # the vertical pixel pair partner of each away sample: its overshooting partner is the other row of the pair
            part = np.zeros_like(s); part[0::2] = s[1::2]; part[1::2] = s[0::2]
            pu = np.zeros_like(yu); pu[0::2] = yu[1::2]; pu[1::2] = yu[0::2]
            over = (pu > hi) | (pu < lo)                      # the partner overshot (vertical pair)
            railsrc = (part <= lo) | (part >= hi)
            tot['away'] += int(away.sum()); tot['away_railpair'] += int((away & railsrc).sum()); tot['away_case3'] += int((away & ~railsrc).sum())
        print(cell, bpp, tot, flush=True)
