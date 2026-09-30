#!/usr/bin/env python3
"""washenergy.py REGIONS.txt ... -- aggregate the OWNER-VERIFIED detector's own
regions into one number per frame: WASH ENERGY = sum over regions of
|mean signed error| x area.  This is the aggregate to rank arms on, because it
weights a region by BOTH how wrong its level is and how much of the picture it
covers -- which region COUNT does not (sect.50.3's withdrawn conclusion) and
which the 4x32 block metric misses when a wash is smaller than one block."""
import sys, re, os
for p in sys.argv[1:]:
    tot=0.0; n=0; worst=0.0
    for ln in open(p):
        m=re.search(r'area\s+(\d+)\s+err\s+([-+0-9.]+)', ln)
        if not m: continue
        a=int(m.group(1)); e=float(m.group(2))
        tot += abs(e)*a; n+=1
        if abs(e)>abs(worst): worst=e
    print("%-42s regions %3d  wash energy %9.0f  worst region mean %+7.1f"
          % (os.path.basename(p), n, tot, worst))
