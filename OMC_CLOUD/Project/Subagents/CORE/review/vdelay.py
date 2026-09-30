# Inherent vertical delay of a continuous (frame-long) line-based lifting transform.
# Analysis: m(c) = last source row coefficient c needs.  Synthesis: deps(r) = coefficients pixel row r needs.
# D = max_r max_{c in deps(r)} m(c) - r   (lines of lookahead the codec adds, encoder+decoder combined,
# with optimal packetisation);  also naive Mallat-per-slice packetisation extra slice periods.
import itertools
def analysis(N, levels):
    # track for every value the max source row (and min) it depends on
    X = [(r, r) for r in range(N)]  # (min,max) source rows
    coefs = []  # (level, index, (min,max))
    for lv in levels:
        P, U = lv['P'], lv['U']; m = len(X) // 2
        E = X[0::2]; O = X[1::2]
        H = []
        for i in range(m):
            lo, hi = O[i]
            for o in P:
                j = min(max(i + o, 0), m - 1); lo = min(lo, E[j][0]); hi = max(hi, E[j][1])
            H.append((lo, hi))
        L = []
        for i in range(m):
            lo, hi = E[i]
            for o in U:
                j = i + o
                if 0 <= j < m: lo = min(lo, H[j][0]); hi = max(hi, H[j][1])
            L.append((lo, hi))
        coefs.append(H); X = L
    coefs.append(X)
    return coefs  # coefs[l] for H at level l (0=finest), coefs[-1] = coarsest L
def synthesis(N, levels, coefs):
    nl = len(levels)
    # value = set of (band, index) as frozenset of ids; do structural with python sets of tuples (small N)
    X = [frozenset([('L', i)]) for i in range(len(coefs[-1]))]
    for l in range(nl - 1, -1, -1):
        P, U = levels[l]['P'], levels[l]['U']; m = len(X)
        H = [frozenset([('H%d' % l, i)]) for i in range(m)]
        E = []
        for i in range(m):
            s = set(X[i])
            for o in U:
                j = i + o
                if 0 <= j < m: s |= H[j]
            E.append(frozenset(s))
        O = []
        for i in range(m):
            s = set(H[i])
            for o in P:
                j = min(max(i + o, 0), m - 1); s |= E[j]
            O.append(frozenset(s))
        X = [None] * (2 * m); X[0::2] = E; X[1::2] = O
    return X
def delay(levels, N=256, S=8):
    co = analysis(N, levels); pix = synthesis(N, levels, co)
    def mrow(t):
        b, i = t
        return co[-1][i][1] if b == 'L' else co[int(b[1:])][i][1]
    def slice_of(t):
        b, i = t; l = len(levels) if b == 'L' else int(b[1:]) + 1
        return (i << l) // S
    lo, hi = 64, N - 64   # interior rows only (frame edges excluded)
    D = max(max(mrow(t) for t in pix[r]) - r for r in range(lo, hi))
    # naive Mallat packetisation: encoder lookahead Le and decoder packet reach
    Le = 0
    for l, H in enumerate(co[:-1]):
        for i, (a, b) in enumerate(H):
            if lo <= (i << (l + 1)) < hi:
                k = (i << (l + 1)) // S; Le = max(Le, b - ((k + 1) * S - 1))
    for i, (a, b) in enumerate(co[-1]):
        if lo <= (i << len(levels)) < hi:
            k = (i << len(levels)) // S; Le = max(Le, b - ((k + 1) * S - 1))
    Kx = max(max(slice_of(t) for t in pix[r]) - r // S for r in range(lo, hi))
    lat_naive = max(((r // S) + max(slice_of(t) for t in pix[r]) - r // S + 1) * S + Le + S - r for r in range(lo, hi))
    return D, Le, Kx, lat_naive
P53 = [0, 1]; P97 = [-1, 0, 1, 2]
sym = [-1, 0]
def lag(a): return [-a, -a - 1]
cases = {
 '5/3 symmetric, 2V': [dict(P=P53, U=sym)] * 2,
 '5/3 symmetric, 3V': [dict(P=P53, U=sym)] * 3,
 'one-sided acyclic (3,2), 2V': [dict(P=P53, U=lag(3)), dict(P=P53, U=lag(2))],
 'one-sided acyclic (5,3,2), 3V': [dict(P=P53, U=lag(5)), dict(P=P53, U=lag(3)), dict(P=P53, U=lag(2))],
 'predict-only (2,0), 2V': [dict(P=P53, U=[])] * 2,
 'predict-only (4,0), 2V': [dict(P=P97, U=[])] * 2,
 '9/7-M (4-tap P + sym U), 2V': [dict(P=P97, U=sym)] * 2,
}
for S in (8, 16):
    print(f"slice_h = {S}")
    for k, lv in cases.items():
        D, Le, Kx, ln = delay(lv, S=S)
        print(f"  {k:34s} inherent D = {D:2d} lines | naive per-slice packets: enc lookahead {Le:2d} lines, decoder reaches +{Kx} slices, worst latency {ln} lines (today 2S = {2*S})")
