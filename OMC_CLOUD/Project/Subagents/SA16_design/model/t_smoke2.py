import sys, time, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
cell = sys.argv[1] if len(sys.argv) > 1 else 'dng720'; NF = int(sys.argv[2]) if len(sys.argv) > 2 else 3
path, W, H = yuv.CELLS[cell]; S = 4 if H == 720 else 8
TAB = sys.argv[3] if len(sys.argv) > 3 else None; g1 = omc16.Codec(W, H, S=S, bpp=0.5, tabs=omc16.Tables(TAB)); g2 = omc16.Codec(W, H, S=S, bpp=0.5, tabs=omc16.Tables(TAB))
dref = None
for t in range(NF):
    src = yuv.read_frame(path, W, H, t); t0 = time.time()
    r1 = g1.encode(src); dt = time.time() - t0
    dec = g1.decode(g1.last, dref); rt0 = all(np.array_equal(dec[p], r1[p]) for p in range(3)); dref = r1
    b1 = g1.stats['frame_bits']
    r2 = g2.encode(r1); b2 = g2.stats['frame_bits']
    g2same = all(np.array_equal(r2[p], r1[p]) for p in range(3))
    if not g2same:
        nd = [int((r2[p] != r1[p]).sum()) for p in range(3)]; rows = np.nonzero((r2[0] != r1[0]).any(1))[0]
        dP = int((g2.last['Pe'] != g1.last['Pe']).sum()); dM = int((g2.last['mode'] != g1.last['mode']).sum())
        dH = sum(int((g2.last['holdg'][g] != g1.last['holdg'][g]).sum()) for g in g1.last['holdg'])
        print('   g2 diff: samples %s first rows %s..%s | Pe differ %d slices (g1 %s g2 %s at first) | mode diff %d | hold diff %d' % (
            nd, rows.min() if rows.size else None, rows.max() if rows.size else None, dP,
            g1.last['Pe'][np.nonzero(g2.last['Pe'] != g1.last['Pe'])[0][:3]] if dP else '-', g2.last['Pe'][np.nonzero(g2.last['Pe'] != g1.last['Pe'])[0][:3]] if dP else '-', dM, dH), flush=True)
    ps = [10*np.log10(1023**2/np.mean((r1[p]-src[p])**2.0)) for p in range(3)]
    oob = sum(int(((r < 0) | (r > 1023)).sum()) for r in r1)
    print('f%d %.1fs bits %d/%d rt0=%s | g2 same=%s bits %d (viaread %d/%d) | PSNR %.2f/%.2f/%.2f oob %d fm=%s stats %s' % (
        t, dt, b1, g1.F, rt0, g2same, b2, g2.last['viaread'], g2.NS, *ps, oob, g1.stats.get('final_mismatch', 0),
        {k: v for k, v in g1.stats.items() if k not in ('frame_bits', 'final_mismatch')}), flush=True)
