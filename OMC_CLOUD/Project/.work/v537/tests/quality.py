#!/usr/bin/env python3
"""quality.py - generation-1 quality sanity for the T5 rebuild.

Usage: quality.py master.yuv dec_display.yuv W H fmt depth [slice_h]

Prints per-plane PSNR of the display decode against the master, and the
slice-seam metric: mean |row-to-row| luma step at slice boundaries vs the
interior (excess <= ~0 means joins are no worse than the picture).
"""
import sys
import numpy as np

def planes(buf, W, H, Wc):
    y = buf[:W*H].reshape(H, W)
    cb = buf[W*H:W*H+Wc*H].reshape(H, Wc)
    cr = buf[W*H+Wc*H:W*H+2*Wc*H].reshape(H, Wc)
    return y, cb, cr

def main():
    mfile, dfile, W, H, fmt, depth = sys.argv[1:7]
    sh = int(sys.argv[7]) if len(sys.argv) > 7 else 16
    W, H, depth = int(W), int(H), int(depth)
    Wc = W if fmt == "444" else W // 2
    fw = W*H + 2*Wc*H
    m = np.fromfile(mfile, dtype='<u2')
    d = np.fromfile(dfile, dtype='<u2')
    nf = min(m.size // fw, d.size // fw)
    maxv = (1 << depth) - 1
    names = ["Y", "Cb", "Cr"]
    for f in range(nf):
        mp = planes(m[f*fw:(f+1)*fw].astype(np.float64), W, H, Wc)
        dp = planes(d[f*fw:(f+1)*fw].astype(np.float64), W, H, Wc)
        ps = []
        for p in range(3):
            mse = np.mean((mp[p] - dp[p])**2)
            ps.append(10*np.log10(maxv*maxv/mse) if mse > 0 else float('inf'))
        # seam metric on decoded luma
        dy = dp[0]
        step = np.abs(np.diff(dy, axis=0)).mean(axis=1)  # step[r] = |row r+1 - row r|
        bmask = np.zeros(H-1, bool)
        bmask[sh-1::sh] = True  # boundary between slice rows sh-1 and sh
        bexc = step[bmask].mean() - step[~bmask].mean()
        # same metric on the master for reference
        my = mp[0]
        mstep = np.abs(np.diff(my, axis=0)).mean(axis=1)
        mexc = mstep[bmask].mean() - mstep[~bmask].mean()
        print(f"frame {f}: PSNR Y {ps[0]:.2f} Cb {ps[1]:.2f} Cr {ps[2]:.2f} dB | "
              f"seam excess dec {bexc:+.3f} src {mexc:+.3f} (codes)")

if __name__ == "__main__":
    main()
