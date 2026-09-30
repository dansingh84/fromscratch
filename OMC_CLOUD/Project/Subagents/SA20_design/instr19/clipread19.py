# SA19 route "pure clip decoder + nearest-lattice reading" in the pair pyramid (sufficient-condition proxy):
# gen-1 unconstrained leaves V0 (on their lattices); decoder output = clip(synth(V0)) (never-away by construction).
# gen 2 re-reads leaves by analysis of the clipped picture; a coefficient is recoverable by nearest-lattice rounding iff
# |analysis(clip)[b] - V0[b]| < step/2. Count misses per band/plane.
import numpy as np, sys, yuv, ent, tpp, pyr, codec
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
C = {'cut24': (SA7 + 'cut24.yuv', 256, 64, 0, 1023), 'ext10': (SA7 + 'ext_10_422_l0.yuv', 512, 128, 0, 1023),
     'gfx': (yuv.ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256, 4, 1019), 'dng720': (yuv.CELLS['dng720'][0], 1280, 720, 4, 1019),
     'spot': (yuv.CELLS['spot'][0], 1920, 1080, 4, 1019)}
tabs = ent.Tables(sys.argv[1]); cell = sys.argv[2]; N = int(sys.argv[3])
path, W, H, lo, hi = C[cell]; nf = yuv.nframes(path, W, H)
for bpp in [float(r) for r in sys.argv[4].split(',')]:
    g = tpp.TPP(W, H, bpp, tabs, lo=lo, hi=hi, S=4 if H <= 720 else 8, tilt=0.25, rho=0.35, cheap=1)
    miss = 0; clipped = 0; ncoef = 0; mb = {}
    for f in range(N):
        x = yuv.read_frame(path, W, H, f % nf); o, b, i = g.encode(x)
        for p in range(3):
            V0 = i['V0'][p]; yu, _, _ = pyr.synthesis(V0, lo, hi, legal=False); yc = np.clip(yu, lo, hi)
            clipped += int((yu != yc).sum())
            Tc = pyr.analysis(yc)
            for bd in codec.BANDSP[p]:
                e_r = np.repeat(i['exps'][(p, bd)], g.S // codec.ROWDIV[(p, bd)])[:, None]
                st = (1 << e_r)
                m = np.abs(Tc[bd] - V0[bd]) * 2 >= st
                if bd == 'LL': m = Tc[bd] != V0[bd]          # LL is DPCM closed loop: must be exact
                miss += int(m.sum()); ncoef += m.size; mb[(p, bd)] = mb.get((p, bd), 0) + int(m.sum())
    worst = sorted(mb.items(), key=lambda kv: -kv[1])[:5]
    print('%s @%.2f frames %d: clipped samples %d | nearest-lattice read misses %d of %d coefficients | top bands %s' % (cell, bpp, N, clipped, miss, ncoef, worst), flush=True)
