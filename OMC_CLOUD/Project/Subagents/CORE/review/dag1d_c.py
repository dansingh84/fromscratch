from dag1d import synth_1d, has_cycle, selfloop
N=512; P53=[0,1]; P97=[-1,0,1,2]
def ok(lv):
    pix,nc=synth_1d(N,lv); return (not has_cycle(pix,nc)) and selfloop(N,lv)==0
print("future-only U=H[i+1],H[i+2], 5 levels 5/3 predict:", ok([dict(P=P53,U=[1,2])]*5))
print("future-only U=H[i+1] only, 5 levels:", ok([dict(P=P53,U=[1])]*5))
print("future-only U=H[i+1],H[i+2], H1,H2 9/7-M:", ok([dict(P=P97,U=[1,2])]*2+[dict(P=P53,U=[1,2])]*3))
print("future-only U=H[i+2],H[i+3], H1,H2 9/7-M:", ok([dict(P=P97,U=[2,3])]*2+[dict(P=P53,U=[2,3])]*3))
print("future U=H[i],H[i+1]:", ok([dict(P=P53,U=[0,1])]*5))
# 2V per-level minimal (a1 finest, a2)
best=[]
for a1 in range(1,10):
  for a2 in range(1,10):
    if ok([dict(P=P53,U=[-a1,-a1-1]),dict(P=P53,U=[-a2,-a2-1])]): best.append((a1+a2,a1,a2))
print("2V past-only per-level feasible (a1,a2) smallest:", sorted(best)[:4])
# causal (extrapolating) predictor P uses E[i] only (odd 2i+1 from 2i), past update H[i-1]
print("P=E[i] only, U=H[i-1],H[i-2], 5 levels:", ok([dict(P=[0],U=[-1,-2])]*5))
print("P=E[i-1],E[i] (extrapolation), U=H[i-1]:", ok([dict(P=[-1,0],U=[-1])]*5))
