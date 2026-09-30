import sys, time, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
path, W, H = yuv.CELLS['dng720']; NF = int(sys.argv[1])
g1 = omc16.Codec(W, H, S=4, bpp=0.5, tabs=omc16.Tables('../out/tables/tables_p2.pkl'))
for t in range(NF):
    src = yuv.read_frame(path, W, H, t); t0 = time.time(); r1 = g1.encode(src)
    ps = [10*np.log10(1023**2/np.mean((r1[p]-src[p])**2.0)) for p in range(3)]
    print('f%d %.0fs bits %d/%d est %d Pe med %d holds %s PSNR %.2f/%.2f/%.2f stats %s' % (t, time.time()-t0, g1.stats['frame_bits'], g1.F, g1.stats['est_bits'], np.median(g1.last['Pe']),
          {g: int(v.sum()) for g, v in g1.last['holdg'].items()}, *ps, {k: v for k, v in g1.stats.items() if k not in ('frame_bits','est_bits')}), flush=True)
