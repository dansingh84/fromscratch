/* OMC-CC — colour-space conversion.  See include/omc_cc.h for the rationale,
 * the boundary (no tone mapping) and the C3 argument.
 *
 * Datapath: table lookups, constant multiplies written as shift-adds, and one
 * fixed 12-step binary search.  No dividers, no floating point, no libm, and no
 * data-dependent loop bound.
 */
#include <string.h>

#include "omc_cc.h"

#include "cc_tab.c.inc"

/* SHIFTS ON SIGNED VALUES.  A left shift of a negative value is not
 * defined by C11 (6.5.7p4); these shift-and-add multiplies routinely see
 * negative operands.  Shifting the unsigned representation is defined for
 * every value and compiles to the same instruction on a two's-complement
 * target, so the fixed-point results are unchanged (verified byte-exact
 * against the previous build).  Found by UBSan. */
#define OMC_SHL(v, n) ((int32_t)((uint32_t)(v) << (n)))
#define OMC_SHL64(v, n) ((int64_t)((uint64_t)(v) << (n)))

#define CC_QS 15                       /* matrix coefficients are Q15        */

/* Round-to-nearest de-scale of a Q15 accumulator.  Every matrix product in this
 * file goes through it.  An earlier draft used a bare `>> CC_QS`, which floors:
 * that is a systematic half-count downward bias on EVERY component of EVERY
 * matrix, and there are four matrix stages in one conversion, so a 709 -> 2020
 * -> 709 round trip inherited eight of them. */
#define CC_RS(x) (int32_t)(((x) + (1 << (CC_QS - 1))) >> CC_QS)
/* The same, for the primaries stage, which carries more fraction bits. */
#define CC_RP(x) (((x) + ((int64_t)1 << (CC_QP - 1))) >> CC_QP)
#define CC_CLAMP(v, hi) do { if ((v) < 0) (v) = 0; else if ((v) > (hi)) (v) = (hi); } while (0)

/* Multiplier-free constant multiply, identical in form to the upconverter's
 * uc_mul_sa(): the coefficient is fixed per configuration, so in hardware this
 * is a hard-wired shift-add chain and the loop does not exist.  Bounded at 21
 * iterations (|c| < 2^21 for every published coefficient -- the largest is the
 * BT.2020 -> BT.709 red term, 1.6605 in Q20 = 1741832), no early exit, so the
 * count is the worst case and the typical case alike. */
static int64_t cc_mul_sa(int32_t c, int64_t x)
{
    int64_t acc = 0;
    int neg = c < 0, b;
    if (neg) c = -c;
    for (b = 0; b < 21; b++)
        if ((c >> b) & 1) acc += OMC_SHL64(x, b);
    return neg ? -acc : acc;
}

static const int32_t *cc_prim_mat(const omc_cc_t *c)
{
    int s = c->src_prim, d = c->dst_prim;
    if (s == OMC_CC_P_CUSTOM || d == OMC_CC_P_CUSTOM) return c->prim_custom;
    if (s == d) return CC_P_IDENT;
    if (s == OMC_CC_P_BT709 && d == OMC_CC_P_BT2020) return CC_P_709_2020;
    if (s == OMC_CC_P_BT2020 && d == OMC_CC_P_BT709) return CC_P_2020_709;
    return 0;
}

static int cc_trc_idx(int t)
{
    return t == OMC_CC_T_GAMMA ? 0 : t == OMC_CC_T_HLG ? 1 : -1;   /* [V536] no PQ */
}

static const int32_t *cc_y2r(int m)
{
    return m == OMC_CC_M_BT709 ? CC_M_Y2R_709 :
           m == OMC_CC_M_BT2020 ? CC_M_Y2R_2020 :
           m == OMC_CC_M_BT601 ? CC_M_Y2R_601 : 0;
}

static const int32_t *cc_r2y(int m)
{
    return m == OMC_CC_M_BT709 ? CC_M_R2Y_709 :
           m == OMC_CC_M_BT2020 ? CC_M_R2Y_2020 :
           m == OMC_CC_M_BT601 ? CC_M_R2Y_601 : 0;
}

/* Index of the leading 1.  Six fixed compares, no data-dependent count: in
 * hardware this is a priority encoder, which is combinational. */
static int cc_msb(int64_t x)
{
    int p = 0;
    if (x >> 32) { p += 32; x >>= 32; }
    if (x >> 16) { p += 16; x >>= 16; }
    if (x >>  8) { p +=  8; x >>=  8; }
    if (x >>  4) { p +=  4; x >>=  4; }
    if (x >>  2) { p +=  2; x >>=  2; }
    if (x >>  1) { p +=  1; }
    return p;
}

/* log2 of a positive integer, Q16.  Priority encoder, one shift, one lookup,
 * one add.  Zero and below return a floor rather than minus infinity so the
 * arithmetic downstream stays bounded; 2^-48 is far below any code the tables
 * can produce, so the clamp is unreachable from real picture data. */
#define CC_LOG2_FLOOR (-(48 << 16))
static int32_t cc_log2i(int64_t x)
{
    int p;
    int32_t idx;
    if (x <= 0) return CC_LOG2_FLOOR;
    p = cc_msb(x);
    idx = (int32_t)((p >= 12 ? (x >> (p - 12)) : (x << (12 - p))) - 4096);
    return (int32_t)(p << 16) + CC_LOG2M[idx];
}

/* log2 of a Q28 linear value, expressed as log2 of the NORMALISED quantity --
 * i.e. 1.0 in the table maps to 0.  cc_log2i() returns the log2 of the stored
 * integer, so the Q28 scale has to come back off; forgetting that subtraction
 * pushed every tone-mapped pixel to white, which is the kind of error that is
 * obvious in a ramp and invisible in a still. */
static int32_t cc_log2n(int64_t x)
{
    return cc_log2i(x) - (CC_QL << 16);
}

/* 2^l, where l is Q16 log2 of a value normalised to 1.0, returned in Q28.
 * Integer part of the exponent is a shift; the fraction is one lookup. */
static int64_t cc_exp2q28(int32_t l)
{
    int64_t t = (int64_t)l + ((int64_t)CC_QL << 16);
    int i, f;
    if (t < 0) return 0;
    if (t > ((int64_t)61 << 16)) t = (int64_t)61 << 16;
    i = (int)(t >> 16);
    /* Round the fractional index rather than truncating it: one adder, and it
     * halves this stage's contribution to the log/exp round-trip error. */
    f = (int)(((t & 0xFFFF) + 8) >> 4);
    if (f >= CC_N) { f -= CC_N; i++; }
    if (i >= 30) return (int64_t)CC_EXP2F[f] << (i - 30);
    return ((int64_t)CC_EXP2F[f] + ((int64_t)1 << (29 - i))) >> (30 - i);
}

/* Resolve the declared tone-map curve for this tuple, or NULL. */
static const cc_tm_entry_t *cc_find_tm(int st, int sp, int dt, int dp)
{
    int i;
    for (i = 0; i < CC_TM_NTAB; i++)
        if (CC_TM_TAB[i].src_trc == st && CC_TM_TAB[i].dst_trc == dt &&
            CC_TM_TAB[i].src_peak == sp && CC_TM_TAB[i].dst_peak == dp)
            return &CC_TM_TAB[i];
    return 0;
}

/* BT.2100 HLG system gamma at 1000 cd/m2 is exactly 1.2, and 1000 is the only
 * HLG peak this build declares a curve for, so these are constants rather than
 * a function of the declared peak. */
#define CC_HLG_G    39322      /* 1.2      Q15 */
#define CC_HLG_GM1   6554      /* 0.2      Q15, the OOTF exponent             */
#define CC_HLG_INVG (-5461)    /* (1-g)/g  Q15, the inverse OOTF exponent     */

int omc_cc_validate(const omc_cc_t *c)
{
    if (!c || c->depth < 8 || c->depth > 12) return -1;
    if (cc_trc_idx(c->src_trc) < 0 || cc_trc_idx(c->dst_trc) < 0) return -1;
    if (!cc_y2r(c->src_mtx) || !cc_r2y(c->dst_mtx)) return -1;
    if (c->src_prim == OMC_CC_P_CUSTOM || c->dst_prim == OMC_CC_P_CUSTOM) {
        int r;
        if (!c->prim_custom) return -4;
        for (r = 0; r < 3; r++)
            if (c->prim_custom[r*3] + c->prim_custom[r*3+1] +
                c->prim_custom[r*3+2] != (1 << CC_QP)) return -4;
    } else if (!cc_prim_mat(c)) return -1;
    /* A transfer change is a TONE MAP.  With tone mapping OFF it is refused
     * rather than approximated -- converting HLG to gamma without one silently
     * clips everything above the SDR range.  With it ON, only the published
     * tuples are accepted: a tone map nobody has constants for is a tone map
     * nobody can reproduce. */
    if (c->src_trc != c->dst_trc || c->tone_map) {
        if (!c->tone_map) return -2;
        if (!cc_find_tm(c->src_trc, c->src_peak, c->dst_trc, c->dst_peak))
            return -3;
    }
    return 0;
}

/* Inverse transfer: the code whose linear value is NEAREST `lin`.
 * A fixed 12-step binary search over the 4096-entry forward table -- compares
 * and lookups only, no division, and the same 12 steps every time regardless of
 * the data, so the operation count is not content-dependent.  12 steps is exact
 * for 4096 entries, so there is no accuracy/latency trade here.
 *
 * The final compare picks the nearer of the two bracketing codes.  Without it
 * the search returns the CEILING, which is another systematic half-code upward
 * bias stacked on top of the matrix flooring -- in the wrong direction, so the
 * two do not cancel, they just make the error harder to attribute. */
static int cc_inv_trc(const int32_t *tab, int64_t lin)
{
    int lo = 0, hi = CC_N - 1, k;
    if (lin <= 0) return 0;
    if (lin >= tab[CC_N - 1]) return CC_N - 1;
    for (k = 0; k < 12; k++) {
        int mid = (lo + hi) >> 1;
        if ((int64_t)tab[mid] < lin) lo = mid + 1; else hi = mid;
    }
    if (lo > 0 && (lin - tab[lo - 1]) < ((int64_t)tab[lo] - lin)) lo--;
    return lo;
}

int omc_cc_convert(const omc_cc_t *c,
                   uint16_t *y, int ys, uint16_t *cb, int cbs,
                   uint16_t *cr, int crs, int w, int h)
{
    const int32_t *P, *Y2R, *R2Y, *ES, *ED;
    int rc = omc_cc_validate(c);
    int shift = 12 - c->depth;          /* tables are 12-bit indexed */
    int32_t rnd = shift ? (1 << (shift - 1)) : 0;
    int32_t maxv, unit, mid, ylo_s, yrng_s, crng_s, ylo_d, yrng_d, crng_d;
    int32_t ryr, rcr, ryf, rcf;   /* reciprocals, Q15 -- see below */
    const cc_tm_entry_t *tm = 0;
    int32_t l2sp = 0, l2dp = 0, sat = 1 << CC_QS;
    int shlg = 0, dhlg = 0;
    int i, j;

    if (rc) return rc;
    /* A conversion to itself must not touch the picture.  Without this the
     * matrix pair round trips to within a count and a pass-through leg would
     * accumulate generational error for no reason at all -- and a contribution
     * chain is exactly where a no-op leg gets inserted by a control plane that
     * does not know the source and destination already match. */
    if (c->src_prim == c->dst_prim && c->src_mtx == c->dst_mtx &&
        c->src_trc == c->dst_trc && c->src_full_range == c->dst_full_range &&
        !c->tone_map && c->src_prim != OMC_CC_P_CUSTOM)
        return 0;
    P = cc_prim_mat(c);
    Y2R = cc_y2r(c->src_mtx);
    R2Y = cc_r2y(c->dst_mtx);
    ES = CC_EOTF[cc_trc_idx(c->src_trc)];
    ED = CC_EOTF[cc_trc_idx(c->dst_trc)];

    /* EVERYTHING INSIDE THE LOOP IS 12-BIT.  The samples arrive at `depth` and
     * leave at `depth`, but an 8- or 10-bit intermediate R'G'B' throws away
     * precision the transfer tables are perfectly able to carry, and the throw
     * happens four times per conversion.  Widening to the table's own 12-bit
     * grid costs one shift on the way in and one on the way out; `unit` is
     * maxv << shift rather than 4095 so the widening is exact and reversible
     * (1023 -> 4092 -> 1023), and every table index stays below CC_N. */
    maxv = (1 << c->depth) - 1;
    unit = maxv << shift;
    mid  = (1 << (c->depth - 1)) << shift;
    /* Source and destination ranges are INDEPENDENT.  Limited <-> full is a
     * conversion in its own right -- the one every plant needs when broadcast
     * video meets graphics, and the one that is silently wrong more often than
     * any matrix. */
    if (c->src_full_range) { ylo_s = 0; yrng_s = unit; crng_s = unit; }
    else { ylo_s  = (16 << (c->depth - 8)) << shift;
           yrng_s = (219 << (c->depth - 8)) << shift;
           crng_s = (224 << (c->depth - 8)) << shift; }
    if (c->dst_full_range) { ylo_d = 0; yrng_d = unit; crng_d = unit; }
    else { ylo_d  = (16 << (c->depth - 8)) << shift;
           yrng_d = (219 << (c->depth - 8)) << shift;
           crng_d = (224 << (c->depth - 8)) << shift; }
    if (c->tone_map) {
        tm = cc_find_tm(c->src_trc, c->src_peak, c->dst_trc, c->dst_peak);
        sat = tm->sat;
        shlg = c->src_trc == OMC_CC_T_HLG;
        dhlg = c->dst_trc == OMC_CC_T_HLG;
        /* Where 1.0 in each transfer's table sits, in absolute nits: the peak
         * the caller declared (gamma and HLG; there is no PQ in this codec). */
        l2sp = cc_log2i(c->src_peak);
        l2dp = cc_log2i(c->dst_peak);
    }
    /* Range normalisation used to divide by yrng/crng PER SAMPLE.  Those are
     * configuration constants, so the reciprocals are formed ONCE here and the
     * per-sample path is a shift-add multiply -- no divider, which is what C3
     * requires and what the rest of this codebase already does.  All four fit
     * in 17 bits, which is cc_mul_sa()'s bound: the largest is 8-bit limited
     * range, (4080 << 15) / 3504 = 38152. */
    ryr = (int32_t)(((int64_t)unit << CC_QS) / yrng_s);
    rcr = (int32_t)(((int64_t)unit << CC_QS) / crng_s);
    ryf = (int32_t)(((int64_t)yrng_d << CC_QS) / unit);
    rcf = (int32_t)(((int64_t)crng_d << CC_QS) / unit);

    for (i = 0; i < h; i++) {
        uint16_t *py = y + (size_t)i * ys;
        uint16_t *pb = cb + (size_t)i * cbs;
        uint16_t *pr = cr + (size_t)i * crs;
        for (j = 0; j < w; j++) {
            int32_t Yv, Cbv, Crv, R, G, B, er, eg, eb, ny, ncb, ncr;
            int64_t lr, lg, lb, or_, og, ob;

            /* --- YCbCr -> R'G'B', normalised to 0..unit ------------------- */
            Yv  = CC_RS(cc_mul_sa(ryr, ((int64_t)py[j] << shift) - ylo_s));
            Cbv = CC_RS(cc_mul_sa(rcr, ((int64_t)pb[j] << shift) - mid));
            Crv = CC_RS(cc_mul_sa(rcr, ((int64_t)pr[j] << shift) - mid));

            R = CC_RS(cc_mul_sa(Y2R[0], Yv) + cc_mul_sa(Y2R[1], Cbv) + cc_mul_sa(Y2R[2], Crv));
            G = CC_RS(cc_mul_sa(Y2R[3], Yv) + cc_mul_sa(Y2R[4], Cbv) + cc_mul_sa(Y2R[5], Crv));
            B = CC_RS(cc_mul_sa(Y2R[6], Yv) + cc_mul_sa(Y2R[7], Cbv) + cc_mul_sa(Y2R[8], Crv));
            CC_CLAMP(R, unit);
            CC_CLAMP(G, unit);
            CC_CLAMP(B, unit);

            /* --- to linear light ------------------------------------------ */
            lr = ES[R];
            lg = ES[G];
            lb = ES[B];

            /* --- primaries, in linear light ------------------------------- */
            or_ = CC_RP(cc_mul_sa(P[0], lr) + cc_mul_sa(P[1], lg) + cc_mul_sa(P[2], lb));
            og  = CC_RP(cc_mul_sa(P[3], lr) + cc_mul_sa(P[4], lg) + cc_mul_sa(P[5], lb));
            ob  = CC_RP(cc_mul_sa(P[6], lr) + cc_mul_sa(P[7], lg) + cc_mul_sa(P[8], lb));
            /* A colour outside the DESTINATION gamut lands negative here.  It is
             * clipped, and that is the honest answer: the destination cannot
             * show it.  2020 -> 709 does this constantly and legitimately. */
            if (or_ < 0) or_ = 0;
            if (og < 0) og = 0;
            if (ob < 0) ob = 0;

            /* --- tone map, entirely in the log domain ---------------------- *
             * The gain depends on the pixel's own luminance, so applying it is
             * a variable times a variable -- the per-pixel multiplier C3
             * forbids.  In log2 it is an add.  Every step below is a lookup, a
             * shift, an add or a CONSTANT multiply (which is a shift-add
             * chain): nothing here is a multiplier. */
            if (tm) {
                int64_t Yl = CC_RS(cc_mul_sa(R2Y[0], or_) +
                                   cc_mul_sa(R2Y[1], og) +
                                   cc_mul_sa(R2Y[2], ob));
                int32_t l2r = cc_log2n(or_), l2g = cc_log2n(og),
                        l2b = cc_log2n(ob),  l2y = cc_log2n(Yl);
                int32_t l2Y, gq, idx;
                int32_t lr2, lg2, lb2, l2Yo;
                /* normalised -> absolute display luminance, in log2 nits.
                 * HLG's table is SCENE light, so the BT.2100 OOTF applies:
                 * L = Lw * Ys^(g-1) * s, which in log2 is a constant multiply
                 * and two adds. */
                if (shlg) {
                    int32_t k = (int32_t)CC_RS(cc_mul_sa(CC_HLG_GM1, l2y));
                    l2r += l2sp + k; l2g += l2sp + k; l2b += l2sp + k;
                    l2Y = l2sp + (int32_t)CC_RS(cc_mul_sa(CC_HLG_G, l2y));
                } else {
                    l2r += l2sp; l2g += l2sp; l2b += l2sp;
                    l2Y = l2y + l2sp;
                }
                /* the declared curve: log2 gain against log2 nits.  The index
                 * is a shift because the table's step was chosen to be a power
                 * of two -- no divider. */
                gq = 0;
                if (tm->gain) {
                    idx = (l2Y + CC_TM_BIAS) >> CC_TM_SHIFT;
                    if (idx < 0) idx = 0;
                    if (idx > CC_TM_N - 1) idx = CC_TM_N - 1;
                    gq = OMC_SHL((int32_t)tm->gain[idx], 6); /* Q10 -> Q16 */
                }
                l2Yo = l2Y + gq;
                /* Saturation: a declared exponent, published per curve, applied
                 * to the component's ratio to luminance.  sat == 1 is exactly
                 * the luminance-ratio gain; below 1 desaturates, which is what
                 * keeps a compressed highlight from turning into a colour. */
                lr2 = l2Yo + (int32_t)CC_RS(cc_mul_sa(sat, l2r - l2Y));
                lg2 = l2Yo + (int32_t)CC_RS(cc_mul_sa(sat, l2g - l2Y));
                lb2 = l2Yo + (int32_t)CC_RS(cc_mul_sa(sat, l2b - l2Y));
                /* absolute -> the destination table's normalisation, and the
                 * inverse OOTF if the destination is HLG */
                if (dhlg) {
                    int32_t k = (int32_t)CC_RS(cc_mul_sa(CC_HLG_INVG,
                                                         l2Yo - l2dp));
                    lr2 += k - l2dp; lg2 += k - l2dp; lb2 += k - l2dp;
                } else {
                    lr2 -= l2dp; lg2 -= l2dp; lb2 -= l2dp;
                }
                or_ = cc_exp2q28(lr2);
                og  = cc_exp2q28(lg2);
                ob  = cc_exp2q28(lb2);
            }

            /* --- back through the transfer -------------------------------- */
            er = cc_inv_trc(ED, or_);
            eg = cc_inv_trc(ED, og);
            eb = cc_inv_trc(ED, ob);
            if (er > unit) er = unit;
            if (eg > unit) eg = unit;
            if (eb > unit) eb = unit;

            /* --- R'G'B' -> YCbCr ------------------------------------------ */
            ny  = CC_RS(cc_mul_sa(R2Y[0], er) + cc_mul_sa(R2Y[1], eg) +
                        cc_mul_sa(R2Y[2], eb));
            ncb = CC_RS(cc_mul_sa(R2Y[3], er) + cc_mul_sa(R2Y[4], eg) +
                        cc_mul_sa(R2Y[5], eb));
            ncr = CC_RS(cc_mul_sa(R2Y[6], er) + cc_mul_sa(R2Y[7], eg) +
                        cc_mul_sa(R2Y[8], eb));

            /* --- back to signal range, then down to `depth` --------------- */
            ny  = ylo_d + CC_RS(cc_mul_sa(ryf, ny));
            ncb = mid + CC_RS(cc_mul_sa(rcf, ncb));
            ncr = mid + CC_RS(cc_mul_sa(rcf, ncr));
            ny  = (ny  + rnd) >> shift;
            ncb = (ncb + rnd) >> shift;
            ncr = (ncr + rnd) >> shift;
            CC_CLAMP(ny, maxv);
            CC_CLAMP(ncb, maxv);
            CC_CLAMP(ncr, maxv);
            py[j] = (uint16_t)ny;
            pb[j] = (uint16_t)ncb;
            pr[j] = (uint16_t)ncr;
        }
    }
    return 0;
}

int omc_cc_pipeline_clocks(int tone_map)
{
    return tone_map ? 64 : 32;
}

int omc_cc_selfcheck(void)
{
    int t, i, r;
    /* matrices: exact row sums.  A primaries row that sums to 32767 instead of
     * 32768 puts a permanent cast on every grey. */
    {
        const int32_t *M[] = { CC_P_709_2020, CC_P_2020_709, CC_P_IDENT };
        for (i = 0; i < 3; i++)
            for (r = 0; r < 3; r++)
                if (M[i][r*3] + M[i][r*3+1] + M[i][r*3+2] != (1 << CC_QP))
                    return -1;
    }
    {
        const int32_t *M[] = { CC_M_R2Y_709, CC_M_R2Y_2020, CC_M_R2Y_601 };
        for (i = 0; i < 3; i++) {
            if (M[i][0] + M[i][1] + M[i][2] != (1 << CC_QS)) return -2;
            if (M[i][3] + M[i][4] + M[i][5] != 0) return -2;   /* chroma is
                                                                * zero-sum: grey
                                                                * must give zero
                                                                * chroma        */
            if (M[i][6] + M[i][7] + M[i][8] != 0) return -2;
        }
    }
    /* YCbCr -> R'G'B': the LUMA COLUMN must be exactly unity and the two corner
     * zeros exactly zero.  That, not the row sum, is the property that makes a
     * grey stay grey: with Cb = Cr = 0 the three rows must reproduce Y exactly.
     * A previous revision protected the row sums here instead, which pushed a
     * count into Y2R[3] and put chroma on the neutral axis. */
    {
        const int32_t *M[] = { CC_M_Y2R_709, CC_M_Y2R_2020, CC_M_Y2R_601 };
        for (i = 0; i < 3; i++) {
            if (M[i][0] != (1 << CC_QS) || M[i][3] != (1 << CC_QS) ||
                M[i][6] != (1 << CC_QS)) return -5;
            if (M[i][1] != 0 || M[i][8] != 0) return -5;
        }
    }
    /* transfers: monotonic non-decreasing, zero at zero, and spanning the range */
    for (t = 0; t < CC_NTR; t++) {
        if (CC_EOTF[t][0] != 0) return -3;
        for (i = 1; i < CC_N; i++)
            if (CC_EOTF[t][i] < CC_EOTF[t][i - 1]) return -3;
        if (CC_EOTF[t][CC_N - 1] <= 0) return -3;
    }
    /* The shift-add chain must EQUAL the multiply for every published
     * coefficient over the whole datapath range.  This is the gate that catches
     * a coefficient overflowing cc_mul_sa()'s 21-bit bound -- the chain would
     * silently drop the high bits and the picture would be wrong in a way no
     * row-sum or monotonicity check can see.  Same discipline, and same reason,
     * as omc_uc_selfcheck_poly_mul(). */
    {
        const int32_t *M[] = { CC_P_709_2020, CC_P_2020_709, CC_P_IDENT,
                               CC_M_Y2R_709, CC_M_Y2R_2020, CC_M_Y2R_601,
                               CC_M_R2Y_709, CC_M_R2Y_2020, CC_M_R2Y_601 };
        /* the extremes of every value the chain ever sees: a linear-light
         * sample (Q28), a 12-bit code, and the signed chroma range */
        static const int64_t V[] = { 0, 1, -1, 4095, -4095, 2048, -2048,
                                     (int64_t)1 << CC_QL, -((int64_t)1 << CC_QL),
                                     ((int64_t)1 << CC_QL) + 12345 };
        int k, m;
        for (i = 0; i < 9; i++)
            for (r = 0; r < 9; r++)
                for (k = 0; k < (int)(sizeof V / sizeof V[0]); k++)
                    if (cc_mul_sa(M[i][r], V[k]) != (int64_t)M[i][r] * V[k])
                        return -6;
        /* and the range reciprocals, which are formed at run time from the
         * depth and the range flag -- every combination the API accepts */
        for (m = 8; m <= 12; m++)
            for (k = 0; k < 2; k++) {
                int32_t u = ((1 << m) - 1) << (12 - m);
                int32_t yr = k ? u : ((219 << (m - 8)) << (12 - m));
                int32_t cr = k ? u : ((224 << (m - 8)) << (12 - m));
                int32_t rr[4], q;
                rr[0] = (int32_t)(((int64_t)u << CC_QS) / yr);
                rr[1] = (int32_t)(((int64_t)u << CC_QS) / cr);
                rr[2] = (int32_t)(((int64_t)yr << CC_QS) / u);
                rr[3] = (int32_t)(((int64_t)cr << CC_QS) / u);
                for (q = 0; q < 4; q++)
                    if (cc_mul_sa(rr[q], 4095) != (int64_t)rr[q] * 4095 ||
                        cc_mul_sa(rr[q], -4095) != -(int64_t)rr[q] * 4095)
                        return -6;
            }
    }
    /* log2 / exp2: monotonic, anchored, and MUTUALLY INVERSE.  The round trip
     * is the gate that matters -- the tone-map datapath does its whole job
     * between these two, so an error here is an error on every pixel.  Swept
     * over the full Q28 range, the pair must return the value it was given to
     * within 1 part in 4000, which is the 12-bit mantissa's own resolution. */
    {
        int64_t v;
        if (CC_LOG2M[0] != 0) return -7;
        for (i = 1; i < CC_N; i++)
            if (CC_LOG2M[i] <= CC_LOG2M[i - 1]) return -7;
        if (CC_LOG2M[CC_N - 1] >= (1 << 16)) return -7;
        if (CC_EXP2F[0] != (1 << 30)) return -7;
        for (i = 1; i < CC_N; i++)
            if (CC_EXP2F[i] <= CC_EXP2F[i - 1]) return -7;
        /* Swept from 2^14 up: below that the Q28 grid itself is coarser than
         * the tolerance, so the test would be measuring integer rounding
         * rather than the tables. */
        for (v = 1 << 14; v < ((int64_t)1 << CC_QL); v += (v >> 3) + 1) {
            int64_t w = cc_exp2q28(cc_log2n(v));
            int64_t d = w > v ? w - v : v - w;
            if (d * 2000 > v) return -7;
        }
    }
    /* every declared tone-map tuple is unique and its table is in range */
    {
        int a, b;
        for (a = 0; a < CC_TM_NTAB; a++) {
            for (b = a + 1; b < CC_TM_NTAB; b++)
                if (CC_TM_TAB[a].src_trc == CC_TM_TAB[b].src_trc &&
                    CC_TM_TAB[a].dst_trc == CC_TM_TAB[b].dst_trc &&
                    CC_TM_TAB[a].src_peak == CC_TM_TAB[b].src_peak &&
                    CC_TM_TAB[a].dst_peak == CC_TM_TAB[b].dst_peak)
                    return -8;
            if (cc_trc_idx(CC_TM_TAB[a].src_trc) < 0 ||
                cc_trc_idx(CC_TM_TAB[a].dst_trc) < 0) return -8;
            /* a tone map must never brighten what it is compressing: every
             * gain in a peak-reducing curve is <= 1 (log2 gain <= 0) */
            if (CC_TM_TAB[a].gain && CC_TM_TAB[a].src_peak > CC_TM_TAB[a].dst_peak)
                for (i = 0; i < CC_TM_N; i++)
                    if (CC_TM_TAB[a].gain[i] > 0) return -8;
        }
    }
    /* the primaries matrices must be mutual inverses to within quantisation */
    {
        int a, b, k;
        for (a = 0; a < 3; a++)
            for (b = 0; b < 3; b++) {
                int64_t s = 0;
                for (k = 0; k < 3; k++)
                    s += (int64_t)CC_P_709_2020[a*3+k] * CC_P_2020_709[k*3+b];
                s >>= CC_QP;
                if (s < (a == b ? (1 << CC_QP) - 24 : -24) ||
                    s > (a == b ? (1 << CC_QP) + 24 : 24))
                    return -4;
            }
    }
    return 0;
}
