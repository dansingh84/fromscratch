/* CDF 5/3 integer lifting wavelet (reversible), slice-local, shifts/adds only.
 * Provenance: Le Gall/Tabatabai 5/3 filter (1988) as integer lifting per
 * JPEG 2000 Part 1 (ISO/IEC 15444-1:2000, royalty-free baseline). C1-clean.
 */
#include "internal.h"

/* ---------------------------------------------------------------- sect.55
 * VERTICAL BOTTOM-EDGE EXTENSION (env OMC_VEXT; 0 = v5.0/v5.1.0 behaviour).
 *
 * THE DEFECT.  Whole-sample symmetric extension makes the LAST highpass of a
 * finite even-length run degenerate.  For every interior pair the 5/3 predict
 * is a three-tap average,
 *      H[i] = x[2i+1] - ((x[2i] + x[2i+2]) >> 1),
 * but at the last pair the extension supplies x[2i+2] := x[2i], so it becomes
 *      H[last] = x[n-1] - x[n-2],
 * a plain first difference.  The inverse degenerates the same way, and when
 * H[last] quantises to zero -- the common case at 0.5 bpp, and far commoner on
 * chroma, whose detail coefficients are small -- the reconstruction is
 *      x[n-1] = x[n-2]  exactly,
 * a REPLICATED ROW, where every interior odd row instead gets the smooth
 * average of its two neighbours.
 *
 * OMC applies TWO vertical levels, so the degeneracy COMPOUNDS: level 2 makes
 * the level-1 lowpass L[7] equal L[6] (picture row 14 pinned to row 12), then
 * level 1 pins row 13 to the same value.  The bottom quarter of every slice
 * collapses to one row.
 *
 * MEASURED (ledger sect.55, gfx/DNG arm, 1920x1080 4:2:2 10-bit, 0.5 bpp):
 * the fraction of samples exactly equal to the sample above is 0.532 (luma)
 * and 0.671 (Cb) at slice rows 13-14, against 0.12 / 0.10 at interior rows and
 * 0.029 / 0.027 in the SOURCE -- an 18x and 25x excess.  JPEG XS gen 1 at
 * 1.0 bpp shows a FLAT profile (0.135-0.152 luma, 0.091-0.113 Cb) with no
 * spike anywhere, which is the control that says this is OMC's and not the
 * rate's.  The displaced vertical change lands in one place: the Cb
 * row-to-row step at the slice seam is 12.17 against 5.7 in the interior, and
 * a doubled step at a fixed 16-row pitch is exactly a HORIZONTAL LINE.
 *
 * THE FIX.  At the bottom edge only, replace the mirrored sample with a LINEAR
 * EXTRAPOLATION of the two preceding even samples,
 *      x[2i+2] := 2*x[2i] - x[2i-2],
 * so the predictor continues the local trend instead of flattening it.  With
 * i == 0 (a two-sample run) there is no earlier even sample and the mirror is
 * kept.  Shifts, adds and one subtract; no multiply, no table, no state.
 *
 * REVERSIBILITY is untouched, and that is the whole reason this is safe: a
 * lifting step is exactly invertible for ANY predictor built from values both
 * sides already hold.  The forward predict reads the ORIGINAL even samples;
 * the inverse's first loop reconstructs exactly those even samples before the
 * second loop reads them.  Encoder and decoder therefore evaluate the same
 * expression on the same integers.  This is the same argument OMC_XSL's
 * cross-slice term at the TOP edge already rests on.
 *
 * STRENGTH.  Full linear continuation OVERSHOOTS: it assumes the trend runs on
 * past the slice, which pushes the reconstructed bottom rows beyond the true
 * value and makes the SEAM discontinuity larger -- measured, the Cb step at the
 * seam went 12.17 -> 19.42, trading the flatness defect for a worse line.  So
 * the continuation is scaled in quarters,
 *      x[2i+2] := x[2i] + (((x[2i] - x[2i-2]) * OMC_VEXT + 2) >> 2),
 * where 0 is the v5.0 mirror and 4 is full linear.  The shipped value is the
 * one that flattens the replication profile WITHOUT growing the seam; ledger
 * sect.55.4 sweeps every value and prints both faces of the defect side by
 * side, because a change that fixes one and worsens the other is not a fix.
 *
 * The rounding is symmetric (+2 before the >>2 on a value that may be
 * negative would bias toward zero; the expression below rounds the signed
 * product half-away-from-zero so that a run and its negation behave alike,
 * which matters because the biased pixel domain is signed either side of
 * mid-grey).
 *
 * NORMATIVE.  Both ends must agree, so enabling this is a bitstream change and
 * carries a stream-minor bump.
 *
 * DECISION (v5.3.6, 2026-09-08): NOT SHIPPED -- a qualified candidate at strength -2 on LEVEL 2
 * ONLY, held back by the legality contract.  With it on, the 24-frame rail-plate cut sequence
 * (G-T5-CUT24) commits out-of-range samples at the shipped refresh period: 4 at repair budget 13,
 * 1 at budget 14, and budget 16 breaks the gate's non-vacuity control (G-T5-GAMUT2d) -- while with
 * the mirror the same sequence is 0 at every period at budget 13.  Every boundary-touching change
 * measured this week (Agent 1's per-region vectors, the outside review's boundary-row rung, this
 * predictor) fails the same gate for the same reason: the repair is budgeted per slice and a
 * boundary edit couples the last row to the next slice.  The repair's granularity is the blocker
 * (codec expert question, WORK_QUEUE).  Everything below describes the candidate as qualified:
 * A NEGATIVE strength pulls the virtual sample back to the midpoint of the two even rows
 * above, so the last predict step becomes the two-sided 3:1 blend (3*x[2i] + x[2i-2])/4 to
 * rounding -- the higher codec expert's Way 1 (MEMO 026 sect.5.3), built and proven by
 * Agent 3 (perfect reconstruction over 1080 geometry/mode combinations, generation lock on
 * 24 arms per plane, exact CBR), and measured level by level by the outside review of
 * v5.3.5: level 1 alone does nothing; both levels grow the seam step (+3..+8 %) and the
 * slice-pitch periodicity; positive (extrapolating) strengths amplify the inherited error
 * (variance (9+1)/4 at +2) and raise chroma periodicity 10 %; -4 (the pure two-tap)
 * over-corrects the interior odd rows.  -2 on level 2 lowers replication, keeps the seam
 * step flat (+1 %) and lowers the periodicity on every plane.  Measured on v5.3.6 with the
 * grain fill OFF (the v5.3.5 default that reopened this defect), 12 frames, six cells:
 * VMAF-NEG +0.06 / +0.10 / +0.07 on dng 4:2:2 @0.5, @1.0 and 4:4:4 12-bit @1.0, 0.00 on
 * highwaydriveL, -0.04 on soccer2 (saturated), -0.52 on the 448x256 graphics crop (luma
 * -0.09 dB); replication excess at slice rows 13/14 cut from 15.6x to 5.1x, 19.2x to 2.5x
 * and 26x to 7x; no plane's row-15 bias moves by more than 0.3 code.  What it does NOT do:
 * the last row still carries ~1.3-1.5x the error of the even rows (the seam's line face,
 * docs/CHANGES_v5_3_6.md sect.D).  The rounding of the virtual sample is the symmetric
 * form below (the one measured); Agent 3's floor form (3a+b+2)>>2 is a different, equally
 * exact bitstream and was not the one qualified. */
int omc_vext = 0;       /* [V536] the level-2 3:1 blend is a qualified CANDIDATE, not shipped (see the decision note) */
/* Which vertical LEVEL the continuation applies to (env OMC_VEXT_LVL, bit 0 =
 * level 1, bit 1 = level 2; 3 = both, the unrestricted form).  The two levels
 * contribute the defect differently: level 2's degeneracy pins picture row 14
 * to row 12, and level 1's then pins row 13 to the same value, so the collapse
 * is a PRODUCT of the two.  Breaking either one alone breaks the product, and
 * level 2 is by far the cheaper place to do it -- its boundary row is one row
 * of a (sh/4) x (W/4) band against level 1's (sh/2) x (W/2). */
int omc_vext_lvl = 3;   /* [V536] both levers pinned in the decoder freeze */
static int vext_active = 0;   /* set by the caller for the level being run */

static inline int32_t vext_hi(const int32_t *x, int stride, int i, int nv)
{
    /* the sample one step past the last even sample of the run */
    (void)nv;
    if (!omc_vext || !vext_active || i == 0)
        return x[(2 * i) * stride];                       /* WSS mirror (v5.0) */
    {
        int32_t a = x[(2 * i) * stride], b = x[(2 * i - 2) * stride];
        int32_t d = (a - b) * omc_vext;
        d = d >= 0 ? (d + 2) >> 2 : -((-d + 2) >> 2);     /* symmetric rounding */
        return a + d;
    }
}

/* Forward 1D split of x[0..n) (n even) into L = x[0..n/2), H = x[n/2..n).
 * Lifting (symmetric edge extension):
 *   d[i] = x[2i+1] - ((x[2i] + x[2i+2]) >> 1)      (x[n] := x[n-2] -> uses s edge)
 *   s[i] = x[2i]   + ((d[i-1] + d[i] + 2) >> 2)    (d[-1] := d[0])
 */
/* OMC_XSL (cross-slice boundary term, band-fix §21): the vertical level-1
 * update's missing d[-1] is normally faked with a copy of d[0], which makes
 * every slice reconstruct blind to the slice above — the visible border.
 * When the caller supplies dm1 (second difference of the PREVIOUS slice's
 * last three DECODED rows: zero on ramps, carries real texture phase, known
 * identically to encoder and decoder), the update uses it instead.  The
 * lifting stays exactly invertible for ANY shared dm1. */
/* T5 PAD NEUTRALIZATION (minor 11).  nv is the number of VISIBLE samples of
 * this 1D run; nv == n for every ordinary run.  When nv < n (the last slice of
 * a frame coded taller than its display height) the run behaves as a transform
 * of length nv:
 *   - the whole-sample symmetric extension kicks in at nv, not at n, so no
 *     visible output ever reads a pad sample;
 *   - the pad pairs' outputs are forced to EXACTLY ZERO (they are read nowhere
 *     on the visible path, so this is free), which is a fixed point of code /
 *     decode and therefore survives every generation;
 *   - the inverse replicates the last visible sample across the pad run, so
 *     the committed pad rows are a pure function of the committed visible
 *     rows -- which is what lets a CROPPED baseband picture be re-padded to
 *     exactly the committed picture (docs/TEMPORAL_T5.md section 12).
 * With nv == n every branch below is identical to the pre-T5 code. */
/* [S5-DC] ZERO-MEAN LIFTING ROUNDING (sandbox S5.18).  Every rounding
 * constant in the lifting steps (predict >>1, update +2>>2, 9/7-M predict
 * +8>>4) is a round-half-UP: when a detail coefficient is quantised to zero
 * the picture keeps the forward's rounding and loses the coefficient that
 * carried its complement, and the picture's MEAN rises by ~1/8 code per 1-D
 * pass (measured: +0.44 code at 1 bpp on luma, the visible "OMC is slightly
 * redder" cast the owner saw on 2026-09-02).  The fix alternates the constant
 * by sample-pair index (i & 1): the lifting stays an exact integer bijection
 * for ANY per-index constant, lossless and the generation lock are untouched,
 * and the rounding error is zero-mean over every pair of samples.  Both ends,
 * normative (minor 15).  Cost in hardware: the index LSB. */
static void fwd1d(const int32_t *x, int n, int stride, int32_t *L, int32_t *H,
                  int use_dm1, int32_t dm1, int nv)
{
    int half = n / 2, hv = nv / 2;
    for (int i = 0; i < hv; i++) {
        int32_t s0 = x[(2 * i) * stride];
        int32_t s1 = (2 * i + 2 < nv) ? x[(2 * i + 2) * stride]
                                      : vext_hi(x, stride, i, nv);   /* sect.55 */
        H[i] = x[(2 * i + 1) * stride] - ((s0 + s1 + (i & 1)) >> 1);   /* [S5-DC] */
    }
    for (int i = 0; i < hv; i++) {
        int32_t dl = (i > 0) ? H[i - 1] : (use_dm1 ? dm1 : H[0]);
        L[i] = x[(2 * i) * stride] + ((dl + H[i] + 2 - (i & 1)) >> 2);  /* [S5-DC] */
    }
    for (int i = hv; i < half; i++) L[i] = H[i] = 0; /* pad pairs: neutralized */
}

static void inv1d(const int32_t *L, const int32_t *H, int n, int32_t *x, int stride,
                  int use_dm1, int32_t dm1, int nv)
{
    int hv = nv / 2;
    /* s[i] = L[i] - ((d[i-1] + d[i] + 2) >> 2) */
    for (int i = 0; i < hv; i++) {
        int32_t dl = (i > 0) ? H[i - 1] : (use_dm1 ? dm1 : H[0]);
        x[(2 * i) * stride] = L[i] - ((dl + H[i] + 2 - (i & 1)) >> 2);  /* [S5-DC] */
    }
    /* x[2i+1] = d[i] + ((s[2i] + s[2i+2]) >> 1); the i = hv-1 term takes the
     * same extension the forward took, so it never reads a pad sample */
    for (int i = 0; i < hv; i++) {
        int32_t s0 = x[(2 * i) * stride];
        int32_t s1 = (2 * i + 2 < nv) ? x[(2 * i + 2) * stride]
                                      : vext_hi(x, stride, i, nv);   /* sect.55 */
        x[(2 * i + 1) * stride] = H[i] + ((s0 + s1 + (i & 1)) >> 1);   /* [S5-DC] */
    }
    for (int r = nv; r < n; r++) /* pads: replicate the last visible sample */
        x[r * stride] = x[(nv - 1) * stride];
}

/* (9,7)-M reversible integer lifting: 4-tap dyadic predict (-1,9,9,-1)/16
 * (9x = 8x + x: shift+add), 2-tap update as in 5/3. Provenance: reversible
 * integer-to-integer wavelets, Adams & Kossentini, IEEE Trans. IP 2000 (and
 * earlier interpolating-filter literature) - expired vintage, royalty-free.
 * Whole-sample symmetric extension. */
static inline int32_t sat_s(const int32_t *s, int half, int j)
{
    if (j < 0) j = -j;
    else if (j >= half) j = 2 * half - 1 - j >= 0 ? 2 * half - 1 - j : 0;
    return s[j];
}

static void fwd1d_97(const int32_t *x, int n, int32_t *L, int32_t *H)
{
    int half = n / 2;
    /* gather evens first so predict can address them with extension */
    for (int i = 0; i < half; i++) L[i] = x[2 * i];
    for (int i = 0; i < half; i++) {
        int32_t a = sat_s(L, half, i - 1), b = L[i];
        int32_t cc = sat_s(L, half, i + 1), dd = sat_s(L, half, i + 2);
        /* 9*(s_i + s_{i+1}).  The sum is signed and routinely negative in
         * the biased pixel domain, and a left shift of a negative value is
         * not defined by C11 (6.5.7p4) -- found by UBSan.  Doing the shift
         * on the unsigned representation is defined for every value and
         * compiles to the same instruction on a two's-complement target,
         * so the transform's output is unchanged (verified byte-exact). */
        int32_t nine = (int32_t)((uint32_t)(b + cc) << 3) + (b + cc);
        H[i] = x[2 * i + 1] - ((nine - (a + dd) + 8 - (i & 1)) >> 4);   /* [S5-DC] */
    }
    for (int i = 0; i < half; i++) {
        int32_t dl = (i > 0) ? H[i - 1] : H[0];
        L[i] = L[i] + ((dl + H[i] + 2 - (i & 1)) >> 2);                  /* [S5-DC] */
    }
}

/* even-sample access with whole-sample symmetric extension, strided in x */
static inline int32_t sat_e(const int32_t *x, int half, int j)
{
    if (j < 0) j = -j;
    else if (j >= half) j = 2 * half - 1 - j >= 0 ? 2 * half - 1 - j : 0;
    return x[2 * j];
}

static void inv1d_97(const int32_t *Lc, const int32_t *Hc, int n, int32_t *x)
{
    int half = n / 2;
    /* evens into their final strided positions (no aliasing with odds) */
    for (int i = 0; i < half; i++) {
        int32_t dl = (i > 0) ? Hc[i - 1] : Hc[0];
        x[2 * i] = Lc[i] - ((dl + Hc[i] + 2 - (i & 1)) >> 2);           /* [S5-DC] */
    }
    for (int i = 0; i < half; i++) {
        int32_t a = sat_e(x, half, i - 1), b = x[2 * i];
        int32_t cc = sat_e(x, half, i + 1), dd = sat_e(x, half, i + 2);
        int32_t nine = (int32_t)((uint32_t)(b + cc) << 3) + (b + cc);
        x[2 * i + 1] = Hc[i] + ((nine - (a + dd) + 8 - (i & 1)) >> 4);   /* [S5-DC] */
    }
}

/* horizontal split of rows [r0, r0+nr) over cols [0, nc): in place into L|H
 * halves. filt97 selects the (9,7)-M filter (levels 1-2), else 5/3. */
static void split_h(int32_t *buf, int W, int r0, int nr, int nc, int32_t *tmp, int filt97)
{
    int half = nc / 2;
    for (int r = r0; r < r0 + nr; r++) {
        int32_t *row = buf + (size_t)r * W;
        if (filt97) fwd1d_97(row, nc, tmp, tmp + half);
        else fwd1d(row, nc, 1, tmp, tmp + half, 0, 0, nc);
        memcpy(row, tmp, sizeof(int32_t) * nc);
    }
}

static void join_h(int32_t *buf, int W, int r0, int nr, int nc, int32_t *tmp, int filt97)
{
    int half = nc / 2;
    for (int r = r0; r < r0 + nr; r++) {
        int32_t *row = buf + (size_t)r * W;
        if (filt97) {
            memcpy(tmp, row, sizeof(int32_t) * nc); /* Lc|Hc copy */
            inv1d_97(tmp, tmp + half, nc, row);
        } else {
            inv1d(row, row + half, nc, tmp, 1, 0, 0, nc);
            memcpy(row, tmp, sizeof(int32_t) * nc);
        }
    }
}

/* vertical split of cols [0, nc) over rows [0, nr): rows re-ordered into L|H */
/* The level-1 vertical boundary term d[-1] is passed EXPLICITLY through the
 * transform entry points.  It used to be a file-scope global set around each
 * call, which made two codec instances in one process share it -- breaking the
 * "instances share no mutable state" guarantee in omc1.h and racing outright
 * between threads (make test-threads failed every run). */
static void split_v(int32_t *buf, int W, int nr, int nc, int32_t *tmp,
                    const int32_t *d1m, int nv)
{
    int half = nr / 2;
    int32_t col[64] = {0}, Lc[32], Hc[32];
    for (int c = 0; c < nc; c++) {
        for (int r = 0; r < nr; r++) col[r] = buf[(size_t)r * W + c];
        fwd1d(col, nr, 1, Lc, Hc, d1m != 0, d1m ? d1m[c] : 0, nv);
        for (int r = 0; r < half; r++) {
            buf[(size_t)r * W + c] = Lc[r];
            buf[(size_t)(r + half) * W + c] = Hc[r];
        }
    }
    (void)tmp;
}

static void join_v(int32_t *buf, int W, int nr, int nc, int32_t *tmp,
                   const int32_t *d1m, int nv)
{
    int half = nr / 2;
    int32_t col[64], Lc[32], Hc[32];
    for (int c = 0; c < nc; c++) {
        for (int r = 0; r < half; r++) {
            Lc[r] = buf[(size_t)r * W + c];
            Hc[r] = buf[(size_t)(r + half) * W + c];
        }
        inv1d(Lc, Hc, nr, col, 1, d1m != 0, d1m ? d1m[c] : 0, nv);
        for (int r = 0; r < nr; r++) buf[(size_t)r * W + c] = col[r];
    }
    (void)tmp;
}

/* Full slice forward transform: 2 vertical x 5 horizontal levels; horizontal
 * levels 1-2 use (9,7)-M, the rest 5/3 (see internal.h and docs/BITSTREAM.md). */
/* vv = visible rows of this slice (vv == sh for every slice but the last of a
 * padded frame).  Only the VERTICAL stages take it: the horizontal stages run
 * on full rows, and a neutralized (all-zero) row stays all-zero through them. */
void omc_slice_fwd_p(int32_t *buf, int W, int sh, int32_t *tmp, int vv,
                     const int32_t *d1m)
{
    vext_active = (omc_vext_lvl >> 0) & 1;
    split_v(buf, W, sh, W, tmp, d1m, vv);   /* V level 1: rows -> L|H    */
    vext_active = (omc_vext_lvl >> 1) & 1;
    split_h(buf, W, 0, sh, W, tmp, 1);           /* H level 1 on all rows        */
    split_v(buf, W, sh / 2, W / 2, tmp, 0, vv / 2); /* V level 2 on LL1 cols     */
    vext_active = 0;
    split_h(buf, W, 0, sh / 2, W / 2, tmp, 1);   /* H level 2 on LL1 rows        */
    split_h(buf, W, 0, sh / 4, W / 4, tmp, 0);   /* H level 3 on LL2 rows        */
    split_h(buf, W, 0, sh / 4, W / 8, tmp, 0);   /* H level 4                    */
    split_h(buf, W, 0, sh / 4, W / 16, tmp, 0);  /* H level 5                    */
}

void omc_slice_inv_p(int32_t *buf, int W, int sh, int32_t *tmp, int vv,
                     const int32_t *d1m)
{
    join_h(buf, W, 0, sh / 4, W / 16, tmp, 0);
    join_h(buf, W, 0, sh / 4, W / 8, tmp, 0);
    join_h(buf, W, 0, sh / 4, W / 4, tmp, 0);
    join_h(buf, W, 0, sh / 2, W / 2, tmp, 1);
    vext_active = (omc_vext_lvl >> 1) & 1;
    join_v(buf, W, sh / 2, W / 2, tmp, 0, vv / 2);
    vext_active = (omc_vext_lvl >> 0) & 1;
    join_h(buf, W, 0, sh, W, tmp, 1);
    join_v(buf, W, sh, W, tmp, d1m, vv);
    vext_active = 0;
}

void omc_slice_fwd(int32_t *buf, int W, int sh, int32_t *tmp)
{
    omc_slice_fwd_p(buf, W, sh, tmp, sh, 0);
}

void omc_slice_inv(int32_t *buf, int W, int sh, int32_t *tmp)
{
    omc_slice_inv_p(buf, W, sh, tmp, sh, 0);
}
