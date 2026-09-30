/* Generate the normative colour-conversion tables for OMC-CC.
 *
 * The same discipline the polyphase bank now follows (finding C1): every
 * constant is generated ONCE, offline, and published, so nothing on a normative
 * path calls libm and two vendors cannot disagree because their sin() differs.
 *
 * Emits src/cc_tab.c.inc:
 *   - one EOTF table per transfer: 12-bit code -> linear light, Q16.16
 *   - the primaries matrices, linear light, Q15
 *   - the YCbCr <-> R'G'B' matrices per matrix-coefficient set, Q15
 *
 * Build: cc -O2 gen_cc_tables.c -o gen_cc_tables -lm
 * Run:   ./gen_cc_tables > ../src/cc_tab.c.inc
 */
#include <stdio.h>
#include <math.h>

#define N 4096                      /* 12-bit code space                     */
#define QL 28                       /* linear-light fixed point, 1.0 = 2^QL  */
#define QLF 268435456.0
#define Q15 32768.0                 /* matrix coefficients                   */

/* ---- transfer functions (code' in 0..1 -> linear in 0..1) ---------------- */
static double eotf_gamma(double e) { return pow(e < 0 ? 0 : e, 2.4); }

static double eotf_hlg(double e)    /* ITU-R BT.2100 HLG, scene light */
{
    const double a = 0.17883277, b = 1.0 - 4.0 * a, c = 0.5 - a * log(4.0 * a);
    if (e <= 0.5) return e * e / 3.0;
    return (exp((e - c) / a) + b) / 12.0;
}

typedef double (*eotf_t)(double);
static const struct { const char *name; eotf_t f; } TR[] = {
    { "GAMMA", eotf_gamma }, { "HLG", eotf_hlg },   /* [V536] PQ (ST 2084) removed from the tree: owner ruling 2026-09-06 */
};
#define NTR ((int)(sizeof TR / sizeof TR[0]))

/* ---- primaries, CIE xy ---------------------------------------------------- */
typedef struct { double rx, ry, gx, gy, bx, by, wx, wy; } prim_t;
static const prim_t P709  = {0.640,0.330, 0.300,0.600, 0.150,0.060, 0.3127,0.3290};
static const prim_t P2020 = {0.708,0.292, 0.170,0.797, 0.131,0.046, 0.3127,0.3290};

static void rgb_to_xyz(const prim_t *p, double m[9])
{
    double Xr=p->rx/p->ry, Yr=1, Zr=(1-p->rx-p->ry)/p->ry;
    double Xg=p->gx/p->gy, Yg=1, Zg=(1-p->gx-p->gy)/p->gy;
    double Xb=p->bx/p->by, Yb=1, Zb=(1-p->bx-p->by)/p->by;
    double Xw=p->wx/p->wy, Yw=1, Zw=(1-p->wx-p->wy)/p->wy;
    double d = Xr*(Yg*Zb-Yb*Zg) - Xg*(Yr*Zb-Yb*Zr) + Xb*(Yr*Zg-Yg*Zr);
    double sr = ( Xw*(Yg*Zb-Yb*Zg) - Xg*(Yw*Zb-Yb*Zw) + Xb*(Yw*Zg-Yg*Zw)) / d;
    double sg = ( Xr*(Yw*Zb-Yb*Zw) - Xw*(Yr*Zb-Yb*Zr) + Xb*(Yr*Zw-Yw*Zr)) / d;
    double sb = ( Xr*(Yg*Zw-Yw*Zg) - Xg*(Yr*Zw-Yw*Zr) + Xw*(Yr*Zg-Yg*Zr)) / d;
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

/* Quantise a 3x3 to Q15.
 *
 * `fold` selects WHICH invariant is protected, and getting that choice wrong is
 * exactly the bug this note exists to record.
 *
 * fold = 1 -- protect the ROW SUM.  Correct for the primaries matrices and for
 * R'G'B' -> YCbCr, whose rows sum to exactly 1 (luma) or exactly 0 (the two
 * chroma rows) in real arithmetic.  Rounding each coefficient on its own loses
 * that: a luma row summing to 32767 puts a permanent half-code cast on white,
 * and a chroma row summing to 1 instead of 0 puts chroma on every grey.  So the
 * residue is folded into the largest-magnitude term of the row -- the same trick
 * the polyphase tables use for unity DC, for the same reason.
 *
 * fold = 0 -- protect nothing; round each term independently.  Correct for
 * YCbCr -> R'G'B', whose row sums (1 + 0 + 1.5748 for the R row of BT.709) mean
 * nothing physical: they are the value you would get from Y=Cb=Cr=1, which is
 * not a colour.  Folding a residue into such a row moved up to one count into
 * the *luma* column, and since the luma column is exactly 1.0 -- the property
 * that makes a grey stay grey -- that fold was the direct cause of the
 * "grey 152 -> Cb 512 Cr 511" failure: Y2R[3] came out 32767, R != G, and the
 * neutral axis picked up chroma.  Plain rounding gives 1.0 -> 32768 exactly and
 * 0.0 -> 0 exactly, so the grey axis survives with no fixing up at all. */
static void emit_mat_q(const char *name, const double m[9], int fold, double q1, int qb)
{
    int i, r, k;
    long q[9];
    for (i = 0; i < 9; i++)
        q[i] = (long)(m[i] * q1 + (m[i] < 0 ? -0.5 : 0.5));
    if (fold) for (r = 0; r < 3; r++) {
        double want = m[r*3] + m[r*3+1] + m[r*3+2];
        long tgt = (long)(want * q1 + (want < 0 ? -0.5 : 0.5));
        long got = q[r*3] + q[r*3+1] + q[r*3+2];
        int big = r*3;
        for (k = r*3; k < r*3+3; k++)
            if (fabs(m[k]) > fabs(m[big])) big = k;
        q[big] += tgt - got;
    }
    printf("static const int32_t %s[9] = {", name);
    for (i = 0; i < 9; i++) printf("%s%8ld", i ? ", " : " ", q[i]);
    printf(" };   /* Q%d, %s */\n", qb,
           fold ? "exact row sums" : "plain round, exact luma column");
}

static void emit_mat_f(const char *name, const double m[9], int fold)
{
    emit_mat_q(name, m, fold, Q15, 15);
}

/* The PRIMARIES matrices get more fraction bits than the YCbCr matrices, and
 * the reason is conditioning rather than taste.  BT.2020 -> BT.709 has entries
 * of 1.66 and -0.588, and for a saturated near-primary colour those terms very
 * nearly cancel: an inverse-matrix output of 2e-5 is the residue of two terms of
 * order 0.26, an amplification of about 10^4.  At Q15 the coefficients' own
 * 1.5e-5 relative error therefore lands as a ~20% error on that residue, and
 * because the inverse transfer is near-vertical at black, that shows up as
 * several output codes.  Q20 buys back five bits exactly where the arithmetic
 * is weakest, and costs only a wider constant-multiply chain -- no dividers, no
 * new multipliers.  The YCbCr matrices are well conditioned and stay at Q15. */
static void emit_prim(const char *name, const double m[9])
{
    emit_mat_q(name, m, 1, (double)(1L << 20), 20);
}

static void emit_mat(const char *name, const double m[9]) { emit_mat_f(name, m, 1); }

/* ---- log2 / exp2 tables ---------------------------------------------------
 *
 * Tone mapping multiplies every component by a gain that depends on the pixel's
 * own luminance.  That is a VARIABLE times a VARIABLE, which is exactly the
 * per-pixel multiplier C3 forbids -- so the whole stage is done in the LOG
 * domain, where the multiply is an add.  log2 and exp2 are a priority encoder,
 * a shift and one table lookup each: shifts, adds and lookups only.
 *
 *   CC_LOG2M[i] = log2(1 + i/4096) in Q16, i.e. the mantissa's contribution;
 *                 the exponent comes from the leading-one position.
 *   CC_EXP2F[i] = 2^(i/4096) in Q30, so the integer part of the exponent is a
 *                 shift and the fraction is this lookup.
 */
static void emit_logexp(void)
{
    int i;
    printf("\n/* log2 mantissa, Q16: log2(1 + i/4096).  Leading-one position\n"
           " * supplies the exponent, so this is the whole of log2. */\n");
    printf("static const int32_t CC_LOG2M[%d] = {\n   ", N);
    for (i = 0; i < N; i++) {
        printf("%6ld,", (long)(log2(1.0 + (double)i / N) * 65536.0 + 0.5));
        if ((i & 11) == 11) printf("\n   ");
    }
    printf("\n};\n");
    printf("\n/* 2^(i/4096) in Q30.  Integer part of the exponent is a shift. */\n");
    printf("static const int32_t CC_EXP2F[%d] = {\n   ", N);
    for (i = 0; i < N; i++) {
        printf("%11ld,", (long)(pow(2.0, (double)i / N) * 1073741824.0 + 0.5));
        if ((i & 7) == 7) printf("\n   ");
    }
    printf("\n};\n");
}

/* ---- tone mapping --------------------------------------------------------
 *
 * The curve is ITU-R BT.2390's EETF -- a Hermite knee in the PQ domain, with
 * the source and target luminances DECLARED rather than inferred.  It has no
 * taste parameters: given "this signal peaks at 1000 nits, that display reaches
 * 100", the curve follows.  What taste there is lives in one declared constant,
 * the saturation exponent, and it is published per curve rather than tuned per
 * picture.
 *
 * A curve is tabulated as log2 GAIN against log2 LUMINANCE IN NITS, because
 * that is the form the log-domain datapath consumes directly:
 *   index = (log2(L_nits) * 65536 + 16 * 65536) >> 9      -- a shift, no divide
 *   value = log2(L_out / L_in) in Q10, int16
 * 4096 entries of step 2^-9 log2 covers 32 octaves, 1/16384 nit to 16384 nits,
 * which is past both ends of any broadcast container.
 */
#define TM_N 4096
#define TM_STEP 512.0                  /* Q16 log2 units per entry */
#define TM_BASE (-16.0)                /* log2 nits at index 0     */

/* [V536] The BT.2390 EETF (HDR -> SDR knee) was computed in the ST 2084 code domain and went
 * with the PQ removal (owner ruling 2026-09-06: PQ out of the tree entirely; HLG stays).  The
 * declared set is now the SDR -> HLG reference-white alignment only, which uses no PQ
 * arithmetic.  An HLG -> SDR curve defined without the ST 2084 domain is a legal-team question
 * first (MEMO_TO_LEGAL_REVIEW_from_Fable_002.md), then a design one. */

/* The declared tone-map set.  A conversion outside it is refused, exactly as an
 * undeclared scaling ratio is: a tone map nobody has published constants for is
 * a tone map nobody can reproduce. */
typedef struct {
    const char *name;
    double Lsrc, Ldst;   /* declared peak luminances, nits */
    int inverse;         /* 1 = invert the EETF (SDR -> HDR) */
} tmcurve_t;
static const tmcurve_t TM[] = {
    { "SDR100_HLG1000",  1000,  100, 1 },  /* SDR up onto an HLG wall            */
};
#define NTM ((int)(sizeof TM / sizeof TM[0]))

/* SDR -> HDR is NOT the numerical inverse of the EETF, and finding that out the
 * hard way is worth recording.
 *
 * The forward EETF is compressive and its slope goes to ZERO at the source
 * peak, so its inverse is VERTICAL there.  Tabulated, that inverse maps 94.6
 * nits to 287 and 100 nits to 1000 -- a 3x jump across the top 5 % of the SDR
 * range.  It is monotonic, it passes an endpoint check, and it would tear every
 * highlight in the picture apart.  A curve can be arithmetically correct and
 * still be the wrong function.
 *
 * What SDR -> HDR should do is what ITU-R BT.2408 says: put SDR diffuse white
 * where HDR diffuse white belongs, which is 203 cd/m2 for both PQ and HLG
 * systems.  That is a straight gain in linear light -- 203/100 = 2.03, a
 * CONSTANT log2 gain of 1.0215 across the whole range -- and it is exactly
 * conditioned everywhere.
 *
 * It also invents nothing, which is the point.  An SDR signal carries no
 * information above diffuse white; the headroom an HDR container has above 203
 * nits is for specular highlights the source never recorded.  Filling it is a
 * creative decision, and this codec declines creative decisions in the same
 * breath as it declines an undeclared tone map.  A facility that wants
 * synthetic highlights wants a colourist, not a codec. */
#define REF_WHITE 203.0

static double refwhite_up(double L, double Lsdr, double Ldst)
{
    double o = L * (REF_WHITE / Lsdr);
    return o > Ldst ? Ldst : o;
}

static void emit_tm(void)
{
    int c, i;
    printf("\n#define CC_TM_N %d\n", TM_N);
    printf("#define CC_TM_SHIFT 9      /* Q16 log2 nits >> 9 = table index */\n");
    printf("#define CC_TM_BIAS %d      /* +16.0 in Q16, so index 0 is 2^-16 nits */\n",
           (int)(-TM_BASE * 65536.0));
    for (c = 0; c < NTM; c++) {
        printf("\n/* %s: %.0f nit source onto a %.0f nit display, %s.\n"
               " * log2 gain in Q10. */\n", TM[c].name, TM[c].Lsrc, TM[c].Ldst,
               "reference-white alignment (BT.2408)");
        printf("static const int16_t CC_TM_%s[CC_TM_N] = {\n   ", TM[c].name);
        for (i = 0; i < TM_N; i++) {
            double l2 = TM_BASE + (double)i * TM_STEP / 65536.0;
            double L = pow(2.0, l2), Lo, g;
            /* `inverse` selects the UP direction, which is a reference-white
             * alignment rather than an inverted knee -- see refwhite_up().
             * Lsrc/Ldst are read as (HDR peak, SDR peak) for a forward curve;
             * for an up-mapping the SDR peak is Ldst and the HDR peak Lsrc. */
            Lo = refwhite_up(L, TM[c].Ldst, TM[c].Lsrc);   /* [V536] up-mappings only */
            if (Lo < 1e-12) Lo = 1e-12;
            g = log2(Lo / L) * 1024.0;
            if (g > 32767) g = 32767;
            if (g < -32768) g = -32768;
            printf("%7ld,", (long)(g < 0 ? g - 0.5 : g + 0.5));
            if ((i & 11) == 11) printf("\n   ");
        }
        printf("\n};\n");
    }
    printf("\ntypedef struct {\n"
           "    uint8_t  src_trc, dst_trc;\n"
           "    uint16_t src_peak, dst_peak;   /* declared, nits */\n"
           "    int32_t  sat;                  /* saturation exponent, Q15 */\n"
           "    const int16_t *gain;           /* NULL = container change only */\n"
           "} cc_tm_entry_t;\n\n");
    printf("static const cc_tm_entry_t CC_TM_TAB[] = {\n");
    printf("    {  1, 18,  100, 1000, %5d, CC_TM_SDR100_HLG1000 },\n",  (int)(1.00*32768));
    printf("    { 18, 18, 1000, 1000, %5d, 0 },   /* HLG container, declared peak: identity */\n",
           (int)(1.00*32768));
    printf("};\n#define CC_TM_NTAB ((int)(sizeof CC_TM_TAB / sizeof CC_TM_TAB[0]))\n");
}

int main(void)
{
    int t, i;
    double a[9], b[9], ia[9], m[9];

    printf("/* GENERATED by repro/gen_cc_tables.c -- do not edit.\n"
           " * OMC-CC normative tables.  No libm on any runtime path.\n"
           " *   CC_EOTF[t][code]  12-bit code' -> linear light, Q%d\n"
           " *   CC_P_*            primaries conversion in LINEAR light, Q15\n"
           " *   CC_M_*            YCbCr <-> R'G'B', Q15\n"
           " *\n"
           " * The linear tables are Q%d, not the Q16.16 an earlier draft used.\n"
           " * Gamma 2.4 is very flat near black: at Q16.16 the first THIRTY 12-bit\n"
           " * codes all quantise to linear 0, so every one of them came back out of\n"
           " * the inverse lookup as code 0 and near-black colours lost up to 30\n"
           " * codes -- the dominant term in a 53-code worst-case round trip.  At\n"
           " * Q%d only code 0 is degenerate.  The tables stay int32 (1.0 = 2^%d,\n"
           " * and the largest tabulated value is HLG's 1.00006) and every product\n"
           " * is accumulated in int64, so nothing overflows. */\n\n",
           QL, QL, QL, QL);
    printf("#define CC_N %d\n#define CC_NTR %d\n#define CC_QL %d\n\n", N, NTR, QL);

    printf("static const int32_t CC_EOTF[CC_NTR][CC_N] = {\n");
    for (t = 0; t < NTR; t++) {
        printf("  { /* %s */\n   ", TR[t].name);
        for (i = 0; i < N; i++) {
            double v = TR[t].f((double)i / (N - 1)) * QLF;
            if (v < 0) v = 0;
            if (v > 2147483000.0) v = 2147483000.0;
            printf("%10ld,", (long)(v + 0.5));
            if ((i & 7) == 7) printf("\n   ");
        }
        printf("\n  },\n");
    }
    printf("};\n\n");

    /* primaries: 709 -> 2020 and back, in linear light */
    printf("#define CC_QP 20   /* primaries matrices are Q20, see gen_cc_tables.c */\n");
    rgb_to_xyz(&P709, a); rgb_to_xyz(&P2020, b);
    inv3(b, ia); mul3(ia, a, m); emit_prim("CC_P_709_2020", m);
    rgb_to_xyz(&P2020, a); rgb_to_xyz(&P709, b);
    inv3(b, ia); mul3(ia, a, m); emit_prim("CC_P_2020_709", m);
    { double id[9] = {1,0,0, 0,1,0, 0,0,1}; emit_prim("CC_P_IDENT", id); }

    /* YCbCr <-> R'G'B' for each matrix-coefficient set, non-constant luminance */
    {
        const struct { const char *n; double kr, kb; } K[] = {
            { "709",  0.2126, 0.0722 },
            { "2020", 0.2627, 0.0593 },
            { "601",  0.2990, 0.1140 },
        };
        int j;
        for (j = 0; j < 3; j++) {
            double kr = K[j].kr, kb = K[j].kb, kg = 1 - kr - kb;
            double y2r[9] = { 1, 0, 2*(1-kr),
                              1, -2*(1-kb)*kb/kg, -2*(1-kr)*kr/kg,
                              1, 2*(1-kb), 0 };
            double r2y[9] = { kr, kg, kb,
                              -kr/(2*(1-kb)), -kg/(2*(1-kb)), 0.5,
                              0.5, -kg/(2*(1-kr)), -kb/(2*(1-kr)) };
            char nm[64];
            sprintf(nm, "CC_M_Y2R_%s", K[j].n); emit_mat_f(nm, y2r, 0);
            sprintf(nm, "CC_M_R2Y_%s", K[j].n); emit_mat_f(nm, r2y, 1);
        }
    }
    emit_logexp();
    emit_tm();
    return 0;
}
