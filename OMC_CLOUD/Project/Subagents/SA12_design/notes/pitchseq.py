import sys, numpy as np
W, H, sh = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
fs = W * H * 2; s = np.fromfile(sys.argv[1], dtype='<u2').astype(np.int64); d = np.fromfile(sys.argv[2], dtype='<u2').astype(np.int64)
out = []
for pl, (o, w) in enumerate(((0, W), (W * H, W // 2), (W * H + W * H // 2, W // 2))):
    vs, fr, la = [], [], []
    for t in range(2, 12):
        e = (d[t * fs + o:t * fs + o + w * H] - s[t * fs + o:t * fs + o + w * H]).reshape(H, w)
        dy = np.abs(np.diff(e, axis=0)); ys = np.arange(1, H); m = ys % sh == 0
        vs.append(dy[m].mean() / dy[~m].mean()); ph = [np.abs(e[j::sh]).mean() for j in range(sh)]
        fr.append(ph[0] / np.mean(ph)); la.append(ph[-1] / np.mean(ph))
    out.append('%s v%d %.2f first %.2f last %.2f' % ('Y Cb Cr'.split()[pl], sh, np.mean(vs), np.mean(fr), np.mean(la)))
print(sys.argv[6], ' | '.join(out))
