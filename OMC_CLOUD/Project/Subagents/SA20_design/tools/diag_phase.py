# diag_phase.py CLIP Q R : intra frame 0 with bench/n4_core.po at step Q (env RHO/RHOK/F), mean |error| by column mod 32
# (luma) / mod 16 (chroma) and by row mod 4, ours vs today's frame 0 at rate R. Normalised to each codec's own mean.
import sys, os, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bench'))
from d1_screen import read
from n4_core import po
W, H = 1280, 720; ROOT = '/home/user/fromscratch/OMC_CLOUD/'
c, Q, R = sys.argv[1], float(sys.argv[2]), sys.argv[3]; F = float(os.environ.get('F', '0.7'))
x = read(ROOT + 'Project/.work/arms/%s_1280x720_422_10.yuv' % c, W, H, 0)
t = read(ROOT + 'scratch/today/%s_1280x720_b%s.d.yuv' % (c, R), W, H, 0)
o = [po(p, Q, F, 0, [])[1] for p in x]
for k, nm in enumerate(('Y', 'Cb', 'Cr')):
    px = 32 if k == 0 else 16
    for lab, d in (('ours ', o), ('today', t)):
        e = np.abs(d[k].astype(float) - x[k]); m = e.mean()
        print('%s %s col%%%d %s | row%%4 %s' % (nm, lab, px, ' '.join('%.2f' % (e[:, j::px].mean() / m) for j in range(px)),
              ' '.join('%.2f' % (e[j::4].mean() / m) for j in range(4))))
