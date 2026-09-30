# flatness root-cause probe: per-band detail-energy retention (decode/source) of luma and chroma, CPP vs today,
# steady frames; plus how much of the lost level-0 energy sits in 'kept' vs 'requantised to zero' coefficients.
import sys, numpy as np, seq2, cpp2
src,W,H=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]); FR=[int(x) for x in sys.argv[4].split(",")]; arms=dict(a.split("=") for a in sys.argv[5:])
for nm,path in arms.items():
    acc={}
    for t in FR:
        S=seq2.read(src,W,H,t); D=seq2.read(path,W,H,t)
        for pi in range(3):
            Ts=cpp2.analysis(S[pi],5,2); Td=cpp2.analysis(D[pi],5,2)
            for k in Ts:
                if k=='LL': continue
                a=acc.setdefault((pi,k),np.zeros(2)); a+=[(Td[k].astype(float)**2).sum(),(Ts[k].astype(float)**2).sum()]
    line=[]
    for pi,pn in enumerate(('Y','Cb','Cr')):
        line.append(pn+': '+' '.join(f'{k[0]}{k[1]}={acc[(pi,k)][0]/acc[(pi,k)][1]:.2f}' for k in sorted([k for (p,k) in acc if p==pi],key=lambda x:(x[1],x[0]))))
    print(nm,' | '.join(line),flush=True)
