import sys, numpy as np
W, H, sh = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]); fs = W * H * 2
s = np.fromfile(sys.argv[1], dtype='<u2').astype(np.int64); d = np.fromfile(sys.argv[2], dtype='<u2').astype(np.int64)
out = []
for pl, (o, w) in enumerate(((0, W), (W * H, W // 2), (W * H + W * H // 2, W // 2))):
    a, b = [], []
    for t in range(2, 12):
        e = (d[t * fs + o:t * fs + o + w * H] - s[t * fs + o:t * fs + o + w * H]).reshape(H, w)
        dy = np.abs(np.diff(e, axis=0)); ys = np.arange(1, H); oth = dy[(ys % sh != 0) & (ys % sh != sh // 2)].mean()
        a.append(dy[ys % sh == 0].mean() / oth); b.append(dy[ys % sh == sh // 2].mean() / oth)
    out.append('%s boundary %.2f internal %.2f excess %+.2f' % ('Y Cb Cr'.split()[pl], np.mean(a), np.mean(b), np.mean(a) - np.mean(b)))
print(sys.argv[6], ' | '.join(out))
