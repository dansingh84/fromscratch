from cgain import *
R=AR(0.95)
for L in (1,2,5):
  for taps in ([-1,0],[-1,-2],[-2,-3],[0,1],[-3,-4]):
    best=(-1e9,None)
    for w1 in np.arange(-0.2,0.45,0.025):
      for w2 in np.arange(-0.2,0.45,0.025):
        lv=[dict(P=P53,U=[(taps[0],w1),(taps[1],w2)])]*L
        A,s=matrices(N,lv); g=gain(A,s,R)
        if g>best[0]: best=(g,(round(float(w1),3),round(float(w2),3)))
    print(L,taps,"%.2f"%best[0],best[1])
