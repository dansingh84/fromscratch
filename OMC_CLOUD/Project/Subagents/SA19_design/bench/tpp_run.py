# SA19 driver for the TPP model.
#   train: tpp_run.py train CLIP BPP START_TABLES OUT_COUNTS key=val...   (8 frames of a disjoint training clip)
#   eval:  tpp_run.py eval  CELL BPP TABLES TAG key=val...                (12 frames vs today's real decode)
#   chain: tpp_run.py chain CELL BPP TABLES TAG key=val...                (gen 1 -> gen 2 -> gen 3 identity, N frames)
import numpy as np, sys, os, json, pickle, yuv, ent, tpp, metrics
mode, cell, bpp, tabp, outp = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4], sys.argv[5]
kw = dict(tilt=0.25, rho=0.35)
NF = None
for a in sys.argv[6:]:
    k, v = a.split('=')
    if k in ('fuse', 'wf', 'fine', 'S', 'bx', 'lam', 'ztol', 'fusec', 'cheap', 'ro'): kw[k] = int(v)
    elif k in ('still', 'v2mode'): kw[k] = v
    elif k == 'N': NF = int(v)
    elif k in ('split', 'wk', 'catchpad', 'ecsq'): kw[k] = float(v)
    else: kw[k] = float(v)
if mode == 'train':
    p, W, H = yuv.TRAIN[cell]; tabs = ent.Tables(tabp); new = ent.Tables()
    s = tpp.TPP(W, H, bpp, tabs, **kw); s.c.collect = True; tabs.add = new.add
    for f in range(NF or 8):
        o, b, i = s.encode(yuv.read_frame(p, W, H, f))
    print(cell, bpp, 'bits %.0f over %d' % (b.sum(), i['over']), flush=True)
    pickle.dump(new.cnt, open(outp, 'wb')); sys.exit(0)
FROZEN = cell.endswith('fr'); cell0 = cell[:-2] if FROZEN else cell
p, W, H = yuv.CELLS[cell0]; N = min(NF or 12, yuv.nframes(p, W, H)); tabs = ent.Tables(tabp)
if cell0 == 'dng720': kw.setdefault('S', 4)
if mode == 'chain':
    g = [tpp.TPP(W, H, bpp, tabs, **kw) for _ in range(3)]
    for f in range(N):
        x = yuv.read_frame(p, W, H, f); o1, b1, i1 = g[0].encode(x); o2, b2, i2 = g[1].encode(o1, read=True); o3, b3, i3 = g[2].encode(o2, read=True)
        d12 = sum(int((a != b).sum()) for a, b in zip(o1, o2)); d23 = sum(int((a != b).sum()) for a, b in zip(o2, o3))
        print('f%d g2 diff %d bits %s | g3 diff %d bits %s | over %d' % (f, d12, np.allclose(b1, b2), d23, np.allclose(b2, b3), i1['over']), flush=True)
    sys.exit(0)
s = tpp.TPP(W, H, bpp, tabs, **kw)
src = []; dec = []; allbits = []; over = 0; sl = []; pads = []; catches = []
for f in range(N):
    x = yuv.read_frame(p, W, H, 0 if FROZEN else f); o, b, info = s.encode(x)
    src.append(x); dec.append(o); allbits.append(float(b.sum())); over += info['over']; sl.append([np.asarray(b).tolist(), np.asarray(info['plans']).tolist()]); pads.append(info.get('pad', 0)); catches.append(bool(info.get('catchframe', False)))
os.makedirs('../out/dec', exist_ok=True)
yuv.write_frames('../out/dec/%s_%s_b%s.d.yuv' % (outp, cell, sys.argv[3]), dec)
chg = [[float((dec[f][i] != dec[f - 1][i]).mean()) for i in range(3)] for f in range(1, N)]
r = metrics.summary(src, dec, W, H)
res = dict(cell=cell, bpp=bpp, tag=outp, neg=r['neg'], negmin=r['negmin'], psnr=r['psnr'], negf=r['negf'].tolist(), bits=allbits,
           target=bpp * W * H, over=over, slices=sl, pads=pads, chg=chg, catches=catches, oob=int(sum(((d[i] < 4) | (d[i] > 1019)).sum() for d in dec for i in range(3))))
td = None if FROZEN else yuv.TODAY.get(cell)
if td and os.path.exists(td % sys.argv[3]):
    tdec = [yuv.read_frame(td % sys.argv[3], W, H, f) for f in range(N)]
    rt = metrics.summary(src, tdec, W, H); res.update(today_neg=rt['neg'], today_negmin=rt['negmin'], today_psnr=rt['psnr'])
print('%s %s @%.1f  NEG %.2f (worst %.2f)  PSNR %.2f/%.2f/%.2f  | today NEG %.2f (worst %.2f) PSNR %.2f/%.2f/%.2f | max bits/target %.4f over %d oob %d' % (
    outp, cell, bpp, res['neg'], res['negmin'], *res['psnr'], res.get('today_neg', 0), res.get('today_negmin', 0),
    *res.get('today_psnr', [0, 0, 0]), max(allbits) / res['target'], over, res['oob']), flush=True)
os.makedirs('../out/eval', exist_ok=True); json.dump(res, open('../out/eval/%s_%s_b%s.json' % (outp, cell, sys.argv[3]), 'w'))
