# Clamp-dependency DAG check for interval-clamped lifting synthesis (expert A mechanism
# generalised to an update step).  Structural dependencies (integer rounding => no exact
# cancellation).  Each pixel p has a unique "finaliser" coefficient F(p) (the in-place
# lineage).  A per-coefficient clamp that makes p legal needs every OTHER coefficient that
# reaches p to be final before F(p) is decided: edge c -> F(p).  A cycle = no valid order.
import sys, itertools

def synth_1d(N, levels):
    """levels: list (finest first) of dicts {P:[offs], U:[offs]} offsets relative to i
       (P offsets index evens E[i+o]; U offsets index H[i+o]).  Returns per-pixel (lineage, depset)."""
    # coefficient ids: build Mallat layout sizes
    sizes = []; n = N
    for _ in levels: sizes.append(n // 2); n //= 2
    cid = itertools.count()
    # coarsest low band
    X = [(c, 1 << c) for c in (next(cid) for _ in range(n))]
    Hs = []
    for l in range(len(levels) - 1, -1, -1):
        Hs.append([(c, 1 << c) for c in (next(cid) for _ in range(sizes[l]))])
    Hs = Hs[::-1]  # Hs[l] = level l (finest=0)
    for l in range(len(levels) - 1, -1, -1):
        H = Hs[l]; m = len(H); P = levels[l]['P']; U = levels[l]['U']
        E = []
        for i in range(m):
            lin, dep = X[i]
            for o in U:
                j = i + o
                if 0 <= j < m: dep |= H[j][1]
            E.append((lin, dep))
        O = []
        for i in range(m):
            lin, dep = H[i]
            for o in P:
                j = i + o
                j = min(max(j, 0), m - 1)  # replicate at ends (structure only)
                dep |= E[j][1]
            O.append((lin, dep))
        X = [None] * (2 * m)
        X[0::2] = E; X[1::2] = O
    return X, next(cid)

def has_cycle(pix, ncoef):
    adj = [[] for _ in range(ncoef)]; selfdep = 0
    for lin, dep in pix:
        others = dep & ~(1 << lin)
        # lineage reached twice?  (self-dependency) : detect via a second path is structural;
        # we cannot see multiplicity with bitsets, handled separately below.
        c = others
        while c:
            b = c & -c; k = b.bit_length() - 1; adj[k].append(lin); c ^= b
    # Kahn
    indeg = [0] * ncoef
    for u in range(ncoef):
        for v in adj[u]: indeg[v] += 1
    q = [u for u in range(ncoef) if indeg[u] == 0]; seen = 0
    while q:
        u = q.pop(); seen += 1
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0: q.append(v)
    return seen < ncoef

def selfloop(N, levels):
    # does F(p) reach p via a second path (through a neighbour)?  track dep excluding own lineage
    # by re-running with lineage bit removed from the in-place value and checking if it comes back.
    sizes = []; n = N
    for _ in levels: sizes.append(n // 2); n //= 2
    cid = itertools.count()
    X = [(c, 0) for c in (next(cid) for _ in range(n))]  # dep = OTHER coefs reaching (excl. own lineage)
    full = lambda t: t[1] | (1 << t[0])
    Hs = []
    for l in range(len(levels) - 1, -1, -1):
        Hs.append([(c, 0) for c in (next(cid) for _ in range(sizes[l]))])
    Hs = Hs[::-1]; bad = 0
    for l in range(len(levels) - 1, -1, -1):
        H = Hs[l]; m = len(H); P = levels[l]['P']; U = levels[l]['U']
        E = []
        for i in range(m):
            lin, dep = X[i]
            for o in U:
                j = i + o
                if 0 <= j < m: dep |= full(H[j])
            E.append((lin, dep))
        O = []
        for i in range(m):
            lin, dep = H[i]
            for o in P:
                j = min(max(i + o, 0), m - 1); dep |= full(E[j])
            O.append((lin, dep))
        X = [None] * (2 * m); X[0::2] = E; X[1::2] = O
    for lin, dep in X:
        if dep >> lin & 1: bad += 1
    return bad

if __name__ == '__main__':
    N = 256
    P53 = [0, 1]; P97 = [-1, 0, 1, 2]
    def run(name, levels):
        pix, nc = synth_1d(N, levels)
        cyc = has_cycle(pix, nc); sl = selfloop(N, levels)
        print(f"{name:55s} cycle={cyc}  self-loops={sl}")
    run("predict-only 5 levels (2,0)", [dict(P=P53, U=[])] * 5)
    run("5/3 symmetric 1 level", [dict(P=P53, U=[-1, 0])])
    for L in (1, 2, 3, 4, 5):
        for a in (2, 3, 4, 5, 6, 8, 12, 16, 24, 32):
            lv = [dict(P=P53, U=[-a, -a - 1])] * L
            pix, nc = synth_1d(N, lv)
            if not has_cycle(pix, nc) and selfloop(N, lv) == 0:
                print(f"5/3-predict, one-sided update U=H[i-{a}],H[i-{a+1}] at every level: {L} levels -> first acyclic lag a={a}")
                break
        else:
            print(f"{L} levels: no acyclic lag <= 32")
    # 9/7-M predict (4-tap) at the finest level(s)
    for a in (2, 3, 4, 5, 6, 8, 12, 16, 24, 32):
        lv = [dict(P=P97, U=[-a, -a - 1])] * 2 + [dict(P=P53, U=[-a, -a - 1])] * 3
        pix, nc = synth_1d(N, lv)
        if not has_cycle(pix, nc) and selfloop(N, lv) == 0:
            print(f"horizontal 5 levels (9/7-M predict at H1,H2): first acyclic uniform lag a={a}"); break
    else: print("9/7 5 levels: none <= 32")
    # per-level lag: update only at level 1 (finest), predict-only elsewhere
    for a in (2, 3, 4, 5, 6, 8, 12, 16, 24, 32):
        lv = [dict(P=P53, U=[-a, -a - 1])] + [dict(P=P53, U=[])] * 4
        pix, nc = synth_1d(N, lv)
        if not has_cycle(pix, nc) and selfloop(N, lv) == 0:
            print(f"update at finest level only, 5 levels: acyclic lag a={a}"); break
    for a in (2, 3, 4, 5, 6, 8, 12, 16, 24, 32):
        lv = [dict(P=P53, U=[])] * 4 + [dict(P=P53, U=[-a, -a - 1])]
        pix, nc = synth_1d(N, lv)
        if not has_cycle(pix, nc) and selfloop(N, lv) == 0:
            print(f"update at coarsest level only, 5 levels: acyclic lag a={a}"); break
