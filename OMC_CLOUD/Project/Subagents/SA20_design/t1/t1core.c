/* T1 core (DESIGN §H): causal single-level scan, the same process at every sample.
   pred  = MED(L, U, UL) (x<->y symmetric; JPEG-LS median edge detector) + P (motion-free reference, 0 for intra)
   leaf  q = sign(r) floor(|r|/s + rho), r = x - (P + pred); final = clip(P + pred + q s, lo, hi)  (never-away per sample)
   ctx   class of log2(1 + |qL| + |qU| + (|qUL| + |qUR|)/2 + a), a = (|L-UL| + |U-UL| + |U-UR|) / s  (causal finals)
   Border samples read replicated finals (outside = nearest inside final; row 0 predicts from L, column 0 from U). */
#include <math.h>
#include <stdlib.h>
static inline int med(int L, int U, int C) {
    int mx = L > U ? L : U, mn = L < U ? L : U;
    if (C >= mx) return mn; if (C <= mn) return mx; return L + U - C;
}
void t1_code(const int *x, const int *P, int h, int w, double s, double rho, int lo, int hi,
             int *out, int *q, int *cls, int ncls) {
    for (int i = 0; i < h; i++) for (int j = 0; j < w; j++) {
        int k = i * w + j, pr, L, U, C, R, qL, qU, qC, qR;
        if (i == 0 && j == 0) { L = U = C = R = (lo + hi + 1) / 2; qL = qU = qC = qR = 0; }
        else if (i == 0) { L = U = C = R = out[k - 1]; qL = qU = qC = qR = abs(q[k - 1]); }
        else {
            U = out[k - w]; C = j ? out[k - w - 1] : U; R = j < w - 1 ? out[k - w + 1] : U; L = j ? out[k - 1] : U;
            qU = abs(q[k - w]); qC = j ? abs(q[k - w - 1]) : qU; qR = j < w - 1 ? abs(q[k - w + 1]) : qU; qL = j ? abs(q[k - 1]) : qU;
        }
        int base = P ? P[k] : 0;
        /* prediction works on the difference from the reference when P is given (temporal-spatial planar) */
        if (P) { int PL = (i || j) ? (j ? P[k - 1] : P[k - w]) : P[k], PU = i ? P[k - w] : (j ? P[k - 1] : P[k]);
                 int PC = (i && j) ? P[k - w - 1] : (i ? P[k - w] : (j ? P[k - 1] : P[k]));
                 pr = base + med(L - PL, U - PU, C - PC); }
        else pr = med(L, U, C);
        double a = (abs(L - C) + abs(U - C) + abs(U - R)) / s;
        double v = 1.0 + qL + qU + 0.5 * (qC + qR) + a;
        int c = (int)floor(log2(v) * 2.0); if (c > ncls - 1) c = ncls - 1; cls[k] = c;
        int r = x[k] - pr; int m = (int)floor(fabs((double)r) / s + rho); int qq = r < 0 ? -m : m;
        int y = pr + (int)lround(qq * s); if (y < lo) y = lo; if (y > hi) y = hi;
        q[k] = qq; out[k] = y;
    }
}
