#!/usr/bin/env python3
"""[SA7] DESIGN2 (d): source-only analysis of the 5/3 vertical and (9,7)-M horizontal predictors
at levels 1 and 2.  No codec, no build: it asks what the FIXED predictor costs at hard edges and
what a shorter or one-sided predictor would leave there."""
import sys, numpy as np
src,W,H,f,dep = sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5])
Wc=W//2; fw=W*H+2*Wc*H
Y=np.fromfile(src,dtype=np.uint16)[f*fw:f*fw+W*H].astype(np.int64).reshape(H,W)
maxv=(1<<dep)-1
def report(tag, x, T):
    # x[:, even/odd] along the transform axis (axis 0 = rows for the vertical 5/3)
    e0 = x[0:-2:2]          # x[2i]
    e1 = x[2::2]            # x[2i+2]
    o  = x[1:-1:2]          # x[2i+1]
    n  = min(e0.shape[0], e1.shape[0], o.shape[0])
    e0,e1,o = e0[:n],e1[:n],o[:n]
    two  = np.abs(o - ((e0+e1)//2))            # the shipped two-sided predictor residual
    left = np.abs(o - e0)                      # one-sided, from above
    right= np.abs(o - e1)                      # one-sided, from below
    one  = np.minimum(left,right)
    step = np.abs(e0-e1)                       # the step the predictor spans
    hard = step > T
    print("%-28s samples=%d  hard-step(>%d)=%.2f%%" % (tag, two.size, T, 100*hard.mean()))
    if hard.sum():
        print("      at hard steps : |resid| two-sided p50=%d p99=%d max=%d | one-sided p50=%d p99=%d max=%d"
              % (np.percentile(two[hard],50), np.percentile(two[hard],99), two[hard].max(),
                 np.percentile(one[hard],50), np.percentile(one[hard],99), one[hard].max()))
        better = (one[hard] < two[hard]).mean()
        med_gain = np.median(two[hard].astype(float) - one[hard])
        print("      one-sided smaller on %.1f%% of hard-step positions, median gain %.0f codes"
              % (100*better, med_gain))
    flat = ~hard
    if flat.sum():
        print("      away from steps: two-sided p50=%d p99=%d | one-sided p50=%d p99=%d  (one-sided must NOT be used here)"
              % (np.percentile(two[flat],50), np.percentile(two[flat],99),
                 np.percentile(one[flat],50), np.percentile(one[flat],99)))
    # rail proximity of the hard-step positions
    near = ((o < 0.15*maxv) | (o > 0.85*maxv))
    print("      hard-step positions in the outer 15%% of the range: %.2f%% (rail-adjacent)"
          % (100*(hard & near).mean() if hard.sum() else 0))
T = max(1, (maxv+1)//32)      # 32 codes at 10-bit: a step a 2-tap predictor cannot follow
print("=== %s frame %d, threshold T = %d codes (2^depth/32) ===" % (src.split('/')[-1], f, T))
report("vertical 5/3, level 1", Y, T)
report("vertical 5/3, level 2", Y[::2], T)
