import sys, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
path, W, H = yuv.CELLS['dng720']
cod = omc16.Codec(W, H, S=4, bpp=0.5, tabs=omc16.Tables(sys.argv[1] if len(sys.argv) > 1 else None)); cod.dbg_bits = True
src = yuv.read_frame(path, W, H, 0); rec = cod.encode(src)
tot = cod.stats['frame_bits']; bb = cod.stats['band_bits']
print('frame bits %d  Pe min/med/max %d/%d/%d  PSNR %.2f/%.2f/%.2f' % (tot, cod.last['Pe'].min(), np.median(cod.last['Pe']), cod.last['Pe'].max(), *[10*np.log10(1023**2/np.mean((rec[p]-src[p])**2.0)) for p in range(3)]))
print('headers %d' % (32 + 80 * cod.NS), 'sum band bits %d' % sum(bb.values()), 'other %d' % (tot - 32 - 80 * cod.NS - sum(bb.values())))
for k, v in sorted(bb.items()):
    print('  plane %d %-4s bits %7d  (%.3f bits/coef)  nonzero %6d of %7d' % (k[0], k[1], v, v / cod.stats['band_n'][k], cod.stats['band_nz'][k], cod.stats['band_n'][k]))
