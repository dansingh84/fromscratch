#!/usr/bin/env python3
# today_boil.py — boil (mean |frame-to-frame change|) and ants (share > 6 codes) per plane of today's decodes vs source.
import sys, os, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bench')); from d1_screen import read
R = '/home/user/fromscratch/OMC_CLOUD/'
for c in ('gfx444_B001C001', 'cine_A005C031'):
    src = R + 'Project/.work/arms/%s_1280x720_422_10.yuv' % c; dec = R + 'scratch/today/%s_1280x720_b1.0.d.yuv' % c
    X = [read(src, 1280, 720, f) for f in range(3)]; D = [read(dec, 1280, 720, f) for f in range(3)]; out = []
    for k in range(3):
        do = np.mean([np.abs(D[t][k] - D[t-1][k]).mean() for t in (1, 2)]); ds = np.mean([np.abs(X[t][k] - X[t-1][k]).mean() for t in (1, 2)])
        ao = np.mean([(np.abs(D[t][k] - D[t-1][k]) > 6).mean() for t in (1, 2)]); as_ = np.mean([(np.abs(X[t][k] - X[t-1][k]) > 6).mean() for t in (1, 2)])
        out.append('%s boil %.3f (src %.3f) ants %.2f%% (src %.2f%%)' % ('YUV'[k], do, ds, 100 * ao, 100 * as_))
    print(c, 'today @1.0', ' | '.join(out))
