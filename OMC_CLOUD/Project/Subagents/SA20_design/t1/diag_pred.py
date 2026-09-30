# diag_pred.py CLIP : mean |x1 - P| (luma) for P = zero motion, block MC (16x16, integer), and the per-sample bilinear
# field of t1_seq.py, using the SOURCE frame 0 as the reference (isolates the motion model from coding error)
import sys, os, numpy as np
os.environ.setdefault('CLIPS', ''); sys.argv = [sys.argv[0]] + sys.argv[1:]
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 't1_seq.py')).read().split('\nTR = ')[0]
exec(src)
from dp_screen_core import apply
c = sys.argv[1]; x0, x1 = read(c, 0), read(c, 1)
V = motion(x1[0].astype(np.int64), x0[0].astype(np.int64))
Pb = apply(x0[0].astype(np.int64), V, 16, 1); Pf, _ = predict(x1, x0)
print(c, 'zero %.2f block %.2f field %.2f | vectors nonzero %.0f%% max |v| %d' % (np.abs(x1[0] - x0[0]).mean(), np.abs(x1[0] - Pb).mean(),
      np.abs(x1[0] - Pf[0]).mean(), 100 * (np.abs(V).sum(-1) > 0).mean(), np.abs(V).max()))
