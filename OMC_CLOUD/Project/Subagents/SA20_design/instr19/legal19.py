# SA19 never-away discriminator. Per cell/rate, frames 0..N-1, per plane:
#  OFF = TPP decoder clamp only; FIX = + encoder-side in-range index choice (decoder unchanged).
#  Reference per frame = clip of the legality-off synthesis of the UNCONSTRAINED indices (V0 of the arm; frame 0 shared).
#  away = |out - src| > |clip(yu) - src|; toward = <. Also PSNR of out and of the clip reference, clamp stats.
import numpy as np, sys, yuv, ent, tpp, pyr
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
C = {'cut24': (SA7 + 'cut24.yuv', 256, 64, 0, 1023), 'ext10': (SA7 + 'ext_10_422_l0.yuv', 512, 128, 0, 1023),
     'gfx': (yuv.ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256, 4, 1019), 'dng720': (yuv.CELLS['dng720'][0], 1280, 720, 4, 1019)}
tabs = ent.Tables(sys.argv[1]); cell = sys.argv[2]; N = int(sys.argv[3]); rates = [float(r) for r in sys.argv[4].split(',')]
path, W, H, lo, hi = C[cell]; nf = yuv.nframes(path, W, H)
for bpp in rates:
    for arm in ('OFF', 'FIX'):
        g = tpp.TPP(W, H, bpp, tabs, lo=lo, hi=hi, S=4 if H <= 720 else 8, tilt=0.25, rho=0.35, cheap=1)
        g.c.enc_fix = (arm == 'FIX'); pyr.FIXSTAT.clear()
        st = [dict(n=0, away=0, tow=0, mx=0, se=0.0, sec=0.0) for _ in range(3)]; over = 0; oob = 0
        for f in range(N):
            x = yuv.read_frame(path, W, H, f % nf); o, b, i = g.encode(x); over += i['over']
            for p in range(3):
                yu, _, _ = pyr.synthesis(i['V0'][p], lo, hi, legal=False); yc = np.clip(yu, lo, hi)
                s = x[p]; eo = np.abs(o[p] - s); ec = np.abs(yc - s); d = st[p]
                aw = eo > ec; d['n'] += s.size; d['away'] += int(aw.sum()); d['tow'] += int((eo < ec).sum())
                d['mx'] = max(d['mx'], int((eo - ec)[aw].max()) if aw.any() else 0)
                d['se'] += float((eo.astype(float) ** 2).sum()); d['sec'] += float((ec.astype(float) ** 2).sum())
                oob += int(((o[p] < lo) | (o[p] > hi)).sum())
        fs = {k: v.tolist() for k, v in pyr.FIXSTAT.items()}
        tot = sum(v[0] for v in fs.values()); fixed = sum(v[1] for v in fs.values())
        print('%s @%.2f %s: oob %d overs %d | clamp-site leaves %d, in-range lattice index found %d (%.1f %%)' % (cell, bpp, arm, oob, over, tot, fixed, 100.0 * fixed / max(tot, 1)), flush=True)
        for p, d in enumerate(st):
            ps = lambda se: 10 * np.log10(((1 << 10) - 1) ** 2 / max(se / d['n'], 1e-9))
            print('   plane %d: away vs clip-arm %d (%.4f %%), toward %d, max excess %d | PSNR out %.3f  clip-arm %.3f' % (p, d['away'], 100 * d['away'] / d['n'], d['tow'], d['mx'], ps(d['se']), ps(d['sec'])), flush=True)
