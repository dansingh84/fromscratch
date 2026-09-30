# 2-D clamp-dependency DAG check for the OMC stage order (continuous vertical transform):
# synthesis H5,H4,H3 (rows R/4), H2 (R/2 x C/2), V2 (R/2 x C/2), H1 (R x C), V1 (R x C).
import sys
def join(grid, axis, nr, nc, P, U):
    # grid[r][c] = (lin, dep_other)  dep excludes own lineage; full = dep | 1<<lin
    full = lambda t: t[1] | (1 << t[0])
    lines = range(nr) if axis == 'h' else range(nc)
    n = nc if axis == 'h' else nr
    m = n // 2
    for ln in lines:
        get = (lambda k: grid[ln][k]) if axis == 'h' else (lambda k: grid[k][ln])
        L = [get(k) for k in range(m)]; H = [get(m + k) for k in range(m)]
        E = []
        for i in range(m):
            lin, dep = L[i]
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
        X = [None] * n; X[0::2] = E; X[1::2] = O
        for k in range(n):
            if axis == 'h': grid[ln][k] = X[k]
            else: grid[k][ln] = X[k]
def check(R, C, st):
    grid = [[(r * C + c, 0) for c in range(C)] for r in range(R)]
    order = [('h', R//4, C//8, 'H5'), ('h', R//4, C//4, 'H4'), ('h', R//4, C//2, 'H3')]
    # note: H3..H5 region widths: H3 splits C/4 cols -> join over C/4; follow dwt.c exactly
    order = [('h', R//4, C//16, 'H5'), ('h', R//4, C//8, 'H4'), ('h', R//4, C//4, 'H3'),
             ('h', R//2, C//2, 'H2'), ('v', R//2, C//2, 'V2'), ('h', R, C, 'H1'), ('v', R, C, 'V1')]
    for ax, nr, nc, name in order:
        P, U = st[name]; join(grid, ax, nr, nc, P, U)
    n = R * C; adj = [[] for _ in range(n)]; selfl = 0
    for row in grid:
        for lin, dep in row:
            if dep >> lin & 1: selfl += 1
            d = dep & ~(1 << lin)
            while d:
                b = d & -d; adj[b.bit_length() - 1].append(lin); d ^= b
    indeg = [0] * n
    for u in range(n):
        for v in adj[u]: indeg[v] += 1
    q = [u for u in range(n) if indeg[u] == 0]; seen = 0
    while q:
        u = q.pop(); seen += 1
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0: q.append(v)
    return seen < n, selfl
P53 = [0, 1]; P97 = [-1, 0, 1, 2]
def cfg(v1, v2, h1, h2, h3, h4, h5, p97=True):
    return {'V1': (P53, v1), 'V2': (P53, v2), 'H1': (P97 if p97 else P53, h1), 'H2': (P97 if p97 else P53, h2),
            'H3': (P53, h3), 'H4': (P53, h4), 'H5': (P53, h5)}
R, C = 32, 128
po = []
lag = lambda a: [-a, -a - 1]
tests = {
 'predict-only everywhere': cfg(po, po, po, po, po, po, po),
 'today symmetric updates (5/3 V, 9/7-M H1-2, 5/3 H3-5)': cfg([-1,0],[-1,0],[-1,0],[-1,0],[-1,0],[-1,0],[-1,0]),
 'V one-sided lag (3,2), H predict-only': cfg(lag(3), lag(2), po, po, po, po, po),
 'V one-sided lag (2,2), H predict-only': cfg(lag(2), lag(2), po, po, po, po, po),
 'V one-sided (3,2), H symmetric kept': cfg(lag(3), lag(2), [-1,0],[-1,0],[-1,0],[-1,0],[-1,0]),
 'V (3,2), H one-sided lags (20,20,5,3,2)': cfg(lag(3), lag(2), lag(20), lag(20), lag(5), lag(3), lag(2)),
 'V (3,2), H one-sided lags (2,2,2,2,2)': cfg(lag(3), lag(2), lag(2), lag(2), lag(2), lag(2), lag(2)),
}
for k, v in tests.items():
    cyc, sl = check(R, C, v); print(f"{k:60s} cycle={cyc} self-loops={sl}"); sys.stdout.flush()
