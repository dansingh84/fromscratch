"""compare a joining encoder's output with generation 1: per frame, slices with identical PICTURE (all planes) and
identical CODED SYMBOLS (per-slice md5 of every index array + intra/inter flag, all planes).  usage: joincmp.py g1tag jtag J W H sh"""
import sys, json, numpy as np, os
g1, jt, J, W, H, sh = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
SCR = os.environ['SCR']; fs = W * H * 2; ns = -(-H // sh)
a = np.fromfile(os.path.join(SCR, g1 + '.dec.yuv'), dtype='<u2'); b = np.fromfile(os.path.join(SCR, jt + '.dec.yuv'), dtype='<u2')
ha = json.load(open(g1 + '.hash.json')); hb = json.load(open(jt + '.hash.json'))
row = []; first_all = None
for i in range(len(b) // fs):
    t = J + i; A = a[t * fs:(t + 1) * fs]; B = b[i * fs:(i + 1) * fs]
    planes = lambda X: (X[:W * H].reshape(H, W), X[W * H:W * H + W * H // 2].reshape(H, W // 2), X[W * H + W * H // 2:].reshape(H, W // 2))
    pa, pb = planes(A), planes(B)
    pic = sum(all(np.array_equal(x[k * sh:(k + 1) * sh], y[k * sh:(k + 1) * sh]) for x, y in zip(pa, pb)) for k in range(ns))
    sym = sum(all(ha[str(t)].get('%d_%d' % (pi, k)) == hb[str(i)].get('%d_%d' % (pi, k)) for pi in range(3)) for k in range(ns))
    allsame = pic == ns and sym == ns
    if allsame and first_all is None: first_all = t
    if not allsame: first_all = None
    row.append('f%d pic %d sym %d%s' % (t, pic, sym, ' ALL' if allsame else ''))
print('%s joins at %d (%d slices):' % (jt, J, ns), ' | '.join(row)); print('  byte-identical (all slices, pictures and symbols) from frame', first_all, 'to the end')
