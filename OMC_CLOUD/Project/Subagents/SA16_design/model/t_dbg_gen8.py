import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
path, W, H = yuv.CELLS['floor']; TAB = '../out/tables/tables_p2.pkl'
g1 = omc16.Codec(W, H, S=8, bpp=0.5, tabs=omc16.Tables(TAB)); g2 = omc16.Codec(W, H, S=8, bpp=0.5, tabs=omc16.Tables(TAB))
for t in range(2):
    src = yuv.read_frame(path, W, H, t); r1 = g1.encode(src); r2 = g2.encode(r1)
    d = [(r2[p] != r1[p]) for p in range(3)]; print('t', t, 'diff', [int(x.sum()) for x in d], flush=True)
    if d[0].any():
        rows = np.nonzero(d[0].any(1))[0]; ks = sorted(set((rows // 8).tolist())); print('  differing slices', ks[:10], '... total', len(ks))
        for k in ks[:3]:
            print('  slice', k, 'P g1/g2', g1.last['P'][k], g2.last['P'][k], 'Pe', g1.last['Pe'][k], g2.last['Pe'][k], 'bits %.1f %.1f' % (g1.last['bits'][k], g2.last['bits'][k]))
            for b in range(2 * k, 2 * k + 2):
                dm = np.nonzero(g1.last['mode'][b] != g2.last['mode'][b])[0]
                dh = {g: np.nonzero(g1.last['holdg'][g][b] != g2.last['holdg'][g][b])[0].tolist() for g in ('ll', 'mid', 'fine')}
                dp = np.nonzero(g1.last['Pu'][b] != g2.last['Pu'][b])[0]
                print('    block', b, 'mode diff units', dm.tolist()[:8], 'hold diff', {g: v[:6] for g, v in dh.items() if v}, 'Pu diff', dp.tolist()[:6], 'ucls at first', g1.last['ucls'][dm[0]] if dm.size else None)
            cols = np.nonzero(d[0][8 * k:8 * k + 8].any(0))[0]; print('    differing unit columns', sorted(set((cols // 32).tolist()))[:12])
