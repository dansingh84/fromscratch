/* C unit tests: DWT reversibility, quantizer idempotence, tANS roundtrip,
 * bit IO, and a full slice encode/decode == encoder-recon check on synthetic
 * data. Run via `make test`. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../src/internal.h"

static int fails = 0;
#define CHECK(cond, name) do { \
    if (!(cond)) { printf("FAIL: %s\n", name); fails++; } \
    else printf("ok: %s\n", name); } while (0)

static uint32_t rng_state = 12345;
static uint32_t rnd(void) { rng_state = rng_state * 1103515245u + 12345u; return rng_state >> 8; }

static void test_dwt(void)
{
    enum { W = 256, SH = 16 };
    int32_t *buf = malloc(sizeof(int32_t) * W * SH);
    int32_t *ref = malloc(sizeof(int32_t) * W * SH);
    int32_t tmp[W];
    for (int i = 0; i < W * SH; i++) ref[i] = buf[i] = (int32_t)(rnd() % 4096) - 2048;
    omc_slice_fwd(buf, W, SH, tmp);
    omc_slice_inv(buf, W, SH, tmp);
    CHECK(memcmp(buf, ref, sizeof(int32_t) * W * SH) == 0, "dwt 16-line reversibility");
    for (int i = 0; i < W * 8; i++) ref[i] = buf[i] = (int32_t)(rnd() % 4096) - 2048;
    omc_slice_fwd(buf, W, 8, tmp);
    omc_slice_inv(buf, W, 8, tmp);
    CHECK(memcmp(buf, ref, sizeof(int32_t) * W * 8) == 0, "dwt 8-line reversibility");
    free(buf); free(ref);
}

/* [V536] The level-2 two-sided boundary predictor (OMC_VEXT = -2, OMC_VEXT_LVL = 2; a qualified candidate, not shipped):
 * (a) perfect reconstruction at the shipped setting, at the mirror, and at the other levels/strengths
 *     a probe can select -- a lifting step is exactly invertible for ANY predictor built from values
 *     both sides already hold;
 * (b) NON-VACUITY: the shipped setting produces different coefficients from the mirror (a test that
 *     passes because the lever never acted is the failure class Agent 3 C31 found). */
static void test_vext_pr(void)
{
    enum { W = 128 };
    int32_t *ref = malloc(sizeof(int32_t) * W * 32), *buf = malloc(sizeof(int32_t) * W * 32);
    int32_t *cm = malloc(sizeof(int32_t) * W * 32), tmp[W];
    int sv = omc_vext, sl = omc_vext_lvl, ok = 1, differ = 0;
    static const int strengths[] = { 0, -2, -4, 2, 4 }, levels[] = { 1, 2, 3 };
    for (int a = 0; a < 5 && ok; a++)
        for (int l = 0; l < 3 && ok; l++)
            for (int sh = 16; sh <= 32 && ok; sh += 16) {
                omc_vext = strengths[a]; omc_vext_lvl = levels[l];
                for (int i = 0; i < W * sh; i++) ref[i] = buf[i] = (int32_t)(rnd() % 4096) - 2048;
                omc_slice_fwd(buf, W, sh, tmp);
                if (strengths[a] == 0) memcpy(cm, buf, sizeof(int32_t) * W * sh);
                if (strengths[a] == -2 && levels[l] == 2 && sh == 16 && memcmp(cm, buf, sizeof(int32_t) * W * sh) != 0) differ = 1;
                omc_slice_inv(buf, W, sh, tmp);
                if (memcmp(buf, ref, sizeof(int32_t) * W * sh) != 0) ok = 0;
            }
    omc_vext = sv; omc_vext_lvl = sl;
    CHECK(ok, "boundary predictor: exact reconstruction at strengths {0,-2,-4,2,4} x levels {1,2,3} x slice heights {16,32}");
    CHECK(differ, "boundary predictor NON-VACUITY: the candidate setting (-2, level 2) changes the coefficients relative to the mirror");
    CHECK(sv == 0 && sl == 3, "boundary predictor: the shipped defaults are OMC_VEXT = 0, OMC_VEXT_LVL = 3 (candidate not shipped: G-T5-CUT24)");
    free(ref); free(buf); free(cm);
}

static void test_quant(void)
{
    int ok = 1;
    for (int s = 0; s <= 12 && ok; s++)
        for (int i = 0; i < 20000; i++) {
            int32_t c = (int32_t)(rnd() % 65536) - 32768;
            int32_t q = omc_quant1(c, s);
            int32_t r = omc_dequant1(q, s);
            if (omc_quant1(r, s) != q) { ok = 0; break; }
        }
    CHECK(ok, "quantizer idempotence (all shifts)");
}

static void test_tans(void)
{
    omc_tans_init();
    enum { N = 50000 };
    uint8_t *syms = malloc(N), *tids = malloc(N);
    /* mixed-table symbol stream with a plausible skewed distribution */
    for (int i = 0; i < N; i++) {
        uint32_t r = rnd() % 100;
        syms[i] = r < 70 ? 0 : r < 85 ? 1 : r < 93 ? 2 : r < 97 ? 3 : (uint8_t)(4 + rnd() % 6);
        tids[i] = (uint8_t)(rnd() % (OMC_NTABLES * OMC_NCTX));
    }
    uint8_t *buf = malloc(4 * N + 64);
    omc_bw_t bw;
    omc_bw_init(&bw, buf, 4 * N + 64);
    uint32_t state = OMC_TANS_L;
    for (int k = N; k-- > 0;) {
        const omc_tans_table_t *T = &omc_tans[tids[k] / OMC_NCTX][tids[k] % OMC_NCTX];
        int s = syms[k];
        int nb = (int)(((int64_t)state + T->delta_nbits[s]) >> 16);
        omc_bw_put(&bw, state & ((1u << nb) - 1), nb);
        state = T->next_state[T->delta_find[s] + (state >> nb)];
    }
    size_t bits = omc_bw_finish(&bw);
    omc_br_t br;
    omc_br_init(&br, buf, bits);
    int ok = 1;
    for (int i = 0; i < N; i++) {
        const omc_tans_table_t *T = &omc_tans[tids[i] / OMC_NCTX][tids[i] % OMC_NCTX];
        uint32_t st = state - OMC_TANS_L;
        if (T->sym[st] != syms[i]) { ok = 0; break; }
        state = T->base[st] + omc_br_get(&br, T->nbits[st]) + OMC_TANS_L;
    }
    CHECK(ok && state == OMC_TANS_L, "tANS multi-table roundtrip");
    free(syms); free(tids); free(buf);
}

static void test_slice_roundtrip(void)
{
    omc_config_t cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.width = 256; cfg.height = 64; cfg.bitdepth = 10;
    cfg.chroma = OMC_CF_422; cfg.ver_minor = OMC_VERSION_MINOR; cfg.slice_h = 16;
    cfg.fps_num = 50; cfg.fps_den = 1;
    cfg.bits_per_slice = (uint32_t)(2.0 * 256 * 16) / 8 * 8;
    int W = 256, H = 64, Wc = 128;
    size_t ysz = (size_t)W * H, csz = (size_t)Wc * H;
    uint16_t *pix = malloc((ysz + 2 * csz) * 2);
    uint16_t *rec = malloc((ysz + 2 * csz) * 2);
    uint16_t *dec = malloc((ysz + 2 * csz) * 2);
    /* synthetic: gradient + noise + edges (T5 biased domain) */
    for (size_t i = 0; i < ysz + 2 * csz; i++)
        pix[i] = (uint16_t)((i * 7 % 900) + 64 + (rnd() % 32) + OMC_PIX_BIAS);
    omc_frame_t fin = {{pix, pix + ysz, pix + ysz + csz}, {W, Wc, Wc}};
    omc_frame_t frec = {{rec, rec + ysz, rec + ysz + csz}, {W, Wc, Wc}};
    omc_frame_t fdec = {{dec, dec + ysz, dec + ysz + csz}, {W, Wc, Wc}};

    omc_enc_t *e = omc_enc_create(&cfg);
    omc_dec_t *d = omc_dec_create(&cfg);
    int nsl = omc_num_slices(&cfg);
    size_t sb = cfg.bits_per_slice / 8;
    uint8_t *bs = malloc(sb * (size_t)nsl);
    int64_t n = omc_enc_frame(e, &fin, 0, bs, sb * (size_t)nsl, &frec);
    CHECK(n == (int64_t)(sb * (size_t)nsl), "encode produces exact CBR bytes");
    int64_t m = omc_dec_frame(d, bs, (size_t)n, &fdec);
    CHECK(m == nsl, "decode recovers all slices");
    CHECK(memcmp(rec, dec, (ysz + 2 * csz) * 2) == 0, "rt=0: decoder == encoder recon");
    omc_enc_destroy(e); omc_dec_destroy(d);
    free(pix); free(rec); free(dec); free(bs);
}

static void test_causality(void)
{
    /* Strict causality (C2): encoding slice k must depend only on rows
     * [0, (k+1)*sh) - nothing below. We poison all future rows before each
     * slice call and require byte-identical output vs the clean encode. */
    omc_config_t cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.width = 256; cfg.height = 64; cfg.bitdepth = 10;
    cfg.chroma = OMC_CF_422; cfg.ver_minor = OMC_VERSION_MINOR; cfg.slice_h = 16;
    cfg.fps_num = 50; cfg.fps_den = 1;
    cfg.bits_per_slice = (uint32_t)(2.0 * 256 * 16) / 8 * 8;
    int W = 256, H = 64, Wc = 128, sh = 16;
    size_t ysz = (size_t)W * H, csz = (size_t)Wc * H;
    size_t words = ysz + 2 * csz;
    uint16_t *pix = malloc(words * 2);
    uint16_t *poison = malloc(words * 2);
    for (size_t i = 0; i < words; i++)
        pix[i] = (uint16_t)((rnd() % 1024) + OMC_PIX_BIAS);
    omc_frame_t f1 = {{pix, pix + ysz, pix + ysz + csz}, {W, Wc, Wc}};
    omc_frame_t f2 = {{poison, poison + ysz, poison + ysz + csz}, {W, Wc, Wc}};

    int nsl = omc_num_slices(&cfg);
    size_t sb = cfg.bits_per_slice / 8;
    uint8_t *ref = malloc(sb * (size_t)nsl), *got = malloc(sb * (size_t)nsl);
    omc_enc_t *e1 = omc_enc_create(&cfg);
    int64_t n1 = omc_enc_frame(e1, &f1, 0, ref, sb * (size_t)nsl, NULL);

    omc_enc_t *e2 = omc_enc_create(&cfg);
    size_t off = 0;
    int ok = (n1 > 0);
    for (int k = 0; k < nsl && ok; k++) {
        memcpy(poison, pix, words * 2);
        /* T5 causality bound: slice k depends on input rows
         * [0, (k+1)*sh + 2) — the mandatory un-blend of the slice's last
         * boundary row reads the two rows below it (a fixed 2-line
         * lookahead, documented in TEMPORAL_T5.md).  Poison strictly below
         * that bound.  Slice-level callers apply the un-blend themselves
         * (omc_enc_frame does it internally). */
        for (int p = 0; p < 3; p++) {
            int pw = p == 0 ? W : Wc;
            uint16_t *pl = f2.p[p];
            for (int r = (k + 1) * sh + 2; r < H; r++)
                for (int x = 0; x < pw; x++)
                    pl[(size_t)r * pw + x] = (uint16_t)((rnd() % 1024) + OMC_PIX_BIAS);
        }
        omc_xsl_unblend(&f2, &cfg, 0);
        int r = omc_enc_slice(e2, &f2, 0, k, got + off, NULL);
        if (r < 0) { ok = 0; break; }
        if (memcmp(got + off, ref + off, (size_t)r) != 0) ok = 0;
        off += (size_t)r;
    }
    CHECK(ok, "causality: poisoned rows beyond the 2-line un-blend lookahead "
              "do not change slice bytes");
    omc_enc_destroy(e1); omc_enc_destroy(e2);
    free(pix); free(poison); free(ref); free(got);
}

/* Reentrancy: two encoder instances, frames interleaved A,B,A,B..., must
 * each produce byte-identical streams to fresh sequential runs. Guards the
 * fix that moved the lattice work buffers out of function-local statics
 * (which silently cross-contaminated instances). */
static void fill_frame(uint16_t *pix, size_t n, uint32_t seed)
{
    uint32_t x = seed;
    for (size_t i = 0; i < n; i++) {
        x = x * 1103515245u + 12345u;
        pix[i] = (uint16_t)(64 + ((x >> 16) % 800) + OMC_PIX_BIAS);
    }
}

static void test_reentrancy(void)
{
    omc_config_t cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.width = 64; cfg.height = 32; cfg.bitdepth = 10;
    cfg.chroma = OMC_CF_422; cfg.ver_minor = OMC_VERSION_MINOR; cfg.slice_h = 16;
    cfg.fps_num = 50; cfg.fps_den = 1;
    cfg.bits_per_slice = 32768;
    int nsl = cfg.height / cfg.slice_h;
    size_t fbytes = (size_t)cfg.bits_per_slice / 8 * nsl;
    int W = cfg.width, H = cfg.height, Wc = W / 2;
    size_t words = (size_t)W * H + 2 * (size_t)Wc * H;
    enum { NF = 4 };
    uint16_t *pa = malloc(words * 2 * NF), *pb = malloc(words * 2 * NF);
    for (int f = 0; f < NF; f++) {
        fill_frame(pa + words * f, words, 0xA0000000u + (uint32_t)f);
        fill_frame(pb + words * f, words, 0xB0000000u + (uint32_t)f);
    }
    uint8_t *sa_seq = malloc(fbytes * NF), *sb_seq = malloc(fbytes * NF);
    uint8_t *sa_int = malloc(fbytes * NF), *sb_int = malloc(fbytes * NF);
    /* sequential references */
    for (int which = 0; which < 2; which++) {
        omc_enc_t *e = omc_enc_create(&cfg);
        uint16_t *src = which ? pb : pa;
        uint8_t *dst = which ? sb_seq : sa_seq;
        for (int f = 0; f < NF; f++) {
            uint16_t *px = src + words * f;
            omc_frame_t fr = {{px, px + (size_t)W * H, px + (size_t)W * H + (size_t)Wc * H},
                              {W, Wc, Wc}};
            omc_enc_frame(e, &fr, f, dst + fbytes * f, fbytes, NULL);
        }
        omc_enc_destroy(e);
    }
    /* interleaved run: one process, two live instances, alternating frames */
    omc_enc_t *ea = omc_enc_create(&cfg), *eb = omc_enc_create(&cfg);
    for (int f = 0; f < NF; f++) {
        uint16_t *px = pa + words * f;
        omc_frame_t fr = {{px, px + (size_t)W * H, px + (size_t)W * H + (size_t)Wc * H},
                          {W, Wc, Wc}};
        omc_enc_frame(ea, &fr, f, sa_int + fbytes * f, fbytes, NULL);
        px = pb + words * f;
        omc_frame_t fr2 = {{px, px + (size_t)W * H, px + (size_t)W * H + (size_t)Wc * H},
                           {W, Wc, Wc}};
        omc_enc_frame(eb, &fr2, f, sb_int + fbytes * f, fbytes, NULL);
    }
    omc_enc_destroy(ea); omc_enc_destroy(eb);
    CHECK(memcmp(sa_seq, sa_int, fbytes * NF) == 0 &&
          memcmp(sb_seq, sb_int, fbytes * NF) == 0,
          "reentrancy: interleaved encoder instances byte-match sequential");
    free(pa); free(pb); free(sa_seq); free(sb_seq); free(sa_int); free(sb_int);
}

static void test_validate(void)
{
    omc_config_t cfg;
    char err[160];
    memset(&cfg, 0, sizeof(cfg));
    /* slice_h now DEFAULTS TO 16 (720p-class excepted, A2), so a 1080-row
     * CODED raster is no longer a legal geometry on its own: 1080 does not
     * divide by 16.  A caller with a 1080 picture codes 1088 rows and sets
     * display_height, exactly as tools/omc_enc.c does (BITSTREAM sec 8
     * pad-and-crop).  Both halves of that contract are asserted here. */
    cfg.width = 1920; cfg.height = 1088; cfg.display_height = 1080;
    cfg.bitdepth = 10;
    cfg.chroma = OMC_CF_422; cfg.slice_h = 0; cfg.fps_num = 50; cfg.fps_den = 1;
    cfg.bits_per_slice = 30720;
    int ok = omc_validate_config(&cfg, err, sizeof err) == 0;
    cfg.height = 1080;                       /* unpadded: must be refused now */
    ok = ok && omc_validate_config(&cfg, err, sizeof err) != 0;
    cfg.slice_h = 8;                         /* ...unless the caller asks for 8 */
    ok = ok && omc_validate_config(&cfg, err, sizeof err) == 0;
    cfg.slice_h = 0; cfg.height = 1088;
    cfg.width = 1900;  /* bad alignment */
    ok = ok && omc_validate_config(&cfg, err, sizeof err) != 0;
    cfg.width = 1920; cfg.bits_per_slice = 3840; /* below 0.3 bpp floor */
    ok = ok && omc_validate_config(&cfg, err, sizeof err) != 0;
    cfg.bits_per_slice = 30720; cfg.bitdepth = 9; /* bad depth */
    ok = ok && omc_validate_config(&cfg, err, sizeof err) != 0;
    cfg.bitdepth = 10; cfg.height = 1084; /* bad height for any slice_h */
    ok = ok && omc_validate_config(&cfg, err, sizeof err) != 0;
    cfg.height = 1088; cfg.color.transfer = 18; /* HLG ok ([V536] 16 = PQ is refused: not carried) */
    ok = ok && omc_validate_config(&cfg, err, sizeof err) == 0;
    cfg.color.transfer = 16;                  /* [V536] PQ (ST 2084) is NOT carried: refused */
    ok = ok && omc_validate_config(&cfg, err, sizeof err) != 0;
    cfg.color.transfer = 1;
    CHECK(ok, "config validator: accepts valid, rejects invalid with reasons");
}

/* RCT bijectivity: forward+inverse must be identity for every value the
 * container can carry (BITSTREAM.md section 8). */
static void test_rct(void)
{
    int ok = 1;
    for (int d = 8; d <= 10 && ok; d += 2) {
        int mid_c = 1 << (d + 1), yoff = mid_c - (1 << (d - 1));
        uint32_t x = 12345;
        for (int i = 0; i < 200000 && ok; i++) {
            x = x * 1103515245u + 12345u;
            int R = (int)((x >> 8) % (1u << d));
            int G = (int)((x >> 18) % (1u << d));
            int B = (int)(x % (1u << d));
            int Y = (R + 2 * G + B) >> 2;
            int p0 = Y + yoff, p1 = B - G + mid_c, p2 = R - G + mid_c;
            int Y2 = p0 - yoff, Cb = p1 - mid_c, Cr = p2 - mid_c;
            int G2 = Y2 - ((Cb + Cr) >> 2);
            int B2 = Cb + G2, R2 = Cr + G2;
            ok = (R2 == R && G2 == G && B2 == B) &&
                 p0 >= 0 && p1 >= 0 && p2 >= 0 &&
                 p0 < (4 << d) && p1 < (4 << d) && p2 < (4 << d);
        }
    }
    CHECK(ok, "RCT: bijective and container-legal at 8/10-bit components");
}


/* ---- [A3-FILLQ] fill amplitude vs quantiser idempotence -------------------
 * MEMO 021 sect.5.3 item 1.  Pins the margin that codec.c:4552 protects.
 *
 * The fill fires ONLY where the committed index is zero and the dequantised
 * value is zero (codec.c: "if (fb && v == 0 && qbuf == 0)" at the encoder,
 * "if (fb && rec == 0 && q == 0)" at the decoder).  So at every fill position
 * m = 0 and r_m = 0, and the generation-exactness requirement Q_s(r_m+g) == m
 * reduces to Q_s(g) == 0: the fill must re-quantise to nothing, or the next
 * generation codes a coefficient where this one coded none.
 *
 * Measured (Agent 3, 71,927,559 fill positions): it never fails in shipping
 * configurations.  It CAN fail: --tune vmaf widens the quantiser bias to
 * 2^(s-1) + 2^(s-3), which narrows the zero zone to 0.375*2^s, and the two
 * loudest gains are 0.375 and 0.4375 of a step.  codec.c:4552 clamps the gain
 * to <= 1 whenever tune_vmaf is on, and that clamp is the whole defence.  The
 * margin without it is 0.4375 against 0.5 -- 12.5% of a step.
 *
 * Case A pins the shipping invariant.  Case B is a WITNESS: it asserts the
 * clamp is still load-bearing.  If B ever fails, the arithmetic changed and the
 * margin analysis must be redone -- it does not necessarily mean something
 * broke, but it must not pass unnoticed. */
static int32_t fill_amp_ref(int s, int div, int gain)
{
    /* transcribed from codec.c fill_value_p */
    int sh = s - 2 - div;
    if (sh < 1) return 0;                 /* refused: too small to carry a fill */
    int32_t a = (int32_t)1 << sh;
    if      (gain == 1) a += a >> 2;      /* 1.25x */
    else if (gain == 2) a += a >> 1;      /* 1.50x */
    else if (gain == 3) a += (a >> 1) + (a >> 2);  /* 1.75x */
    return a;
}

static void test_fill_quant_idempotence(void)
{
    int okA = 1, brokeB = 0, checked = 0;
    int firstA_s = -1, firstA_div = -1, firstA_g = -1, firstA_tex = -1;
    for (int tex = 0; tex <= 1; tex++) {
        /* codec.c:4552 -- with the texture bias on, the gain is clamped to <= 1 */
        int gmax = tex ? 1 : 3;
        for (int s = OMC_FILL_MIN_SHIFT; s <= OMC_MAX_SHIFT; s++) {
            for (int div = 0; div <= 3; div++) {
                for (int g = 0; g <= gmax; g++) {
                    int32_t a = fill_amp_ref(s, div, g);
                    if (!a) continue;                 /* no fill emitted here */
                    for (int dz = 0; dz <= 1; dz++) { /* dz only ever pulls 1 -> 0 */
                        int32_t q = omc_quant1b_dz(a, s, tex, dz);
                        checked++;
                        if (q != 0 && okA) {
                            okA = 0; firstA_s = s; firstA_div = div;
                            firstA_g = g; firstA_tex = tex;
                        }
                        /* the sign-symmetric case must behave identically */
                        if (omc_quant1b_dz(-a, s, tex, dz) != -q) okA = 0;
                    }
                }
            }
        }
    }
    if (!okA)
        printf("   first failure: shift %d divisor %d gain %d texture %d\n",
               firstA_s, firstA_div, firstA_g, firstA_tex);
    CHECK(okA, "fill: Q_s(g) == 0 at every reachable (shift, divisor, gain, texture)");

    /* Case B -- the clamp is load-bearing: with the texture bias, the gains the
     * clamp forbids WOULD re-quantise non-zero.  If this stops being true the
     * margin changed; see the header comment. */
    for (int s = OMC_FILL_MIN_SHIFT; s <= OMC_MAX_SHIFT; s++)
        for (int g = 2; g <= 3; g++) {
            int32_t a = fill_amp_ref(s, 0, g);
            if (a && omc_quant1b_dz(a, s, 1, 0) != 0) brokeB = 1;
        }
    CHECK(brokeB, "fill: the tune_vmaf gain clamp (codec.c:4552) is still load-bearing");
    printf("   (%d amplitude/quantiser combinations checked)\n", checked);
}

int main(void)
{
    test_dwt();
    test_vext_pr();
    test_quant();
    test_tans();
    test_slice_roundtrip();
    test_causality();
    test_reentrancy();
    test_validate();
    test_rct();
    test_fill_quant_idempotence();
    printf(fails ? "%d FAILURES\n" : "all ok\n", fails);
    return fails ? 1 : 0;
}
