import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    from vdelay import analysis, synthesis, P53, P97, sym, lag
def foot(levels, S, N=512):
    co = analysis(N, levels); pix = synthesis(N, levels, co)
    def pk(t):
        b, i = t; l = len(levels) if b == 'L' else int(b[1:]) + 1
        return (i << l) // S
    k = N // S // 2
    rows = [r for r in range(N) if any(pk(t) == k for t in pix[r])]
    return min(rows) - k * S, max(rows) - (k * S + S - 1)
for S in (8, 16):
    for name, lv in [('5/3 sym 2V', [dict(P=P53, U=sym)] * 2), ('5/3 sym 3V', [dict(P=P53, U=sym)] * 3),
                     ('one-sided (3,2) 2V', [dict(P=P53, U=lag(3)), dict(P=P53, U=lag(2))])]:
        a, b = foot(lv, S); print(f"S={S:2d} {name:20s}: lost packet damages rows {a:+d} above the slice top to {b:+d} below the slice bottom (plane rows)")
