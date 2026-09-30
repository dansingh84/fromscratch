import sys, time, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
path, W, H = yuv.CELLS['dng720']
cod = omc16.Codec(W, H, S=4, bpp=0.5)
drefs = None
for t in range(3):
    src = yuv.read_frame(path, W, H, t); t0 = time.time()
    rec = cod.encode(src); dt = time.time() - t0
    ps = [10*np.log10(1023**2/np.mean((rec[p]-src[p])**2.0)) for p in range(3)]
    oob = sum(int(((r < 0) | (r > 1023)).sum()) for r in rec)
    dec = cod.decode(cod.last, drefs)
    rt0 = all(np.array_equal(dec[p], rec[p]) for p in range(3))
    info = cod.last['info']
    print('f%d %.1fs bits %d/%d costed %d Pe[0:4]=%s viaread1=%d p2_viaread=%s pass2_exact=%s changed=%d rt0=%s PSNR %.2f/%.2f/%.2f oob %d %s' % (
        t, dt, cod.stats['frame_bits'], cod.F, cod.stats['costed'], cod.last['Pe'][:4], info['viaread1'], info.get('p2_viaread'), info.get('pass2_exact'), info['pass2_changed'], rt0, *ps, oob,
        {k: v for k, v in cod.stats.items() if k not in ('frame_bits', 'costed')}), flush=True)
    drefs = rec
