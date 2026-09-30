import json, sys, numpy as np, glob, os
os.chdir(sys.argv[1] if len(sys.argv)>1 else '.')
def interp(rows, bpp_t, pl):
    x=np.log2([r[1] for r in rows]); y=[r[2][pl] for r in rows]
    o=np.argsort(x); x=np.array(x)[o]; y=np.array(y)[o]
    t=np.log2(bpp_t)
    if t<x[0] or t>x[-1]: return None
    return float(np.interp(t,x,y))
cells=sorted(set(os.path.basename(f).split('.')[0] for f in glob.glob('*.base.json')))
agg={}
for c in cells:
    if not os.path.exists(c+'.json'): continue
    B=json.load(open(c+'.base.json')); Hh=json.load(open(c+'.json'))
    for v,res in Hh.items():
        rows=res['-1']; brow=B['-1']
        line=[]
        for R in (0.5,1.0,2.0):
            d=[]
            for pl in range(3):
                a=interp(rows,R,pl); b=interp(brow,R,pl)
                d.append(None if a is None or b is None else a-b)
            agg.setdefault((v,R),[]).append(d); line.append('/'.join('%+.2f'%x if x is not None else 'na' for x in d))
        oor=sum(r[3] for r in rows)
        print('%-8s %-14s  0.5: %s  1.0: %s  2.0: %s  oor=%d'%(c,v,line[0],line[1],line[2],oor))
print('MEAN over cells (dB vs baseline, Y/Cb/Cr):')
for v in sorted(set(k[0] for k in agg)):
    s=[]
    for R in (0.5,1.0,2.0):
        L=[d for d in agg[(v,R)] if None not in d]
        m=np.mean(L,0) if L else [np.nan]*3; w=np.min(L,0) if L else [np.nan]*3
        s.append('%.1f: %+.2f/%+.2f/%+.2f (worst %+.2f/%+.2f/%+.2f, n=%d)'%(R,*m,*w,len(L)))
    print(' ',v,' | '.join(s))
# row phase at Qf=7 : ratio of last row and first row to the slice mean, per plane
print('ROW PHASE (Qf=7; first-row/mean, last-row/mean per plane):')
for c in cells:
    if not os.path.exists(c+'.json'): continue
    B=json.load(open(c+'.base.json')); Hh=json.load(open(c+'.json'))
    def rp(ph): return ' '.join('%.2f/%.2f'%(p[0]/np.mean(p),p[-1]/np.mean(p)) for p in ph)
    print('  %-8s base %s'%(c,rp(B['phase-1'])))
    for v,res in Hh.items():
        r=[x for x in res['-1'] if abs(x[0]-7.0)<1e-9][0]
        print('  %-8s %-14s %s  bpp=%.2f'%(c,v,rp(r[6]),r[1]))
