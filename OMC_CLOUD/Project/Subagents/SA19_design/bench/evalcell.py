# evaluate one cell: encode N frames with the sequence codec, compare with today's REAL decode (same frames)
# usage: evalcell.py CELL BPP BACKEND TABLES OUTTAG [key=val ...]
import numpy as np, sys, os, json, yuv, ent, seq, metrics
cell, bpp, backend, tabp, tag = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
kw = {}; skw = {}; MODES = None; ORACLE = 0; CCV = 0; EVENTS = (); EAGES = (); EVCAP = 0; NOISEK = 0.0; HABS = 0.0; RECOFF = 0
for a in sys.argv[6:]:
    k, v = a.split('=')
    if k == 'oracle': ORACLE = int(v); continue
    if k == 'ccv': CCV = int(v); continue
    if k == 'events': EVENTS = tuple(int(z) for z in v.split(':')); continue
    if k == 'eages': EAGES = tuple(int(z) for z in v.split(':')); continue
    if k == 'evcap': EVCAP = int(v); continue
    if k == 'noisek': NOISEK = float(v); continue
    if k == 'habs': HABS = float(v); continue
    if k == 'recoff': RECOFF = int(v); continue
    if k == 'modes': MODES = [float(z) for z in v.split(',')]; continue
    if k in ('refresh', 'clean', 'S', 'cycle', 'bx', 'lam', 'still_hold', 'ry', 'ztol'): skw[k] = int(v)
    elif k == 'l1k': skw[k] = float(v)
    elif k == 'rho_still': skw[k] = float(v)
    else: kw[k] = float(v)
p, W, H = (yuv.CELLS[cell] if cell in yuv.CELLS else yuv.TRAIN[cell]); N = min(12, yuv.nframes(p, W, H))
tabs = ent.Tables(tabp)
s = seq.Seq(W, H, bpp, tabs, backend=backend, **skw, **kw)
s.c.modes = MODES; s.oracle_src = bool(ORACLE); s.ccv = CCV; s.events = EVENTS; s.event_ages = EAGES; s.ev_cap = bool(EVCAP); s.noise_k = NOISEK; s.hold_abs = HABS; s.c.recoff = RECOFF
src = []; dec = []; allbits = []; over = 0; plans = []
for f in range(N):
    x = yuv.read_frame(p, W, H, f); o, b, info = s.encode(x)
    src.append(x); dec.append(o); allbits.append(float(b.sum())); over += info['over']; plans.append(np.bincount(info['plans'], minlength=1).argmax())
os.makedirs('../out/dec', exist_ok=True)
dpath = '../out/dec/%s_%s_b%s.d.yuv' % (tag, cell, sys.argv[2]); yuv.write_frames(dpath, dec)
r = metrics.summary(src, dec, W, H)
td = yuv.TODAY.get(cell)
res = dict(cell=cell, bpp=bpp, tag=tag, neg=r['neg'], negmin=r['negmin'], psnr=r['psnr'], negf=r['negf'].tolist(),
           bits=allbits, target=bpp * W * H, over=over, oob=int(sum(((d[i] < 4) | (d[i] > 1019)).sum() for d in dec for i in range(3))))
if td and os.path.exists(td % sys.argv[2]):
    tdec = [yuv.read_frame(td % sys.argv[2], W, H, f) for f in range(N)]
    rt = metrics.summary(src, tdec, W, H)
    res.update(today_neg=rt['neg'], today_negmin=rt['negmin'], today_psnr=rt['psnr'], today_negf=rt['negf'].tolist())
print('%s %s @%.1f  NEG %.2f (worst %.2f)  PSNR %.2f/%.2f/%.2f   | today NEG %.2f (worst %.2f) PSNR %.2f/%.2f/%.2f  | max frame bits/target %.4f over %d oob %d' % (
    tag, cell, bpp, res['neg'], res['negmin'], *res['psnr'], res.get('today_neg', 0), res.get('today_negmin', 0),
    *res.get('today_psnr', [0, 0, 0]), max(allbits) / res['target'], over, res['oob']), flush=True)
os.makedirs('../out/eval', exist_ok=True)
res['mode_hist'] = {'%d_%s' % k: v.tolist() for k, v in s.c.mode_hist.items()}
if MODES: print('modes', MODES, res['mode_hist'], flush=True)
json.dump(res, open('../out/eval/%s_%s_b%s.json' % (tag, cell, sys.argv[2]), 'w'))
