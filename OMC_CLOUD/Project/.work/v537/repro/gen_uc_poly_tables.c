/* Generate the normative polyphase coefficient tables for OMC-UC.
 *
 * src/upconv.c originally built these at RUNTIME in double precision (sin/sqrt
 * plus a 30-term Bessel series), which made the non-dyadic path's coefficients
 * a function of the host libm rather than normative constants -- see finding
 * C1.  The tightest coefficient sits 0.0038 from a rounding tie, so a differing
 * sin(), an x87 80-bit intermediate or FMA contraction can flip a tap and
 * change the picture.
 *
 * This program is bit-identical to the original uc_build_poly().  Its output is
 * src/uc_poly_tab.c.inc, which the codec now includes instead of computing:
 * every supported conversion has published constants and no libm call remains
 * on any normative path.
 *
 * Build: cc -O2 gen_uc_poly_tables.c -o gen_uc_poly_tables -lm
 * Run:   ./gen_uc_poly_tables            # the .inc, on stdout
 *        ./gen_uc_poly_tables --report   # human-readable, with tie margins
 */
#include <stdio.h>
#include <string.h>
#include <math.h>

#define K 12
#define MAXTAPS 48
#define PI 3.14159265358979323846

/* The DECLARED supported set.  Interpolation is any denominator up to 16 (the
 * phase-count cap); decimation is an enumerated list, because its aperture --
 * and therefore its table, its reach and its latency -- depends on the ratio.
 * A conversion outside this set is refused rather than approximated. */
static const int DEC[][2] = {           /* {num, den}, num > den */
    {2, 1}, {3, 1}, {4, 1},             /* 2:1, 3:1, 4:1                     */
    {3, 2}, {5, 2},                     /* 1080->720, 2160->864              */
    {4, 3}, {5, 3},                     /* 4:3, 5:3                          */
    {5, 4},                             /* 5:4                               */
    {6, 5}, {7, 6}, {8, 7}, {9, 8},     /* near-unity: aspect framing needs
                                         * these -- 14:9 alone wants 7/6 and
                                         * 8/7 -- and they are cheap because a
                                         * near-unity aperture stays near 12  */
};
#define NDEC ((int)(sizeof DEC / sizeof DEC[0]))

static int taps(int num, int den)
{
    int nt;
    if (num <= den) return K;
    nt = (K * num + den - 1) / den;
    nt = (nt + 1) & ~1;
    return nt > MAXTAPS ? 0 : nt;
}

/* Bit-identical to the original uc_build_poly() body. */
static double tie_worst;
static void build(int num, int den, int q[MAXTAPS * 16], int *ntp)
{
    int ph, k, m, nt = taps(num, den);
    double D = num > den ? (double)num / (double)den : 1.0;
    *ntp = nt;
    tie_worst = 1.0;
    for (ph = 0; ph < den; ph++) {
        double w[MAXTAPS], sum = 0.0;
        double t = (double)ph / (double)den;
        int big = 0, acc = 0;
        for (k = 0; k < nt; k++) {
            double x = ((double)(k - (nt / 2 - 1)) - t) / D;
            double sinc = (x == 0.0) ? 1.0 : sin(PI * x) / (PI * x);
            double a = 2.0 * (double)k / (double)(nt - 1) - 1.0;
            double bi = 0.0, term = 1.0, arg = 6.0 * sqrt(1.0 - a * a) / 2.0;
            double b0 = 0.0, t0 = 1.0, a0 = 6.0 / 2.0;
            for (m = 1; m < 30; m++) { term *= (arg * arg) / (double)(m * m); bi += term; }
            for (m = 1; m < 30; m++) { t0 *= (a0 * a0) / (double)(m * m); b0 += t0; }
            w[k] = sinc * (1.0 + bi) / (1.0 + b0);
            sum += w[k];
        }
        for (k = 0; k < nt; k++) {
            double v = w[k] / sum * 1024.0;
            double d = fabs(v - floor(v) - 0.5);
            if (d < tie_worst) tie_worst = d;
            q[ph * nt + k] = (int)(v < 0 ? -(int)(-v + 0.5) : (int)(v + 0.5));
            acc += q[ph * nt + k];
            if (w[k] > w[big]) big = k;
        }
        q[ph * nt + big] += 1024 - acc;          /* exact unity DC gain */
    }
}

static void emit(int num, int den, int report)
{
    int q[MAXTAPS * 16], nt, ph, k;
    build(num, den, q, &nt);
    if (report) {
        printf("/* %d/%d  nt=%d  tie margin %.4f */\n", num, den, nt, tie_worst);
        for (ph = 0; ph < den; ph++) {
            printf("  {");
            for (k = 0; k < nt; k++) printf("%5d%s", q[ph * nt + k], k < nt - 1 ? "," : "");
            printf(" },   /* phase %d/%d */\n", ph, den);
        }
        printf("\n");
        return;
    }
    printf("static const int32_t UC_P_%d_%d[%d] = {\n", num, den, den * nt);
    for (ph = 0; ph < den; ph++) {
        printf("   ");
        for (k = 0; k < nt; k++) printf("%5d,", q[ph * nt + k]);
        printf("   /* phase %d/%d */\n", ph, den);
    }
    printf("};\n");
}

int main(int argc, char **argv)
{
    int report = argc > 1 && !strcmp(argv[1], "--report");
    int i, den;

    if (report) {
        printf("OMC-UC polyphase tables, /1024, exact unity DC.\n"
               "'tie margin' is the closest any coefficient came to a .5 rounding\n"
               "boundary -- the smaller it is, the more a differing libm or an\n"
               "x87/FMA intermediate could have flipped that tap by one.\n\n");
        for (den = 1; den <= 5; den++) emit(1, den, 1);
        for (i = 0; i < NDEC; i++) emit(DEC[i][0], DEC[i][1], 1);
        return 0;
    }

    printf("/* GENERATED by repro/gen_uc_poly_tables.c -- do not edit.\n"
           " * Normative polyphase coefficients, /1024, exact unity DC gain.\n"
           " * Interpolation: denominators 1..16 (aperture 12).\n"
           " * Decimation: the declared ratio set; aperture scales with num/den.\n"
           " * omc_uc_selfcheck_poly() verifies these at run time. */\n\n");
    for (den = 1; den <= 16; den++) emit(1, den, 0);
    for (i = 0; i < NDEC; i++) emit(DEC[i][0], DEC[i][1], 0);

    printf("\ntypedef struct {\n"
           "    uint8_t num, den, nt;\n"
           "    const int32_t *c;\n"
           "} uc_poly_entry_t;\n\n"
           "static const uc_poly_entry_t UC_POLY_TAB[] = {\n");
    for (den = 1; den <= 16; den++)
        printf("    { 1, %2d, %2d, UC_P_1_%d },\n", den, K, den);
    for (i = 0; i < NDEC; i++)
        printf("    { %d, %d, %2d, UC_P_%d_%d },\n", DEC[i][0], DEC[i][1],
               taps(DEC[i][0], DEC[i][1]), DEC[i][0], DEC[i][1]);
    printf("};\n#define UC_POLY_NTAB ((int)(sizeof UC_POLY_TAB / "
           "sizeof UC_POLY_TAB[0]))\n");
    return 0;
}
