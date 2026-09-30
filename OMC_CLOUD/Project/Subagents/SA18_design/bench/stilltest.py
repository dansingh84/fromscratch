# still areas: (a) frozen input (one frame repeated), (b) mixed clip (still dng1080 background + moving PiP).
# counts samples of the STILL region that change from one decoded frame to the next (frames 2..N-1), per plane,
# and whether each change moves toward or away from the source.
import numpy as np, sys, yuv, ent, seq
tabp = sys.argv[1]; kind = sys.argv[2]; bpp = float(sys.argv[3]); N = int(sys.argv[4]) if len(sys.argv) > 4 else 12
kw = {}; skw = {}; EV = (); EA = (); CC = 0; ECP = 0; NK = 0.0; HA = 0.0
for a in sys.argv[5:]:
    k, v = a.split('=')
    if k == 'events': EV = tuple(int(z) for z in v.split(':')); continue
    if k == 'eages': EA = tuple(int(z) for z in v.split(':')); continue
    if k == 'ccv': CC = int(v); continue
    if k == 'evcap': ECP = int(v); continue
    if k == 'noisek': NK = float(v); continue
    if k == 'habs': HA = float(v); continue
    if k in ('bx', 'lam', 'S', 'refresh', 'cycle', 'still_hold'): skw[k] = int(v)
    elif k == 'rho_still': skw[k] = float(v)
    else: kw[k] = float(v)
W, H = 1920, 1080
import os; MY = int(os.environ.get("MY", 24)); MX = int(os.environ.get("MX", 64))
bg = yuv.read_frame(yuv.CELLS['dng1080'][0], W, H, 0)
def frame(t):
    if kind == 'frozen': return [p.copy() for p in bg]
    m = yuv.read_frame(yuv.CELLS['floor'][0], W, H, t % 24); fr = []
    for i, (b, x) in enumerate(zip(bg, m)):
        c = b.copy(); sx = 2 if i else 1
        c[272:808, 480 // sx:1440 // sx] = x[272:808, 480 // sx:1440 // sx]; fr.append(c)
    return fr
still = [np.ones((H, W), bool), np.ones((H, W // 2), bool), np.ones((H, W // 2), bool)]
if kind != 'frozen':
    for i in range(3):
        sx = 2 if i else 1; m = still[i]; m[272 - MY:808 + MY, max(0, (480 - MX) // sx):(1440 + MX) // sx] = False   # margin: motion/transform reach
cnt = [np.zeros(p.shape, np.int64) for p in still]
s = seq.Seq(W, H, bpp, ent.Tables(tabp), **skw, **kw); s.events = EV; s.event_ages = EA; s.ccv = CC; s.ev_cap = bool(ECP); s.noise_k = NK; s.hold_abs = HA; prev = None
for t in range(N):
    x = frame(t); o, b, info = s.encode(x)
    if prev is not None and t >= 2:
        out = []
        for i in range(3):
            ch = (o[i] != prev[i]) & still[i]; cnt[i] += ch
            tow = ch & (np.abs(o[i] - x[i]) < np.abs(prev[i] - x[i])); away = ch & (np.abs(o[i] - x[i]) > np.abs(prev[i] - x[i]))
            out.append('%.3f%% (toward %d away %d, mean|chg| %.2f)' % (100 * ch.sum() / still[i].sum(), tow.sum(), away.sum(), float(np.abs(o[i] - prev[i])[ch].mean()) if ch.any() else 0.0))
        print('%s @%.1f frame %2d still-region samples changed  Y %s | Cb %s | Cr %s | bits %.0f' % (kind, bpp, t, *out, b.sum()), flush=True)
    prev = o

hs = []
for i in range(3):
    h = np.bincount(cnt[i][still[i]].ravel(), minlength=6)[:6]
    hs.append(' '.join('%d:%.2f%%' % (k, 100 * h[k] / still[i].sum()) for k in range(6)))
print('changes per still sample over frames 2..N-1 (count:share)  Y %s | Cb %s | Cr %s' % tuple(hs), flush=True)
