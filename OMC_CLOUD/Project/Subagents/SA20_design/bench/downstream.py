#!/usr/bin/env python3
# downstream.py (SA20Q G71c): error of samples DOWNSTREAM of clipped samples vs elsewhere, per plane, rail clips.
# o = our decode (per-sample clip in the closed loop); u = the same picture decoded rail-free (legality-blind);
# downstream = not itself clipped but within 3 samples of a sample whose rail-free value left the range.
# Reports mean |o - src| downstream vs mean |clip(u) - src| on the same samples (excess = legality-caused error),
# plus mean |o - src| on non-downstream samples of the same near-rail blocks.
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); os.environ.setdefault('RHO', '0.42')
import n4_core
from n4_core import po
exec(open(os.path.join(os.path.dirname(__file__), 'rail_test.py')).read().split('res = []')[0].split('import n4_core')[1].replace('from n4_core import po', ''))
def dil(m, r=3):
    o = m.copy()
    for d in range(1, r + 1):
        o[d:, :] |= m[:-d, :]; o[:-d, :] |= m[d:, :]; o[:, d:] |= m[:, :-d]; o[:, :-d] |= m[:, d:]
    return o
for name, (fn, W, H, lo, hi, n) in CELLS.items():
    X = frames(fn, W, H, min(n, 6))
    for Q in (8.0, 32.0, 128.0):
        acc = [[0, 0.0, 0.0, 0, 0.0] for _ in range(3)]
        for x in X:
            o, _ = code(x, Q, lo, hi); u, _ = code(x, Q, -10 ** 9, 10 ** 9)
            for k in range(3):
                cl = (u[k] < lo) | (u[k] > hi); ds = dil(cl) & ~cl; near = dil(cl, 16) & ~ds & ~cl
                a = acc[k]; a[0] += int(ds.sum()); a[1] += np.abs(o[k] - x[k])[ds].sum(); a[2] += np.abs(np.clip(u[k], lo, hi) - x[k])[ds].sum()
                a[3] += int(near.sum()); a[4] += np.abs(o[k] - x[k])[near].sum()
        print('%s Q%.0f ' % (name, Q) + ' | '.join('%s downstream n %d: ours %.2f vs rail-free %.2f (excess %+.2f) ; nearby others ours %.2f' % (
            'YUV'[k], a[0], a[1] / max(a[0], 1), a[2] / max(a[0], 1), (a[1] - a[2]) / max(a[0], 1), a[4] / max(a[3], 1)) for k, a in enumerate(acc)), flush=True)
