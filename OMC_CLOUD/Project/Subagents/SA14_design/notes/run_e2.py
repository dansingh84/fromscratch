"""E2: legality + generation exactness of the NEST core (intra, whole frame, no slices).
gen1: analysis -> quantise -> closure -> read (canonical description) -> decode = y1
gen2: canonical analysis of y1 -> read -> must equal gen1's description; decode must equal y1."""
import sys, time, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA14_design/notes')
import nest, common14 as cm

n2d, n1d = 2, 3
out = []
def run(name, X, dep, D0, lo_v=None, hi_v=None):
    M = (1 << dep) - 1
    lo_v = 0 if lo_v is None else lo_v
    hi_v = M if hi_v is None else hi_v
    lo = np.full(X.shape, lo_v, np.int64); hi = np.full(X.shape, hi_v, np.int64)
    sh = cm.shifts_for(n2d, n1d, X.shape, D0)
    t = time.time()
    ql, top, rec, st = nest.encode_intra(X, lo, hi, n2d, n1d, sh)
    legal = int(((rec < lo_v) | (rec > hi_v)).sum())
    desc, bits = nest.read_description(ql, top)
    y1 = nest.decode_description(desc, lo, hi, n2d, n1d)
    same1 = int((y1 != rec).sum())
    # gen 2
    ql2, top2 = nest.canonical_leaves(y1, lo, hi, n2d, n1d)
    desc2, bits2 = nest.read_description(ql2, top2)
    dsame = True
    for a, b in zip(desc[:-1], desc2[:-1]):
        for n in a:
            if a[n][0] != b[n][0] or not np.array_equal(a[n][1], b[n][1]):
                dsame = False
    if desc[-1][1] != desc2[-1][1] or not np.array_equal(desc[-1][2], desc2[-1][2]):
        dsame = False
    y2 = nest.decode_description(desc2, lo, hi, n2d, n1d)
    moved = int((y2 != y1).sum())
    nesc = sum(int((d['esc'] != 0).sum()) for lvl in ql for d in lvl.values()) + int((top['esc'] != 0).sum())
    p = cm.psnr(X, y1, dep)
    line = (f"{name:14s} D0={D0:4d} bpp_plane={bits/X.size:6.3f} psnr={p:6.2f} oob={legal} "
            f"closure_iters={st['iters']} converted={st['converted']} escapes={nesc} "
            f"desc_decodes_to_y1={same1==0} gen2_desc_identical={dsame} gen2_moved={moved} t={time.time()-t:.1f}s")
    print(line, flush=True)
    out.append(line)

if __name__ == '__main__':
    for D0 in (8, 32, 128):
        for cell in ('gfx', 'dng1080', 'spot'):
            planes, dep = cm.read_frame(cell, 8)
            for pn, X in zip(('Y', 'Cb', 'Cr'), planes):
                run(f"{cell}-{pn}", X, dep, D0)
        run('rails-10', cm.synth_rails(dep=10), 10, D0)
        run('rails-12', cm.synth_rails(dep=12), 12, D0 * 4)
        run('rails-lim10', np.clip(cm.synth_rails(dep=10), 4, 1019), 10, D0, 4, 1019)
    open('/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA14_design/out/e2.txt', 'w').write('\n'.join(out) + '\n')
