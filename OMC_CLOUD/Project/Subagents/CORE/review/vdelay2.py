from vdelay import analysis, synthesis, P53, P97, sym, lag
def lat(levels, S, sub=1, N=512, pack='naive'):
    """latency in LUMA lines (excl. 2-line pipeline) for a plane with vertical subsampling sub
    (chroma 4:2:0: sub=2, slice has S/sub plane rows).  pack: 'naive' = Mallat per slice;
    'comp' = each coefficient in the first packet after it becomes computable."""
    Sp = S // sub; co = analysis(N, levels); pix = synthesis(N, levels, co)
    def m(t):
        b, i = t; return co[-1][i][1] if b == 'L' else co[int(b[1:])][i][1]
    def pk(t):
        b, i = t
        if pack == 'comp': return m(t) // Sp
        l = len(levels) if b == 'L' else int(b[1:]) + 1
        return (i << l) // Sp
    # packet k ready when every coefficient in it is computable: time (in plane rows)
    ready = {}
    for l, H in enumerate(co[:-1]):
        for i, _ in enumerate(H):
            t = ('H%d' % l, i); k = pk(t); ready[k] = max(ready.get(k, 0), m(t) + 1, (k + 1) * Sp)
    for i, _ in enumerate(co[-1]):
        t = ('L', i); k = pk(t); ready[k] = max(ready.get(k, 0), m(t) + 1, (k + 1) * Sp)
    worst = 0
    for r in range(96 // sub, N - 96 // sub):
        K = max(pk(t) for t in pix[r])
        arr = max(ready[k] for k in range(K + 1) if k in ready) * sub + S   # luma lines; + S pacing
        cap = r * sub + sub   # luma line time when plane row r is complete
        worst = max(worst, arr - cap + sub)  # latency from capture of the row's first luma line
    return worst
cases = {
 'today per-slice (mirror), 2V': None,
 '5/3 symmetric, 2V': [dict(P=P53, U=sym)] * 2,
 '5/3 symmetric, 3V': [dict(P=P53, U=sym)] * 3,
 'one-sided acyclic (3,2), 2V': [dict(P=P53, U=lag(3)), dict(P=P53, U=lag(2))],
 'one-sided acyclic (5,3,2), 3V': [dict(P=P53, U=lag(5)), dict(P=P53, U=lag(3)), dict(P=P53, U=lag(2))],
 'predict-only (2,0), 2V': [dict(P=P53, U=[])] * 2,
}
fmt = [('720p50', 8, 20.0/720), ('720p60', 8, 16.6667/720), ('1080p50', 16, 20.0/1080), ('1080p60', 16, 16.6667/1080), ('2160p50', 16, 20.0/2160)]
for name, lv in cases.items():
    for pack in ('naive', 'comp'):
        if lv is None and pack == 'comp': continue
        row = []
        for f, S, lt in fmt:
            if lv is None:
                Ly = Lc = 2 * S
            else:
                Ly = lat(lv, S, 1, pack=pack); Lc = lat(lv, S, 2, pack=pack)
            row.append(f"{f}: Y {Ly+2:2d} / 4:2:0 C {Lc+2:2d} lines = {(max(Ly,Lc)+2)*lt:.3f} ms")
        print(f"{name:32s} [{pack:5s}] " + " | ".join(row))
