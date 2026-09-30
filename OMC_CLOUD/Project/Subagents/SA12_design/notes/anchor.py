"""T0: legal ANCHOR BRACKETING for intra slices.  Per slice: (1) the slice's LAST row is coded first as a 1-D legal
horizontal pyramid (5 H levels, same step rule); (2) the 16-row pyramid is coded with that row KNOWN: its pixel boxes
are the decoded anchor values (degenerate), so every coefficient whose legal interval collapses to one value is
derived (not transmitted); (3) the next slice's top context = decoded rows above (which end with the anchor).
Compared with the plain slice pyramid, intra, frame f8, same Qf.  Reports coded-entropy bpp (degenerate coefficients
excluded, anchor bits included), PSNR, slice-boundary excess (boundary vs half-slice step, rel. to other rows),
first/last row ratio, VMAF-NEG, and the gen-2 check.  usage: anchor.py tag path W H sh Qf"""
import sys, os, math, subprocess, numpy as np
os.environ['HF_FAST'] = '1'; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hf
T = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools'; SCR = os.environ['SCR']
tag, path, W, H, sh, Qf = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), float(sys.argv[6])
L, nv, kH, kV = 5, 3, 's10', 's10a'
src = hf.load(path, W, H, 8, '422')
def steps(Wp, rows, nvv):
    w = hf.weights(rows, Wp, L, nvv, kH, kV); ks = hf.keys(L, nvv); w[ks[-1]] *= 4.0
    return {k: max(1, int(round(2.0 ** round(Qf - 0.5 * math.log2(w[k]))))) for k in ks}
def code_plane(P, anchor, Pin=None):
    Hh, Wp = P.shape; ns = Hh // sh; X = (P if Pin is None else Pin)[:ns * sh].astype(np.int64)
    st = steps(Wp, sh, nv); sta = steps(Wp, 1, 0)       # anchor: its own 1-row H-only geometry
    rec = np.zeros((ns * sh, Wp), np.int64); syms = {}; allQ = []
    for k in range(ns):
        r0 = k * sh; ctx = None
        if k > 0: hf._slice0[0] = k - 1; ctx = hf.ctx_of(rec[r0 - sh:r0][None], L, nv, kH)
        hf._slice0[0] = k
        LO = np.zeros((1, sh, Wp), np.int64); HI = np.full((1, sh, Wp), 1023, np.int64)
        if anchor:
            A = X[r0 + sh - 1][None, None, :]
            Ca = hf.Coder('enc', sta)
            ar = hf.rec_level(Ca, 1, L, 0, A, np.zeros(A.shape, np.int64), np.full(A.shape, 1023, np.int64), kH, kV, None)[0, 0]
            for kk, v in Ca.Q.items(): syms.setdefault(('A',) + kk, []).append(v.ravel())
            LO[0, -1] = ar; HI[0, -1] = ar; allQ.append(Ca.Q)
        C = hf.Coder('enc', st)
        rec[r0:r0 + sh] = hf.rec_level(C, 1, L, nv, X[r0:r0 + sh][None], LO, HI, kH, kV, ctx)[0]
        allQ.append(C.Q)
        for kk, v in C.Q.items(): syms.setdefault(kk, []).append(v[~C.deg[kk]].ravel())
    bits = sum(hf.ent(np.concatenate(v)) for v in syms.values() if sum(len(x) for x in v))
    return rec, bits, allQ
out = {}
for anchor in (0, 1):
    recs, tb, Qs = [], 0.0, []
    for P in src:
        r, b, q = code_plane(P, anchor); recs.append(r); tb += b; Qs.append(q)
    # generation 2: re-encode the decoded picture; compare every index and sample
    g2 = True
    for pi, (P, r) in enumerate(zip(src, recs)):
        r2, _, q2 = code_plane(P, anchor, Pin=np.vstack([r, P[r.shape[0]:]]))
        g2 &= bool(np.array_equal(r2, r) and all(np.array_equal(a[kk], b[kk]) for a, b in zip(Qs[pi], q2) for kk in a))
    n = recs[0].shape[0]; line = []
    for pi, (P, r) in enumerate(zip(src, recs)):
        e = (r - P[:n]).astype(float); dy = np.abs(np.diff(e, axis=0)); ys = np.arange(1, n)
        oth = dy[(ys % sh != 0) & (ys % sh != sh // 2)].mean(); ph = [np.abs(e[j::sh]).mean() for j in range(sh)]
        line.append('%s PSNR %.2f excess %+.2f (bnd %.2f int %.2f) first %.2f last %.2f' % ('Y Cb Cr'.split()[pi], 10 * math.log10(1023 ** 2 / (e ** 2).mean()),
                    (dy[ys % sh == 0].mean() - dy[ys % sh == sh // 2].mean()) / oth, dy[ys % sh == 0].mean() / oth, dy[ys % sh == sh // 2].mean() / oth, ph[0] / np.mean(ph), ph[-1] / np.mean(ph)))
    sp = os.path.join(SCR, tag + 's.yuv'); dp = os.path.join(SCR, tag + 'd.yuv')
    np.concatenate([P[:n].astype('<u2').ravel() for P in src]).tofile(sp); np.concatenate([r.astype('<u2').ravel() for r in recs]).tofile(dp)
    neg = subprocess.run(['bash', T + '/negscore.sh', sp, dp, str(W), str(n), '422', '10', '1'], capture_output=True, text=True, cwd=T).stdout.strip().splitlines()[-1]
    os.remove(sp); os.remove(dp)
    print('%s Qf %.1f %-8s bpp(ent) %.3f NEG %s g2 %s | %s' % (tag, Qf, 'ANCHOR' if anchor else 'plain', tb / (W * n), neg, g2, ' | '.join(line)), flush=True)
