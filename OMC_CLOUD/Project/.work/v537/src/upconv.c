/* OMC-UC — normative 2x resolution upconversion and its exact inverse.
 *
 * See include/omc_uc.h for the structure and the reversibility argument.
 *
 * Provenance (C1):
 *   - Lifting factorisation of a wavelet/interpolation pair: Sweldens, "The
 *     lifting scheme", Appl. Comput. Harmon. Anal. 1996; integer-to-integer
 *     mapping per Calderbank/Daubechies/Sweldens/Yeo 1998.  Same family and
 *     the same vintage class as the codec's existing (9,7)-M transform, whose
 *     predict step is the (4,2) member of the identical interpolating family.
 *   - Half-band interpolating kernel: windowed-sinc (Kaiser window, Kaiser
 *     1966; sinc interpolation is classical).  Coefficients derived here, not
 *     taken from any codec: explicitly NOT the AVC 6-tap or the HEVC 8-tap
 *     luma interpolators (C1 forbids AVC/HEVC internals), and not JPEG XS's.
 *   - Edge-directed interpolation by directional line matching: Doyle (1990)
 *     edge-line averaging and the pre-1995 deinterlacing literature; the
 *     modulus/orientation view is Jensen & Anastassiou, IEEE TIP 1995.  >30 and
 *     >25 years respectively; expired vintage.  The specific gate set (SAD
 *     ratio + match-quality-versus-roughness + 3-tap median) is own work.
 *   - Overshoot limiting against the local sample envelope: monotonicity-
 *     preserving interpolation, folk practice predating digital video.
 *
 * Per-pixel datapath: adds, shifts, compares, table lookups.  Every constant
 * multiply is written as its shift-add decomposition, exactly as the codec
 * writes the (9,7)-M 9x as (x<<3)+x.  No multipliers, no dividers, no adaptive
 * state, no data-dependent iteration.
 */
#include <stdlib.h>
#include <string.h>

#include "omc1.h"
#include "omc_uc.h"

/* SHIFTS ON SIGNED VALUES.  A left shift of a negative value is not
 * defined by C11 (6.5.7p4); these shift-and-add multiplies routinely see
 * negative operands.  Shifting the unsigned representation is defined for
 * every value and compiles to the same instruction on a two's-complement
 * target, so the fixed-point results are unchanged (verified byte-exact
 * against the previous build).  Found by UBSan. */
#define OMC_SHL(v, n) ((int32_t)((uint32_t)(v) << (n)))

/* ------------------------------------------------------------------ kernel
 * 12-tap Kaiser(beta=6.0) windowed-sinc half-band interpolator, /1024.
 * Selected by measurement over 2/4/6/8/10/12/16-tap Lagrange, Deslauriers-
 * Dubuc, Lanczos and Kaiser candidates (see the selection table in the
 * delivery document): flattest passband that still fits the 8-source-row
 * dependency budget, with image rejection <= -55 dB.
 */
static const int32_t UC_C[OMC_UC_KTAPS] = {
    -1, 8, -27, 72, -177, 637, 637, -177, 72, -27, 8, -1
};

/* Multiplier-free evaluation of the symmetric 12-tap kernel.
 *   x[0..11] are the taps at offsets -5 .. +6 around the interpolated point.
 *   9 adds for the coefficients + 5 accumulate adds + 6 symmetry folds. */
static inline int32_t uc_tap12(const int32_t *x)
{
    int32_t s0 = x[0] + x[11];        /*    -1 */
    int32_t s1 = x[1] + x[10];        /*     8 = <<3                        */
    int32_t s2 = x[2] + x[9];         /*   -27 = -(<<5) + (<<2) + 1         */
    int32_t s3 = x[3] + x[8];         /*    72 = (<<6) + (<<3)              */
    int32_t s4 = x[4] + x[7];         /*  -177 = -((<<7)+(<<5)+(<<4)+1)     */
    int32_t s5 = x[5] + x[6];         /*   637 = (<<9)+(<<7)-(<<2)+1        */
    int32_t acc = -s0;
    acc += OMC_SHL(s1, 3);
    acc -= OMC_SHL(s2, 5) - OMC_SHL(s2, 2) - s2;
    acc += OMC_SHL(s3, 6) + OMC_SHL(s3, 3);
    acc -= OMC_SHL(s4, 7) + OMC_SHL(s4, 5) + OMC_SHL(s4, 4) + s4;
    acc += OMC_SHL(s5, 9) + OMC_SHL(s5, 7) - OMC_SHL(s5, 2) + s5;
    return (acc + (1 << (OMC_UC_KSHIFT - 1))) >> OMC_UC_KSHIFT;
}

/* Self-check for the shift-add decomposition above: returns 0 if the
 * multiplier-free form reproduces the tabulated kernel exactly over the whole
 * datapath range.  Called by tests/test_uc.c -- the C3 claim is that UC_C is
 * documentation and uc_tap12() is the implementation, so they must agree. */
int omc_uc_selfcheck_kernel(void)
{
    int t, v;
    int32_t x[OMC_UC_KTAPS];
    for (t = 0; t < OMC_UC_KTAPS; t++) {
        for (v = -4096; v <= 4095; v++) {
            int u2, bad;
            int64_t acc = 0;
            for (u2 = 0; u2 < OMC_UC_KTAPS; u2++) x[u2] = 0;
            x[t] = v;
            for (u2 = 0; u2 < OMC_UC_KTAPS; u2++) acc += (int64_t)UC_C[u2] * x[u2];
            bad = (int32_t)((acc + 512) >> 10) != uc_tap12(x);
            if (bad) return -1;
        }
    }
    /* and one full-amplitude combined case */
    for (t = 0; t < OMC_UC_KTAPS; t++) x[t] = (t & 1) ? 4095 : -4096;
    {
        int64_t acc = 0;
        int u2;
        for (u2 = 0; u2 < OMC_UC_KTAPS; u2++) acc += (int64_t)UC_C[u2] * x[u2];
        if ((int32_t)((acc + 512) >> 10) != uc_tap12(x)) return -1;
    }
    return 0;
}

/* whole-sample symmetric extension (identical convention to src/dwt.c) */
static inline int uc_mir(int i, int n)
{
    int p;
    if ((unsigned)i < (unsigned)n) return i;   /* interior: no arithmetic at all */
    if (n <= 1) return 0;
    p = 2 * n - 2;
    if (i < 0) i = -i;
    if (i < p) return i >= n ? p - i : i;      /* one fold: a compare and a subtract */
    i %= p;                                    /* only for |i| >= 2n-2, unreachable
                                                * from any predictor: the widest reach
                                                * is KTAPS/2 + max|d|/2 + max|k| taps,
                                                * far inside one period of the mirror */
    return i >= n ? p - i : i;
}

/* ------------------------------------------------- direction search tables
 * Candidates are in HALF-sample units of the axis orthogonal to the pass:
 * candidate d means the structure crosses the sample above the interpolated
 * point d/2 samples one way and the sample below d/2 samples the other, i.e.
 * a slope of d samples per sample-step.  Search order is normative (ties
 * resolve to the first, smallest-|d| candidate).
 */
static const int8_t UC_CAND_V[OMC_UC_NCAND] = {0, 1, -1, 2, -2, 3, -3, 4, -4, 6, -6, 8, -8};
static const int8_t UC_CAND_H[11] = {0, 1, -1, 2, -2, 3, -3, 4, -4, 6, -6};
/* SAD tap offsets, in whole samples along the pass axis */
static const int8_t UC_SAD_V[5] = {-6, -3, 0, 3, 6};
/* The horizontal pass's SAD taps are offsets along the IMAGE ROW axis, so their
 * span is charged directly to the vertical dependency reach and therefore to
 * the latency budget.  {-2, 0, +2} keeps the analytic worst-case reach at 8
 * source rows == slice_h; {-3, 0, +3} pushes it to 9 and would cost a second
 * slice period at 720p/1080p.  See omc_uc_analytic_reach() and the reach gate
 * in tests/test_uc.c, which enforce this from the constants themselves. */
static const int8_t UC_SAD_H[3] = {-2, 0, 2};

#define UC_MARGIN 4   /* directional SAD must beat straight by this factor    */
#define UC_ABS 6      /* ... and beat the local roughness by this factor      */
/* Minimum EVIDENCE for the direction path to engage at all.
 *
 * Both acceptance gates are MULTIPLICATIVE -- `cbest * UC_MARGIN <= cost0` and
 * `cbest * UC_ABS <= rough` -- so a candidate whose SAD is exactly zero passes
 * BOTH of them for any threshold, however strict.  Raising UC_ABS to 512 was
 * measured and changed nothing at all: 0 * 512 <= rough is still true.
 *
 * Zero and near-zero SADs are common on low-bandwidth planes, which is why this
 * showed up first as 4:2:2 chroma crawl (0.58% excess low-motion temporal
 * energy against luma's 0.03%, while the same content at 4:4:4 showed 0.02%).
 * The direction map then flickers frame to frame on whatever noise breaks the
 * tie, and a flickering map is crawl.
 *
 * The fix is an ABSOLUTE floor on the straight prediction's own cost: if the
 * separable estimate already matches to within about one code value per SAD
 * tap, there is no staircase to straighten and a correction can only add
 * noise.  This is the converse of the lesson the gate set already encodes --
 * a relative threshold cannot tell "matched perfectly" from "nothing here",
 * exactly as an absolute one cannot tell "quiet" from "correct".
 *
 * The floor is a single constant rather than a per-pass one so the independent
 * Python model's `dact` -- which already carried exactly this gate, unused,
 * with the C never implementing it -- expresses the same rule with one number.
 * xcheck.py sets dact to match; the two implementations agree bit for bit. */
#define UC_EVID(depth) (4 << ((depth) - 8))
/* Cross-line monotonicity.  The structure must CROSS the interpolated line
 * once (an edge: the swing over four lines equals the sum of the steps) rather
 * than oscillate across it (a near-Nyquist grating: the steps cancel).  Acting
 * on the second case is what makes edge-directed scalers lay cross-hatch
 * "worms" over fine periodic detail -- fabric, crowds, foliage.  Measured on a
 * 0.45 cycle/sample zone plate: without this gate the above-Nyquist energy is
 * -33.4 dB and the patterning is visible at 3x magnification; with it, -37.5 dB
 * against -38.7 dB for the separable spine alone, and the patterning is gone.
 * Cost, measured: staircase 0.2904 -> 0.2947 output pixels on aliased edges. */
#define UC_MONO_TOL(depth) (1 << ((depth) - 8))
#define UC_OVER 2     /* overshoot allowance = (|A-B| >> UC_OVER) + UC_FLOOR   */
/* Absolute floor on the allowance, 4 code values at 10-bit / 16 at 12-bit.
 * Without it the envelope collapses to zero wherever the two bounding samples
 * are equal, which suppresses legitimate sub-sample peaks near Nyquist as well
 * as ringing (measured: MTF at 0.7*Nyquist 0.931 -> 0.934, reconstruction PSNR
 * +0.06 dB).
 *
 * The floor is itself CAPPED BY THE LOCAL STEP, i.e. min(FLOOR, |A-B|).  A flat
 * region has |A-B| = 0 and therefore no allowance at all, so no ringing can
 * enter it; a region with signal gets the full floor.  Without the cap the
 * predictor was free to ring +/-4 codes inside perfectly flat areas -- found on
 * real footage as a visible oscillation in a letterbox/pillarbox bar, which is
 * also a sub-black level violation.  Near Nyquist |A-B| is large, so the cap
 * costs nothing there and the MTF benefit is retained. */
#define UC_FLOOR(depth) (1 << ((depth) - 8))

/* Coherence filter width over the accepted direction map, in positions.
 *
 * A median of width W suppresses accepted runs of length <= (W-1)/2 and passes
 * everything longer.  The original width was 3, which removes lone flips only.
 * Measured on the zone-plate instrument at 0.45 cycles/sample, W = 3 leaves 156
 * samples whose value lands on the OPPOSITE side of the local mean from BOTH
 * the separable spine and lanczos4 -- isolated polarity inversions, the
 * `G3 pixelation` class -- and those samples form 111 clusters of length <= 2,
 * exactly the size a 3-tap median cannot reach.  The two LINEAR references
 * bound each other at 200 code values over the same picture and never exceed
 * it, so any larger excursion is attributable to this stage by construction.
 *
 * W = 5 removes runs of <= 2.  Cost is a 5-element selection network instead of
 * a 3-element one; a genuine oriented edge is coherent over far more than two
 * positions, which is the premise the median already rested on at W = 3.
 * harness/uc_verify.py gate G3f pins the result. */
#define UC_COHERE 5

/* Median of the UC_COHERE accepted directions centred on j (whole-sample
 * symmetric extension, as everywhere else).  Fixed bounds, no division, no
 * data-dependent iteration. */
static inline int uc_median_dir(const int8_t *d, int j, int n)
{
    int v[UC_COHERE], i, k;
    for (i = 0; i < UC_COHERE; i++)
        v[i] = d[uc_mir(j + i - UC_COHERE / 2, n)];
    for (i = 1; i < UC_COHERE; i++) {
        int t = v[i];
        for (k = i; k > 0 && v[k - 1] > t; k--) v[k] = v[k - 1];
        v[k] = t;
    }
    return v[UC_COHERE / 2];
}

typedef struct {
    const int8_t *cand;
    int ncand;
    const int8_t *sad;
    int nsad;
} uc_pass_t;

static const uc_pass_t UC_PASS_V = {UC_CAND_V, OMC_UC_NCAND, UC_SAD_V, 5};
static const uc_pass_t UC_PASS_H = {UC_CAND_H, 11, UC_SAD_H, 3};

/* Worst-case vertical dependency reach, in SOURCE rows, computed from the
 * normative constants alone -- not from a measurement, because the direction
 * search only touches its extreme taps on content that makes an extreme
 * candidate win, and a benign test picture will under-report it.
 *
 *   output row R      <- intermediate rows R .. R+E
 *                        E = max|d|/2 + max|k| (+1 if max|d| is odd, for the
 *                        half-sample lattice)          [H-pass direction search]
 *   intermediate row t <- source row t/2                        (t even)
 *                      <- source rows (t-1)/2 - 5 .. (t-1)/2 + KTAPS/2  (t odd)
 *
 * The binding case is R odd (an interpolated output row) reaching an odd
 * intermediate row, which is itself vertically predicted.
 *
 * The latency contract is: reach <= slice_h.  Then the upconverted output of
 * slice k depends on nothing later than slice k+1, i.e. exactly one slice
 * period.  slice_h is 8 at 720p and 1080p, so 8 is the budget. */
int omc_uc_analytic_reach_n(int levels)
{
    /* Cascading two 2x levels does NOT keep the reach at one level's value.
     * A 4x output row R sits on 2x row R/2, which needs 2x rows up to
     * (R/2) + reach1; that 2x row needs source rows up to
     * ((R/2 + reach1) >> 1) + reach1 = R/4 + reach1/2 + reach1.
     * With reach1 = 8 that is 12 source rows, so 4x costs TWO slice periods at
     * slice_h = 8 and one at slice_h = 16.  Measured confirmation and the
     * per-format latency consequence are in tests/test_uc.c and
     * harness/uc_verify.py. */
    int r = omc_uc_analytic_reach(), i;
    for (i = 1; i < levels; i++) r = (r >> 1) + omc_uc_analytic_reach();
    return r;
}

int omc_uc_analytic_reach(void)
{
    int dmax = 0, kmax = 0, worst = 0, i, R, t;
    for (i = 0; i < 11; i++) if (UC_CAND_H[i] > dmax) dmax = UC_CAND_H[i];
    for (i = 0; i < 3; i++) if (UC_SAD_H[i] > kmax) kmax = UC_SAD_H[i];
    {
        int E = dmax / 2 + kmax + (dmax & 1 ? 1 : 0);
        for (R = 0; R <= 1; R++) {
            int own = (R & 1) ? (R - 1) / 2 : R / 2;
            for (t = 0; t <= E; t++) {
                int tt = R + t;
                int src = (tt & 1) ? (tt - 1) / 2 + OMC_UC_KTAPS / 2 : tt / 2;
                if (src - own > worst) worst = src - own;
            }
        }
    }
    return worst;
}

/* ---------------------------------------------------------------- the core
 * One predicted line.  `a` and `b` are the two bounding sample lines (the even
 * lattice immediately above and below the interpolated line); `pre` is the
 * separable 12-tap prediction already computed for every position; `ah`/`bh`
 * are the half-sample lattices of `a` and `b` (length 2*n).  Everything the
 * function reads is a function of the even lattice alone, which is what makes
 * the whole operator exactly invertible.
 */
static void uc_dirmap(const uc_pass_t *ps, const int32_t *a, const int32_t *b,
                      const int32_t *a0, const int32_t *a3,
                      const int32_t *ah, const int32_t *bh, int n, int depth,
                      int absf, int8_t *dtmp)
{
    int j, c, t;
    int n2 = 2 * n;

    for (j = 0; j < n; j++) {
        int32_t cost0 = 0, cbest = 0, rough = 0;
        int dbest = 0;
        int base = 2 * j;
        for (t = 0; t < ps->nsad; t++) {
            int k = ps->sad[t];
            int32_t d0 = ah[uc_mir(base + 2 * k, n2)] - bh[uc_mir(base + 2 * k, n2)];
            int i0 = uc_mir(j + k, n), i1 = uc_mir(j + k + 1, n);
            int32_t r0 = a[i1] - a[i0], r1 = b[i1] - b[i0];
            cost0 += d0 < 0 ? -d0 : d0;
            rough += (r0 < 0 ? -r0 : r0) + (r1 < 0 ? -r1 : r1);
        }
        cbest = cost0;
        for (c = 1; c < ps->ncand; c++) {
            int d = ps->cand[c];
            int32_t cost = 0;
            for (t = 0; t < ps->nsad; t++) {
                int k = 2 * ps->sad[t];
                int32_t v = ah[uc_mir(base + d + k, n2)] - bh[uc_mir(base - d + k, n2)];
                cost += v < 0 ? -v : v;
                if (cost >= cbest) break;      /* early-out: strict argmin kept */
            }
            if (cost < cbest) { cbest = cost; dbest = d; }
        }
        /* two independent gates: the winner must beat the straight prediction
         * decisively AND match far better than the lines are locally rough --
         * the second is what keeps texture and grain out of this path. */
        {   /* cross-line monotonicity (see UC_MONO_TOL) */
            int32_t d1 = a[j] - a0[j], d2 = b[j] - a[j], d3 = a3[j] - b[j];
            int32_t roughv = (d1 < 0 ? -d1 : d1) + (d2 < 0 ? -d2 : d2) +
                             (d3 < 0 ? -d3 : d3);
            int32_t nv = a3[j] - a0[j];
            if (nv < 0) nv = -nv;
            if (roughv > nv + UC_MONO_TOL(depth)) dbest = 0;
        }
        if (dbest != 0 && cost0 >= UC_EVID(depth) &&
            cbest * UC_MARGIN <= cost0 && cbest * absf <= rough)
            dtmp[j] = (int8_t)dbest;
        else
            dtmp[j] = 0;
    }
}

/* Dyadic correction: the interpolated line sits exactly half way, so the
 * along-direction estimate is the 2-tap average of the two half-lattice
 * samples.  Bit-identical to the original formulation. */
static void uc_direct(const uc_pass_t *ps, const int32_t *a, const int32_t *b,
                      const int32_t *a0, const int32_t *a3,
                      const int32_t *ah, const int32_t *bh, int n, int depth,
                      int absf, int32_t *pre, int8_t *dtmp)
{
    int j;
    int n2 = 2 * n;
    uc_dirmap(ps, a, b, a0, a3, ah, bh, n, depth, absf, dtmp);

    for (j = 0; j < n; j++) {              /* coherence median, UC_COHERE taps */
        int d = uc_median_dir(dtmp, j, n);
        int base = 2 * j;
        int32_t pd, pv, lim, corr;
        if (d == 0) continue;
        pd = (ah[uc_mir(base + d, n2)] + bh[uc_mir(base - d, n2)] + 1) >> 1;
        pv = (a[j] + b[j] + 1) >> 1;
        lim = a[j] - b[j];
        if (lim < 0) lim = -lim;
        corr = pd - pv;
        if (corr > lim) corr = lim;
        else if (corr < -lim) corr = -lim;
        pre[j] += corr;
    }
}

/* Build the half-sample lattice of one line: h[2j] = x[j],
 * h[2j+1] = (x[j] + x[j+1] + 1) >> 1.  One add and one shift per sample. */
static void uc_halflat(const int32_t *x, int n, int32_t *h)
{
    int j;
    for (j = 0; j < n; j++) {
        h[2 * j] = x[j];
        h[2 * j + 1] = (x[j] + x[uc_mir(j + 1, n)] + 1) >> 1;
    }
}

/* Predict one interpolated line from the even lattice.
 *   get(ctx, i, out) must write line i (length n) of the even lattice.
 *   `i` is the gap index: the produced line sits between lines i and i+1.
 * `nl` is the number of even lines (for mirror extension). */
typedef void (*uc_get_t)(void *ctx, int i, int32_t *out);

static void uc_predict(const omc_uc_t *u, const uc_pass_t *ps, uc_get_t get,
                       void *ctx, int i, int nl, int n, int32_t *p, int32_t *ws)
{
    int32_t *lines = ws;                    /* 12 * n */
    int32_t *a = lines + (size_t)OMC_UC_KTAPS * n;
    int32_t *b = a + n;
    int32_t *ah = b + n;
    int32_t *bh = ah + 2 * n;
    int8_t *dtmp = (int8_t *)(bh + 2 * n);
    int32_t tap[OMC_UC_KTAPS];
    int t, j;
    int32_t maxv = (int32_t)((1u << u->depth) - 1);

    for (t = 0; t < OMC_UC_KTAPS; t++)
        get(ctx, uc_mir(i + t - (OMC_UC_KTAPS / 2 - 1), nl), lines + (size_t)t * n);
    memcpy(a, lines + (size_t)(OMC_UC_KTAPS / 2 - 1) * n, sizeof(int32_t) * n);
    memcpy(b, lines + (size_t)(OMC_UC_KTAPS / 2) * n, sizeof(int32_t) * n);

    for (j = 0; j < n; j++) {
        for (t = 0; t < OMC_UC_KTAPS; t++) tap[t] = lines[(size_t)t * n + j];
        p[j] = uc_tap12(tap);
    }

    if (u->direction) {
        const int32_t *a0 = lines + (size_t)(OMC_UC_KTAPS / 2 - 2) * n;  /* line i-1 */
        const int32_t *a3 = lines + (size_t)(OMC_UC_KTAPS / 2 + 1) * n;  /* line i+2 */
        uc_halflat(a, n, ah);
        uc_halflat(b, n, bh);
        uc_direct(ps, a, b, a0, a3, ah, bh, n, u->depth,
                  UC_ABS, p, dtmp);
    }

    for (j = 0; j < n; j++) {               /* overshoot limiter + range clamp */
        int32_t lo = a[j] < b[j] ? a[j] : b[j];
        int32_t hi = a[j] < b[j] ? b[j] : a[j];
        int32_t step = hi - lo;
        int32_t fl = UC_FLOOR(u->depth);
        int32_t o = (step >> UC_OVER) + (step < fl ? step : fl);
        int32_t v = p[j];
        if (v < lo - o) v = lo - o;
        if (v > hi + o) v = hi + o;
        if (v < 0) v = 0;
        if (v > maxv) v = maxv;
        p[j] = v;
    }
}

/* ----------------------------------------------------------- line fetchers */
typedef struct {          /* even lattice = rows of a uint16 source plane */
    const uint16_t *p;
    int stride, n;
} uc_src_t;

static void uc_get_src(void *ctx, int i, int32_t *out)
{
    uc_src_t *s = (uc_src_t *)ctx;
    const uint16_t *r = s->p + (size_t)i * s->stride;
    int j;
    for (j = 0; j < s->n; j++) out[j] = r[j];
}

typedef struct {          /* even lattice = COLUMNS of the intermediate band */
    const int32_t *band;  /* rows [rlo, rlo+nb) of the 2h-row intermediate    */
    int rlo, nb, w, h2;
} uc_col_t;

static void uc_get_col(void *ctx, int i, int32_t *out)
{
    uc_col_t *c = (uc_col_t *)ctx;
    int t;
    /* Rows outside the materialised band are clamped.  They are never read for
     * an output row inside [r0, r1): the measured dependency reach (6 source
     * rows, i.e. 7 intermediate rows) is strictly inside the band's E = 8
     * margin, so the clamped entries are dead.  tests/test_uc.c proves this by
     * comparing every band split against the whole-plane result. */
    for (t = 0; t < c->h2; t++) {
        int r = t;
        if (r < c->rlo) r = c->rlo;
        else if (r >= c->rlo + c->nb) r = c->rlo + c->nb - 1;
        out[t] = c->band[(size_t)(r - c->rlo) * c->w + i];
    }
}

typedef struct {          /* even lattice = even rows of an int32 plane */
    const int32_t *p;
    int stride, n;
} uc_i32_t;

/* ------------------------------------------------------------------- sizes */
static size_t uc_ws_lines(int n)
{
    return (size_t)(OMC_UC_KTAPS + 2) * n + 4 * (size_t)n + (size_t)n / 4 + 8;
}

size_t omc_uc_scratch_bytes(int w, int h)
{
    int n = w > 2 * h ? w : 2 * h;
    return uc_ws_lines(n) * sizeof(int32_t) + 64;
}

/* --------------------------------------------------------------------- up */
int omc_uc_up_plane(const omc_uc_t *u, const uint16_t *src, int ss, int w, int h,
                    uint16_t *dst, int ds, int r0, int r1)
{
    int H2 = 2 * h, E = 8;          /* E = intermediate-row reach of the H pass */
    int rlo, rhi, nb, R, j;
    int32_t *band, *ws, *p;
    uc_src_t sc;
    uc_col_t cc;

    if (!u || !src || !dst || w < 2 || h < 2 || (w & 1) || r0 < 0 || r1 > H2 || r0 > r1)
        return -1;
    if (r0 == r1) return 0;

    rlo = r0 - E; if (rlo < 0) rlo = 0;
    rhi = r1 + E; if (rhi > H2) rhi = H2;
    nb = rhi - rlo;

    band = (int32_t *)malloc((size_t)nb * w * sizeof(int32_t));
    ws = (int32_t *)malloc(omc_uc_scratch_bytes(w, h));
    p = (int32_t *)malloc((size_t)(w > H2 ? w : H2) * sizeof(int32_t));
    if (!band || !ws || !p) { free(band); free(ws); free(p); return -1; }

    /* --- vertical pass: build intermediate rows [rlo, rhi) ---------------- */
    sc.p = src; sc.stride = ss; sc.n = w;
    for (R = rlo; R < rhi; R++) {
        int32_t *row = band + (size_t)(R - rlo) * w;
        if ((R & 1) == 0) {
            const uint16_t *s = src + (size_t)(R >> 1) * ss;
            for (j = 0; j < w; j++) row[j] = s[j];
        } else {
            uc_predict(u, &UC_PASS_V, uc_get_src, &sc, R >> 1, h, w, row, ws);
        }
    }

    /* --- horizontal pass: one output row at a time ------------------------ */
    cc.band = band; cc.rlo = rlo; cc.nb = nb; cc.w = w; cc.h2 = H2;
    for (R = r0; R < r1; R++) {
        const int32_t *row = band + (size_t)(R - rlo) * w;
        uint16_t *o = dst + (size_t)R * ds;
        for (j = 0; j < w; j++) o[2 * j] = (uint16_t)row[j];
    }
    for (j = 0; j < w; j++) {
        uc_predict(u, &UC_PASS_H, uc_get_col, &cc, j, w, H2, p, ws);
        for (R = r0; R < r1; R++) dst[(size_t)R * ds + 2 * j + 1] = (uint16_t)p[R];
    }

    free(band); free(ws); free(p);
    return 0;
}

/* ==================================================================== SCALE
 * Non-dyadic (rational) conversion, e.g. 720p -> 1080p (3/2).
 *
 * Cascading the 2x operator with a decimator does NOT work here: the 2x stage
 * already reaches 8 source rows, and any further vertical resampling adds to
 * that, pushing past slice_h and costing a second slice period.  So the
 * rational path is a SINGLE-STAGE polyphase resampler: 12-tap, linear phase,
 * one fixed coefficient set per phase.
 *
 * For a ratio num/den in lowest terms there are exactly `den` distinct phases,
 * and den is small for every broadcast conversion (720p->1080p is 3).  Each
 * phase is therefore a FIXED coefficient vector, exactly like the dyadic
 * kernel, so hardware instantiates `den` hard-wired shift-add chains and C3
 * holds unchanged -- omc_uc_scale_selfcheck() proves the decomposition for the
 * shipped ratios the same way omc_uc_selfcheck_kernel() does for the 2x case.
 * At den = 2 the bank reduces exactly to UC_C, so the 2x path is the special
 * case of this one, not a different filter.
 *
 * WHAT IS LOST: reversibility.  A rational resampling is not a lifting step and
 * has no exact inverse.  down(up(x)) == x is a DYADIC-ONLY guarantee.  The
 * co-siting convention is kept: output sample n maps to source position
 * n * num / den, so at den = 2 output 2k lands exactly on source k.
 */
#define OMC_UC_MAXPHASE 16
/* Aperture cap.  A decimating bank needs KTAPS * D taps (see uc_find_poly);
 * 48 admits every conversion up to D = 4, i.e. 2160p -> 540p.  Beyond that the
 * reach stops fitting a slice period anyway, so the cap and the latency rule
 * refuse the same set. */
#define OMC_UC_MAXTAPS 48

/* Number of taps for a conversion whose source:dest ratio is num:den.
 *
 * UPCONVERSION (num <= den) is interpolation: the cutoff stays at the source
 * Nyquist and the aperture is the 12-tap kernel, unchanged, so every existing
 * result stands.  DOWNCONVERSION (num > den) is decimation: the cutoff must
 * move DOWN to the OUTPUT Nyquist or everything above it folds back into the
 * picture, and a lowpass with D times the period needs D times the aperture. */

static int uc_gcd(int a, int b);   /* defined below */

/* Centre-aligned output->source mapping for the rational path (see
 * omc_uc_scale_aligned).  Returns the integer source index in *ip and the
 * phase in *php.  When the ratio's parity does not admit an exact phase the
 * function falls back to the historical corner-aligned mapping and returns 0,
 * so the caller can report the ratio as un-aligned rather than pretend. */
static int uc_map_pos(int r, int num, int den, int *ip, int *hph, int siting)
{
    int64_t den2 = 2 * (int64_t)den;
    int64_t N, i, h;
    if (siting == OMC_SITE_COSITED) {
        /* output sample 0 on source sample 0 -- chroma siting.  Exactly the
         * mapping this scaler had before centre alignment, and the only one
         * that keeps 4:2:2 chroma on the luma it belongs to. */
        int64_t pos = (int64_t)r * num;
        *ip = (int)(pos / den);
        *hph = (int)(2 * (pos % den));
        return 1;
    }
    N = (int64_t)(2 * r + 1) * num - den;           /* units of 1/(2*den) */
    i = N / den2; h = N - i * den2;
    if (h < 0) { h += den2; i -= 1; }               /* floor, not truncate */
    *ip = (int)i; *hph = (int)h;                    /* h in [0, 2*den)     */
    return 1;
}

/* 1 when the (sw,sh)->(dw,dh) conversion is centre-aligned on both axes, 0 when
 * an axis falls back to the corner mapping (mixed-parity ratio: exact centring
 * would need a 2*den phase bank).  Callers that care about geometric
 * registration should test this. */
int omc_uc_scale_aligned(int sw, int sh, int dw, int dh)
{
    (void)sw; (void)sh; (void)dw; (void)dh;
    return 1;   /* every rational ratio is centre-aligned: even half-phases use
                 * a published phase, odd ones use the derived half-phase */
}

int omc_uc_scale_taps(int num, int den)
{
    int nt;
    if (num <= den) return OMC_UC_KTAPS;
    nt = (OMC_UC_KTAPS * num + den - 1) / den;
    nt = (nt + 1) & ~1;
    return nt > OMC_UC_MAXTAPS ? 0 : nt;        /* 0 = ratio not supported */
}

/* Worst-case vertical reach of the rational path for a given ratio, in SOURCE
 * rows: the aperture's lower half.  At D = 1 it is 6 (one slice period, as
 * before), but a 2:1 decimation reaches 12 and a 3:2 decimation 9, and those
 * are extra slice periods that have to be counted rather than assumed away. */
int omc_uc_scale_reach_r(int num, int den)
{
    int nt;
    /* 1:1 on this axis is the identity and omc_uc_scale_plane() now takes it as
     * such, so the reach really is zero rather than the aperture's six.  Gate
     * G19 measures it; before the identity fast path existed this returned 6,
     * and a horizontal-only conversion was charged a slice period it never
     * used. */
    if (num == den) return 0;
    nt = omc_uc_scale_taps(num, den);
    return nt ? nt / 2 : 0;
}

#include "uc_poly_tab.c.inc"

/* A resolved coefficient bank: a POINTER INTO THE CONST TABLE, never a copy in
 * a mutable global.  The previous form cached the active bank in file-scope
 * arrays keyed on (num, den), which made the operator stateful -- two threads
 * scaling different ratios would race, and it contradicted the "no state, no
 * adaptive parameters" property the dyadic path genuinely has.  Resolving to a
 * const pointer removes the state entirely: the tables are read-only, so any
 * number of threads may share them. */
typedef struct {
    const int32_t *c;      /* den * nt coefficients, phase-major */
    int den, nt;
} uc_bank_t;

/* Multiplier-free evaluation of an arbitrary tabulated coefficient.
 *
 * The dyadic kernel is written as an explicit shift-add chain and proved equal
 * to UC_C by omc_uc_selfcheck_kernel().  The rational bank could not be, because
 * its coefficients are a table rather than six literals -- so the reference
 * implementation multiplied, and C3's "no per-pixel multiplier" rested on the
 * claim that hardware would hard-wire a chain per phase.  A claim is not a
 * proof, and this is the document's own standard applied to the path it was not
 * applied to.
 *
 * uc_mul_sa() walks the coefficient's bits and accumulates shifts.  The
 * coefficient is a compile-time constant per phase, so in hardware this IS the
 * hard-wired chain and the loop does not exist; in C the bound is fixed at 12
 * iterations (|c| <= 1024 < 2^11) with no data-dependent exit, so it is the
 * worst case and the typical case alike.  omc_uc_selfcheck_poly_mul() proves it
 * equals the multiply for every coefficient in every published table, over the
 * whole datapath range. */
static inline int32_t uc_mul_sa(int32_t c, int32_t x)
{
    int32_t acc = 0;
    int neg = c < 0, b;
    if (neg) c = -c;
    for (b = 0; b < 12; b++)
        if ((c >> b) & 1) acc += OMC_SHL(x, b);
    return neg ? -acc : acc;
}

/* Resolve the bank for ratio num:den, or NULL if the ratio is outside the
 * declared set.  Pure lookup: no computation, no libm, no state. */
static const uc_poly_entry_t *uc_find_poly(int den, int num)
{
    int i;
    for (i = 0; i < UC_POLY_NTAB; i++) {
        if (UC_POLY_TAB[i].den != den) continue;
        if ((num > den) != (UC_POLY_TAB[i].num > UC_POLY_TAB[i].den)) continue;
        if (num > den && UC_POLY_TAB[i].num != num) continue;
        return &UC_POLY_TAB[i];
    }
    return NULL;
}

/* Proof that the shift-add form equals the tabulated multiply, for every
 * coefficient in every published bank, over the whole datapath range.  This is
 * the rational path's equivalent of omc_uc_selfcheck_kernel() -- the check the
 * dyadic kernel always had and this one did not. */
int omc_uc_selfcheck_poly_mul(void)
{
    int i, k, v;
    for (i = 0; i < UC_POLY_NTAB; i++) {
        int n = UC_POLY_TAB[i].den * UC_POLY_TAB[i].nt;
        for (k = 0; k < n; k++) {
            int32_t c = UC_POLY_TAB[i].c[k];
            for (v = -4096; v <= 4095; v++)
                if (uc_mul_sa(c, v) != c * v) return -(i + 1);
        }
    }
    return 0;
}

/* Structural verification of the published bank (C3/C8 evidence).  Checks the
 * properties the arithmetic depends on, none of which involve libm, so this is
 * a real check on every platform rather than a restatement of the generator:
 *   - every phase sums to exactly 1024 (unity DC: no conversion changes level);
 *   - phase 0 of every bank is the unit impulse (an on-grid output sample is
 *     the source sample, so a ratio's identity phase is exact);
 *   - the 1:2 interpolating phase equals UC_C, i.e. the rational path reduces
 *     EXACTLY to the dyadic kernel rather than approximately;
 *   - phase p mirrors phase den-p (linear phase: no geometric shift).
 * Returns 0 on success, or -(index + 1) of the first table that fails. */
int omc_uc_selfcheck_poly(void)
{
    int i, ph, k;
    for (i = 0; i < UC_POLY_NTAB; i++) {
        int den = UC_POLY_TAB[i].den, nt = UC_POLY_TAB[i].nt;
        const int32_t *c = UC_POLY_TAB[i].c;
        for (ph = 0; ph < den; ph++) {
            int32_t s = 0;
            for (k = 0; k < nt; k++) s += c[ph * nt + k];
            if (s != 1024) return -(i + 1);
        }
        if (UC_POLY_TAB[i].num <= den) {
            /* INTERPOLATION only: an on-grid output sample IS the source
             * sample, so phase 0 is the unit impulse.  A DECIMATING phase 0 is
             * a lowpass -- it must still average, or it would alias -- so the
             * impulse property is checked where it holds and the symmetry
             * property below is checked everywhere. */
            for (k = 0; k < nt; k++)
                if (c[k] != (k == nt / 2 - 1 ? 1024 : 0)) return -(i + 1);
        }
        /* NO tap-symmetry check for a single-phase decimator, and the reason is
         * worth recording because the obvious invariant is false here.  The
         * kernel construction centres the Kaiser window at (nt-1)/2 while the
         * sinc is centred at (nt/2 - 1) + ph/den; those coincide exactly at the
         * dyadic phase (ph/den = 1/2), which is why UC_C is symmetric, and
         * differ by half a sample at ph = 0.  A den = 1 decimator therefore has
         * genuinely unequal taps either side of its peak and asserting symmetry
         * fails on a correct table.  What actually matters is the group delay,
         * i.e. whether the picture moves, and that is MEASURED rather than
         * assumed: gate G16c puts it at -0.002 output rows at 2:1 and -0.005 at
         * 3:2, against a 0.05 tolerance. */
        if (UC_POLY_TAB[i].num == 1 && den == 2) {
            for (k = 0; k < OMC_UC_KTAPS; k++)
                if (c[nt + k] != UC_C[k]) return -(i + 1);
        }
        for (ph = 1; ph * 2 <= den; ph++) {
            int q = den - ph;
            if (q == ph || q >= den) continue;
            for (k = 0; k < nt; k++)
                if (c[ph * nt + k] != c[q * nt + (nt - 1 - k)]) return -(i + 1);
        }
    }
    return 0;
}

/* ------------------------------------------------- rational-path direction
 * The dyadic operator's direction stage assumes the predicted line sits
 * exactly half way between its two bounding lines.  A rational conversion puts
 * it at t = ph/den, so both the candidate offsets and the blend weight have to
 * carry the phase.
 *
 * Geometry: a structure of slope d (half-samples per line) through the output
 * point crosses the line ABOVE at +2*t*d and the line BELOW at -2*(1-t)*d, in
 * half-sample units.  At t = 1/2 that is +d and -d, i.e. the dyadic case, so
 * this is a strict generalisation rather than a second algorithm.
 *
 * The SEARCH is unchanged and stays symmetric: an edge's orientation is a
 * property of the picture, not of the output grid, so the same four gates and
 * the same constants decide it.  Only the CORRECTION carries the phase.
 *
 * Both tables are built once per output LINE (den and ph are fixed for the
 * whole line), so the divisions below are amortised over `len` samples and the
 * per-sample path stays adds, shifts, compares and lookups (C3).
 *
 * APPLIED TO THE VERTICAL PASS ONLY.  The horizontal pass's SAD taps are
 * offsets along the image ROW axis, so their span is charged to the vertical
 * dependency reach -- and on the rational path the vertical decimation
 * amplifies it: at 4/3 the source advances 0.75 rows per output row, so an
 * H-pass span of E output rows costs 0.75*E source rows on top of the 12-tap
 * aperture's 6.  Even E = 3 gives 6 + 3 = 9 > slice_h = 8.  There is no room
 * for it inside one slice period, which is the same structural limit section
 * 10.6 records for the dyadic H pass, made worse by the decimation.  Stated
 * here so the omission is a measured decision rather than a gap. */
/* Per-candidate sampling geometry at phase ph/den.
 *
 * The structure through the output point crosses the line ABOVE at column
 * offset +t*d and the line BELOW at -(1-t)*d, in WHOLE samples, t = ph/den.
 * The dyadic path reads those two positions off a half-sample lattice, which
 * is exact only because t = 1/2 makes both offsets land on a half-sample.  At
 * t = 1/3 the true offsets are +d/3 and -2d/3, and snapping them to the
 * half-lattice collapses them onto the dyadic +-d/2 -- measured: that snapping
 * costs -314% of the staircase metric at 45 degrees on a 3/2 conversion, i.e.
 * it makes the picture markedly worse, which is how it was found.
 *
 * So the position is carried exactly: an integer part q and a fractional
 * weight quantised to /16.  Both are computed once per output LINE (den and ph
 * are fixed for the whole line) and reduce to the half-lattice identically
 * when den = 2, so the dyadic path is unchanged by construction. */
typedef struct {
    int8_t qA, qB;      /* integer column offsets                    */
    int8_t fA, fB;      /* fractional weights, /16                   */
} uc_fpos_t;

static void uc_fracofs(const uc_pass_t *ps, int ph, int den,
                       int *w16, uc_fpos_t *fp)
{
    int c;
    *w16 = (16 * ph + den / 2) / den;              /* t, quantised to /16 */
    for (c = 0; c < ps->ncand; c++) {
        int d = ps->cand[c];
        int nA = ph * d, nB = -(den - ph) * d;
        int qA = nA / den, qB = nB / den;
        int rA = nA - qA * den, rB = nB - qB * den;
        if (rA < 0) { qA--; rA += den; }           /* floor, not truncate */
        if (rB < 0) { qB--; rB += den; }
        fp[c].qA = (int8_t)qA; fp[c].fA = (int8_t)((16 * rA + den / 2) / den);
        fp[c].qB = (int8_t)qB; fp[c].fB = (int8_t)((16 * rB + den / 2) / den);
    }
}

/* line[j + q + f/16], by linear interpolation.  One 4-bit-constant multiply
 * pair and a shift; the constant is fixed for the whole line, so in hardware
 * it is `den` hard-wired shift-add chains exactly as the polyphase bank is. */
static inline int32_t uc_fsamp(const int32_t *line, int j, int q, int f, int n)
{
    int32_t v0 = line[uc_mir(j + q, n)];
    int32_t v1 = line[uc_mir(j + q + 1, n)];
    return f ? ((v0 * (16 - f) + v1 * f + 8) >> 4) : v0;
}

/* Per-position direction correction for one rational output line.  Writes the
 * correction (not the sample) so the caller can add it before the limiter,
 * exactly as the dyadic path does.
 *
 * APPLIED TO THE VERTICAL PASS ONLY.  The horizontal pass's SAD taps are
 * offsets along the image ROW axis, so their span is charged to the vertical
 * dependency reach -- and on the rational path the vertical decimation
 * amplifies it: at 4/3 the source advances 0.75 rows per output row, so an
 * H-pass span of E output rows costs 0.75*E source rows on top of the 12-tap
 * aperture's 6.  Even E = 3 gives 6 + 3 = 9 > slice_h = 8.  There is no room
 * inside one slice period -- the same structural limit section 10.6 records
 * for the dyadic H pass, made worse by the decimation.  Stated so the omission
 * is a measured decision rather than a gap. */
static void uc_direct_frac(const uc_pass_t *ps, const int32_t *a, const int32_t *b,
                           const int32_t *a0, const int32_t *a3,
                           const int32_t *ah, const int32_t *bh, int n, int depth,
                           int w16, const uc_fpos_t *fp, int absf,
                           int32_t *corr, int8_t *dtmp)
{
    int j, c;
    uc_dirmap(ps, a, b, a0, a3, ah, bh, n, depth, absf, dtmp);
    for (j = 0; j < n; j++) {
        int d = uc_median_dir(dtmp, j, n);
        int32_t da, db, lim, cv;
        corr[j] = 0;
        if (d == 0) continue;
        for (c = 0; c < ps->ncand; c++) if (ps->cand[c] == d) break;
        if (c >= ps->ncand) continue;
        da = uc_fsamp(a, j, fp[c].qA, fp[c].fA, n) - a[j];
        db = uc_fsamp(b, j, fp[c].qB, fp[c].fB, n) - b[j];
        cv = ((16 - w16) * da + w16 * db + 8) >> 4;
        lim = a[j] - b[j];
        if (lim < 0) lim = -lim;
        if (cv > lim) cv = lim;
        else if (cv < -lim) cv = -lim;
        corr[j] = cv;
    }
}

static int uc_gcd(int a, int b) { while (b) { int t = a % b; a = b; b = t; } return a; }


/* Derive the filter at half-phase (p0 + 1/2) from the two published phases.
 * dst must hold bk->nt entries.  See the file-level note on centre alignment. */
static void uc_halfphase(const uc_bank_t *bk, int p0, int32_t *dst)
{
    int k, nt = bk->nt, big = 0;
    const int32_t *a = bk->c + (size_t)p0 * nt;
    const int32_t *b;
    int shift_b = 0;
    int32_t sum = 0;
    if (p0 + 1 < bk->den) b = bk->c + (size_t)(p0 + 1) * nt;
    else { b = bk->c; shift_b = 1; }   /* wrap: phase 0, one sample later */
    for (k = 0; k < nt; k++) {
        int32_t bv = shift_b ? (k >= 1 ? b[k - 1] : 0) : b[k];
        int32_t v = a[k] + bv;
        dst[k] = v >= 0 ? (v + 1) >> 1 : -((-v + 1) >> 1);
        sum += dst[k];
        if (dst[k] > dst[big]) big = k;
    }
    dst[big] += 1024 - sum;            /* exact unity DC, as the generator does */
}

/* One 1-D polyphase pass over `n` output lines of length `len`.
 * get(ctx, i, out) writes source line i.  Output line o samples source position
 * o * num / den.  Returns via cb(o, line). */
static void uc_scale_line(const omc_uc_t *u, const uc_bank_t *bk,
                          const int32_t *lines, int nl, int len,
                          int i0, int ph, const int32_t *dcorr, int32_t *out,
                          const int32_t *cov)
{
    int j;
    int32_t maxv = (int32_t)((1u << u->depth) - 1);
    const int32_t *c = cov ? cov : bk->c + (size_t)ph * bk->nt;
    int nt = bk->nt;
    /* Limiter envelope.  For interpolation the bounding pair IS the envelope,
     * which is what makes the ringing guarantee exact.  For decimation the
     * output is a weighted mean over ~D source samples and may legitimately sit
     * outside the two nearest ones, so clamping to that pair would clip real
     * signal.  The envelope therefore spans the central 2*ceil(D) taps, which
     * is exactly the bounding pair at D = 1. */
    int nb = nt / OMC_UC_KTAPS + 1, blo, bhi;
    if (nb < 1) nb = 1;
    blo = nt / 2 - nb; bhi = nt / 2 + nb;
    if (blo < 0) blo = 0;
    if (bhi > nt) bhi = nt;
    (void)nl; (void)i0;
    for (j = 0; j < len; j++) {
        int64_t acc = 0;
        int32_t lo, hi, a, b, o;
        int k;
        for (k = 0; k < nt; k++)
            acc += uc_mul_sa(c[k], lines[(size_t)k * len + j]);
        {
            int32_t v = (int32_t)((acc + 512) >> 10);
            if (dcorr) v += dcorr[j];       /* direction, before the limiter */
            a = lines[(size_t)(nt / 2 - 1) * len + j];
            b = lines[(size_t)(nt / 2) * len + j];
            lo = a < b ? a : b; hi = a < b ? b : a;
            for (k = blo; k < bhi; k++) {
                int32_t x = lines[(size_t)k * len + j];
                if (x < lo) lo = x;
                if (x > hi) hi = x;
            }
            o = ((hi - lo) >> UC_OVER);
            { int32_t step = hi - lo, fl = UC_FLOOR(u->depth);
              o += step < fl ? step : fl; }
            if (v < lo - o) v = lo - o;
            if (v > hi + o) v = hi + o;
            if (v < 0) v = 0;
            if (v > maxv) v = maxv;
            out[j] = v;
        }
    }
}

/* Scratch the rational path needs, in bytes, for a (sw, sh) -> (*, dh)
 * conversion.  Sized from the SAME expressions the allocations below use, so
 * the two cannot drift; the aperture is the worst case over both axes, because
 * the caller may not know which axis decimates harder. */
size_t omc_uc_scale_scratch_bytes(int sw, int sh, int dw, int dh)
{
    int ntmax = 0, ntv, nth, g;
    if (sw < 2 || sh < 2 || dw < 2 || dh < 2) return 0;
    /* BOTH axes, from the same expressions the body uses.  An earlier draft
     * took only (sw, sh, dh) and inferred the horizontal aperture from sw
     * alone; on a 2:1 horizontal decimation that reported 12 taps where the
     * body wanted 24, and the resulting overrun showed up as a heap corruption
     * three call frames away.  A scratch sizer that does not take every
     * dimension the body uses is a buffer overflow waiting for the right
     * ratio. */
    g = uc_gcd(sh, dh); ntv = omc_uc_scale_taps(sh / g, dh / g);
    g = uc_gcd(sw, dw); nth = omc_uc_scale_taps(sw / g, dw / g);
    ntmax = ntv > nth ? ntv : nth;
    if (!ntmax) ntmax = OMC_UC_MAXTAPS;   /* unsupported ratio: size for the cap
                                           * so the caller's buffer is never the
                                           * reason a refusal turns into a crash */
    return (size_t)ntmax * sw * sizeof(int32_t)          /* lines */
         + (size_t)dh * sw * sizeof(int32_t)             /* mid   */
         + (size_t)sw * sizeof(int32_t)                  /* row   */
         + (size_t)ntmax * dh * sizeof(int32_t)          /* cols  */
         + (size_t)dh * sizeof(int32_t)                  /* orow  */
         + (size_t)4 * sw * sizeof(int32_t)              /* dh2   */
         + (size_t)sw * sizeof(int32_t)                  /* dcorr */
         + (size_t)sw                                    /* dtmp  */
         + 8 * 16;                                       /* alignment slack */
}

/* The rational path with CALLER-OWNED memory.  The dyadic path has had this
 * shape since the original design (omc_uc_up_plane_ws + omc_uc_scratch_bytes)
 * and the rational path did not -- it allocated internally, which is the one
 * place the operator's C did not look like the hardware it describes.  In
 * fabric these are fixed buffers sized at synthesis; a heap call is a thing a
 * synthesis run cannot do at all.  omc_uc_scale_plane() below is now a thin
 * wrapper that allocates and calls this, so the convenience form still exists
 * and the two are gated byte-identical. */
int omc_uc_scale_plane_ws(const omc_uc_t *u, const uint16_t *src, int ss, int sw, int sh,
                          uint16_t *dst, int ds, int dw, int dh, void *ws, size_t wsz)
{
    return omc_uc_scale_plane_ws_sited(u, src, ss, sw, sh, dst, ds, dw, dh,
                                       ws, wsz, OMC_SITE_CENTRE);
}

int omc_uc_scale_plane_ws_sited(const omc_uc_t *u, const uint16_t *src, int ss,
                                int sw, int sh, uint16_t *dst, int ds, int dw,
                                int dh, void *ws, size_t wsz, int siting)
{
    int gv, gh, denv, denh, numv, numh, r, j, t;
    int ntv, nth, ntmax;
    int32_t *lines = NULL, *mid = NULL, *row = NULL, *cols = NULL, *orow = NULL;
    int32_t *dh2 = NULL, *dcorr = NULL;
    int8_t *dtmp = NULL;
    uc_fpos_t fp[OMC_UC_NCAND];
    uc_bank_t bkv, bkh;
    int rc = -1;
    if (!u || !src || !dst || sw < 2 || sh < 2 || dw < 2 || dh < 2) return -1;
    /* UC_C is an INTERPOLATOR: its cutoff sits at the SOURCE Nyquist.  Asking it
     * to decimate puts the stopband in the wrong place and folds everything
     * above the OUTPUT Nyquist back into the picture -- measured on a
     * band-limited zone plate, -6.3 dB of aliased energy at 2/3 and -3.1 dB at
     * 1/2, against -26.4 dB for the same operator upconverting.  Correct
     * decimation needs a ratio-scaled aperture, which is a different filter and
     * a different reach; until omc_uc_scale_reach() and omc_validate_config()
     * carry that reach, refuse rather than return a broken picture.
     * See omc_uc_scale_plane_down(). */

    gv = uc_gcd(sh, dh); numv = sh / gv; denv = dh / gv;
    gh = uc_gcd(sw, dw); numh = sw / gh; denh = dw / gh;
    if (denv > OMC_UC_MAXPHASE || denh > OMC_UC_MAXPHASE) return -2;  /* ratio too fine */
    ntv = omc_uc_scale_taps(numv, denv);
    nth = omc_uc_scale_taps(numh, denh);
    if (!ntv || !nth) return -3;   /* decimation steeper than the aperture cap */
    ntmax = ntv > nth ? ntv : nth;

    /* Carve the caller's block.  No allocation on this path at all. */
    {
        unsigned char *q = (unsigned char *)ws;
        if (!ws || wsz < omc_uc_scale_scratch_bytes(sw, sh, dw, dh)) return -1;
        lines = (int32_t *)q; q += (size_t)ntmax * sw * sizeof(int32_t);
        mid   = (int32_t *)q; q += (size_t)dh * sw * sizeof(int32_t);
        row   = (int32_t *)q; q += (size_t)sw * sizeof(int32_t);
        cols  = (int32_t *)q; q += (size_t)ntmax * dh * sizeof(int32_t);
        orow  = (int32_t *)q; q += (size_t)dh * sizeof(int32_t);
        dh2   = (int32_t *)q; q += (size_t)4 * sw * sizeof(int32_t);
        dcorr = (int32_t *)q; q += (size_t)sw * sizeof(int32_t);
        dtmp  = (int8_t *)q;
    }

    { const uc_poly_entry_t *e = uc_find_poly(denv, numv);
      if (!e) { rc = -3; goto out; }
      bkv.c = e->c; bkv.den = denv; bkv.nt = e->nt; }
    /* A ratio of 1:1 on this axis is the identity: phase 0 of the 1/1 bank is a
     * unit impulse, so the filtered result is the source row and the limiter
     * cannot move it.  Running the pass anyway still READS a 12-tap window,
     * which gives a horizontal-only conversion a phantom VERTICAL reach of six
     * rows -- and reach is what buys slice periods.  Skipping it makes a
     * horizontal-only resample genuinely horizontal: byte-identical output,
     * zero vertical reach.  Gate G19 proves both. */
    if (numv == 1 && denv == 1) {
        for (r = 0; r < dh; r++) {
            const uint16_t *sp = src + (size_t)r * ss;
            int32_t *m = mid + (size_t)r * sw;
            for (j = 0; j < sw; j++) m[j] = sp[j];
        }
        goto hpass;
    }
    for (r = 0; r < dh; r++) {                       /* vertical pass */
        int32_t hcv[OMC_UC_MAXTAPS];
        const int32_t *covv = NULL;
        int i, hp, ph;
        uc_map_pos(r, numv, denv, &i, &hp, siting);
        ph = hp >> 1;
        if (hp & 1) { uc_halfphase(&bkv, ph, hcv); covv = hcv; }
        for (t = 0; t < ntv; t++) {
            const uint16_t *sp = src + (size_t)uc_mir(i + t - (ntv / 2 - 1), sh) * ss;
            for (j = 0; j < sw; j++) lines[(size_t)t * sw + j] = sp[j];
        }
        {
            const int32_t *dc = NULL;
            if (u->direction && ph != 0 && numv <= denv) {
                const int32_t *pa = lines + (size_t)(ntv / 2 - 1) * sw;
                const int32_t *pb = lines + (size_t)(ntv / 2) * sw;
                const int32_t *p0 = lines + (size_t)(ntv / 2 - 2) * sw;
                const int32_t *p3 = lines + (size_t)(ntv / 2 + 1) * sw;
                int32_t *ah = dh2, *bh = dh2 + 2 * sw;
                int w16;
                uc_halflat(pa, sw, ah);
                uc_halflat(pb, sw, bh);
                uc_fracofs(&UC_PASS_V, ph, denv, &w16, fp);
                uc_direct_frac(&UC_PASS_V, pa, pb, p0, p3, ah, bh, sw, u->depth,
                               w16, fp,
                               UC_ABS,
                               dcorr, dtmp);
                dc = dcorr;
            }
            uc_scale_line(u, &bkv, lines, sh, sw, i, ph, dc, row, covv);
        }
        memcpy(mid + (size_t)r * sw, row, sizeof(int32_t) * sw);
    }
hpass:
    { const uc_poly_entry_t *e = uc_find_poly(denh, numh);
      if (!e) { rc = -3; goto out; }
      bkh.c = e->c; bkh.den = denh; bkh.nt = e->nt; }
    for (j = 0; j < dw; j++) {                       /* horizontal pass */
        int32_t hch[OMC_UC_MAXTAPS];
        const int32_t *covh = NULL;
        int i, hp, ph;
        uc_map_pos(j, numh, denh, &i, &hp, siting);
        ph = hp >> 1;
        if (hp & 1) { uc_halfphase(&bkh, ph, hch); covh = hch; }
        for (t = 0; t < nth; t++) {
            int c = uc_mir(i + t - (nth / 2 - 1), sw);
            for (r = 0; r < dh; r++) cols[(size_t)t * dh + r] = mid[(size_t)r * sw + c];
        }
        uc_scale_line(u, &bkh, cols, sw, dh, i, ph, NULL, orow, covh);
        for (r = 0; r < dh; r++) dst[(size_t)r * ds + j] = (uint16_t)orow[r];
    }
    rc = 0;
out:
    return rc;
}

/* Convenience wrapper: allocates the scratch and calls the workspace form.
 * Kept because every existing caller and the whole harness uses it, and gated
 * byte-identical against the _ws form. */
int omc_uc_scale_plane(const omc_uc_t *u, const uint16_t *src, int ss, int sw, int sh,
                       uint16_t *dst, int ds, int dw, int dh)
{
    return omc_uc_scale_plane_sited(u, src, ss, sw, sh, dst, ds, dw, dh,
                                    OMC_SITE_CENTRE);
}

int omc_uc_scale_plane_sited(const omc_uc_t *u, const uint16_t *src, int ss,
                             int sw, int sh, uint16_t *dst, int ds, int dw,
                             int dh, int siting)
{
    size_t n = omc_uc_scale_scratch_bytes(sw, sh, dw, dh);
    void *ws;
    int rc;
    if (!n) return -1;
    ws = malloc(n);
    if (!ws) return -1;
    rc = omc_uc_scale_plane_ws_sited(u, src, ss, sw, sh, dst, ds, dw, dh, ws, n,
                                     siting);
    free(ws);
    return rc;
}

/* Latency of a rational conversion, and whether A2 admits it.
 *
 * The decoder emits source rows one slice at a time, so the converter's
 * vertical reach -- omc_uc_scale_reach_r(), which for a DECIMATION is half the
 * ratio-scaled aperture, not the fixed 6 of an interpolation -- costs
 * ceil(reach / slice_h) whole slice periods.  The rest of the model is
 * docs/LATENCY.md verbatim, identical to the rule omc_validate_config() already
 * applies to the dyadic cascade.
 *
 * Returns 0 and writes the total in ms, or -1 if the conversion cannot hold the
 * sub-1 ms bar, or -3 if the ratio is steeper than the aperture cap.  A caller
 * that cannot honour a refusal must not offer the conversion. */
int omc_uc_format_supported(int w, int h)
{
    (void)w;
    return h >= OMC_UC_MIN_HEIGHT;
}

int omc_uc_scale_latency(int sw, int sh, int dw, int dh, int slice_h,
                         int fps_num, int fps_den, double *total_ms, int *periods)
{
    return omc_uc_scale_latency_ex(sw, sh, dw, dh, slice_h, fps_num, fps_den,
                                   OMC_OUT_RASTER, total_ms, periods);
}

int omc_uc_scale_latency_ex(int sw, int sh, int dw, int dh, int slice_h,
                            int fps_num, int fps_den, int batched,
                            double *total_ms, int *periods)
{
    int gv = uc_gcd(sh, dh), numv = sh / gv, denv = dh / gv;
    int gh = uc_gcd(sw, dw), numh = sw / gh, denh = dw / gh;
    int reach, per, nsl;
    double frame_ms, line_ms, slice_ms, total;
    if (sh < 2 || dh < 2 || slice_h < 1 || !fps_num || !fps_den) return -1;

    if (denv > OMC_UC_MAXPHASE || denh > OMC_UC_MAXPHASE) return -3;
    /* Ask the APERTURE whether the ratio is supported, not the reach: a 1:1
     * axis is supported and has reach zero, and conflating "zero reach" with
     * "unsupported" made a colour-only conversion -- source raster equal to
     * destination raster -- look like a refused ratio. */
    if (!omc_uc_scale_taps(numv, denv) || !omc_uc_scale_taps(numh, denh))
        return -3;
    reach = omc_uc_scale_reach_r(numv, denv);
    nsl = sh / slice_h;
    if (nsl < 1) return -1;
    frame_ms = 1000.0 * (double)fps_den / (double)fps_num;
    line_ms = frame_ms / (double)sh;
    slice_ms = frame_ms / (double)nsl;
    /* RASTER-CLOCKED OUTPUT STAGE (the default; omc_uc_scale_latency_ex() takes
     * the slice-batched figure).  The converter needs `reach` source rows beyond
     * the row it is producing.  When rows go downstream as they become final and
     * the output is clocked at the destination raster rate, the requirement is
     *
     *      T >= reach * line_time
     *
     * independent of slice height -- output for source row r is producible once
     * slice floor((r+reach)/sh) has landed and is due at r*line + T, and
     * maximising over r puts the worst case at r = m*sh - reach.  Verified by
     * row-by-row simulation over every supported (format, slice height, reach),
     * not by algebra alone (tests/test_uc.c).
     *
     * PLUS ONE LINE for OMC_XSL level 3: slice k rewrites the LAST ROW of slice
     * k-1 when it reconstructs, so that row is not final until one slice period
     * later.  It sits at the end of its slice and therefore already had sh-1
     * lines of slack, so the net cost is exactly one line -- not the whole slice
     * period a strictly row-streaming sink would otherwise have to assume.
     *
     * The price is an output buffer of the filter aperture plus one slice
     * (<= 68 rows at the steepest supported ratio) and a free-running output
     * clock; a genlocked facility has both.  An integration that cannot hand
     * rows over this way must declare cfg.uc_out_batched and take the older,
     * higher figure. */
    per = (reach + slice_h - 1) / slice_h;      /* slice-batched charge */
    total = slice_h * line_ms + slice_ms + 2 * line_ms
            + (batched ? per * slice_ms
                       : (reach ? (reach + 1) * line_ms : 0.0));
    if (!batched) per = 0;                      /* the charge is in LINES now */
    if (total_ms) *total_ms = total;
    if (periods) *periods = per;
    /* Below B4's floor is a FORMAT refusal, and it outranks the latency verdict
     * -- it would be wrong to describe a conversion the codec does not carry as
     * merely expensive.  It is reported LAST so the caller still receives the
     * latency figures: a bench raster below the floor is a perfectly ordinary
     * thing to measure, and the harness measures plenty of them. */
    if (!omc_uc_format_supported(dw, dh)) return -4;
    /* POSITIVE means "buildable, but declare it"; NEGATIVE means "cannot".
     * Those are different answers and conflating them was a policy error: a
     * conversion this operator can perform correctly, at a latency the caller
     * is told, is not the same thing as a ratio there are no coefficients for.
     * A2 is a property of the contribution PRODUCT, and a facility that wants
     * 720p50 -> 360p on a leg where 1.06 ms is fine should get it -- with the
     * figure in front of it, not with a refusal. */
    return total < 1.0 ? 0 : 1;
}

/* Worst-case vertical reach of the rational path, in SOURCE rows: the 12-tap
 * aperture alone, because there is no cascaded stage.  6 <= slice_h = 8, so the
 * rational path also costs exactly one slice period. */
int omc_uc_scale_reach(void) { return OMC_UC_KTAPS / 2; }

/* ------------------------------------------------------------ aspect framing
 * Pillarbox / letterbox / 14:9 / centre-cut, i.e. an aspect conversion.
 *
 * This is bookkeeping around the scaler rather than new signal processing: the
 * ACTIVE picture is a rational conversion of a source CROP into a destination
 * RECT, and everything outside that rect is filled with a constant.  Both the
 * crop and the rect are the caller's geometry decision -- 16:9 into 4:3 with
 * bars top and bottom, 4:3 into 16:9 with bars left and right, the 14:9
 * compromise, or a centre cut that crops instead of barring.
 *
 * Two properties are worth having in code rather than in a note:
 *
 *   - the bars are written ONCE, from the fill level, and the scaler never
 *     touches them.  So a bar is exactly the level asked for, with no ringing
 *     leaking into it from the active picture edge -- which is the defect
 *     section 10.5 of the delivery document records finding in a real
 *     pillarbox, from the opposite direction;
 *   - the crop is honoured by the SCALER's own edge extension.  Passing an
 *     offset pointer and the source stride makes uc_mir() mirror at the crop
 *     boundary, which is what a crop should do; mirroring at the full picture
 *     edge would pull content from outside the crop into it.
 *
 * The rect's HORIZONTAL placement and width must be even so a 4:2:2 chroma
 * plane can carry the same geometry at half width.  The vertical is left free
 * on purpose: the standard 16:9-into-4:3 letterbox is 1440x810 active in a
 * 1440x1080 raster, i.e. 135-line bars, and requiring even rows would refuse
 * the commonest conversion there is.  (4:2:0 would need both; B2 puts 4:2:0
 * out of scope.)  Returns 0, -1 on a bad argument, or whatever
 * omc_uc_scale_plane() returns for an unsupported ratio. */
int omc_uc_frame_plane(const omc_uc_t *u,
                       const uint16_t *src, int ss, int sw, int sh,
                       int sx, int sy, int scw, int sch,
                       uint16_t *dst, int ds, int dw, int dh,
                       int dx, int dy, int dcw, int dch,
                       uint16_t fill, int mirror)
{
    int r, c;
    if (!u || !src || !dst) return -1;
    if (sx < 0 || sy < 0 || scw < 2 || sch < 2 || sx + scw > sw || sy + sch > sh)
        return -1;
    if (dx < 0 || dy < 0 || dcw < 2 || dch < 2 || dx + dcw > dw || dy + dch > dh)
        return -1;
    if ((dx | dcw) & 1) return -1;      /* 4:2:2 chroma geometry, see above */

    for (r = 0; r < dh; r++) {                  /* bars, written once */
        uint16_t *o = dst + (size_t)r * ds;
        if (r < dy || r >= dy + dch) {
            for (c = 0; c < dw; c++) o[c] = fill;
        } else {
            for (c = 0; c < dx; c++) o[c] = fill;
            for (c = dx + dcw; c < dw; c++) o[c] = fill;
        }
    }
    if (omc_uc_scale_plane(u, src + (size_t)sy * ss + sx, ss, scw, sch,
                           dst + (size_t)dy * ds + dx, ds, dcw, dch) < 0)
        return -1;
    /* Horizontal mirror, applied to the framed rect only.  It is a reversal
     * WITHIN a line, so it needs nothing the line does not already hold: no
     * extra reach, no extra slice period, no extra memory.  That is why this
     * flip is offered and the other three are not. */
    if (mirror)
        for (r = 0; r < dch; r++) {
            uint16_t *o = dst + (size_t)(dy + r) * ds + dx;
            for (c = 0; c < dcw / 2; c++) {
                uint16_t t = o[c];
                o[c] = o[dcw - 1 - c];
                o[dcw - 1 - c] = t;
            }
        }
    return 0;
}

/* ------------------------------------------------------------------- down
 * Exact integer inverse: undo the horizontal lifting level, then the vertical
 * one.  With the Reference-mode detail bands (H == 0) the recovered update
 * terms are zero and this reduces to lattice decimation -- but it is written
 * in full so the inverse holds for any detail band a future profile may carry.
 */
/* Window-aware row getter: `p` holds rows [lo, lo+nb) of a plane whose true
 * height is `n`, so mirroring is done against the TRUE height and then mapped
 * into the window.  This is what makes banding exact rather than approximate --
 * mirroring at the window edge would fabricate content the whole-plane call
 * never sees.  The window is guaranteed by the caller to cover every row the
 * predictor can reach; if it ever did not, the clamp below would silently
 * differ from the whole-plane result, which is exactly what the band gate in
 * tests/test_uc.c exists to catch. */
typedef struct { const int32_t *p; int stride, len, lo, nb, n; } uc_win_t;

static void uc_get_win(void *ctx, int i, int32_t *out)
{
    const uc_win_t *wn = (const uc_win_t *)ctx;
    int r = uc_mir(i, wn->n) - wn->lo;
    if (r < 0) r = 0;
    if (r >= wn->nb) r = wn->nb - 1;
    memcpy(out, wn->p + (size_t)r * wn->stride, sizeof(int32_t) * wn->len);
}

int omc_uc_down_plane_band(const omc_uc_t *u, const uint16_t *src, int ss,
                           int w, int h, uint16_t *dst, int ds, int r0, int r1)
{
    int H2 = 2 * h;
    /* Rows of the INTERMEDIATE (horizontally-inverted) picture the vertical
     * inverse can reach for destination rows [r0, r1):  the 12-tap aperture,
     * the direction search's own reach, and the update's one-row look-back,
     * all doubled because intermediate rows are at twice the destination
     * pitch.  Generous by a couple of rows; the band gate proves the result is
     * identical to the whole-plane call, so the only cost of generosity is
     * memory. */
    const int MARG = 2 * (OMC_UC_KTAPS / 2 + 3) + 4;
    int lo, hi, nb, R, i, j, rc = -1;
    int32_t *inter = NULL, *ev = NULL, *hb = NULL, *ws = NULL, *p = NULL;
    int32_t *evr = NULL, *hv = NULL;
    uc_win_t wn;
    uc_col_t cc;

    if (!u || !src || !dst || w < 2 || h < 2) return -1;
    if (r0 < 0) r0 = 0;
    if (r1 > h) r1 = h;
    if (r1 <= r0) return 0;

    lo = 2 * r0 - MARG; if (lo < 0) lo = 0;
    hi = 2 * r1 + MARG; if (hi > H2) hi = H2;
    nb = hi - lo;

    inter = (int32_t *)malloc((size_t)nb * w * sizeof(int32_t));
    ev    = (int32_t *)malloc((size_t)nb * w * sizeof(int32_t));
    hb    = (int32_t *)malloc((size_t)nb * w * sizeof(int32_t));
    ws    = (int32_t *)malloc(omc_uc_scratch_bytes(w, h));
    p     = (int32_t *)malloc((size_t)(w > H2 ? w : H2) * sizeof(int32_t));
    if (!inter || !ev || !hb || !ws || !p) goto out;

    for (R = 0; R < nb; R++)
        for (j = 0; j < w; j++)
            ev[(size_t)R * w + j] = src[(size_t)(lo + R) * ss + 2 * j];

    /* horizontal inverse over the window's rows only */
    cc.band = ev; cc.rlo = lo; cc.nb = nb; cc.w = w; cc.h2 = H2;
    for (j = 0; j < w; j++) {
        uc_predict(u, &UC_PASS_H, uc_get_col, &cc, j, w, H2, p, ws);
        for (R = 0; R < nb; R++)
            hb[(size_t)R * w + j] =
                (int32_t)src[(size_t)(lo + R) * ss + 2 * j + 1] - p[lo + R];
    }
    for (R = 0; R < nb; R++)
        for (j = 0; j < w; j++) {
            int32_t hm = hb[(size_t)R * w + uc_mir(j - 1, w)];
            inter[(size_t)R * w + j] = ev[(size_t)R * w + j] +
                                       ((hm + hb[(size_t)R * w + j] + 2) >> 2);
        }

    /* vertical inverse for the requested destination rows */
    {
        int elo = (lo + 1) / 2, ehi = hi / 2, en = ehi - elo;   /* even rows held */
        /* The update term reads hv[uc_mir(i-1, h)].  At i = 0 that mirrors to
         * row 1 -- ABOVE the band, not below -- so the detail rows must extend
         * one row past r1 as well as one before r0. */
        int vlo = r0 - 1, vhi = r1 + 1;
        if (vlo < 0) vlo = 0;
        if (vhi > h) vhi = h;
        evr = (int32_t *)malloc((size_t)(en > 0 ? en : 1) * w * sizeof(int32_t));
        hv  = (int32_t *)malloc((size_t)(vhi - vlo) * w * sizeof(int32_t));
        if (!evr || !hv) goto out;
        for (i = 0; i < en; i++)
            memcpy(evr + (size_t)i * w, inter + (size_t)(2 * (elo + i) - lo) * w,
                   sizeof(int32_t) * w);
        wn.p = evr; wn.stride = w; wn.len = w; wn.lo = elo; wn.nb = en; wn.n = h;
        for (i = vlo; i < vhi; i++) {
            uc_predict(u, &UC_PASS_V, uc_get_win, &wn, i, h, w, p, ws);
            for (j = 0; j < w; j++)
                hv[(size_t)(i - vlo) * w + j] =
                    inter[(size_t)(2 * i + 1 - lo) * w + j] - p[j];
        }
        for (i = r0; i < r1; i++)
            for (j = 0; j < w; j++) {
                int im = uc_mir(i - 1, h);
                int32_t hm = hv[(size_t)(im - vlo) * w + j];
                int32_t v = evr[(size_t)(i - elo) * w + j] +
                            ((hm + hv[(size_t)(i - vlo) * w + j] + 2) >> 2);
                dst[(size_t)i * ds + j] = (uint16_t)v;
            }
    }
    rc = 0;
out:
    free(inter); free(ev); free(hb); free(ws); free(p); free(evr); free(hv);
    return rc;
}

int omc_uc_down_plane(const omc_uc_t *u, const uint16_t *src, int ss, int w, int h,
                      uint16_t *dst, int ds)
{
    return omc_uc_down_plane_band(u, src, ss, w, h, dst, ds, 0, h);
}
