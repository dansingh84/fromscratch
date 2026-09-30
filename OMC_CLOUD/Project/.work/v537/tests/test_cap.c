/* The boundary-blend cap is per-CONTEXT, not per-process (CAP_RULE_REVIEW F1).
 *
 * A multi-channel server runs several encoders in one process at DIFFERENT
 * rates, which is exactly what a process-wide cap cannot survive: the last
 * context created would decide the blend for all of them, and a stream encoded
 * with one cap does not reconstruct under another.  This test builds that
 * situation on purpose -- one context below 0.75 bpp (cap 8) and one above
 * (cap 4), alive at the same time, frames interleaved -- and requires each to
 * produce exactly what it produces alone, and to round-trip through its own
 * decoder byte-exactly.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "omc1.h"

static int fails = 0;
#define CHECK(c, m) do { printf("%s: %s\n", (c) ? "ok" : "FAIL", m); \
                         if (!(c)) fails++; } while (0)

enum { W = 256, H = 32, SH = 16, NF = 3 };
#define WC (W / 2)
#define WORDS ((size_t)W * H + 2 * (size_t)WC * H)

static void fill(uint16_t *p, size_t n, uint32_t seed)
{
    uint32_t x = seed;
    for (size_t i = 0; i < n; i++) { x = x * 1103515245u + 12345u;
                                     p[i] = (uint16_t)(64 + ((x >> 16) % 800)
                                                       + OMC_PIX_BIAS); }
}

static void cfg_at(omc_config_t *c, uint32_t bps)
{
    memset(c, 0, sizeof(*c));
    c->width = W; c->height = H; c->bitdepth = 10; c->chroma = OMC_CF_422;
    c->ver_minor = OMC_VERSION_MINOR; c->slice_h = SH;
    c->fps_num = 50; c->fps_den = 1; c->bits_per_slice = bps;
}

/* The cap edits the RECONSTRUCTION (and through it the temporal reference), so
 * the reconstruction is the sensitive observable -- a bitstream comparison only
 * bites once prediction is actually selected, which needs real content. */
static void run(omc_enc_t *e, const uint16_t *pix, uint8_t *out, size_t fb,
                uint16_t *rec)
{
    for (int f = 0; f < NF; f++) {
        const uint16_t *px = pix + WORDS * f;
        omc_frame_t fr = {{(uint16_t *)px, (uint16_t *)(px + (size_t)W * H),
                           (uint16_t *)(px + (size_t)W * H + (size_t)WC * H)},
                          {W, WC, WC}};
        uint16_t *r = rec + WORDS * f;
        omc_frame_t fo = {{r, r + (size_t)W * H,
                           r + (size_t)W * H + (size_t)WC * H}, {W, WC, WC}};
        omc_enc_frame(e, &fr, f, out + fb * f, fb, rec ? &fo : NULL);
    }
}

/* Bit depth was the last open half of this rule and it is CLOSED (2026-08-12,
 * measured, no change needed).  On identical content coded at both depths --
 * cow, native 12-bit, heavy film grain -- the seam excess as a fraction of full
 * scale (x1000) came out:
 *
 *      depth    0.5 bpp   0.8 bpp   1.0 bpp
 *      10-bit    +1.01     +0.60     +0.40
 *      12-bit    +0.62     +0.17     +0.05
 *
 * 12-bit is BETTER behaved than 10-bit at the same bitrate, not worse, and cap 4
 * against cap 8 barely registers at either depth.  The cap itself already scales
 * with depth in the reconstruction (cap * ((maxv+1)>>10)), so ±4 at 10-bit and
 * ±16 at 12-bit are the same fraction of full scale.  Nothing to fix. */

int main(void)
{
    /* 0.5 bpp and 1.5 bpp at this geometry: the rule picks 8 and 4 */
    const uint32_t LO = (uint32_t)(0.5 * W * SH), HI = (uint32_t)(1.5 * W * SH);
    omc_config_t clo, chi;
    cfg_at(&clo, LO); cfg_at(&chi, HI);
    int nsl = H / SH;
    size_t flo = (size_t)LO / 8 * nsl, fhi = (size_t)HI / 8 * nsl;
    uint16_t *pa = malloc(WORDS * 2 * NF), *pb = malloc(WORDS * 2 * NF);
    for (int f = 0; f < NF; f++) {
        fill(pa + WORDS * f, WORDS, 0xA0000000u + (uint32_t)f);
        fill(pb + WORDS * f, WORDS, 0xB0000000u + (uint32_t)f);
    }
    uint8_t *a1 = malloc(flo * NF), *b1 = malloc(fhi * NF);
    uint8_t *a2 = malloc(flo * NF), *b2 = malloc(fhi * NF);
    uint16_t *ra1 = malloc(WORDS * 2 * NF), *ra2 = malloc(WORDS * 2 * NF);
    uint16_t *rb1 = malloc(WORDS * 2 * NF), *rb2 = malloc(WORDS * 2 * NF);

    /* alone */
    omc_enc_t *e = omc_enc_create(&clo); run(e, pa, a1, flo, ra1); omc_enc_destroy(e);
    e = omc_enc_create(&chi);            run(e, pb, b1, fhi, rb1); omc_enc_destroy(e);

    /* together, interleaved, in the order that breaks a process-wide cap:
     * the HIGH-rate context is created last, so a global would force cap 4
     * onto the low-rate stream too. */
    omc_enc_t *ea = omc_enc_create(&clo);
    omc_enc_t *eb = omc_enc_create(&chi);
    for (int f = 0; f < NF; f++) {
        const uint16_t *px = pa + WORDS * f;
        omc_frame_t fa = {{(uint16_t *)px, (uint16_t *)(px + (size_t)W * H),
                           (uint16_t *)(px + (size_t)W * H + (size_t)WC * H)},
                          {W, WC, WC}};
        { uint16_t *r = ra2 + WORDS * f;
          omc_frame_t fo = {{r, r + (size_t)W * H,
                             r + (size_t)W * H + (size_t)WC * H}, {W, WC, WC}};
          omc_enc_frame(ea, &fa, f, a2 + flo * f, flo, &fo); }
        px = pb + WORDS * f;
        omc_frame_t fb2 = {{(uint16_t *)px, (uint16_t *)(px + (size_t)W * H),
                            (uint16_t *)(px + (size_t)W * H + (size_t)WC * H)},
                           {W, WC, WC}};
        { uint16_t *r = rb2 + WORDS * f;
          omc_frame_t fo = {{r, r + (size_t)W * H,
                             r + (size_t)W * H + (size_t)WC * H}, {W, WC, WC}};
          omc_enc_frame(eb, &fb2, f, b2 + fhi * f, fhi, &fo); }
    }
    omc_enc_destroy(ea); omc_enc_destroy(eb);

    CHECK(memcmp(a1, a2, flo * NF) == 0 && memcmp(ra1, ra2, WORDS * 2 * NF) == 0,
          "low-rate context: stream AND reconstruction unchanged by a "
          "high-rate context in the same process");
    CHECK(memcmp(b1, b2, fhi * NF) == 0 && memcmp(rb1, rb2, WORDS * 2 * NF) == 0,
          "high-rate context: stream AND reconstruction unchanged by a "
          "low-rate context in the same process");

    /* and each must reconstruct under its own decoder */
    for (int which = 0; which < 2; which++) {
        omc_config_t *c = which ? &chi : &clo;
        uint8_t *bs = which ? b2 : a2;
        size_t fb = which ? fhi : flo;
        const uint16_t *src = which ? pb : pa;
        omc_enc_t *ee = omc_enc_create(c);
        omc_dec_t *dd = omc_dec_create(c);
        uint16_t *rec = malloc(WORDS * 2), *dec = malloc(WORDS * 2);
        int ok = 1;
        for (int f = 0; f < NF; f++) {
            const uint16_t *px = src + WORDS * f;
            omc_frame_t fr = {{(uint16_t *)px, (uint16_t *)(px + (size_t)W * H),
                               (uint16_t *)(px + (size_t)W * H + (size_t)WC * H)},
                              {W, WC, WC}};
            omc_frame_t fo = {{rec, rec + (size_t)W * H,
                               rec + (size_t)W * H + (size_t)WC * H}, {W, WC, WC}};
            omc_frame_t fd = {{dec, dec + (size_t)W * H,
                               dec + (size_t)W * H + (size_t)WC * H}, {W, WC, WC}};
            uint8_t *tmp = malloc(fb);
            omc_enc_frame(ee, &fr, f, tmp, fb, &fo);
            omc_dec_frame(dd, bs + fb * f, fb, &fd);
            if (memcmp(tmp, bs + fb * f, fb) != 0) ok = 0;
            if (memcmp(rec, dec, WORDS * 2) != 0) ok = 0;
            free(tmp);
        }
        CHECK(ok, which ? "rt=0 on the high-rate context (cap 4)"
                        : "rt=0 on the low-rate context (cap 8)");
        omc_enc_destroy(ee); omc_dec_destroy(dd); free(rec); free(dec);
    }
    free(pa); free(pb); free(a1); free(b1); free(a2); free(b2);
    /* the reconstruction buffers were leaking: LeakSanitizer flagged
     * 393216 bytes in four allocations, which would have masked a real
     * codec leak in any later ASan run of this suite */
    free(ra1); free(ra2); free(rb1); free(rb2);
    printf(fails ? "FAILURES: %d\n" : "all ok\n", fails);
    return fails ? 1 : 0;
}
