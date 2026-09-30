#!/usr/bin/env python3
"""armstat.py -- summarise one or more artifactmap region files into the
numbers a comparison needs: region COUNT, total AREA and worst / total
SEVERITY, split by sign.  Counts alone hid the effect the ledger corrected
for in sect.50.3, so area and severity are reported alongside them."""
import sys, os, re
def load(p):
    out=[]
    if not os.path.exists(p): return out
    for ln in open(p):
        m=re.match(r'(\w+)\s+rows\s+(\d+)-\s*(\d+)\s+cols\s+(\d+)-\s*(\d+)\s+area\s+(\d+)\s+err\s+([-+0-9.]+)\s+src\s+([0-9.]+)\s+slice\s+(\d+)',ln.replace('- ','-'))
        if not m:
            f=ln.split()
            if len(f)>=13:
                out.append(dict(kind=f[0],area=int(f[6]),err=float(f[8]),src=float(f[10]),slice=int(f[12])))
            continue
        out.append(dict(kind=m.group(1),area=int(m.group(6)),err=float(m.group(7)),src=float(m.group(8)),slice=int(m.group(9))))
    return out
print(f"{'arm':28s} {'B#':>4s} {'Barea':>8s} {'Bmax':>7s} {'Bsev':>10s} {'D#':>4s} {'Darea':>8s} {'Dmax':>7s} {'Dsev':>10s}")
for p in sys.argv[1:]:
    r=load(p); tag=os.path.basename(p).replace('_regions.txt','')
    b=[x for x in r if x['kind']=='BRIGHT']; d=[x for x in r if x['kind']=='DARK']
    ba=sum(x['area'] for x in b); da=sum(x['area'] for x in d)
    bm=max([x['err'] for x in b],default=0.0); dm=min([x['err'] for x in d],default=0.0)
    bs=sum(abs(x['err'])*x['area'] for x in b); ds=sum(abs(x['err'])*x['area'] for x in d)
    print(f"{tag:28s} {len(b):4d} {ba:8d} {bm:+7.1f} {bs:10.0f} {len(d):4d} {da:8d} {dm:+7.1f} {ds:10.0f}")
