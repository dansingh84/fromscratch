import sys, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
path, W, H = yuv.CELLS['dng720']; today = yuv.TODAY['dng720'] % '0.5'
cod = omc16.Codec(W, H, S=4, bpp=0.5, tabs=omc16.Tables('../out/tables/tables_p2.pkl')); cod.dbg_bits = True
recs = []
for t in range(3):
    src = yuv.read_frame(path, W, H, t); recs.append(cod.encode(src))
    print('f%d PSNR mine %.2f/%.2f/%.2f  today %.2f/%.2f/%.2f' % ((t,) + tuple(10*np.log10(1023**2/np.mean((recs[t][p]-src[p])**2.0)) for p in range(3)) + tuple(10*np.log10(1023**2/np.mean((yuv.read_frame(today, W, H, t)[p]-src[p])**2.0)) for p in range(3))))
yuv.write_frames('../out/eval/diag_dng720_0.5.yuv', recs)
bb = cod.stats['band_bits']; tot = sum(bb.values()); print('frame-2 band bits (accumulated over 3 frames): total %d' % tot)
for k, v in sorted(bb.items(), key=lambda kv: -kv[1])[:8]: print('   ', k, int(v), '%.3f b/coef' % (v / cod.stats['band_n'][k]), 'nz', cod.stats['band_nz'][k])
t = 2; src = yuv.read_frame(path, W, H, t); td = yuv.read_frame(today, W, H, t)
for name, d in (('mine', recs[t]), ('today', td)):
    for p, pn in enumerate(('Y', 'Cb', 'Cr')):
        e = np.abs(d[p] - src[p]).astype(float); cols = np.arange(e.shape[1]); rows = np.arange(e.shape[0])
        cp = [e[:, cols % 32 == i].mean() for i in range(32)]; rp = [e[rows % 4 == i].mean() for i in range(4)]
        print('%-5s %-2s mean|e| %.2f | col phase mod32 min/max %.2f/%.2f (edge cols 0,31: %.2f %.2f) | row phase mod4 %s | signed mean %+.3f' % (
            name, pn, e.mean(), min(cp), max(cp), cp[0], cp[31], ' '.join('%.2f' % x for x in rp), (d[p] - src[p]).mean()))
