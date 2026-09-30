import sys, numpy as np
sys.path.insert(0,'.')
import nv2, common14 as cm
REFINE = int(sys.argv[1]) if len(sys.argv) > 1 else 0
def shifts(shape, D0, mins=1):
    # reuse nests-based step rule (same transform), minimum shift 1 (IDQ needs step >= 2)
    import nests; cm.nest = nests
    sh = cm.shifts_for(2, 3, shape, D0)
    return {k: max(mins, v) for k, v in sh.items()}
def intra_params(X, sh):
    P = nv2.Params(); P.sh = sh
    lv, L = nv2.plain(np.zeros_like(X))
    P.cp = [{n: np.zeros_like(v) for n, v in d.items()} for d in lv]; P.cp_top = None
    return P
def run(name, X, dep, D0, lov=None, hiv=None):
    M = (1 << dep) - 1; lov = 0 if lov is None else lov; hiv = M if hiv is None else hiv
    lo = np.full(X.shape, lov, np.int64); hi = np.full(X.shape, hiv, np.int64)
    sh = shifts(X.shape, D0); P = intra_params(X, sh)
    q, qt = nv2.encode(X, P, lo, hi)
    if REFINE: q, qt, nre = nv2.refine(X, q, qt, P, lo, hi)
    y, _ = nv2.decode(q, qt, P, lo, hi)
    q2, qt2 = nv2.recover(y, P, lo, hi)
    same = all(np.array_equal(q[l][n], q2[l][n]) for l in range(nv2.NL) for n in q[l]) and np.array_equal(qt, qt2)
    y2, _ = nv2.decode(q2, qt2, P, lo, hi)
    # clip reference: same indices through a plain inverse + clip  (nests synthesis with INF windows)
    b = nv2.bits_of(q, qt)
    print(f"sat={nv2.STATS['sat']} ", end=''); nv2.STATS['sat']=0
    print(f"{name:10s} D0={D0:3d} bits/px={b/X.size:.4f} psnr={cm.psnr(X,y,dep):.3f} oob={int(((y<lov)|(y>hiv)).sum())} maxerr={int(np.abs(y-X).max())} gen2_indices_identical={same} gen2_moved={int((y2!=y).sum())}", flush=True)
    return y
if __name__ == '__main__':
    for D0 in (32, 128, 256):
        for cell in ('dng1080', 'spot', 'gfx'):
            p, dep = cm.read_frame(cell, 8)
            for pn, X in zip('YBR', p): run(f"{cell}-{pn}", X, dep, D0)
        run('rails10', cm.synth_rails(dep=10), 10, D0)
        run('rails12', cm.synth_rails(dep=12), 12, D0 * 4)
        run('railslim', np.clip(cm.synth_rails(dep=10), 4, 1019), 10, D0, 4, 1019)
        run('rails8', np.clip(cm.synth_rails(dep=8),0,255), 8, max(4, D0 // 4))
