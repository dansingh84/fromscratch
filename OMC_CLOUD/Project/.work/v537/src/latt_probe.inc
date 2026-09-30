/* ==== [S2-STEP] NEW CODE: the constructive legality step and its probe (LEDGER_SANDBOX S2). ====
 * Everything in this file is new; nothing here is part of the legacy repair. ====
 *
 * ---- SANDBOX INSTRUMENT sect.S2.1: THE LATTICE PROBE (OMC_LATT_PROBE=1) ----
 *
 * Question it answers (LEDGER_SANDBOX.md S1.10 / S2): on a slice whose
 * committed picture leaves the legal range, does a LATTICE POINT exist --
 * reached by moving individual emitted coefficients by whole quantiser steps,
 * on the encoder's own reconstruction, with the encoder's own inverse
 * transform -- that puts every sample inside the margin the repair targets,
 * and how much picture energy does reaching it cost compared with what the
 * shipped iterative repair finally removed?
 *
 * It is an INSTRUMENT: it never changes what is emitted.  It runs once per
 * violating slice, at repair pass 0, on private copies of the coefficient
 * buffers, and prints one line per slice at the end of that slice's encode.
 *
 * Method: greedy coordinate descent on the exact integer inverse.  At each
 * step every coefficient whose synthesis support (GM_BASIS box) covers an
 * offending sample is a candidate; each candidate is moved by one quantiser
 * step (toward zero only in arm "red"; either direction in arm "both"); the
 * plane is inverse-transformed EXACTLY for each candidate and the move that
 * buys the most reduction of total out-of-margin distance per unit of
 * picture energy ((delta)^2 * ||g_b||^2) is applied.  No linearisation, no
 * shape, no pass schedule.  A grain-fill value at a moved position is
 * dropped (the shipped repair does the same via the per-band fill veto).
 *
 * FPGA note (owner rule, 2026-09-02): this search re-runs the slice inverse
 * per candidate and is NOT a production form.  Its job is to establish
 * whether the constructive answer exists and what it costs; the bounded
 * production form is designed only if the answer is yes. */

/* the step's margin per row (identical to the encoder's gm_need window): `cap` on the two
 * boundary rows so the barrier DISPLAY blend (<= cap) cannot carry them out of range.  After
 * the step closes a slice the legacy margin reserve (omc_gm_loopneed) is disarmed for it
 * (latt_closed): the blend is display-only and the in-loop edit is off (OMC_XSL_LOOPFREE), so a
 * blended sample that sits inside the cap of the rail is legal and has no downstream
 * consequence -- measured, LEDGER_SANDBOX S2.14 parts 2-4. */
static inline int32_t latt_margin(int r, int sh, int first, int last, int32_t cap)
{
    if (r == 0 && !first) return cap;
    if (r == sh - 1 && !last) return cap;
    if (omc_xsl_casc && ((r == 1 && !first) || (r == sh - 2 && !last))) return cap >> omc_xsl_casc;
    return 0;
}

static int32_t *latt_p0[OMC_NPLANES], *latt_last[OMC_NPLANES];
static int32_t *latt_cur[OMC_NPLANES], *latt_work[OMC_NPLANES];
static int32_t *latt_q[OMC_NPLANES];      /* q per position (band-flat) */
static int32_t *latt_work2[OMC_NPLANES];
static uint8_t *latt_mark[OMC_NPLANES];   /* candidate mark per position */
/* ============================================================ [A5-LATTMEMO]
 * Agent 5 / Task E.  The candidate search, memoised.
 *
 * WHAT IT REPLACES.  The move loop below re-scores EVERY marked candidate after
 * every accepted move.  Measured, that search is 35.4 % of the whole encoder on
 * spotrobot @0.4 -- 3.8x the cost of all the plane inverses in the step put
 * together, which is not where I expected to find it.
 *
 * WHY IT IS EXACTLY VALUE-PRESERVING.  latt_est_excess2() starts from `ex_now`
 * and adds (d1 - d0) ONLY over the candidate's own synthesis-support box,
 * reading `work` only inside that box.  So:
 *   - gain = ex - ex2 = -(sum of local deltas) is INDEPENDENT of `ex`, and
 *   - it depends on `work` only inside the candidate's support box.
 * An accepted move changes `work` only inside ITS support box.  A candidate
 * whose box does not intersect the moved box therefore has a bit-identical
 * gain and cost, and does not need re-scoring.  The selection rule
 * (`gain * bcost > bgain * cost`, strict, first-wins-ties) is a max over a
 * total order, so grouping the two directions per position and then comparing
 * positions in the same order picks the same winner.
 * Invalidation is deliberately CONSERVATIVE (a superset of the true overlap):
 * invalidating too much only costs time, never correctness.
 *
 * FPGA: no new arithmetic; 25 bytes per coefficient position per plane of
 * scratch (~1.5 MB at 1080p 4:2:2), which the 2026-09-04 part ruling makes
 * affordable.  No latency term, no bitstream effect. */
static int64_t *latt_cg[OMC_NPLANES];    /* cached gain per position */
static int64_t *latt_cc2[OMC_NPLANES];   /* cached cost per position */
static int32_t *latt_cnv[OMC_NPLANES];   /* cached winning new value */
static int32_t *latt_cnq[OMC_NPLANES];   /* cached winning new q */
static uint8_t *latt_cvalid[OMC_NPLANES];/* 0 = must re-score, 1 = cache good */
static uint8_t *latt_bad[OMC_NPLANES];    /* offending pixel mask */
static uint8_t *latt_forb[OMC_NPLANES];   /* arm E: positions whose estimate lied */
static int32_t *latt_need[OMC_NPLANES];   /* per-block allowance, codes (wash guard) */
static int32_t *latt_req[OMC_NPLANES];    /* per-pixel required move at pass 0 (signed), guard form 4 */
static int32_t *latt_plan[OMC_NPLANES];   /* diagnostic: the lattice point the step chose */
static int latt_plan_valid, latt_plan_slice;
static uint8_t *latt_bad0[OMC_NPLANES];   /* pass-0 offending mask (guard exempts these) */
static size_t latt_cap[OMC_NPLANES];
static int latt_have0, latt_passes;
static double latt_peak[OMC_NPLANES][OMC_NBANDS]; static int latt_peak_pw[OMC_NPLANES];
/* exact interior synthesis response of one coefficient per band, Q12, measured once per
 * geometry by impulse through the real inverse: g[b][(y - by0) * bw + (x - bx0)] */
typedef struct { int by0, by1, bx0, bx1, vd, hd; int32_t *g; } latt_basis_t;
static latt_basis_t latt_bas[OMC_NPLANES][OMC_NBANDS]; static int latt_bas_pw[OMC_NPLANES];

static void latt_measure_basis(ctx_common_t *c, int32_t *tmp, int p)
{
    int pw = plane_width(c, p), sh = c->sh;
    if (latt_bas_pw[p] == pw) return;
    size_t n = (size_t)pw * sh;
    int32_t *buf = calloc(n, sizeof(int32_t));
    omc_band_t bl[OMC_NBANDS];
    omc_band_layout(pw, sh, bl);
    for (int b = 0; b < OMC_NBANDS; b++) {
        latt_basis_t *B = &latt_bas[p][b];
        int vd = sh / bl[b].h, hd = pw / bl[b].w;
        int rr = bl[b].h / 2, cc = bl[b].w / 2;
        memset(buf, 0, n * sizeof(int32_t));
        buf[(size_t)(bl[b].r0 + rr) * pw + bl[b].c0 + cc] = 1 << 12;
        omc_slice_inv_p(buf, pw, sh, tmp, sh, 0);
        int y0 = sh, y1 = -1, x0 = pw, x1 = -1;
        for (int y = 0; y < sh; y++)
            for (int x = 0; x < pw; x++)
                if (buf[(size_t)y * pw + x]) {
                    if (y < y0) y0 = y;
                if (y > y1) y1 = y;
                    if (x < x0) x0 = x;
                    if (x > x1) x1 = x;
                }
        if (y1 < y0) { y0 = y1 = rr * vd; x0 = x1 = cc * hd; }
        B->by0 = y0 - rr * vd; B->by1 = y1 - rr * vd; B->bx0 = x0 - cc * hd; B->bx1 = x1 - cc * hd;
        B->vd = vd; B->hd = hd;
        int bw = x1 - x0 + 1, bh = y1 - y0 + 1;
        free(B->g); B->g = malloc(sizeof(int32_t) * (size_t)bw * bh);
        for (int y = 0; y < bh; y++)
            for (int x = 0; x < bw; x++)
                B->g[y * bw + x] = buf[(size_t)(y0 + y) * pw + x0 + x];
    }
    free(buf);
    latt_bas_pw[p] = pw;
}

/* exact-table estimate of the out-of-margin distance after moving coefficient (b,row,col) by dv */
/* [A5-LATTMEMO] Invalidate every cached candidate whose synthesis-support box
 * can intersect the pixel rectangle [Y0,Y1] x [X0,X1].  For band b a candidate
 * at (row,col) covers rows [row*vd+by0, row*vd+by1] and cols
 * [col*hd+bx0, col*hd+bx1], so the candidate rows/cols that can overlap are a
 * contiguous range on each axis.  Rounded outward on purpose: invalidating a
 * superset costs a re-score, never a wrong answer. */
/* integer floor/ceil division, denominator > 0.  No float anywhere on a codec
 * path (C3) -- the first cut of this used floorf() and had no business doing
 * so in a shifts-and-adds codebase. */
static inline int latt_fdiv(int a, int b) { return a >= 0 ? a / b : -((-a + b - 1) / b); }
static inline int latt_cdiv(int a, int b) { return a >= 0 ? (a + b - 1) / b : -((-a) / b); }

static void latt_inval_box(ctx_common_t *c, int p, int Y0, int Y1, int X0, int X1)
{
    int pw = plane_width(c, p), sh = c->sh;
    omc_band_t bl[OMC_NBANDS];
    omc_band_layout(pw, sh, bl);
    for (int b = 0; b < OMC_NBANDS; b++) {
        const latt_basis_t *B = &latt_bas[p][b];
        int vd = B->vd, hd = B->hd;
        if (vd <= 0 || hd <= 0) continue;
        int r0 = latt_fdiv(Y0 - B->by1, vd);
        int r1 = latt_cdiv(Y1 - B->by0, vd);
        int c0 = latt_fdiv(X0 - B->bx1, hd);
        int c1 = latt_cdiv(X1 - B->bx0, hd);
        if (r0 < 0) r0 = 0;
        if (c0 < 0) c0 = 0;
        if (r1 > bl[b].h - 1) r1 = bl[b].h - 1;
        if (c1 > bl[b].w - 1) c1 = bl[b].w - 1;
        for (int rr = r0; rr <= r1; rr++) {
            uint8_t *v = latt_cvalid[p] + (size_t)(bl[b].r0 + rr) * pw + bl[b].c0;
            for (int cc = c0; cc <= c1; cc++) v[cc] = 0;
        }
    }
}

static int64_t latt_est_excess2(ctx_common_t *c, int p, const int32_t *pix, int64_t ex_now,
                                int b, int row, int col, int32_t dv, int nrows,
                                int32_t mid_bias, int32_t lo, int32_t hi, int32_t cap,
                                int first, int last)
{
    const latt_basis_t *B = &latt_bas[p][b];
    int pw = plane_width(c, p), sh = c->sh;
    int bw = B->bx1 - B->bx0 + 1;
    int64_t ex = ex_now;
    for (int y = row * B->vd + B->by0; y <= row * B->vd + B->by1; y++) {
        if (y < 0 || y >= nrows) continue;
        int32_t m = latt_margin(y, sh, first, last, cap);
        int32_t l = lo + m, h = hi - m;
        const int32_t *rowp = pix + (size_t)y * pw;
        const int32_t *gr = B->g + (size_t)(y - row * B->vd - B->by0) * bw;
        for (int x = col * B->hd + B->bx0; x <= col * B->hd + B->bx1; x++) {
            if (x < 0 || x >= pw) continue;
            int64_t prod = (int64_t)dv * gr[x - col * B->hd - B->bx0];
            int32_t dpx = (int32_t)((prod + (prod >= 0 ? 2048 : -2048)) >> 12);
            if (!dpx) continue;
            int32_t v = rowp[x] + mid_bias;
            int32_t d0 = v < l ? l - v : v > h ? v - h : 0;
            int32_t v2 = v + dpx;
            int32_t d1 = v2 < l ? l - v2 : v2 > h ? v2 - h : 0;
            ex += d1 - d0;
        }
    }
    return ex;
}

static void latt_measure_peak(ctx_common_t *c, int32_t *tmp, int p)
{
    int pw = plane_width(c, p), sh = c->sh;
    if (latt_peak_pw[p] == pw) return;
    size_t n = (size_t)pw * sh;
    int32_t *buf = calloc(n, sizeof(int32_t));
    omc_band_t bl[OMC_NBANDS];
    omc_band_layout(pw, sh, bl);
    for (int b = 0; b < OMC_NBANDS; b++) {
        memset(buf, 0, n * sizeof(int32_t));
        int rr = bl[b].r0 + bl[b].h / 2, cc = bl[b].c0 + bl[b].w / 2;
        buf[(size_t)rr * pw + cc] = 1 << 16;
        omc_slice_inv_p(buf, pw, sh, tmp, sh, 0);
        double pk = 0;
        for (size_t i = 0; i < n; i++) { double v = (double)buf[i] / 65536.0; if (v < 0) v = -v; if (v > pk) pk = v; }
        latt_peak[p][b] = pk;
    }
    free(buf);
    latt_peak_pw[p] = pw;
}

/* linear estimate of the out-of-margin distance after moving coefficient (b, row, col)
 * by dv, using the separable sign/magnitude runs of GM_BASIS on the CURRENT exact
 * pixels `pix` (inverse of cur).  Only pixels inside the coefficient's support change. */
static int64_t latt_est_excess(ctx_common_t *c, int p, const int32_t *pix, int64_t ex_now,
                               int b, int row, int col, int32_t dv, int nrows,
                               int32_t mid_bias, int32_t lo, int32_t hi, int32_t cap,
                               int first, int last)
{
    const gm_basis_t *G = &GM_BASIS[b];
    int pw = plane_width(c, p), sh = c->sh;
    double pk = latt_peak[p][b];
    int64_t ex = ex_now;
    for (int a = 0; a < G->ny; a++) {
        int y0 = row * G->vd + G->y[a].off, y1 = y0 + G->y[a].len;
        if (y0 < 0) y0 = 0;
        if (y1 > nrows) y1 = nrows;
        for (int y = y0; y < y1; y++) {
            int32_t m = latt_margin(y, sh, first, last, cap);
            int32_t l = lo + m, h = hi - m;
            double wy = (double)G->y[a].w * G->y[a].sgn / 1024.0;
            for (int q = 0; q < G->nx; q++) {
                int x0 = col * G->hd + G->x[q].off, x1 = x0 + G->x[q].len;
                if (x0 < 0) x0 = 0;
                if (x1 > pw) x1 = pw;
                double g = wy * (double)G->x[q].w * G->x[q].sgn / 1024.0 * G->s0 * pk;
                int32_t dpx = (int32_t)((double)dv * g + (dv * g >= 0 ? 0.5 : -0.5));
                if (!dpx) continue;
                const int32_t *rowp = pix + (size_t)y * pw;
                for (int x = x0; x < x1; x++) {
                    int32_t v = rowp[x] + mid_bias;
                    int32_t d0 = v < l ? l - v : v > h ? v - h : 0;
                    int32_t v2 = v + dpx;
                    int32_t d1 = v2 < l ? l - v2 : v2 > h ? v2 - h : 0;
                    ex += d1 - d0;
                }
            }
        }
    }
    return ex;
}
static char latt_line[2200];

static const int64_t latt_g2[OMC_NBANDS] =
    { 590942, 173111, 96074, 55229, 33853, 26841, 10294, 11792, 10100, 4840 };


static int latt_on(void)
{
    static int v = -1;
    if (v < 0) v = getenv("OMC_LATT_PROBE") ? atoi(getenv("OMC_LATT_PROBE")) : 0;
    return v;
}


static void latt_ensure(int p, size_t n)
{
    if (latt_cap[p] >= n) return;
    free(latt_p0[p]); free(latt_last[p]); free(latt_cur[p]); free(latt_work[p]);
    free(latt_q[p]); free(latt_mark[p]); free(latt_bad[p]); free(latt_work2[p]); free(latt_forb[p]);
    free(latt_cg[p]); free(latt_cc2[p]); free(latt_cnv[p]); free(latt_cnq[p]); free(latt_cvalid[p]);
    latt_p0[p]   = malloc(n * sizeof(int32_t));
    latt_last[p] = malloc(n * sizeof(int32_t));
    latt_cur[p]  = malloc(n * sizeof(int32_t));
    latt_work[p] = malloc(n * sizeof(int32_t));
    latt_q[p]    = malloc(n * sizeof(int32_t));
    latt_work2[p] = malloc(n * sizeof(int32_t));
    latt_mark[p] = malloc(n);
    latt_cg[p]     = malloc(n * sizeof(int64_t));
    latt_cc2[p]    = malloc(n * sizeof(int64_t));
    latt_cnv[p]    = malloc(n * sizeof(int32_t));
    latt_cnq[p]    = malloc(n * sizeof(int32_t));
    latt_cvalid[p] = malloc(n);
    latt_bad[p]  = malloc(n);
    latt_forb[p] = malloc(n);
    free(latt_need[p]); latt_need[p] = malloc(sizeof(int32_t) * (n / 32 + 64));
    free(latt_bad0[p]); latt_bad0[p] = malloc(n);
    free(latt_req[p]); latt_req[p] = malloc(n * sizeof(int32_t));
    free(latt_plan[p]); latt_plan[p] = malloc(n * sizeof(int32_t));
    latt_cap[p] = n;
}

/* called at the slice's reconstruct site, every pass: keep the first and the
 * latest coefficient-domain lattice point */
static void latt_capture(omc_enc_t *e, ctx_common_t *c, int sh)
{
    for (int p = 0; p < OMC_NPLANES; p++) {
        size_t n = (size_t)plane_width(c, p) * sh;
        latt_ensure(p, n);
        if (!latt_have0) memcpy(latt_p0[p], e->sbuf[p], n * sizeof(int32_t));
        memcpy(latt_last[p], e->sbuf[p], n * sizeof(int32_t));
    }
    if (latt_plan_valid && getenv("OMC_LATT_STAT")) {
        int64_t nd = 0; int32_t mx = 0;
        for (int p = 0; p < OMC_NPLANES; p++) {
            size_t n = (size_t)plane_width(c, p) * sh;
            for (size_t i = 0; i < n; i++) {
                int32_t d = e->sbuf[p][i] - latt_plan[p][i];
                if (d) { nd++; if (d < 0) d = -d; if (d > mx) mx = d; }
            }
        }
        fprintf(stderr, "LATTCHK s%d emitted-vs-chosen: %lld positions differ, max |d| %d\n",
                latt_plan_slice, (long long)nd, (int)mx);
        latt_plan_valid = 0;
    }
    latt_have0 = 1;
    latt_passes++;
}


/* out-of-margin distance of one plane's committed rows; pix is the inverse
 * output (coefficient buffer after omc_slice_inv_p), rows [0, nrows) */
static int64_t latt_excess(const int32_t *pix, int pw, int sh, int nrows,
                           int32_t mid_bias, int32_t lo, int32_t hi, int32_t cap,
                           int first, int last, int *cnt, uint8_t *bad)
{
    int64_t ex = 0; int k = 0;
    for (int r = 0; r < nrows; r++) {
        int32_t m = latt_margin(r, sh, first, last, cap);
        int32_t l = lo + m, h = hi - m;
        const int32_t *row = pix + (size_t)r * pw;
        uint8_t *bm = bad ? bad + (size_t)r * pw : 0;
        for (int x = 0; x < pw; x++) {
            int32_t v = row[x] + mid_bias;
            int32_t d = v < l ? l - v : v > h ? v - h : 0;
            if (bm) bm[x] = d ? 1 : 0;
            if (d) { ex += d; k++; }
        }
    }
    if (cnt) *cnt = k;
    return ex;
}

typedef struct { int ok, moves, cnt_end, cands, ll_moves; int64_t ex0, ex_end;
                 double energy; int32_t maxll; double lvl; int ninv, lies; } latt_res_t;

/* the G7 instrument, in-loop: largest |mean signed change| over an LL-support
 * block ((sh/4) rows x 32 cols) between two coefficient-domain lattice points,
 * measured on their exact inverses, in picture codes */
static double latt_level(ctx_common_t *c, int32_t *tmp, int p, const int32_t *a, const int32_t *b,
                         int32_t *wa, int32_t *wb, int vvis, int nrows)
{
    int pw = plane_width(c, p), sh = c->sh;
    size_t n = (size_t)pw * sh;
    const int32_t *d1m = c->xsl_live[p] ? c->xsl_buf[p] : 0;
    memcpy(wa, a, n * sizeof(int32_t)); omc_slice_inv_p(wa, pw, sh, tmp, vvis, d1m);
    memcpy(wb, b, n * sizeof(int32_t)); omc_slice_inv_p(wb, pw, sh, tmp, vvis, d1m);
    int bh = sh / 4 > 0 ? sh / 4 : 1, bw = 32;
    double worst = 0;
    for (int y0 = 0; y0 < nrows; y0 += bh)
        for (int x0 = 0; x0 < pw; x0 += bw) {
            int64_t sum = 0; int cnt = 0;
            for (int y = y0; y < y0 + bh && y < nrows; y++)
                for (int x = x0; x < x0 + bw && x < pw; x++) {
                    sum += (int64_t)wb[(size_t)y * pw + x] - wa[(size_t)y * pw + x]; cnt++;
                }
            double m = cnt ? (double)sum / cnt : 0; if (m < 0) m = -m;
            if (m > worst) worst = m;
        }
    return worst;
}

static void latt_search(omc_enc_t *e, ctx_common_t *c, int p, int arm,
                        const shift_plan_t *sp, uint32_t mode_mask,
                        int slice_idx, int nrows, int vvis,
                        int32_t lo, int32_t hi, int32_t cap, int32_t llmax, latt_res_t *R)
{
    int pw = plane_width(c, p), sh = c->sh;
    size_t n = (size_t)pw * sh;
    omc_band_t bl[OMC_NBANDS];
    omc_band_layout(pw, sh, bl);
    int32_t mid_bias = c->mid + OMC_REF_BIAS;
    const int32_t *d1m = c->xsl_live[p] ? c->xsl_buf[p] : 0;
    int first = slice_idx == 0, last = slice_idx >= c->nslices - 1;
    int32_t *cur = latt_cur[p], *work = latt_work[p], *qq = latt_q[p];
    uint8_t *mark = latt_mark[p], *bad = latt_bad[p];
    memcpy(cur, latt_p0[p], n * sizeof(int32_t));
    /* q per position, band-flat: qbuf[p][b][i] at bl[b] raster position */
    for (int b = 0; b < OMC_NBANDS; b++)
        for (int i = 0; i < bl[b].h * bl[b].w; i++)
            qq[(size_t)(bl[b].r0 + i / bl[b].w) * pw + bl[b].c0 + i % bl[b].w] =
                e->qbuf[p][b][i];
    memset(R, 0, sizeof *R);
    memcpy(work, cur, n * sizeof(int32_t));
    omc_slice_inv_p(work, pw, sh, e->tmp, vvis, d1m);
    int cnt;
    int64_t ex = latt_excess(work, pw, sh, nrows, mid_bias, lo, hi, cap, first, last, &cnt, bad);
    R->ex0 = ex; R->ninv = 1;
    uint8_t *forb = latt_forb[p]; memset(forb, 0, n); int lies = 0;
    if (arm == 2) latt_measure_peak(c, e->tmp, p);
    int maxcand = getenv("OMC_LATT_MAXCAND") ? atoi(getenv("OMC_LATT_MAXCAND")) : 8000;
    int maxmoves = getenv("OMC_LATT_MAXMOVES") ? atoi(getenv("OMC_LATT_MAXMOVES")) : 128;
    while (ex > 0 && R->moves < maxmoves) {
        /* candidates: coefficients whose support box covers an offending pixel */
        memset(mark, 0, n);
        int ncand = 0;
        for (int b = 0; b < OMC_NBANDS; b++) {
            const gm_basis_t *G = &GM_BASIS[b];
            int vd = sh / bl[b].h, hd = pw / bl[b].w;
            for (int y = 0; y < nrows; y++) {
                const uint8_t *bm = bad + (size_t)y * pw;
                for (int x = 0; x < pw; x++) {
                    if (!bm[x]) continue;
                    int r0 = (y - G->sy1 - 1) / vd, r1 = (y - G->sy0 + 1) / vd;
                    int c0 = (x - G->sx1 - 1) / hd, c1 = (x - G->sx0 + 1) / hd;
                    if (r0 < 0) r0 = 0;
                    if (r1 >= bl[b].h) r1 = bl[b].h - 1;
                    if (c0 < 0) c0 = 0;
                    if (c1 >= bl[b].w) c1 = bl[b].w - 1;
                    for (int rr = r0; rr <= r1; rr++)
                        for (int cc = c0; cc <= c1; cc++) {
                            size_t pos = (size_t)(bl[b].r0 + rr) * pw + bl[b].c0 + cc;
                            if (!mark[pos]) { mark[pos] = (uint8_t)(b + 1); ncand++; }
                        }
                }
            }
        }
        R->cands += ncand;
        int stride = ncand > maxcand ? (ncand + maxcand - 1) / maxcand : 1;
        double best = 0; size_t bpos = 0; int32_t bnew = 0, bq = 0, bb = -1, bqold = 0; int64_t bex = 0;
        int64_t bdv = 0; int seen = 0;
        for (int b = 0; b < OMC_NBANDS; b++) {
            int m = (int)((mode_mask >> (p * OMC_NBANDS + b)) & 1);
            int w = bl[b].w;
            for (int i = 0; i < bl[b].h * w; i++) {
                size_t pos = (size_t)(bl[b].r0 + i / w) * pw + bl[b].c0 + i % w;
                if (mark[pos] != b + 1) continue;
                if (forb[pos]) continue;
                if ((seen++ % stride) != 0) continue;
                int s = coeff_shift(sp, p, b, i);
                int32_t q = qq[pos];
                int32_t pred = m ? e->pcoef[p][b][i] : 0;
                for (int dir = -1; dir <= 1; dir += 2) {
                    int32_t nq = q + dir;
                    if (arm == 0 || arm == 2) {         /* toward zero only */
                        if (q == 0) break;
                        if ((q > 0 && nq >= q) || (q < 0 && nq <= q)) continue;
                    }
                    int32_t nv = omc_dequant1(nq, s) + pred;
                    int32_t ov = cur[pos];
                    if (nv == ov) continue;
                    if (b == 0 && llmax >= 0) {
                        int32_t dl = nv - latt_p0[p][pos];
                        if (dl < 0) dl = -dl;
                        if (dl > llmax) continue;
                    }
                    int64_t ex2;
                    if (arm == 2) {
                        ex2 = latt_est_excess(c, p, work, ex, b, i / w, i % w, nv - ov, nrows,
                                              mid_bias, lo, hi, cap, first, last);
                    } else {
                        cur[pos] = nv;
                        memcpy(work, cur, n * sizeof(int32_t));
                        omc_slice_inv_p(work, pw, sh, e->tmp, vvis, d1m);
                        ex2 = latt_excess(work, pw, sh, nrows, mid_bias, lo, hi, cap,
                                          first, last, 0, 0);
                        cur[pos] = ov;
                    }
                    if (ex2 >= ex) continue;
                    int64_t dv = (int64_t)nv - ov;
                    double cost = (double)dv * dv * latt_g2[b] / 10000.0;
                    double gain = (double)(ex - ex2) / (cost > 0 ? cost : 1e-9);
                    if (gain > best) { best = gain; bpos = pos; bnew = nv; bq = nq; bb = b;
                                       bex = ex2; bdv = dv; bqold = q; }
                }
            }
        }
        if (bb < 0) break;                         /* no improving single move */
        int64_t ex_prev = ex;
        cur[bpos] = bnew; qq[bpos] = bq; ex = bex; R->moves++;
        if (bb == 0) R->ll_moves++;
        R->energy += (double)bdv * bdv * latt_g2[bb] / 10000.0;
        memcpy(work, cur, n * sizeof(int32_t));
        omc_slice_inv_p(work, pw, sh, e->tmp, vvis, d1m);
        R->ninv++;
        int64_t exv = latt_excess(work, pw, sh, nrows, mid_bias, lo, hi, cap, first, last, &cnt, bad);
        if (arm == 2 && getenv("OMC_LATT_DBG"))
            fprintf(stderr, "  E-dbg move b=%d pos=%zu dv=%lld est=%lld exact=%lld before=%lld\n",
                    bb, bpos, (long long)bdv, (long long)bex, (long long)exv, (long long)ex_prev);
        if (arm == 2 && exv >= ex_prev) {       /* the estimate lied: undo, forbid, go on */
            cur[bpos] = cur[bpos] - bdv; qq[bpos] = bqold; forb[bpos] = 1;
            R->moves--; R->energy -= (double)bdv * bdv * latt_g2[bb] / 10000.0;
            memcpy(work, cur, n * sizeof(int32_t));
            omc_slice_inv_p(work, pw, sh, e->tmp, vvis, d1m);
            R->ninv++;
            ex = latt_excess(work, pw, sh, nrows, mid_bias, lo, hi, cap, first, last, &cnt, bad);
            if (++lies > 16) break;
            continue;
        }
        ex = exv;
    }
    R->ex_end = ex; R->cnt_end = cnt; R->ok = ex == 0; R->lies = lies;
    for (int i = 0; i < bl[0].h * bl[0].w; i++) {
        size_t pos = (size_t)(bl[0].r0 + i / bl[0].w) * pw + bl[0].c0 + i % bl[0].w;
        int32_t dl = cur[pos] - latt_p0[p][pos]; if (dl < 0) dl = -dl;
        if (dl > R->maxll) R->maxll = dl;
    }
    R->lvl = latt_level(c, e->tmp, p, latt_p0[p], cur, latt_work2[p], work, vvis, nrows);
}

static void latt_probe_run(omc_enc_t *e, ctx_common_t *c, const shift_plan_t *sp,
                           uint32_t mode_mask, int slice_idx, int frame_idx, int vvis,
                           int32_t lo, int32_t hi, int32_t cap, int32_t llcap, int bad0, int need0,
                           int Q0, int ns0)
{
    int sh = c->sh;
    int dh = c->cfg.display_height ? c->cfg.display_height : c->H;
    int nrows = slice_idx * sh + sh > dh ? dh - slice_idx * sh : sh;
    if (nrows > vvis) nrows = vvis;
    int len = snprintf(latt_line, sizeof latt_line, "LATT f%d s%d bad0=%d need0=%d plan0=%d,%d llcap=%d",
                       frame_idx, slice_idx, bad0, need0, Q0, ns0, (int)llcap);
    static const char *nm[5] = { "A:red-noLL", "B:red-llcap", "C:red-free", "D:both-llcap", "E:lin-noLL" };
    for (int p = 0; p < OMC_NPLANES; p++) {
        latt_res_t r[5];
        latt_search(e, c, p, 0, sp, mode_mask, slice_idx, nrows, vvis, lo, hi, cap, 0, &r[0]);
        if (r[0].ex0 == 0) continue;
        latt_search(e, c, p, 0, sp, mode_mask, slice_idx, nrows, vvis, lo, hi, cap, llcap, &r[1]);
        latt_search(e, c, p, 0, sp, mode_mask, slice_idx, nrows, vvis, lo, hi, cap, -1, &r[2]);
        latt_search(e, c, p, 1, sp, mode_mask, slice_idx, nrows, vvis, lo, hi, cap, llcap, &r[3]);
        latt_search(e, c, p, 2, sp, mode_mask, slice_idx, nrows, vvis, lo, hi, cap, 0, &r[4]);
        len += snprintf(latt_line + len, sizeof latt_line - (size_t)len, " | p%d ex0=%lld",
                        p, (long long)r[0].ex0);
        for (int a = 0; a < 5 && len < (int)sizeof latt_line - 1; a++)
            len += snprintf(latt_line + len, sizeof latt_line - (size_t)len,
                            " %s[ok=%d mv=%d inv=%d lies=%d ll=%d maxll=%d lvl=%.1f exE=%lld cnt=%d en=%.3g]",
                            nm[a], r[a].ok, r[a].moves, r[a].ninv, r[a].lies, r[a].ll_moves, (int)r[a].maxll, r[a].lvl,
                            (long long)r[a].ex_end, r[a].cnt_end, r[a].energy);
        if (len >= (int)sizeof latt_line - 1) break;
    }
}

/* end of slice: what the shipped repair finally removed, against the pass-0
 * lattice point, in the same energy units */
static void latt_report(omc_enc_t *e, ctx_common_t *c, int sh, int gm_bad, int fellback, int redone,
                        int QE, int nsE, int vvis, int nrows)
{
    double en = 0; int64_t nchg = 0; int32_t maxll = 0; double lvl = 0;
    for (int p = 0; p < OMC_NPLANES; p++) {
        int pw = plane_width(c, p);
        omc_band_t bl[OMC_NBANDS];
        omc_band_layout(pw, sh, bl);
        for (int b = 0; b < OMC_NBANDS; b++)
            for (int r = 0; r < bl[b].h; r++)
                for (int x = 0; x < bl[b].w; x++) {
                    size_t pos = (size_t)(bl[b].r0 + r) * pw + bl[b].c0 + x;
                    int64_t dv = (int64_t)latt_last[p][pos] - latt_p0[p][pos];
                    if (dv) { nchg++; en += (double)dv * dv * latt_g2[b] / 10000.0;
                        if (b == 0) { int32_t a = dv < 0 ? (int32_t)-dv : (int32_t)dv; if (a > maxll) maxll = a; } }
                }
    }
    for (int p = 0; p < OMC_NPLANES; p++) {
        double l = latt_level(c, e->tmp, p, latt_p0[p], latt_last[p], latt_work2[p], latt_work[p], vvis, nrows);
        if (l > lvl) lvl = l;
    }
    fprintf(stderr, "%s | ship[passes=%d bad=%d fell=%d redo=%d planE=%d,%d nchg=%lld maxll=%d lvl=%.1f en=%.3g]\n",
            latt_line, latt_passes, gm_bad, fellback, redone, QE, nsE, (long long)nchg, (int)maxll, lvl, en);
    latt_line[0] = 0;
}

/* ---- sect.S2.4 THE CONSTRUCTIVE LEGALITY STEP (OMC_GM_LATT=1; default 0 in the sandbox)
 *
 * At repair pass 0 of an unlocked, non-CDR slice whose committed picture leaves
 * the legal range: choose, per offending plane, a bounded set of single-step
 * lattice moves in the DETAIL bands (LL never touched; both directions; a move
 * to q == 0 inside a band whose fill bit is set is not allowed, because the
 * re-emission would paint a fill value there rather than zero), ranked by the
 * linearised basis on the pixels the exact inverse already holds, each applied
 * move verified by ONE exact inverse of that plane.  If every offending plane
 * closes inside the move budget, the chosen lattice point is written into the
 * slice's source arrays (coef = the lattice value; dcoef = value - prediction,
 * so either coding mode reconstructs it exactly) and the slice is re-emitted
 * once.  Otherwise nothing is written and the shipped repair runs unchanged.
 *
 * Generation safety: the trigger is "committed samples outside the legal
 * range", which is false at generation 2 by construction, so the step is a
 * no-op there.  Determinism: integer ranking, fixed candidate order.
 * Work bound: at most (OMC_GM_LATT_MAX + lies + 1) plane inverses per
 * offending plane, plus one re-emission of the slice. */
static int latt_mode(void)
{
    static int v = -1;
    if (v < 0) v = getenv("OMC_GM_LATT") ? atoi(getenv("OMC_GM_LATT")) : 1;   /* promoted: default ON */
    return v;
}
static int latt_applied, latt_closed;   /* latt_closed: the step closed this slice */
static int64_t latt_st_slices, latt_st_closed, latt_st_moves, latt_st_inv, latt_st_lies;

typedef struct { int b, i; int32_t v, q; } latt_move_t;

/* the wash guard: largest |mean signed change| over an LL-support block
 * ((sh/4) x 32) between two exact pixel buffers, in codes */
static int latt_blockshift(const int32_t *a, const int32_t *b, int pw, int sh, int nrows,
                           const int32_t *need, int32_t lvlmax, const uint8_t *exempt,
                           const int32_t *req)
{
    int bh = sh / 4 > 0 ? sh / 4 : 1, bw = 32;
    int nbx = (pw + bw - 1) / bw;
    int32_t worst = 0;
    for (int y0 = 0; y0 < nrows; y0 += bh)
        for (int x0 = 0; x0 < pw; x0 += bw) {
            int64_t sum = 0; int cnt = 0;
            for (int y = y0; y < y0 + bh && y < nrows; y++)
                for (int x = x0; x < x0 + bw && x < pw; x++) {
                    size_t q = (size_t)y * pw + x;
                    if (exempt && exempt[q]) continue;   /* form 3: its move was required */
                    int64_t d = (int64_t)b[q] - a[q];
                    if (req) {                            /* form 4: only the movement BEYOND what was required counts */
                        int32_t r = req[q];
                        if (r > 0) d = d > r ? d - r : (d < 0 ? d : 0);
                        else if (r < 0) d = d < r ? d - r : (d > 0 ? d : 0);
                    }
                    sum += d; cnt++;
                }
            int32_t m = (int32_t)(cnt ? (sum < 0 ? -sum : sum) / cnt : 0);
            int32_t allow = lvlmax + (need ? need[(y0 / bh) * nbx + x0 / bw] : 0);
            int32_t over = m - allow;
            if (over > worst) worst = over;
        }
    return worst;                                   /* > 0 = some block exceeds its allowance */
}

/* the per-block allowance from the pass-0 picture: mean out-of-margin distance the fix
 * legitimately has to move in that block */
static void latt_block_need(const int32_t *pix, int pw, int sh, int nrows, int32_t mid_bias,
                            int32_t lo, int32_t hi, int32_t cap, int first, int last, int32_t *need)
{
    int bh = sh / 4 > 0 ? sh / 4 : 1, bw = 32;
    int nbx = (pw + bw - 1) / bw;
    for (int y0 = 0; y0 < nrows; y0 += bh)
        for (int x0 = 0; x0 < pw; x0 += bw) {
            int64_t sum = 0; int cnt = 0;
            for (int y = y0; y < y0 + bh && y < nrows; y++) {
                int32_t m = latt_margin(y, sh, first, last, cap);
                int32_t l = lo + m, h = hi - m;
                for (int x = x0; x < x0 + bw && x < pw; x++) {
                    int32_t v = pix[(size_t)y * pw + x] + mid_bias;
                    sum += v < l ? l - v : v > h ? v - h : 0; cnt++;
                }
            }
            need[(y0 / bh) * nbx + x0 / bw] = (int32_t)(cnt ? (sum + cnt - 1) / cnt : 0);
        }
}
#define LATT_MAXMV 1024

static int latt_plane_solve(omc_enc_t *e, ctx_common_t *c, int p, const shift_plan_t *sp,
                            uint32_t mode_mask, uint32_t fill_mask, int slice_idx,
                            int nrows, int vvis, int32_t lo, int32_t hi, int32_t cap,
                            int maxmv, int32_t lvlmax, int gf, int32_t llmax, int redonly, latt_move_t *mv, int *nmv, int *ninv, int *nlies,
                            int *nlvl)
{
    int pw = plane_width(c, p), sh = c->sh;
    size_t n = (size_t)pw * sh;
    omc_band_t bl[OMC_NBANDS];
    omc_band_layout(pw, sh, bl);
    int32_t mid_bias = c->mid + OMC_REF_BIAS;
    const int32_t *d1m = c->xsl_live[p] ? c->xsl_buf[p] : 0;
    int first = slice_idx == 0, last = slice_idx >= c->nslices - 1;
    int32_t *cur = latt_cur[p], *work = latt_work[p], *qq = latt_q[p];
    uint8_t *mark = latt_mark[p], *bad = latt_bad[p], *forb = latt_forb[p];
    memcpy(cur, latt_p0[p], n * sizeof(int32_t));
    memset(forb, 0, n);
    memset(latt_cvalid[p], 0, n);            /* [A5-LATTMEMO] */
    for (int b = 0; b < OMC_NBANDS; b++)
        for (int i = 0; i < bl[b].h * bl[b].w; i++)
            qq[(size_t)(bl[b].r0 + i / bl[b].w) * pw + bl[b].c0 + i % bl[b].w] = e->qbuf[p][b][i];
    latt_measure_basis(c, e->tmp, p);
    memcpy(work, cur, n * sizeof(int32_t));
    omc_slice_inv_p(work, pw, sh, e->tmp, vvis, d1m);
    int cnt;
    int64_t ex = latt_excess(work, pw, sh, nrows, mid_bias, lo, hi, cap, first, last, &cnt, bad);
    int32_t *pix0 = latt_work2[p];
    memcpy(pix0, work, n * sizeof(int32_t));             /* the pass-0 exact pixels */
    memcpy(latt_bad0[p], bad, n);                      /* pass-0 offending mask */
    {   /* required signed move per pixel at pass 0 (guard form 4) */
        int32_t *rq = latt_req[p];
        memset(rq, 0, n * sizeof(int32_t));
        for (int y = 0; y < nrows; y++) {
            int32_t m = latt_margin(y, sh, first, last, cap);
            int32_t l = lo + m, h = hi - m;
            for (int x = 0; x < pw; x++) {
                int32_t v = pix0[(size_t)y * pw + x] + mid_bias;
                rq[(size_t)y * pw + x] = v < l ? l - v : v > h ? h - v : 0;
            }
        }
    }
    latt_block_need(pix0, pw, sh, nrows, mid_bias, lo, hi, cap, first, last, latt_need[p]);
    *ninv = 1; *nlies = 0; *nmv = 0; *nlvl = 0;
    if (ex == 0) return 1;
    static int invmax = -1;
    if (invmax < 0) invmax = getenv("OMC_GM_LATT_INVMAX") ? atoi(getenv("OMC_GM_LATT_INVMAX")) : 0;
    while (ex > 0 && *nmv < maxmv && (invmax <= 0 || *ninv < invmax)) {
        memset(mark, 0, n);
        const int b_lo = llmax >= 0 ? 0 : 1;              /* LL only on the last-resort rung */
        for (int b = b_lo; b < OMC_NBANDS; b++) {
            const gm_basis_t *G = &GM_BASIS[b];
            int vd = sh / bl[b].h, hd = pw / bl[b].w;
            for (int y = 0; y < nrows; y++) {
                const uint8_t *bm = bad + (size_t)y * pw;
                for (int x = 0; x < pw; x++) {
                    if (!bm[x]) continue;
                    int r0 = (y - G->sy1 - 1) / vd, r1 = (y - G->sy0 + 1) / vd;
                    int c0 = (x - G->sx1 - 1) / hd, c1 = (x - G->sx0 + 1) / hd;
                    if (r0 < 0) r0 = 0;
                    if (r1 >= bl[b].h) r1 = bl[b].h - 1;
                    if (c0 < 0) c0 = 0;
                    if (c1 >= bl[b].w) c1 = bl[b].w - 1;
                    for (int rr = r0; rr <= r1; rr++)
                        for (int cc = c0; cc <= c1; cc++)
                            mark[(size_t)(bl[b].r0 + rr) * pw + bl[b].c0 + cc] = (uint8_t)(b + 1);
                }
            }
        }
        /* best move by integer ratio (ex - est) / (dv^2 * g2): compare cross products */
        int64_t bgain = 0, bcost = 1; size_t bpos = 0; int32_t bnew = 0, bq = 0, bb = -1, bi = 0, bqold = 0;
        int64_t bex = 0, bdv = 0;
        for (int b = b_lo; b < OMC_NBANDS; b++) {
            int m = (int)((mode_mask >> (p * OMC_NBANDS + b)) & 1);
            int fb = b >= OMC_FILL_BANDS_FROM &&
                     ((fill_mask >> (p * 6 + b - OMC_FILL_BANDS_FROM)) & 1);
            int w = bl[b].w;
            for (int i = 0; i < bl[b].h * w; i++) {
                size_t pos = (size_t)(bl[b].r0 + i / w) * pw + bl[b].c0 + i % w;
                if (mark[pos] != b + 1 || forb[pos]) continue;
                /* [A5-LATTMEMO] cached: this position's support box has not
                 * been touched since it was scored, so its gain and cost are
                 * bit-identical to the values held. */
                if (latt_cvalid[p][pos]) {
                    int64_t cgain = latt_cg[p][pos];
                    if (cgain > 0) {
                        int64_t ccost = latt_cc2[p][pos];
                        if (bb < 0 || cgain * bcost > bgain * ccost) {
                            bgain = cgain; bcost = ccost; bpos = pos;
                            bnew = latt_cnv[p][pos]; bq = latt_cnq[p][pos];
                            bb = b; bi = i; bdv = (int64_t)bnew - cur[pos];
                            bqold = qq[pos]; bex = 0;
                        }
                    }
                    continue;
                }
                int64_t pgain = 0, pcost = 1; int32_t pnv = 0, pnq = 0; int phave = 0;
                int s = coeff_shift(sp, p, b, i);
                int32_t q = qq[pos];
                int32_t pred = m ? e->pcoef[p][b][i] : 0;
                for (int dir = -1; dir <= 1; dir += 2) {
                    int32_t nq = q + dir;
                    if (nq == 0 && fb) continue;          /* would become a fill position */
                    if (redonly) {                        /* toward zero only: never adds a symbol, so it
                                                           * cannot starve a later slice's bit budget */
                        if (q == 0) break;
                        if ((q > 0 && nq >= q) || (q < 0 && nq <= q)) continue;
                    }
                    int32_t nv = omc_dequant1(nq, s) + pred;
                    int32_t ov = cur[pos];
                    if (nv == ov) continue;
                    if (b == 0) {                          /* bounded level move: llmax plus the largest
                                                            * move the pixels under this coefficient's support
                                                            * actually REQUIRE (never beyond the rail) */
                        int32_t dl = nv - latt_p0[p][pos];
                    if (dl < 0) dl = -dl;
                        const gm_basis_t *G0 = &GM_BASIS[0];
                        int vd0 = sh / bl[0].h, hd0 = pw / bl[0].w;
                        int rr0 = i / w, cc0 = i % w;
                        int32_t mreq = 0;
                        for (int y = rr0 * vd0 + G0->sy0; y <= rr0 * vd0 + G0->sy1; y++) {
                            if (y < 0 || y >= nrows) continue;
                            for (int x = cc0 * hd0 + G0->sx0; x <= cc0 * hd0 + G0->sx1; x++) {
                                if (x < 0 || x >= pw) continue;
                                int32_t rq = latt_req[p][(size_t)y * pw + x]; if (rq < 0) rq = -rq;
                                if (rq > mreq) mreq = rq;
                            }
                        }
                        if (dl > llmax + mreq) continue;
                    }
                    int64_t ex2 = latt_est_excess2(c, p, work, ex, b, i / w, i % w, nv - ov, nrows,
                                                   mid_bias, lo, hi, cap, first, last);
                    if (ex2 >= ex) continue;
                    int64_t dv = (int64_t)nv - ov;
                    int64_t cost = dv * dv * latt_g2[b];   /* x1e4, common factor */
                    int64_t gain = ex - ex2;
                    if (!phave || gain * pcost > pgain * cost) {
                        phave = 1; pgain = gain; pcost = cost; pnv = nv; pnq = nq;
                    }
                }
                /* [A5-LATTMEMO] store this position's best, then fold it into
                 * the global best in the SAME order the original did. */
                latt_cvalid[p][pos] = 1;
                latt_cg[p][pos]  = phave ? pgain : 0;
                latt_cc2[p][pos] = phave ? pcost : 1;
                latt_cnv[p][pos] = pnv;
                latt_cnq[p][pos] = pnq;
                if (phave && (bb < 0 || pgain * bcost > bgain * pcost)) {
                    bgain = pgain; bcost = pcost; bpos = pos; bnew = pnv; bq = pnq;
                    bb = b; bi = i; bdv = (int64_t)pnv - cur[pos]; bqold = qq[pos]; bex = 0;
                }
            }
        }
        if (bb < 0) break;
        int64_t ex_prev = ex;
        cur[bpos] = bnew; qq[bpos] = bq;
        memcpy(work, cur, n * sizeof(int32_t));
        omc_slice_inv_p(work, pw, sh, e->tmp, vvis, d1m);
        (*ninv)++;
        int64_t exv = latt_excess(work, pw, sh, nrows, mid_bias, lo, hi, cap, first, last, &cnt, bad);
        /* guard form (env OMC_GM_LATT_GF): 1 = flat L; 2 = L + block need; 3 = flat L on the
         * pixels that were in range at pass 0 (collateral shift only) */
        int bs = latt_blockshift(pix0, work, pw, sh, nrows,
                                 gf == 2 ? latt_need[p] : 0, lvlmax,
                                 gf == 3 ? latt_bad0[p] : 0,
                                 gf == 4 ? latt_req[p] : 0);
        int lvlbad = lvlmax > 0 && bs > 0;
        { static int dbg = -2; if (dbg == -2) dbg = getenv("OMC_LATT_DBG2") ? atoi(getenv("OMC_LATT_DBG2")) : -1;
          if (dbg == slice_idx)
              fprintf(stderr, "  DBG2 s%d p%d move b=%d i=%d dv=%lld ex %lld->%lld bs=%d lvlmax=%d gf=%d\n",
                      slice_idx, p, bb, bi, (long long)bdv, (long long)ex_prev, (long long)exv, bs, (int)lvlmax, gf); }
        if (exv >= ex_prev || lvlbad) {       /* estimate lied, or the move shifts a level: undo, forbid */
            cur[bpos] -= (int32_t)bdv; qq[bpos] = bqold; forb[bpos] = 1;
            memcpy(work, cur, n * sizeof(int32_t));
            omc_slice_inv_p(work, pw, sh, e->tmp, vvis, d1m);
            (*ninv)++;
            ex = latt_excess(work, pw, sh, nrows, mid_bias, lo, hi, cap, first, last, &cnt, bad);
            if (lvlbad) (*nlvl)++; else (*nlies)++;
            {   /* [A5-LATTMEMO] the undo put `work` back, but the tried move
                 * had already invalidated nothing yet -- only this position's
                 * own entry is now stale (it is forbidden from here on). */
                latt_cvalid[p][bpos] = 0;
            }
            if (*nlies + *nlvl > 32) break;
            continue;
        }
        mv[*nmv].b = bb; mv[*nmv].i = bi; mv[*nmv].v = bnew; mv[*nmv].q = bq; (*nmv)++;
        (void)bex;
        {   /* [A5-LATTMEMO] the move changed `work` only inside its own support
             * box; every cached candidate that overlaps it must be re-scored. */
            const latt_basis_t *BM = &latt_bas[p][bb];
            int wb = bl[bb].w, rm = bi / wb, cm = bi % wb;
            latt_inval_box(c, p, rm * BM->vd + BM->by0, rm * BM->vd + BM->by1,
                              cm * BM->hd + BM->bx0, cm * BM->hd + BM->bx1);
        }
        ex = exv;
    }
    return ex == 0;
}

/* returns 1 and writes the chosen lattice point into e->coef / e->dcoef when
 * every offending plane closed; returns 0 and writes nothing otherwise */
static int latt_apply(omc_enc_t *e, ctx_common_t *c, const shift_plan_t *sp,
                      uint32_t mode_mask, uint32_t fill_mask, int slice_idx, int frame_idx,
                      int vvis, int32_t lo, int32_t hi, int32_t cap, int can_inter)
{
    int sh = c->sh;
    int dh = c->cfg.display_height ? c->cfg.display_height : c->H;
    int nrows = slice_idx * sh + sh > dh ? dh - slice_idx * sh : sh;
    if (nrows > vvis) nrows = vvis;
    int maxmv = getenv("OMC_GM_LATT_MAX") ? atoi(getenv("OMC_GM_LATT_MAX")) : 128;
    if (maxmv > LATT_MAXMV) maxmv = LATT_MAXMV;
    /* the wash guard, quoted at 10-bit and scaled to the depth; 0 disables */
    /* the allowance is quoted for a 4-row LL-support block (slice_h 16) and scaled by
     * 16/slice_h: the same collateral level change spreads over half the rows at slice_h 8 */
    int lvl10 = getenv("OMC_GM_LATT_LVL") ? atoi(getenv("OMC_GM_LATT_LVL")) : 8;
    if (!getenv("OMC_GM_LATT_LVL_FIXED")) lvl10 = lvl10 * 16 / (sh > 0 ? sh : 16);
    int32_t lvlmax = (int32_t)(((int64_t)lvl10 * (c->maxv + 1) + 512) / 1024);
    if (lvl10 > 0 && lvlmax < 1) lvlmax = 1;
    static latt_move_t mv[OMC_NPLANES][LATT_MAXMV];
    int nmv[OMC_NPLANES];
    int ok = 1, tmv = 0, tinv = 0, tl = 0, tv = 0, tretry = 0;
    for (int p = 0; p < OMC_NPLANES; p++) {
        latt_ensure(p, (size_t)plane_width(c, p) * sh);
        /* the guard ladder: the guard is a preference, closure is the contract.  Form 4
         * (overshoot-aware) first; a plane it cannot close is searched again from the pass-0
         * point with form 3 (offending pixels exempt), then with no guard.  Every rung is a
         * constructive closure and every one is far gentler than the shipped fallback. */
        /* rungs: 0 = form-4 guard, detail bands only; 1 = form-3 guard; 2 = no guard; 3 = the
         * LAST RESORT: no guard and bounded LL moves (a level change of at most OMC_GM_LATT_LLMAX
         * codes at 10-bit, default 8, scaled to the depth).  Bounded by construction; the shipped
         * fallback's level moves were 100-300 codes. */
        /* rung 0: reduction-only moves under the form-4 guard (bit-neutral or bit-saving: a
         * later slice's causal budget is never starved -- measured S2.14 part 5: two-direction
         * moves on earlier slices pushed a rail-heavy slice over a plan-rung cliff, Q8/ns1 ->
         * Q9/ns0, 776 bytes coarser); rung 1: both directions, form-4 guard; rung 2: form-3;
         * rung 3: no guard; rung 4 (default off): bounded LL. */
        static const int ladder[5] = { 4, 4, 3, 0, 0 };
        static const int redl[5]   = { 1, 0, 0, 0, 0 };
        static int gf0 = -1; if (gf0 < 0) gf0 = getenv("OMC_GM_LATT_GF") ? atoi(getenv("OMC_GM_LATT_GF")) : 4;
        static int ll10 = -1; if (ll10 < 0) ll10 = getenv("OMC_GM_LATT_LLMAX") ? atoi(getenv("OMC_GM_LATT_LLMAX")) : 0;   /* 0 = last-resort LL rung OFF (falsified, S2.14 part 5) */
        int32_t llmax_codes = (int32_t)(((int64_t)ll10 * (c->maxv + 1) + 512) / 1024);
        int r = 0;
        for (int rung = 0; rung < (ll10 > 0 ? 5 : 4) && !r; rung++) {
            int gf = rung <= 1 ? gf0 : ladder[rung];
            int32_t lm = gf ? lvlmax : 0;
            int32_t llm = (rung == 4 && ll10 > 0) ? llmax_codes : -1;
            int n2, i2, l2, v2;
            r = latt_plane_solve(e, c, p, sp, mode_mask, fill_mask, slice_idx, nrows, vvis,
                                 lo, hi, cap, rung == 4 ? LATT_MAXMV : maxmv, lm, gf, llm, redl[rung],
                                 mv[p], &n2, &i2, &l2, &v2);
            nmv[p] = n2; tmv += n2; tinv += i2; tl += l2; tv += v2;
            if (rung) tretry++;
            if (getenv("OMC_GM_LATT_NORETRY")) break;
            if (!r && rung == 1 && v2 == 0) rung = 2;       /* guard never fired on the two-direction rung: skip form 3 */
        }
        if (!r) ok = 0;
    }
    latt_st_slices++; latt_st_moves += tmv; latt_st_inv += tinv; latt_st_lies += tl;
    if (getenv("OMC_LATT_STAT"))
        fprintf(stderr, "LATTAPPLY f%d s%d ok=%d moves=%d inv=%d lies=%d lvlrej=%d retry=%d\n",
                frame_idx, slice_idx, ok, tmv, tinv, tl, tv, tretry);
    if (!ok) return 0;
    latt_st_closed++;
    for (int p = 0; p < OMC_NPLANES; p++) {
        int pw = plane_width(c, p);
        omc_band_t bl[OMC_NBANDS];
        omc_band_layout(pw, sh, bl);
        memcpy(latt_plan[p], latt_p0[p], (size_t)pw * sh * sizeof(int32_t));
        for (int k = 0; k < nmv[p]; k++) {
            int b = mv[p][k].b, i = mv[p][k].i;
            e->coef[p][b][i] = mv[p][k].v;
            if (can_inter) e->dcoef[p][b][i] = mv[p][k].v - e->pcoef[p][b][i];
            latt_plan[p][(size_t)(bl[b].r0 + i / bl[b].w) * pw + bl[b].c0 + i % bl[b].w] = mv[p][k].v;
        }
    }
    latt_plan_valid = 1; latt_plan_slice = slice_idx; latt_closed = 1;
    return 1;
}

void omc_enc_latt_report(void)
{
    if (!getenv("OMC_LATT_STAT")) return;
    fprintf(stderr, "omc_enc: latt: slices %lld closed %lld moves %lld inverses %lld lies %lld\n",
            (long long)latt_st_slices, (long long)latt_st_closed, (long long)latt_st_moves,
            (long long)latt_st_inv, (long long)latt_st_lies);
}
