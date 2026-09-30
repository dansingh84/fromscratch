# Exhibit a concrete cycle: 1-D, 2 levels (the two vertical levels), 5/3 predict, one-sided update H[i-2],H[i-3]
from dag1d import synth_1d
N = 64; lv = [dict(P=[0, 1], U=[-2, -3])] * 2
pix, nc = synth_1d(N, lv)
# names: coarsest L ids 0..15 (L2[i]), then H level2 ids 16..31 (H2[i]), then H level1 32..63 (H1[i])
def name(c):
    return f"L2[{c}]" if c < 16 else (f"H2[{c-16}]" if c < 32 else f"H1[{c-32}]")
fin = {lin: r for r, (lin, dep) in enumerate(pix)}
adj = {}
for r, (lin, dep) in enumerate(pix):
    d = dep & ~(1 << lin)
    while d:
        b = d & -d; adj.setdefault(b.bit_length() - 1, []).append(lin); d ^= b
# DFS for a cycle
import sys; sys.setrecursionlimit(10000)
color = {}; stack = []
def dfs(u):
    color[u] = 1; stack.append(u)
    for v in adj.get(u, []):
        if color.get(v) == 1:
            cyc = stack[stack.index(v):] + [v]; return cyc
        if v not in color:
            c = dfs(v)
            if c: return c
    color[u] = 2; stack.pop(); return None
for s in range(20, nc):
    if s not in color:
        c = dfs(s)
        if c:
            print("cycle (edge a->b: a must be final before b's clamp is decided; b finalises pixel row fin[b]):")
            print("  " + " -> ".join(f"{name(x)}(row {fin[x]})" for x in c)); break
