# Coding gain (high-rate, optimal allocation, biorthogonal-weighted) of 1-D multi-level
# lifting transforms, linear (no rounding), periodic extension.  AR(1) and empirical.
import numpy as np
def fwd(x, levels):
    out=[]; s=x.astype(float)
    for lv in levels:
        e=s[0::2].copy(); o=s[1::2].copy(); m=len(e)
        P=lv['P']; U=lv['U']
        h=o.copy()
        for off,w in P: h-= w*np.roll(e,-off)
        l=e.copy()
        for off,w in U: l+= w*np.roll(h,-off)
        out.append(h); s=l
    out.append(s); return out
def matrices(N, levels):
    A=np.stack([np.concatenate(fwd(np.eye(N)[:,j],levels)) for j in range(N)],axis=1)
    sizes=[len(b) for b in fwd(np.zeros(N),levels)]
    return A,sizes
def gain(A,sizes,R):
    S=np.linalg.inv(A); C=A@R@A.T; var=np.diag(C); w=(S**2).sum(0)
    N=A.shape[0]; lg=0; k=0; sx=np.mean(np.diag(R))
    for n in sizes:
        lg+= n/N*np.log10(np.mean(var[k:k+n])*np.mean(w[k:k+n])); k+=n
    return 10*(np.log10(sx)-lg)
N=256
d=np.arange(N); dd=np.minimum(d,N-d)
def AR(r): return r**np.abs(np.subtract.outer(dd*0+np.arange(N),np.arange(N))).clip(0) if False else np.array([[r**min(abs(i-j),N-abs(i-j)) for j in range(N)] for i in range(N)])
P53=[(0,.5),(1,.5)]; U53=[(-1,.25),(0,.25)]
P97=[(-1,-1/16),(0,9/16),(1,9/16),(2,-1/16)]
def lvls(L,U,P=P53): return [dict(P=P,U=U)]*L
def best_onesided(L, lags, P=P53, R=None):
    # lags: per-level lag a; taps H[i-a],H[i-a-1] with weights optimised (same per level) by grid
    best=(-1e9,None)
    for w1 in np.arange(-0.2,0.45,0.05):
        for w2 in np.arange(-0.2,0.45,0.05):
            lv=[dict(P=P,U=[(-a,w1),(-a-1,w2)]) for a in lags]
            A,s=matrices(N,lv); g=gain(A,s,R)
            if g>best[0]: best=(g,(round(w1,2),round(w2,2)))
    return best
if __name__=='__main__':
    for r in (0.95,0.8):
        R=AR(r)
        print(f"--- AR(1) rho={r}")
        for L,lags in ((1,[2]),(2,[3,2]),(5,[17,9,5,3,2])):
            A,s=matrices(N,lvls(L,U53)); g53=gain(A,s,R)
            A,s=matrices(N,lvls(L,[])); gpo=gain(A,s,R)
            gos=best_onesided(L,lags,R=R)
            gnl=best_onesided(L,[2]*L,R=R)  # lag 2 everywhere (cyclic for L>1, gain only)
            print(f"L={L}: 5/3 {g53:.2f} dB | predict-only {gpo:.2f} | one-sided acyclic lags {lags}: {gos[0]:.2f} w={gos[1]} | lag2-all (cyclic) {gnl[0]:.2f}")
