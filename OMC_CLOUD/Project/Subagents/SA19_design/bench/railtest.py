# legality on rail extremes: out-of-range, gen-2 exactness, and toward/away vs the same indices + plain clip
import numpy as np, sys, yuv, ent, seq, pyr, codec
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
CELLS = {'cut24': (SA7 + 'cut24.yuv', 256, 64, 0, 1023), 'ext10': (SA7 + 'ext_10_422_l0.yuv', 512, 128, 0, 1023),
         'ext10l1': (SA7 + 'ext_10_422_l1.yuv', 512, 128, 4, 1019), 'gfx': (yuv.ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256, 4, 1019),
         'dng720': (yuv.CELLS['dng720'][0], 1280, 720, 4, 1019)}
tabs = ent.Tables(sys.argv[1])
for cell in sys.argv[2].split(','):
    path, W, H, lo, hi = CELLS[cell]; N = min(6, yuv.nframes(path, W, H))
    for bpp in (0.25, 0.5, 1.0, 2.0):
        g1 = seq.Seq(W, H, bpp, tabs, lo=lo, hi=hi, S=8 if H % 8 == 0 else 4); g2 = seq.Seq(W, H, bpp, tabs, lo=lo, hi=hi, S=g1.S)
        st = dict(oob=0, gen2=0, moved=0, toward=0, away=0, maxaway=0, excess=0, n=0, over=0)
        for f in range(N):
            x = yuv.read_frame(path, W, H, f); o1, b1, i1 = g1.encode(x); o2, b2, i2 = g2.encode(o1, read=True)
            st['over'] += i1['over']
            st['gen2'] += sum(int((a != b).sum()) for a, b in zip(o1, o2))
            for p in range(3):
                st['oob'] += int(((o1[p] < lo) | (o1[p] > hi)).sum()); st['n'] += o1[p].size
                # comparison arm: identical indices, synthesis WITHOUT clamps, then per-sample clip
                Q, plans = i1['Q'][p], i1['plans']; c = g1.c; nS = H // g1.S; V = {}
                base = i1['base'][p] if i1['base'] is not None else None
                im = i1['im'][p] if i1['im'] is not None else None
                F = pyr.analysis(o1[p]); V = {}
                for b in codec.BANDS:
                    e_s = np.array([c.E[plans[k]][(p, b)] for k in range(nS)])
                    stp = (1 << np.repeat(e_s, g1.S // codec.ROWDIV[b]))[:, None]
                    if b == 'LL': V[b] = F['LL']          # same LL as the legal decode (LL is a clamped leaf itself)
                    else: V[b] = Q[b] * stp + (base[b] if base is not None else 0)
                yu, _, _ = pyr.synthesis(V, lo, hi, legal=False); yc = np.clip(yu, lo, hi)
                s = x[p]; ea = np.abs(o1[p] - s); ec = np.abs(yc - s); eu = np.abs(yu - s)
                ch = o1[p] != yu
                st['moved'] += int(ch.sum()); st['toward'] += int((ch & (ea < eu)).sum()); st['away'] += int((ch & (ea > eu)).sum())
                st['excess'] += int((ea > ec).sum()); st['maxaway'] = max(st['maxaway'], int((ea - ec).max()))
        print('%s @%.2f: out-of-range %d / %d; gen-2 differing samples %d; samples changed by legality %d (toward %d, away %d); worse than clip %d (max excess %d codes); CBR overs %d' % (
            cell, bpp, st['oob'], st['n'], st['gen2'], st['moved'], st['toward'], st['away'], st['excess'], st['maxaway'], st['over']), flush=True)
