# SA19: never-away measurement for TPP. For every inter/intra frame, per plane: compare the legal output o with the
# PRE-LEGAL synthesis yu (same leaves, no clamps) and with clip(yu). "away" = |o - s| > |yu - s| (legality moved the
# sample farther from its source). Reports count, max excess, and the share of the plane's squared error they carry.
import numpy as np, sys, yuv, ent, tpp, pyr
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
C = {'cut24': (SA7 + 'cut24.yuv', 256, 64, 0, 1023), 'ext10': (SA7 + 'ext_10_422_l0.yuv', 512, 128, 0, 1023),
     'gfx': (yuv.ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256, 4, 1019), 'dng720': (yuv.CELLS['dng720'][0], 1280, 720, 4, 1019)}
tabs = ent.Tables(sys.argv[1]); cell = sys.argv[2]; kw = dict(tilt=0.25, rho=0.35)
for a in sys.argv[4:]:
    k, v = a.split('='); kw[k] = int(v) if k in ('fuse', 'wf', 'S') else (v if k == 'still' else float(v))
path, W, H, lo, hi = C[cell]; N = int(sys.argv[3]); nf = yuv.nframes(path, W, H)
for bpp in (0.5, 1.0):
    g = tpp.TPP(W, H, bpp, tabs, lo=lo, hi=hi, S=4 if H <= 720 else 8, **kw)
    st = [dict(n=0, away=0, tow=0, mx=0, se_away=0.0, se=0.0, vsclip_away=0) for _ in range(3)]
    for f in range(N):
        x = yuv.read_frame(path, W, H, f % nf); o, b, i = g.encode(x)
        for p in range(3):
            yu, _, _ = pyr.synthesis(i['V0'][p], lo, hi, legal=False)
            s = x[p]; eo = np.abs(o[p] - s); eu = np.abs(yu - s); ec = np.abs(np.clip(yu, lo, hi) - s)
            aw = eo > eu; d = st[p]
            d['n'] += s.size; d['away'] += int(aw.sum()); d['tow'] += int((eo < eu).sum())
            d['mx'] = max(d['mx'], int((eo - eu)[aw].max()) if aw.any() else 0)
            d['se_away'] += float((eo[aw].astype(float) ** 2).sum()); d['se'] += float((eo.astype(float) ** 2).sum())
            d['vsclip_away'] += int((eo > ec).sum())
    for p, d in enumerate(st):
        print('%s @%.1f plane %d: moved away %d (%.4f %% of samples), toward %d, max excess %d codes, share of plane SE %.4f %% | farther than plain clip %d' % (
            cell, bpp, p, d['away'], 100 * d['away'] / d['n'], d['tow'], d['mx'], 100 * d['se_away'] / max(d['se'], 1), d['vsclip_away']), flush=True)
