#!/usr/bin/env python3
"""[SA7-PO] Synthetic extrema for DESIGN3 gate (2).

Every pattern is built to press the legality cap, and one of them is built to
break it on purpose: the ADVERSARIAL CHECKERBOARD puts the four diagonal
corners of an (odd,odd) sample at the LOW rail and its four edge neighbours at
the HIGH rail, which is exactly the configuration for which the HH bands'
effective predictor

    P_eff = 1/2(N+S+W+E) - 1/4(NW+NE+SW+SE)

leaves the legal window (REPORT 17.6).  If the cap is doing what it claims,
this is where it has to work hardest.
"""
import sys, numpy as np

def build(W, H, NF, depth, fmt, limited):
    maxv = (1 << depth) - 1
    if limited:                      # broadcast-legal window for this depth
        lo = 16 << (depth - 8); hi = 235 << (depth - 8)
        clo = 16 << (depth - 8); chi = 240 << (depth - 8)
    else:
        lo = 0; hi = maxv; clo = 0; chi = maxv
    Wc = W // 2 if fmt == '422' else W
    out = []
    for f in range(NF):
        y = np.zeros((H, W), dtype=np.uint16)
        band = H // 8
        # 0: flat at the low rail          4: horizontal ramp
        # 1: flat at the high rail         5: vertical ramp
        # 2: 1-px checkerboard             6: ADVERSARIAL checkerboard (see above)
        # 3: 2-px checkerboard             7: rail-to-rail 4-px bars
        yy, xx = np.mgrid[0:H, 0:W]
        y[0*band:1*band] = lo
        y[1*band:2*band] = hi
        r = slice(2*band, 3*band); y[r] = np.where((xx[r]+yy[r]) % 2 == 0, lo, hi)
        r = slice(3*band, 4*band); y[r] = np.where(((xx[r]//2)+(yy[r]//2)) % 2 == 0, lo, hi)
        r = slice(4*band, 5*band); y[r] = (lo + (hi-lo)*xx[r]//max(W-1,1)).astype(np.uint16)
        r = slice(5*band, 6*band); y[r] = (lo + (hi-lo)*yy[r]//max(H-1,1)).astype(np.uint16)
        # the adversarial pattern: corners low, edges high, on the odd/odd lattice
        r = slice(6*band, 7*band)
        ox, oy = xx[r] % 2, yy[r] % 2
        y[r] = np.where((ox == 1) & (oy == 1), hi,                 # the predicted site
              np.where((ox == 0) & (oy == 0), lo, hi))             # corners low, edges high
        r = slice(7*band, 8*band); y[r] = np.where((xx[r]//4) % 2 == 0, lo, hi)
        # phase the whole thing per frame so the temporal path is exercised too
        y = np.roll(y, f, axis=1)
        cb = np.where(((np.arange(Wc)[None,:] + np.arange(H)[:,None] + f) % 2) == 0,
                      clo, chi).astype(np.uint16)
        cr = np.where(((np.arange(Wc)[None,:] - np.arange(H)[:,None] + f) % 2) == 0,
                      chi, clo).astype(np.uint16)
        out += [y.tobytes(), cb.tobytes(), cr.tobytes()]
    return b''.join(out)

if __name__ == '__main__':
    W, H, NF, depth, fmt, limited, path = (int(sys.argv[1]), int(sys.argv[2]),
        int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], int(sys.argv[6]), sys.argv[7])
    open(path, 'wb').write(build(W, H, NF, depth, fmt, limited))
    print(path)
