# diag_inter.py CLIP S : code frame 1 against P (source frame 0 warped) at step S; share of nonzero leaves and bits per plane
import sys, os, numpy as np
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 't1_seq.py')).read().split('\nfor c in os.environ')[0]
c, s = sys.argv[1], float(sys.argv[2]); os.environ['CLIPS'] = ''
exec(src)
x0, x1 = read(c, 0), read(c, 1); Ps, nn = predict(x1, x0)
for k in range(3):
    y, q, cl = code(x1[k], s, Ps[k]); e = np.abs(x1[k] - Ps[k])
    print('plane %d: mean|x-P| %.2f  nonzero leaves %.1f%%  bits/sample %.3f  final mean|err| %.2f  classes used %s' % (
        k, e.mean(), 100 * (q != 0).mean(), bits([(q, cl)], 1) / q.size, np.abs(y - x1[k]).mean(), np.bincount(cl.ravel(), minlength=16)[:16] * 100 // q.size))
