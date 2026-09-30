# rails: cut24 (0/1023 plates against ramps) and ext10 (rail extremes), legal codec vs the same codec with a plain
# pixel clip (not exact): out-of-range count, bits at exact CBR, per-plane PSNR, samples worse than clip, gen-2 identity.
import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
A = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
CELLS = {'cut24': (A + 'cut24.yuv', 256, 64), 'ext10': (A + 'ext_10_422_l0.yuv', 512, 128), 'ext10b': (A + 'ext_10_422_l1.yuv', 512, 128)}
TAB = os.environ.get('TAB', '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/out/tables/tables_p2.pkl')
def psnr(a, b): return [10 * np.log10(1023 ** 2 / max(1e-9, np.mean((a[p] - b[p]) ** 2.0))) for p in range(3)]
for name in (sys.argv[1:] or ['cut24', 'ext10', 'ext10b']):
    path, W, H = CELLS[name]; nf = min(6, yuv.nframes(path, W, H))
    for bpp in (0.5, 1.0):
        res = {}
        for legal in (True, False):
            cod = omc16.Codec(W, H, S=4, bpp=bpp, tabs=omc16.Tables(TAB), legal=legal); g2 = omc16.Codec(W, H, S=4, bpp=bpp, tabs=omc16.Tables(TAB), legal=legal)
            oob = 0; ps = []; recs = []; g2ok = []; bits = []; pe = []
            for t in range(nf):
                src = yuv.read_frame(path, W, H, t); r1 = cod.encode(src); recs.append(r1); bits.append(int(cod.stats['frame_bits'])); pe.append(int(np.median(cod.last['Pe'])))
                oob += sum(int(((r < 0) | (r > 1023)).sum()) for r in r1); ps.append(psnr(r1, src))
                if legal:
                    r2 = g2.encode(r1); g2ok.append(all(np.array_equal(r2[p], r1[p]) for p in range(3)) and int(g2.stats['frame_bits']) == int(cod.stats['frame_bits']))
            res[legal] = dict(oob=oob, psnr=np.mean(ps, 0), recs=recs, g2=g2ok, bits=bits, pe=pe, stats=dict(cod.stats))
        L, C = res[True], res[False]
        worse = 0; better = 0; maxex = 0; n = 0
        for t in range(nf):
            src = yuv.read_frame(path, W, H, t)
            for p in range(3):
                el = np.abs(L['recs'][t][p] - src[p]); ec = np.abs(C['recs'][t][p] - src[p])
                worse += int((el > ec).sum()); better += int((el < ec).sum()); maxex = max(maxex, int((el - ec).max())); n += el.size
        print('%s @%.1f | legal: oob %d, PSNR %.2f/%.2f/%.2f, bits %s, Pe med %s, g2 identical %s | clip arm: oob %d, PSNR %.2f/%.2f/%.2f | samples legal worse than clip %d (%.4f %%), better %d, max excess %d codes | stats %s' % (
            name, bpp, L['oob'], *L['psnr'], L['bits'], L['pe'], all(L['g2']), C['oob'], *C['psnr'], worse, 100.0 * worse / n, better, maxex, {k: v for k, v in L['stats'].items() if k not in ('frame_bits', 'est_bits')}), flush=True)
