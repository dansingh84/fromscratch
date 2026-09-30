from dag1d import synth_1d, has_cycle, selfloop
N=512; P53=[0,1]; P97=[-1,0,1,2]
def ok(lv): 
    pix,nc=synth_1d(N,lv); return (not has_cycle(pix,nc)) and selfloop(N,lv)==0
def minlag(mk):
    for a in range(1,80):
        if ok(mk(a)): return a
    return None
for L in range(1,6):
    print("uniform lag, %d levels 5/3-predict:"%L, minlag(lambda a:[dict(P=P53,U=[-a,-a-1])]*L))
# single-tap one-sided update (U=H[i-a]) 
for L in range(1,6):
    print("single tap lag, %d levels:"%L, minlag(lambda a:[dict(P=P53,U=[-a])]*L))
# update at level k only (k=0 finest) in a 5-level stack, rest predict-only
for k in range(5):
    print("update only at level %d of 5 (0=finest):"%(k+1), minlag(lambda a:[dict(P=P53,U=([-a,-a-1] if j==k else [])) for j in range(5)]))
# 9/7-M predict at H1,H2 with update only at those levels, H3-H5 predict-only
print("H1,H2 9/7-M predict + one-sided update, H3-5 predict-only:", minlag(lambda a:[dict(P=P97,U=[-a,-a-1])]*2+[dict(P=P53,U=[])]*3))
print("2 vertical levels 5/3-predict + update:", minlag(lambda a:[dict(P=P53,U=[-a,-a-1])]*2))
print("3 vertical levels:", minlag(lambda a:[dict(P=P53,U=[-a,-a-1])]*3))
