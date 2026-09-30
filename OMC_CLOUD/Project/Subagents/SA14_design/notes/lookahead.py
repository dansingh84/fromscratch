"""Vertical lookahead of the continuous leaf-reading 5/3 with V vertical levels: decoded row r depends on source
rows up to r + L.  Computed exactly by perturbation on a column (linear integer lifting, no quantisation needed:
dependency = union of analysis supports of the coefficients whose synthesis basis covers row r)."""
import numpy as np, sys
sys.argv += ['0']
sys.path.insert(0,'.')
import seam_test3 as st
N=128
def fwd(x,V):
    bands=[]; L=x
    for v in range(V):
        L,d=st.v53_fwd_col(L); bands.append(d)
    return bands,L
def inv(bands,L):
    for d in reversed(bands): L=st.v53_inv_col(L,d)
    return L
for V in (1,2,3):
    # analysis support of every coefficient
    base=np.zeros((N,1),np.int64); b0,L0=fwd(base,V)
    coefs=[('L',i) for i in range(L0.shape[0])]+[(v,i) for v in range(V) for i in range(b0[v].shape[0])]
    amax={}
    for r in range(N):
        x=base.copy(); x[r]=1000; b,L=fwd(x,V)
        for i in range(L.shape[0]):
            if L[i,0]!=L0[i,0]: amax[('L',i)]=max(amax.get(('L',i),-1),r)
        for v in range(V):
            for i in range(b[v].shape[0]):
                if b[v][i,0]!=b0[v][i,0]: amax[(v,i)]=max(amax.get((v,i),-1),r)
    look=[]
    for c in coefs:
        bb=[np.zeros_like(d) for d in b0]; LL=np.zeros_like(L0)
        if c[0]=='L': LL[c[1]]=1000
        else: bb[c[0]][c[1]]=1000
        rows=np.nonzero(inv(bb,LL)[:,0])[0]
        for r in rows:
            if 16<r<N-16: look.append(amax.get(c,r)-r)
    print(f"{V} vertical levels: decoded row r needs source rows up to r+{max(look)}")
