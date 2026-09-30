from dag1d import synth_1d
for lv, nm in [([dict(P=[0,1],U=[-3,-4]), dict(P=[0,1],U=[-2,-3])], 'V lags (3,2)'),
               ([dict(P=[0,1],U=[-2,-3])]*2, 'lag 2 both (design text)'),
               ([dict(P=[0,1],U=[])]*2, 'predict-only')]:
    pix, nc = synth_1d(128, lv); fin = {lin: r for r, (lin, dep) in enumerate(pix)}
    back = 0; fwdmax = 0
    for r, (lin, dep) in enumerate(pix):
        d = dep & ~(1 << lin)
        while d:
            b = d & -d; a = b.bit_length() - 1; d ^= b
            if fin[a] > r: back += 1; fwdmax = max(fwdmax, fin[a] - r)
    print(f"{nm:26s}: edges from a LATER row into an earlier row's clamp: {back}, max reach {fwdmax} rows")
