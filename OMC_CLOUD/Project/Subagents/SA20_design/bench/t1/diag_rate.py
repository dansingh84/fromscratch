# diag_rate.py CLIP S0 : bits of inter frame 1 (P = decoded frame 0 at step S0, warped) at a range of steps, per plane,
# and the share of luma leaves that escape (|q| > K) - checks that bits fall smoothly as the step grows
import sys, os, numpy as np
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 't1_seq.py')).read().split('\nfor c in os.environ')[0]
c, s0 = sys.argv[1], float(sys.argv[2]); os.environ['CLIPS'] = ''
exec(src)
x0, x1 = read(c, 0), read(c, 1); y0, _ = frame(x0, s0, None); Ps, nn = predict(x1, y0)
for s in [s0 * 2 ** (e / 8) for e in range(-8, 5)]:
    ys, parts = frame(x1, s, Ps); b = [bits([pp], 1) / (W * H) for pp in parts]
    print('step %6.2f  bpp Y %.3f Cb %.3f Cr %.3f total %.3f  Y nonzero %.2f%%  escapes %.3f%%  Y err %.2f' % (s, *b, sum(b) + 10 * nn / (W * H),
          100 * (parts[0][0] != 0).mean(), 100 * (np.abs(parts[0][0]) > K).mean(), np.abs(ys[0] - x1[0]).mean()))
