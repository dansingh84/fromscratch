import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
path, W, H = yuv.CELLS['dng720']
g1 = omc16.Codec(W, H, S=4, bpp=0.5); g2 = omc16.Codec(W, H, S=4, bpp=0.5)
src = yuv.read_frame(path, W, H, 0); r1 = g1.encode(src)
print('g1 bits per slice (first 6):', np.round(g1.last['bits'][:6]), 'Pe', g1.last['Pe'][:6])
os.environ['DBG_READ'] = '1'
r2 = g2.encode(r1)
bad = np.nonzero((r2[0] != r1[0]).any(1))[0]
print('diff rows', bad.min() if bad.size else None, bad.max() if bad.size else None, 'slices', sorted(set((bad // 4).tolist())) if bad.size else None)
for k in sorted(set((bad // 4).tolist()))[:4] if bad.size else []:
    print('slice', k, 'g1 bits %.1f Pe %d | g2 bits %.1f Pe %d' % (g1.last['bits'][k], g1.last['Pe'][k], g2.last['bits'][k], g2.last['Pe'][k]))
