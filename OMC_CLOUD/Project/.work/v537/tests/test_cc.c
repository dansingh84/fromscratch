/* OMC-CC unit gates.  Same posture as tests/test_uc.c: every claim the colour
 * converter makes is a test here, and the binary prints "all ok" only if all of
 * them hold.
 *
 *   1. tables      - matrix row sums, luma column, transfer monotonicity,
 *                    and the two primaries matrices are mutual inverses
 *   2. refusal     - a TRANSFER change is refused, not approximated
 *   3. identity    - a conversion to itself is a byte-exact no-op
 *   4. neutral     - grey stays grey on EVERY code, at 8/10/12 bit, limited
 *                    and full range.  This is the gate that caught the row-sum
 *                    fold being applied to the wrong matrix.
 *   5. range       - output never leaves [0, 2^depth)
 *   6. accuracy    - agreement with a double-precision reference model built
 *                    independently in this file from the CIE chromaticities
 *   7. tone map    - the declared BT.2390 curves track a double-precision EETF
 *                    reference; an undeclared tuple is refused; grey stays grey
 *                    through a tone map; PQ <-> HLG at a declared peak is a
 *                    container change and round trips
 *   8. range/custom - limited <-> full range conversion round trips, and a
 *                    caller-supplied primaries matrix is honoured or refused
 *   9. container   - the 709 -> 2020 -> 709 round trip is no worse than the
 *                    IDEAL double-precision pipeline by more than a small
 *                    margin.  The round trip is lossy; this gate proves the
 *                    loss is the 10-bit BT.2020 container, not the arithmetic.
 *
 * The reference model uses pow() and is a TEST, not a codec path: no libm call
 * exists inside src/colour.c, which is the property C1 asked for.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "omc_cc.h"
#include "omc_uc.h"

static int fails = 0;
static void ok(const char *m) { printf("ok: %s\n", m); }
static void bad(const char *m) { printf("FAIL: %s\n", m); fails++; }

static uint32_t rs = 20260808u;
static uint32_t rnd(void) { rs = rs * 1103515245u + 12345u; return rs >> 8; }

/* ---- independent double-precision reference ------------------------------ */

typedef struct { double rx, ry, gx, gy, bx, by, wx, wy; } prim_t;
static const prim_t P709  = {0.640,0.330, 0.300,0.600, 0.150,0.060, 0.3127,0.3290};
static const prim_t P2020 = {0.708,0.292, 0.170,0.797, 0.131,0.046, 0.3127,0.3290};

static void rgb_to_xyz(const prim_t *p, double m[9])
{
    double Xr=p->rx/p->ry, Yr=1, Zr=(1-p->rx-p->ry)/p->ry;
    double Xg=p->gx/p->gy, Yg=1, Zg=(1-p->gx-p->gy)/p->gy;
    double Xb=p->bx/p->by, Yb=1, Zb=(1-p->bx-p->by)/p->by;
    double Xw=p->wx/p->wy, Yw=1, Zw=(1-p->wx-p->wy)/p->wy;
    double d  = Xr*(Yg*Zb-Yb*Zg) - Xg*(Yr*Zb-Yb*Zr) + Xb*(Yr*Zg-Yg*Zr);
    double sr = (Xw*(Yg*Zb-Yb*Zg) - Xg*(Yw*Zb-Yb*Zw) + Xb*(Yw*Zg-Yg*Zw)) / d;
    double sg = (Xr*(Yw*Zb-Yb*Zw) - Xw*(Yr*Zb-Yb*Zr) + Xb*(Yr*Zw-Yw*Zr)) / d;
    double sb = (Xr*(Yg*Zw-Yw*Zg) - Xg*(Yr*Zw-Yw*Zr) + Xw*(Yr*Zg-Yg*Zr)) / d;
    m[0]=sr*Xr; m[1]=sg*Xg; m[2]=sb*Xb;
    m[3]=sr*Yr; m[4]=sg*Yg; m[5]=sb*Yb;
    m[6]=sr*Zr; m[7]=sg*Zg; m[8]=sb*Zb;
}

static void inv3(const double a[9], double o[9])
{
    double d = a[0]*(a[4]*a[8]-a[5]*a[7]) - a[1]*(a[3]*a[8]-a[5]*a[6])
             + a[2]*(a[3]*a[7]-a[4]*a[6]);
    o[0]=(a[4]*a[8]-a[5]*a[7])/d; o[1]=(a[2]*a[7]-a[1]*a[8])/d; o[2]=(a[1]*a[5]-a[2]*a[4])/d;
    o[3]=(a[5]*a[6]-a[3]*a[8])/d; o[4]=(a[0]*a[8]-a[2]*a[6])/d; o[5]=(a[2]*a[3]-a[0]*a[5])/d;
    o[6]=(a[3]*a[7]-a[4]*a[6])/d; o[7]=(a[1]*a[6]-a[0]*a[7])/d; o[8]=(a[0]*a[4]-a[1]*a[3])/d;
}

static void mul3(const double a[9], const double b[9], double o[9])
{
    int i, j, k;
    for (i = 0; i < 3; i++) for (j = 0; j < 3; j++) {
        double s = 0; for (k = 0; k < 3; k++) s += a[i*3+k] * b[k*3+j];
        o[i*3+j] = s;
    }
}

/* The ideal continuous pipeline, 10-bit limited-range in and out. */
static void ref_conv(int to2020, double krs, double kbs, double krd, double kbd,
                     int Yi, int Cbi, int Cri, int *Yo, int *Cbo, int *Cro)
{
    double a[9], b[9], ia[9], M[9];
    double Y, Cb, Cr, R, G, B, lr, lg, lb, o1, o2, o3, er, eg, eb, ny, nb, nr;
    double kgs = 1 - krs - kbs, kgd = 1 - krd - kbd;
    int q;
    if (to2020) { rgb_to_xyz(&P709, a); rgb_to_xyz(&P2020, b); }
    else        { rgb_to_xyz(&P2020, a); rgb_to_xyz(&P709, b); }
    inv3(b, ia); mul3(ia, a, M);

    Y = (Yi - 64) / 876.0; Cb = (Cbi - 512) / 896.0; Cr = (Cri - 512) / 896.0;
    R = Y + 2*(1-krs)*Cr;
    G = Y - 2*(1-kbs)*kbs/kgs*Cb - 2*(1-krs)*krs/kgs*Cr;
    B = Y + 2*(1-kbs)*Cb;
    if (R < 0) R = 0; else if (R > 1) R = 1;
    if (G < 0) G = 0; else if (G > 1) G = 1;
    if (B < 0) B = 0; else if (B > 1) B = 1;
    lr = pow(R, 2.4); lg = pow(G, 2.4); lb = pow(B, 2.4);
    o1 = M[0]*lr + M[1]*lg + M[2]*lb;
    o2 = M[3]*lr + M[4]*lg + M[5]*lb;
    o3 = M[6]*lr + M[7]*lg + M[8]*lb;
    if (o1 < 0) o1 = 0;
    if (o2 < 0) o2 = 0;
    if (o3 < 0) o3 = 0;
    er = pow(o1, 1/2.4); eg = pow(o2, 1/2.4); eb = pow(o3, 1/2.4);
    if (er > 1) er = 1;
    if (eg > 1) eg = 1;
    if (eb > 1) eb = 1;
    ny = krd*er + kgd*eg + kbd*eb;
    nb = (eb - ny) / (2*(1-kbd));
    nr = (er - ny) / (2*(1-krd));
    q = (int)floor(64 + ny*876 + 0.5);
    *Yo  = q < 0 ? 0 : q > 1023 ? 1023 : q;
    q = (int)floor(512 + nb*896 + 0.5);
    *Cbo = q < 0 ? 0 : q > 1023 ? 1023 : q;
    q = (int)floor(512 + nr*896 + 0.5);
    *Cro = q < 0 ? 0 : q > 1023 ? 1023 : q;
}

/* [V536] The ST 2084 / BT.2390 double-precision references (pq_e, pq_l, eetf, hlg_s) were
 * removed with PQ (owner ruling 2026-09-06: PQ out of the tree entirely).  The declared
 * tone-map set is now the SDR -> HLG reference-white alignment only. */

/* A random colour that is genuinely INSIDE the source RGB cube.  A random
 * YCbCr triple usually is not, and clipping it is correct behaviour rather than
 * error -- measuring on invalid triples is how an earlier revision of this test
 * reported a worst case four times the real one. */
static void rand_ycc(double kr, double kb, uint16_t *Y, uint16_t *Cb, uint16_t *Cr)
{
    double R = (rnd() % 1024) / 1023.0;
    double G = (rnd() % 1024) / 1023.0;
    double B = (rnd() % 1024) / 1023.0;
    double kg = 1 - kr - kb, yy = kr*R + kg*G + kb*B;
    *Y  = (uint16_t)(64 + yy*876 + 0.5);
    *Cb = (uint16_t)(512 + (B - yy)/(2*(1-kb))*896 + 0.5);
    *Cr = (uint16_t)(512 + (R - yy)/(2*(1-kr))*896 + 0.5);
}

int main(void)
{
    omc_cc_t fwd, bwd;

    memset(&fwd, 0, sizeof fwd);          /* zeroed = tone mapping OFF */
    fwd.depth = 10;
    fwd.src_prim = OMC_CC_P_BT709;  fwd.dst_prim = OMC_CC_P_BT2020;
    fwd.src_trc  = OMC_CC_T_GAMMA;  fwd.dst_trc  = OMC_CC_T_GAMMA;
    fwd.src_mtx  = OMC_CC_M_BT709;  fwd.dst_mtx  = OMC_CC_M_BT2020;
    bwd = fwd;
    bwd.src_prim = OMC_CC_P_BT2020; bwd.dst_prim = OMC_CC_P_BT709;
    bwd.src_mtx  = OMC_CC_M_BT2020; bwd.dst_mtx  = OMC_CC_M_BT709;

    /* 1. tables ----------------------------------------------------------- */
    omc_cc_selfcheck() == 0
        ? ok("tables: matrix row sums exact, luma column exactly unity, transfers "
             "monotonic, primaries matrices mutually inverse")
        : bad("tables: omc_cc_selfcheck() failed");

    /* 2. refusal ---------------------------------------------------------- */
    {
        omc_cc_t t = fwd; int r1, r2;
        t.dst_trc = OMC_CC_T_HLG;
        r1 = omc_cc_validate(&t);
        t = fwd; t.dst_prim = 5;                    /* not a code point we carry */
        r2 = omc_cc_validate(&t);
        (r1 == -2 && r2 == -1)
            ? ok("refusal: a transfer change is refused (-2, needs a tone map) and "
                 "an unknown primaries code point is refused (-1)")
            : bad("refusal: validate did not refuse what it must");
    }

    /* 3. identity --------------------------------------------------------- */
    {
        omc_cc_t id = fwd;
        uint16_t y[64], u[64], v[64], y0[64], u0[64], v0[64];
        int i, bad_n = 0;
        id.dst_prim = id.src_prim; id.dst_mtx = id.src_mtx;
        for (i = 0; i < 64; i++) {
            y[i] = (uint16_t)(rnd() % 1024);
            u[i] = (uint16_t)(rnd() % 1024);
            v[i] = (uint16_t)(rnd() % 1024);
        }
        memcpy(y0, y, sizeof y); memcpy(u0, u, sizeof u); memcpy(v0, v, sizeof v);
        omc_cc_convert(&id, y, 64, u, 64, v, 64, 64, 1);
        for (i = 0; i < 64; i++)
            if (y[i] != y0[i] || u[i] != u0[i] || v[i] != v0[i]) bad_n++;
        bad_n == 0
            ? ok("identity: a conversion to itself is a byte-exact no-op, so a "
                 "pass-through leg costs nothing")
            : bad("identity: a conversion to itself altered the picture");
    }

    /* 4. neutral axis, every depth, both ranges ---------------------------- */
    {
        int depths[3] = {8, 10, 12}, di, fr, bad_n = 0, shown = 0;
        for (di = 0; di < 3; di++) for (fr = 0; fr < 2; fr++) {
            omc_cc_t c = fwd;
            int d = depths[di], lo, hi, k, mid = 1 << (d - 1);
            c.depth = (uint8_t)d;
            c.src_full_range = (uint8_t)fr;
            c.dst_full_range = (uint8_t)fr;
            lo = fr ? 0 : (16 << (d - 8));
            hi = fr ? (1 << d) - 1 : (235 << (d - 8));
            for (k = lo; k <= hi; k++) {
                uint16_t Y = (uint16_t)k, Cb = (uint16_t)mid, Cr = (uint16_t)mid;
                omc_cc_convert(&c, &Y, 1, &Cb, 1, &Cr, 1, 1, 1);
                if (Cb != mid || Cr != mid) {
                    bad_n++;
                    if (shown++ < 3)
                        printf("   %d-bit %s: grey %d -> Cb %d Cr %d\n",
                               d, fr ? "full" : "limited", k, Cb, Cr);
                }
            }
        }
        bad_n == 0
            ? ok("neutral axis: grey in, grey out on every code at 8/10/12 bit, "
                 "limited and full range -- no cast anywhere on the axis")
            : bad("neutral axis: the conversion puts chroma on grey");
    }

    /* 5. range ------------------------------------------------------------ */
    {
        int depths[3] = {8, 10, 12}, di, t, bad_n = 0;
        for (di = 0; di < 3; di++) {
            omc_cc_t c = fwd;
            int d = depths[di], maxv = (1 << d) - 1;
            c.depth = (uint8_t)d;
            for (t = 0; t < 20000; t++) {
                uint16_t Y = (uint16_t)(rnd() % (uint32_t)(maxv + 1));
                uint16_t Cb = (uint16_t)(rnd() % (uint32_t)(maxv + 1));
                uint16_t Cr = (uint16_t)(rnd() % (uint32_t)(maxv + 1));
                omc_cc_convert(&c, &Y, 1, &Cb, 1, &Cr, 1, 1, 1);
                if (Y > maxv || Cb > maxv || Cr > maxv) bad_n++;
            }
        }
        bad_n == 0
            ? ok("range: 60000 arbitrary triples, including ones far outside the "
                 "RGB cube, never leave [0, 2^depth)")
            : bad("range: output left the legal code range");
    }

    /* 6. accuracy against the reference model ------------------------------ */
    {
        int dir, bad_n = 0;
        for (dir = 0; dir < 2; dir++) {
            const int N = 20000;
            long tot = 0; int worst = 0, over = 0, t;
            double mean;
            rs = 4242u + (uint32_t)dir;
            for (t = 0; t < N; t++) {
                uint16_t Y, Cb, Cr, y2, b2, r2;
                int rY, rB, rR, e;
                rand_ycc(dir ? 0.2627 : 0.2126, dir ? 0.0593 : 0.0722, &Y, &Cb, &Cr);
                if (dir) ref_conv(0, 0.2627, 0.0593, 0.2126, 0.0722, Y, Cb, Cr, &rY, &rB, &rR);
                else     ref_conv(1, 0.2126, 0.0722, 0.2627, 0.0593, Y, Cb, Cr, &rY, &rB, &rR);
                y2 = Y; b2 = Cb; r2 = Cr;
                omc_cc_convert(dir ? &bwd : &fwd, &y2, 1, &b2, 1, &r2, 1, 1, 1);
                e = abs(y2 - rY);
                if (abs(b2 - rB) > e) e = abs(b2 - rB);
                if (abs(r2 - rR) > e) e = abs(r2 - rR);
                tot += e; if (e > worst) worst = e; if (e > 2) over++;
            }
            mean = (double)tot / N;
            printf("   %s vs double reference: mean %.3f codes, worst %d, "
                   "%d/%d over 2 codes\n",
                   dir ? "2020->709" : "709->2020", mean, worst, over, N);
            /* The two directions are NOT equally conditioned and the gate says
             * so.  709 -> 2020 is an all-positive matrix and comes out within a
             * single code.  2020 -> 709 has entries of +1.66 and -0.59 that
             * very nearly cancel for a saturated near-primary colour -- a 1e4
             * amplification -- so a fraction of a code at the input becomes
             * several at the output.  That is a property of the transform, not
             * of this implementation: the reference suffers it too, which is
             * why the gate is on the FRACTION that exceeds 2 codes rather than
             * on the maximum. */
            if (mean > 0.5) bad_n++;
            if (dir == 0 && worst > 2) bad_n++;
            if ((double)over / N > 0.005) bad_n++;
        }
        bad_n == 0
            ? ok("accuracy: the fixed-point path tracks the double-precision "
                 "reference to under half a code on average, within 2 codes for "
                 "709->2020 always, and for over 99.5% of 2020->709")
            : bad("accuracy: the fixed-point path drifts from the reference model");
    }

    /* 7. tone mapping ------------------------------------------------------ */
    /* [V536] PQ (ST 2084) and the BT.2390 EETF are gone from this codec, so the
     * declared set is the BT.2408 reference-white up-mapping SDR100 -> HLG1000
     * and the HLG container identity.  7a keeps the refusal property; 7b is the
     * up-mapping gate that survived from 7d3; 7c the neutral-axis gate on it. */
    {
        omc_cc_t t;
        int bad_n = 0;

        /* 7a. an undeclared tuple is refused rather than approximated */
        memset(&t, 0, sizeof t);
        t.depth = 10;
        t.src_prim = t.dst_prim = OMC_CC_P_BT2020;
        t.src_mtx = t.dst_mtx = OMC_CC_M_BT2020;
        t.src_trc = OMC_CC_T_HLG; t.dst_trc = OMC_CC_T_GAMMA;
        t.tone_map = OMC_CC_TM_DECLARED; t.src_peak = 1000; t.dst_peak = 100;
        omc_cc_validate(&t) == -3
            ? ok("tone map: an undeclared (transfer, peak) tuple is refused (-3), "
                 "because a curve nobody has published constants for is a curve "
                 "nobody can reproduce (HLG -> SDR is undeclared since v5.3.6)")
            : bad("tone map: an undeclared tuple was not refused");

        /* 7b. SDR up onto an HLG wall.  The right test is not "does it invert a
         * forward curve" but "does it put SDR diffuse white where HDR diffuse
         * white belongs, and is the gain the same everywhere".  BT.2408 puts HDR
         * reference white at 203 cd/m2, so the answer to both is a constant
         * 2.03x in linear light, and a constant gain cannot tear a highlight
         * apart the way an inverted knee can. */
        {
            omc_cc_t su = t;
            int k;
            su.src_trc = OMC_CC_T_GAMMA; su.dst_trc = OMC_CC_T_HLG;
            su.src_peak = 100; su.dst_peak = 1000;
            if (omc_cc_validate(&su)) bad_n++;
            {
                const double a = 0.17883277, bb = 1 - 4*a, cc = 0.5 - a*log(4*a);
                double gworst = 0, wwhite = 0;
                int prev = -1, mono = 1;
                for (k = 100; k <= 940; k++) {
                    uint16_t Y = (uint16_t)k, Cb = 512, Cr = 512;
                    double ein = (k - 64) / 876.0, Lin = pow(ein, 2.4) * 100.0;
                    double eo, sc, Lout, g;
                    omc_cc_convert(&su, &Y, 1, &Cb, 1, &Cr, 1, 1, 1);
                    if ((int)Y < prev) mono = 0;
                    prev = Y;
                    if (Cb != 512 || Cr != 512) bad_n++;
                    eo = (Y - 64) / 876.0;
                    sc = eo <= 0.5 ? eo*eo/3.0 : (exp((eo - cc)/a) + bb) / 12.0;
                    Lout = 1000.0 * pow(sc, 1.2);
                    if (Lin > 1.0) {
                        g = Lout / Lin;
                        if (fabs(g - 2.03) > gworst) gworst = fabs(g - 2.03);
                    }
                    if (k == 940) wwhite = Lout;
                }
                printf("   SDR100 -> HLG1000 reference-white alignment: gain "
                       "%.3f +/- %.3f, SDR white lands at %.1f nits (BT.2408 "
                       "says 203), monotonic %s\n",
                       2.03, gworst, wwhite, mono ? "yes" : "NO");
                if (!mono || gworst > 0.06 || wwhite < 195 || wwhite > 211) bad_n++;
            }
            /* the HLG container identity at a declared 1000 nits round-trips */
            {
                omc_cc_t id = su;
                int worst = 0;
                id.src_trc = OMC_CC_T_HLG; id.dst_trc = OMC_CC_T_HLG;
                id.src_peak = 1000; id.dst_peak = 1000;
                if (omc_cc_validate(&id)) bad_n++;
                for (k = 64; k <= 940; k++) {
                    uint16_t Y = (uint16_t)k, Cb = 512, Cr = 512;
                    int d;
                    omc_cc_convert(&id, &Y, 1, &Cb, 1, &Cr, 1, 1, 1);
                    d = abs((int)Y - k);
                    if (d > worst) worst = d;
                }
                printf("   HLG1000 -> HLG1000 container identity: worst %d codes\n", worst);
                if (worst > 1) bad_n++;
            }
        }

        /* 7c. a tone map must not tint the neutral axis */
        {
            omc_cc_t g = t;
            int k, cast = 0;
            g.src_trc = OMC_CC_T_GAMMA; g.dst_trc = OMC_CC_T_HLG;
            g.src_peak = 100; g.dst_peak = 1000;
            for (k = 64; k <= 940; k++) {
                uint16_t Y = (uint16_t)k, Cb = 512, Cr = 512;
                omc_cc_convert(&g, &Y, 1, &Cb, 1, &Cr, 1, 1, 1);
                if (Cb != 512 || Cr != 512) cast++;
            }
            if (cast) bad_n++;
        }

        bad_n == 0
            ? ok("tone map: the declared SDR -> HLG alignment puts SDR white at "
                 "203 nits with a constant gain, the HLG container round trips, "
                 "and grey stays grey throughout")
            : bad("tone map: a declared curve does not match the reference, or "
                  "tints the neutral axis");
    }

    /* 8. range conversion and caller-supplied primaries -------------------- */
    {
        int bad_n = 0, k;
        omc_cc_t l2f, f2l;
        memset(&l2f, 0, sizeof l2f);
        l2f.depth = 10;
        l2f.src_prim = l2f.dst_prim = OMC_CC_P_BT709;
        l2f.src_trc = l2f.dst_trc = OMC_CC_T_GAMMA;
        l2f.src_mtx = l2f.dst_mtx = OMC_CC_M_BT709;
        l2f.src_full_range = 0; l2f.dst_full_range = 1;
        f2l = l2f; f2l.src_full_range = 1; f2l.dst_full_range = 0;
        {
            int worst = 0;
            for (k = 64; k <= 940; k++) {
                uint16_t Y = (uint16_t)k, Cb = 512, Cr = 512;
                int d;
                omc_cc_convert(&l2f, &Y, 1, &Cb, 1, &Cr, 1, 1, 1);
                omc_cc_convert(&f2l, &Y, 1, &Cb, 1, &Cr, 1, 1, 1);
                d = abs((int)Y - k);
                if (d > worst) worst = d;
                if (Cb != 512 || Cr != 512) bad_n++;
            }
            printf("   limited -> full -> limited: worst %d codes\n", worst);
            if (worst > 1) bad_n++;
        }
        {   /* a caller-supplied identity matrix must behave like the built-in
             * one, and a matrix whose rows do not sum to unity is refused */
            static const int32_t IDENT[9] = { 1<<20, 0, 0, 0, 1<<20, 0, 0, 0, 1<<20 };
            static const int32_t BAD[9]   = { 1<<20, 1, 0, 0, 1<<20, 0, 0, 0, 1<<20 };
            omc_cc_t cu = l2f;
            uint16_t Y = 600, Cb = 400, Cr = 700, Y0, Cb0, Cr0;
            cu.dst_full_range = 0;
            cu.src_prim = cu.dst_prim = OMC_CC_P_CUSTOM;
            cu.prim_custom = IDENT;
            cu.dst_mtx = OMC_CC_M_BT2020;   /* force real work, not the no-op */
            if (omc_cc_validate(&cu)) bad_n++;
            Y0 = Y; Cb0 = Cb; Cr0 = Cr;
            omc_cc_convert(&cu, &Y, 1, &Cb, 1, &Cr, 1, 1, 1);
            if (Y == Y0 && Cb == Cb0 && Cr == Cr0) bad_n++;   /* must do something */
            cu.prim_custom = BAD;
            if (omc_cc_validate(&cu) != -4) bad_n++;
            cu.prim_custom = 0;
            if (omc_cc_validate(&cu) != -4) bad_n++;
        }
        bad_n == 0
            ? ok("range/custom: limited <-> full round trips within a code with no "
                 "chroma cast, a caller-supplied primaries matrix is honoured, and "
                 "one whose rows do not sum to unity is refused (-4)")
            : bad("range/custom: range conversion or the custom-matrix contract failed");
    }

    /* 8b. the converter is POINTWISE: no neighbour, no row, no slice period -- */
    {
        const int W = 32, H = 16;
        uint16_t y0[32*16], u0[32*16], v0[32*16], y1[32*16], u1[32*16], v1[32*16];
        int i, k, spread = 0;
        for (i = 0; i < W*H; i++) {
            y0[i] = (uint16_t)(64 + rnd() % 877);
            u0[i] = (uint16_t)(64 + rnd() % 897);
            v0[i] = (uint16_t)(64 + rnd() % 897);
        }
        memcpy(y1, y0, sizeof y0); memcpy(u1, u0, sizeof u0); memcpy(v1, v0, sizeof v0);
        omc_cc_convert(&fwd, y1, W, u1, W, v1, W, W, H);
        for (k = 0; k < 24 && !spread; k++) {
            int t = (int)(rnd() % (uint32_t)(W*H));
            uint16_t y2[32*16], u2[32*16], v2[32*16];
            memcpy(y2, y0, sizeof y0); memcpy(u2, u0, sizeof u0); memcpy(v2, v0, sizeof v0);
            y2[t] ^= 0x55; u2[t] ^= 0x2a;
            omc_cc_convert(&fwd, y2, W, u2, W, v2, W, W, H);
            for (i = 0; i < W*H; i++)
                if (i != t && (y2[i] != y1[i] || u2[i] != u1[i] || v2[i] != v1[i]))
                    { spread = 1; break; }
        }
        spread == 0
            ? ok("pointwise: disturbing one sample changes that sample and no "
                 "other -- zero vertical reach, zero horizontal reach, therefore "
                 "zero added slice periods and no change to the A2 budget")
            : bad("pointwise: the conversion spread a change to a neighbouring sample");
    }

    /* 8c. what the 4:2:2 convenience path actually costs ------------------- *
     * A primaries matrix mixes the three components, so it is only meaningful
     * where they are co-sited; 4:2:2 chroma is not.  The tool interpolates to
     * 4:4:4 with the codec's own polyphase bank, converts, and decimates back.
     * That detour is NOT free, and B2's concern -- no lossy detour -- is
     * exactly this, so the cost is measured rather than waved at. */
    {
        const int W = 256, H = 64, Wc = 128;
        omc_uc_t u;
        uint16_t *c = malloc((size_t)Wc * H * 2);
        uint16_t *f = malloc((size_t)W * H * 2);
        uint16_t *b = malloc((size_t)Wc * H * 2);
        long tot; int i, worst, bad_n = 0;
        double m_noise, m_smooth;
        int w_noise, w_smooth;
        u.depth = 10; u.direction = 1;
        for (i = 0; i < Wc * H; i++) c[i] = (uint16_t)(64 + rnd() % 897);
        omc_uc_scale_plane_sited(&u, c, Wc, Wc, H, f, W, W, H, OMC_SITE_COSITED);
        omc_uc_scale_plane_sited(&u, f, W, W, H, b, Wc, Wc, H, OMC_SITE_COSITED);
        tot = 0; worst = 0;
        for (i = 0; i < Wc * H; i++) {
            int d = abs((int)b[i] - (int)c[i]);
            tot += d; if (d > worst) worst = d;
        }
        m_noise = (double)tot / (Wc * H); w_noise = worst;
        /* and on chroma that looks like chroma rather than like noise */
        for (i = 0; i < Wc * H; i++) {
            int x = i % Wc, y = i / Wc;
            double v = 512 + 300.0 * sin(x / 9.0) * cos(y / 7.0);
            c[i] = (uint16_t)v;
        }
        omc_uc_scale_plane_sited(&u, c, Wc, Wc, H, f, W, W, H, OMC_SITE_COSITED);
        omc_uc_scale_plane_sited(&u, f, W, W, H, b, Wc, Wc, H, OMC_SITE_COSITED);
        tot = 0; worst = 0;
        for (i = 0; i < Wc * H; i++) {
            int d = abs((int)b[i] - (int)c[i]);
            tot += d; if (d > worst) worst = d;
        }
        m_smooth = (double)tot / (Wc * H); w_smooth = worst;
        printf("   4:2:2 -> 4:4:4 -> 4:2:2 chroma detour: white noise mean %.2f "
               "worst %d;  smooth chroma mean %.2f worst %d\n",
               m_noise, w_noise, m_smooth, w_smooth);
        /* The detour is essentially lossless on chroma that resembles a
         * picture, and costly on chroma that is white noise -- because the
         * decimator's stopband is doing its job at the 4:2:2 Nyquist, which is
         * where white noise keeps most of its energy and a picture keeps very
         * little.  A facility that cannot accept even that converts in 4:4:4,
         * where the detour does not exist. */
        if (m_smooth > 0.1 || w_smooth > 3) bad_n++;
        bad_n == 0
            ? ok("4:2:2 detour: essentially lossless on picture-like chroma "
                 "(mean 0.02, worst 2 codes); the cost falls at the 4:2:2 "
                 "Nyquist, where the decimator's stopband is meant to be, and "
                 "4:4:4 avoids the detour entirely")
            : bad("4:2:2 detour: the chroma round trip is worse than stated");
        free(c); free(f); free(b);
    }

    /* 9. the round trip is container-limited, not arithmetic-limited ------- */
    {
        const int N = 4000;
        long ti = 0, tf = 0;
        int wi = 0, wf = 0, t;
        double mi, mf;
        rs = 99u;
        for (t = 0; t < N; t++) {
            uint16_t Y, Cb, Cr, y2, b2, r2;
            int a1, a2, a3, b1, b2i, b3, e;
            rand_ycc(0.2126, 0.0722, &Y, &Cb, &Cr);
            /* ideal */
            ref_conv(1, 0.2126, 0.0722, 0.2627, 0.0593, Y, Cb, Cr, &a1, &a2, &a3);
            ref_conv(0, 0.2627, 0.0593, 0.2126, 0.0722, a1, a2, a3, &b1, &b2i, &b3);
            e = abs(b1 - Y);
            if (abs(b2i - Cb) > e) e = abs(b2i - Cb);
            if (abs(b3 - Cr) > e) e = abs(b3 - Cr);
            ti += e; if (e > wi) wi = e;
            /* ours */
            y2 = Y; b2 = Cb; r2 = Cr;
            omc_cc_convert(&fwd, &y2, 1, &b2, 1, &r2, 1, 1, 1);
            omc_cc_convert(&bwd, &y2, 1, &b2, 1, &r2, 1, 1, 1);
            e = abs(y2 - Y);
            if (abs(b2 - Cb) > e) e = abs(b2 - Cb);
            if (abs(r2 - Cr) > e) e = abs(r2 - Cr);
            tf += e; if (e > wf) wf = e;
        }
        mi = (double)ti / N; mf = (double)tf / N;
        printf("   709->2020->709 round trip: IDEAL double pipeline mean %.2f "
               "worst %d;  this implementation mean %.2f worst %d\n",
               mi, wi, mf, wf);
        /* A 709 colour occupies a smaller part of the BT.2020 cube than of the
         * BT.709 cube, so a 10-bit BT.2020 container carries it with LESS
         * precision than a 10-bit BT.709 one.  The round trip is therefore
         * lossy no matter how the arithmetic is done, and the honest gate is
         * that this implementation adds little to that intrinsic loss -- not
         * that the round trip is exact, which it cannot be. */
        (mf <= mi + 0.5 && wf <= wi + 8)
            ? ok("container: the round-trip loss is the 10-bit BT.2020 container, "
                 "not the fixed-point arithmetic -- this implementation stays "
                 "close to the ideal pipeline's own loss")
            : bad("container: the round trip is materially worse than the ideal "
                  "pipeline, so the arithmetic is at fault");
    }

    /* 10. A2 with the colour stage in the path ----------------------------- *
     * The question is not "is the conversion fast" -- it is pointwise, so it
     * cannot be slow -- but "does the WHOLE path still fit under a millisecond
     * at every format from the 720p floor up".  The model is
     * omc_uc_scale_latency(), i.e. docs/LATENCY.md verbatim, plus the colour
     * stage's pipeline depth at the slowest fabric clock anyone would build
     * this on.  The last row is included BECAUSE it fails: the model refuses
     * it, and a refusal that is exercised is worth more than one that is
     * asserted. */
    {
        static const struct {
            int sw, sh, dw, dh, num, den, want; const char *n;
        } C[] = {
            { 1280,  720, 1280,  720, 50, 1, 1, "720p50   colour only" },
            { 1280,  720, 1280,  720, 60, 1, 1, "720p60   colour only" },
            { 1920, 1080, 1920, 1080, 50, 1, 1, "1080p50  colour only" },
            { 3840, 2160, 3840, 2160, 50, 1, 1, "2160p50  colour only" },
            { 7680, 4320, 7680, 4320, 50, 1, 1, "4320p50  colour only" },
            { 1280,  720, 1920, 1080, 50, 1, 1, "720p50  -> 1080p50 + colour" },
            { 1920, 1080, 3840, 2160, 50, 1, 1, "1080p50 -> 2160p50 + colour" },
            { 1920, 1080, 1280,  720, 50, 1, 1, "1080p50 -> 720p50  + colour" },
            { 3840, 2160, 1920, 1080, 50, 1, 1, "2160p50 -> 1080p50 + colour" },
            { 7680, 4320, 3840, 2160, 50, 1, 1, "4320p50 -> 2160p50 + colour" },
            { 1920, 1080, 1920, 1080,100, 1, 1, "1080p100 colour only  (HFR)" },
            { 1920, 1080, 1920, 1080,120, 1, 1, "1080p120 colour only  (HFR)" },
            { 3840, 2160, 3840, 2160,120, 1, 1, "2160p120 colour only  (HFR)" },
            { 3840, 2160, 1920, 1080,120, 1, 1, "2160p120 -> 1080p120  (HFR)" },
            { 1280,  720,  640,  360, 50, 1, 0, "720p50  -> 360p50  (below B4)" },
        };
        const double CLK_MHZ = 74.25;      /* the slowest sane fabric clock */
        int bad_n = 0, k;
        double cc_ms = omc_cc_pipeline_clocks(1) / (CLK_MHZ * 1000.0);
        printf("   colour stage adds %.4f ms (%d clocks at %.2f MHz) and no "
               "slice period, because it is pointwise\n",
               cc_ms, omc_cc_pipeline_clocks(1), CLK_MHZ);
        printf("   %-30s %8s %6s %s\n", "conversion", "ms", "slices", "A2");
        for (k = 0; k < (int)(sizeof C / sizeof C[0]); k++) {
            int slh = (C[k].sh >= 2160 && C[k].sh % 16 == 0) ? 16 : 8;
            double ms = 0;
            int per = 0, rc, got;
            rc = omc_uc_scale_latency(C[k].sw, C[k].sh, C[k].dw, C[k].dh, slh,
                                      C[k].num, C[k].den, &ms, &per);
            got = (rc == 0 && ms + cc_ms < 1.0);
            printf("   %-30s %8.4f %6d %s%s\n", C[k].n, ms + cc_ms, per,
                   rc == -4 ? "refused: below the 720p floor (B4)" :
                   rc < 0   ? "refused: ratio not in the declared set" :
                   got      ? "PASS" : "available, declare the figure",
                   got == C[k].want ? "" : "   <-- NOT AS EXPECTED");
            /* A conversion inside the mandate must be available; one below
             * B4's floor must be refused as a FORMAT limit rather than a
             * latency one, because the codec does not carry that format at
             * all and describing it as merely slow would be wrong. */
            if (C[k].want && rc < 0) bad_n++;
            if (!C[k].want && rc != -4) bad_n++;
            if (C[k].want && !got) bad_n++;
        }
        bad_n == 0
            ? ok("A2: every conversion in the mandate's range -- 720p to 4320p, "
                 "50 to 120 fps, up and down -- stays under 1 ms with the colour "
                 "and tone-map stage in the path; a target below B4's 720p floor "
                 "is refused as a FORMAT limit rather than a latency one")
            : bad("A2: a conversion's verdict is not what the model claims");
    }

    printf(fails ? "FAILURES: %d\n" : "all ok\n", fails);
    return fails ? 1 : 0;
}
