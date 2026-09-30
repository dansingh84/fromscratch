/* T5 cross-slice boundary (XSL) gates.  Three things this build must never
 * lose:
 *
 * G-T5-XSL1  XSL CANNOT BE TURNED OFF.  The boundary reconstruction is a
 *            normative always-on part of the codec: the old OMC_XSL /
 *            OMC_XSL_NOEDIT / OMC_XSL_NODISP environment levers must be
 *            inert.  (The seam blend is what keeps slice joins invisible at
 *            and below 0.5 bpp; an environment that could disable it would
 *            also silently break the generation-exactness contract, because
 *            the encoder-side un-blend and the decoder-side blend must agree
 *            forever.)
 *
 * G-T5-XSL2  THE EDIT IS EXACTLY REVERSIBLE, WHOLE-PICTURE.  The boundary
 *            edit is a lifting cascade (each step's correction reads only
 *            rows it does not touch), the barrier display blend is the same
 *            cascade under the refresh-barrier conditions, and
 *            omc_xsl_unblend() must invert the composition exactly on every
 *            barrier phase.  Verified here through the codec itself: the
 *            generation-2 re-encode of a decode reproduces the decode
 *            byte-for-byte, which is only possible if the un-blend recovered
 *            the committed reconstruction exactly at every boundary of every
 *            frame.
 *
 * G-T5-XSL3  GENERATION EXACTNESS THROUGH INTER FRAMES.  The v4.9 gate was
 *            intra-only by necessity (its in-loop edit made inter frames
 *            unverifiable).  T5's contract is stronger and so is the gate:
 *            a 4-frame sequence with motion and two refresh phases (R=2)
 *            must chain byte-exactly for 4 generations — pixels equal from
 *            generation 1, streams equal from generation 2.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "omc1.h"

static int fails = 0;
static int rt0_bad = 0;
#define GM_PASS 13   /* the shipped default; see docs/TEMPORAL_T5.md 12.22 */
#define CHECK(c, m) do { printf("%s: %s\n", (c) ? "ok" : "FAIL", m); \
                         if (!(c)) fails++; } while (0)

enum { W = 256, H = 64, SH = 16, NF = 4 };
#define WC (W / 2)
#define WORDS ((size_t)W * H + 2 * (size_t)WC * H)

/* Textured content with per-frame motion (a 2 px/frame horizontal roll) so
 * inter coding and the derived motion vector genuinely engage.  Values are
 * in the T5 biased domain. */
static void fill(uint16_t *p, uint32_t seed, int frame)
{
    uint32_t x = seed;
    for (int y = 0; y < H; y++)
        for (int i = 0; i < W + 2 * WC; i++) {
            int xx = (i + 2 * frame) % (W + 2 * WC);
            x = seed + (uint32_t)(y * 31 + xx) * 2654435761u;
            x = x * 1103515245u + 12345u;
            int base = 200 + 6 * y + ((y / 5) % 3) * 40;
            p[(size_t)y * (W + 2 * WC) + i] =
                (uint16_t)(base + ((x >> 18) % 24) + OMC_PIX_BIAS);
        }
}

static void cfg_init(omc_config_t *c)
{
    memset(c, 0, sizeof(*c));
    c->width = W; c->height = H; c->bitdepth = 10; c->chroma = OMC_CF_422;
    c->ver_minor = OMC_VERSION_MINOR; c->slice_h = SH;
    c->fps_num = 50; c->fps_den = 1;
    c->refresh_r = 2;                 /* both barrier phases inside 4 frames */
    c->bits_per_slice = 2 * W * SH;   /* 1.0 bpp on luma pixels */
}

static void planes(omc_frame_t *fr, uint16_t *b)
{
    fr->p[0] = b; fr->p[1] = b + (size_t)W * H;
    fr->p[2] = b + (size_t)W * H + (size_t)WC * H;
    fr->stride[0] = W; fr->stride[1] = WC; fr->stride[2] = WC;
}

/* encode NF frames from pix[], decode them, return both streams and decodes */
static void run_chain(const omc_config_t *c, const uint16_t *pix,
                      uint8_t *bs, uint16_t *dec)
{
    size_t fb = (size_t)(c->bits_per_slice / 8) * (H / SH);
    omc_enc_t *e = omc_enc_create(c);
    omc_dec_t *d = omc_dec_create(c);
    for (int f = 0; f < NF; f++) {
        omc_frame_t fr; planes(&fr, (uint16_t *)pix + WORDS * f);
        omc_enc_frame(e, &fr, f, bs + fb * f, fb, NULL);
        omc_frame_t fo; planes(&fo, dec + WORDS * f);
        omc_dec_frame(d, bs + fb * f, fb, &fo);
    }
    omc_enc_destroy(e);
    omc_dec_destroy(d);
}

/* ---------------------------------------------------------- G-T5-PAD ----
 * PAD NEUTRALIZATION (minor 11).  A raster coded taller than its display
 * height (here 64 coded rows for a 56-row display, slice_h 16: the last slice
 * has v = 8 visible rows and 8 pad rows) must satisfy two properties:
 *   (a) the committed pad rows are exactly a replication of the committed last
 *       VISIBLE row -- a pure function of the visible picture, so a cropped
 *       baseband decode can be re-padded to the committed picture; and
 *   (b) doing exactly that -- crop, re-pad by replication, re-encode --
 *       reproduces the committed picture byte for byte at generation 2.
 * The gate also runs itself with the pre-minor-11 behaviour reintroduced
 * (the debug_oldpads API) and REQUIRES that arm to fail: a gate that cannot fail
 * proves nothing, which is the lesson this project's own register records. */
enum { DH = 56 };   /* display height; coded H = 64, so 8 pad rows */

static int pad_chain(int oldpads, int *repl_ok)
{
    omc_config_t c; cfg_init(&c);
    c.display_width = W; c.display_height = DH;

    size_t fb = (size_t)(c.bits_per_slice / 8) * (H / SH);
    uint16_t *pix = malloc(WORDS * 2), *d1 = malloc(WORDS * 2), *d2 = malloc(WORDS * 2);
    uint8_t *bs = malloc(fb);
    if (!pix || !d1 || !d2 || !bs) return -1;
    fill(pix, 999u, 0);
    /* generation 1 */
    omc_enc_t *e = omc_enc_create(&c); omc_dec_t *d = omc_dec_create(&c);
    if (oldpads) { omc_enc_debug_oldpads(e, 1); omc_dec_debug_oldpads(d, 1); }
    omc_frame_t fr; planes(&fr, pix);
    omc_enc_frame(e, &fr, 0, bs, fb, NULL);
    omc_frame_t fo; planes(&fo, d1);
    omc_dec_frame(d, bs, fb, &fo);
    omc_enc_destroy(e); omc_dec_destroy(d);
    /* (a) committed pads == replication of the committed last visible row */
    *repl_ok = 1;
    for (int p = 0; p < 3; p++) {
        int pw = p ? WC : W;
        const uint16_t *pl = d1 + (p == 0 ? 0 : (p == 1 ? (size_t)W * H
                                                        : (size_t)W * H + (size_t)WC * H));
        for (int r = DH; r < H; r++)
            for (int x = 0; x < pw; x++)
                if (pl[(size_t)r * pw + x] != pl[(size_t)(DH - 1) * pw + x])
                    *repl_ok = 0;
    }
    /* (b) crop to the display raster and re-pad by replication -- exactly what
     * a baseband hop leaves a downstream encoder -- then re-encode */
    memcpy(d2, d1, WORDS * 2);
    for (int p = 0; p < 3; p++) {
        int pw = p ? WC : W;
        uint16_t *pl = d2 + (p == 0 ? 0 : (p == 1 ? (size_t)W * H
                                                  : (size_t)W * H + (size_t)WC * H));
        for (int r = DH; r < H; r++)
            memcpy(pl + (size_t)r * pw, pl + (size_t)(DH - 1) * pw, (size_t)pw * 2);
    }
    uint8_t *bs2 = malloc(fb);
    uint16_t *g2 = malloc(WORDS * 2);
    e = omc_enc_create(&c); d = omc_dec_create(&c);
    if (oldpads) { omc_enc_debug_oldpads(e, 1); omc_dec_debug_oldpads(d, 1); }
    omc_frame_t f2; planes(&f2, d2);
    omc_enc_frame(e, &f2, 0, bs2, fb, NULL);
    omc_frame_t fo2; planes(&fo2, g2);
    omc_dec_frame(d, bs2, fb, &fo2);
    omc_enc_destroy(e); omc_dec_destroy(d);
    /* compare the VISIBLE picture (what baseband carries) */
    int same = 1;
    for (int p = 0; p < 3 && same; p++) {
        int pw = p ? WC : W;
        size_t off = (p == 0 ? 0 : (p == 1 ? (size_t)W * H : (size_t)W * H + (size_t)WC * H));
        for (int r = 0; r < DH && same; r++)
            if (memcmp(d1 + off + (size_t)r * pw, g2 + off + (size_t)r * pw, (size_t)pw * 2))
                same = 0;
    }
    free(pix); free(d1); free(d2); free(bs); free(bs2); free(g2);
    return same;
}

/* ------------------------------------------------------- G-T5-GAMUT ----
 * STRICT IN-GAMUT MODE (docs/TEMPORAL_T5.md 12.22).  A baseband hand-off --
 * decode to ordinary legal-range video, send it down a link, re-encode it --
 * is exact only while the committed picture stays inside the legal range,
 * because a legal-range container clips what falls outside it and a clipped
 * sample is no longer the lattice point the next encoder needs to recognise.
 * --gamut-strict makes the encoder keep the committed picture inside that
 * range.  Three properties, and the gate would be worthless without the first:
 *
 * G-T5-GAMUT1  the mode is NON-VACUOUS: rail-touching content with the mode
 *              OFF really does commit samples outside the legal range;
 * G-T5-GAMUT2  with the mode ON that count is zero, and the baseband chain on
 *              the same content is byte-exact -- pixels from generation 1,
 *              streams from generation 2;
 * G-T5-GAMUT3  the mode is INERT on content that never leaves the range: the
 *              stream is byte-identical to the one the mode-off encoder
 *              writes, so turning it on is free wherever it is not needed.
 */
/* Rail-hard content: hard black and white plates at exactly 0 and maxv, a
 * full-range ramp, and a plate edge that walks across slice boundaries frame
 * by frame so it lands in every position.  `hard` makes the walking feature
 * ONE ROW tall, which is the pathological case: a single-row rail feature
 * sitting on a slice boundary cannot be pulled off the rail once the quantizer
 * has flattened its neighbourhood, and the XSL boundary edit then carries it
 * out of range (docs/TEMPORAL_T5.md 12.22).  The ordinary arm uses a four-row
 * feature, which is what real rail content looks like and what the project's
 * own rail clip contains. */
static void fill_rails_g(uint16_t *p, int frame, int hard)
{
    const int maxv = 1023;
    for (int y = 0; y < H; y++)
        for (int i = 0; i < W + 2 * WC; i++) {
            int pw = (i < W) ? W : WC;
            int x0 = (i < W) ? i : ((i - W) % WC);
            int x = (x0 + 2 * frame) % pw;   /* the picture pans, as real content does */
            int v;
            if (x < pw / 4) v = 0;                                    /* black plate */
            else if (x < pw / 2) v = maxv;                            /* white plate */
            else if (x < 3 * pw / 4) v = ((x - pw / 2) * maxv) / (pw / 4); /* ramp */
            else v = maxv;                                            /* white plate */
            if (hard) {
                /* the pathological addition: a ONE-ROW rail line whose position
                 * walks across a slice boundary frame by frame */
                int line = (SH - 1 + 2 * frame) % H;
                if (y == line) v = maxv;
                if (y == (line + 1) % H) v = 0;
            }
            p[(size_t)y * (W + 2 * WC) + i] = (uint16_t)(v + OMC_PIX_BIAS);
        }
}
/* The ordinary arm: real-looking textured content that has been GRADED TO THE
 * RAILS, which is the class the hand-off report exposed -- ordinary footage
 * whose highlights sit on the container's white point, not synthetic plates.
 * A handful of samples per slice overshoot; the mode is expected to clear all
 * of them, and the baseband chain then has to be byte-exact. */
static void fill_rails(uint16_t *p, int frame)
{
    const int maxv = 1023;
    uint32_t x;
    for (int y = 0; y < H; y++)
        for (int i = 0; i < W + 2 * WC; i++) {
            int xx = (i + 2 * frame) % (W + 2 * WC);
            x = 4242u + (uint32_t)(y * 31 + xx) * 2654435761u;
            x = x * 1103515245u + 12345u;
            int v = 690 + 4 * y + ((y / 5) % 3) * 30 + (int)((x >> 18) % 96);
            if (v > maxv) v = maxv;
            if (v < 0) v = 0;
            p[(size_t)y * (W + 2 * WC) + i] = (uint16_t)(v + OMC_PIX_BIAS);
        }
}

/* encode NF frames with an explicit strict setting; report the gamut count */
/* set by run_strict: the repair's internal work, so a determinism gate can
 * assert the PATH as well as the output (see G-T5-GAMUT5) */
static int64_t gm_last_slices, gm_last_passes, gm_last_unfixed;

static void run_strict(const omc_config_t *c, const uint16_t *pix, int passes,
                       uint8_t *bs, uint16_t *dec, int64_t *oob)
{
    size_t fb = (size_t)(c->bits_per_slice / 8) * (H / SH);
    omc_enc_t *e = omc_enc_create(c);
    omc_dec_t *d = omc_dec_create(c);
    omc_enc_set_gamut_strict(e, passes);
    uint16_t *rcb = malloc(WORDS * 2);
    for (int f = 0; f < NF; f++) {
        omc_frame_t fr; planes(&fr, (uint16_t *)pix + WORDS * f);
        omc_frame_t rc; planes(&rc, rcb);               /* recon: the mode needs it */
        omc_enc_frame(e, &fr, f, bs + fb * f, fb, &rc);
        omc_frame_t fo; planes(&fo, dec + WORDS * f);
        omc_dec_frame(d, bs + fb * f, fb, &fo);
        /* rt = 0 (mandate C4): the encoder's own reconstruction must equal
         * what the decoder produces, byte for byte, with the repair running.
         * If the repair could ever leave the two disagreeing, every exactness
         * claim above it would be measuring the wrong buffer. */
        if (memcmp(rcb, dec + WORDS * f, WORDS * 2)) rt0_bad++;
    }
    free(rcb);
    if (oob) *oob = omc_enc_oob(e);
    gm_last_slices  = omc_enc_gamut_slices(e);
    gm_last_passes  = omc_enc_gamut_repairs(e);
    gm_last_unfixed = omc_enc_gamut_unfixed(e);
    omc_enc_destroy(e);
    omc_dec_destroy(d);
}

/* [A2-CUTPROBE6] (Agent 2, notes/patch_cutprobe6.py; landed in v5.3.6 as gate G-T5-CUT24) run_strict with an explicit frame count */
/* [V15] per-slice total-pass accounting from the last run_strict_n encode.
 * omc_gm_redomax is the repair lever the cap formula follows; the gate asserts
 * the cap against the same expression the encoder derives it from, so the two
 * cannot drift. */
extern int omc_gm_redomax;
static int gm_last_total_max, gm_last_total_cap;
static long long gm_last_capstops;
/* [V15] FNV-1a of the decoded pictures: proves the gate arm is bit-identical
 * to the base tree's, which a pass-counter must not disturb. */
static unsigned long long dec_hash64(const uint16_t *d, size_t n)
{
    unsigned long long h = 1469598103934665603ULL;
    const unsigned char *p = (const unsigned char *)d;
    for (size_t i = 0; i < n * 2; i++) { h ^= p[i]; h *= 1099511628211ULL; }
    return h;
}
static void run_strict_n(const omc_config_t *c, const uint16_t *pix, int passes,
                         uint8_t *bs, uint16_t *dec, int64_t *oob, int nf)
{
    size_t fb = (size_t)(c->bits_per_slice / 8) * (H / SH);
    omc_enc_t *e = omc_enc_create(c);
    omc_dec_t *d = omc_dec_create(c);
    omc_enc_set_gamut_strict(e, passes);
    uint16_t *rcb = malloc(WORDS * 2);
    for (int f = 0; f < nf; f++) {
        omc_frame_t fr; planes(&fr, (uint16_t *)pix + WORDS * f);
        omc_frame_t rc; planes(&rc, rcb);
        omc_enc_frame(e, &fr, f, bs + fb * f, fb, &rc);
        omc_frame_t fo; planes(&fo, dec + WORDS * f);
        omc_dec_frame(d, bs + fb * f, fb, &fo);
    }
    free(rcb);
    if (oob) *oob = omc_enc_oob(e);
    gm_last_unfixed = omc_enc_gamut_unfixed(e);
    gm_last_total_max = omc_enc_gamut_total_max(e);   /* [V15] */
    gm_last_total_cap = omc_enc_gamut_total_cap(e);   /* [V15] */
    gm_last_capstops  = (long long)omc_enc_gamut_capstops(e);  /* [V15] */
    omc_enc_destroy(e);
    omc_dec_destroy(d);
}

/* ---------------------------------------------------------- G-T5-CALM ----
 * TEMPORAL CALM (the "ants" fix, docs/TEMPORAL_T5.md 12.23).  Two properties,
 * and the second is only worth anything because the first one holds.
 *
 * G-T5-CALM1  THE FIX FIRES, AND THE GATE IS NON-VACUOUS.  A master that is
 *             FLAT and STATIC in the source -- a constant field carrying a
 *             sub-code dither of a couple of codes, exactly the sensor noise
 *             that carries a coefficient back and forth across the quantizer's
 *             zero/one boundary -- must show frame-to-frame movement in the
 *             DECODE with the fix off, and much less of it with the fix on.
 *             Both halves are checked: an arm that cannot fail proves nothing.
 *
 * G-T5-CALM2  AND IT CANNOT COST GENERATION EXACTNESS.  The same content, with
 *             the fix ON so the kill is demonstrably firing, must still chain
 *             byte-exactly: generation 2 reproduces generation 1's pixels and
 *             generation 3 reproduces generation 2's stream.  This is the gate
 *             form of the lattice argument in 12.23.7 -- the kill tests a
 *             STRICT |c| < (1 << s) and a committed coefficient is exactly
 *             q << s, so it can never fire on a picture that has already been
 *             through the codec.
 */
extern int omc_calm;      /* src/codec.c; internal, declared here for the gate */
extern int omc_calm_thr;
extern int omc_gm_mode;   /* the in-gamut repair's reduction rule */
extern int omc_gm_num, omc_gm_den;
extern int omc_gm_fallback_on;

/* A flat, statically dithered field with one heavily textured strip, so the
 * rate allocator has somewhere to spend and the flat area gets a coarse
 * enough step for the boundary to matter. */
static void fill_flat(uint16_t *p, int frame)
{
    for (int y = 0; y < H; y++)
        for (int i = 0; i < W + 2 * WC; i++) {
            uint32_t x = (uint32_t)(y * 7919 + i * 104729 + frame * 15485863);
            x = x * 1103515245u + 12345u; x ^= x >> 15;
            x = x * 2654435761u; x ^= x >> 13;
            int v;
            if (y >= H / 2 && y < H / 2 + H / 8)
                v = 400 + (int)((x >> 17) % 400);        /* the texture strip */
            else
                v = 512 + (int)((x >> 19) % 17) - 8;   /* flat + a -8..+8 dither */
            p[(size_t)y * (W + 2 * WC) + i] = (uint16_t)(v + OMC_PIX_BIAS);
        }
}

/* P(|frame-to-frame difference| > 6 codes) over the FLAT rows of the luma
 * plane -- the project's own ants tail (docs/REPORT.md 18.6), in parts per
 * 10000 so the gate can compare integers. */
static int ants_tail(const uint16_t *dec)
{
    long n = 0, hit = 0;
    for (int f = 1; f < NF; f++)
        for (int y = 0; y < H; y++) {
            if (y >= H / 2 && y < H / 2 + H / 8) continue;   /* skip texture */
            for (int i = 0; i < W; i++) {
                const uint16_t *a = dec + WORDS * (f - 1);
                const uint16_t *b = dec + WORDS * f;
                int d = (int)b[(size_t)y * W + i] - (int)a[(size_t)y * W + i];
                if (d < 0) d = -d;
                n++; if (d > 6) hit++;
            }
        }
    return n ? (int)((hit * 10000 + n / 2) / n) : 0;
}

static int dump_cut24(const char *path)
{
    const int NFL = 24, CUTEVERY = 6;
    uint16_t *lg = malloc(WORDS * 2 * (size_t)NFL);
    if (!lg) return 1;
    for (int f = 0; f < NFL; f++) {
        if ((f / CUTEVERY) & 1) fill(lg + WORDS * f, 12345u, f);
        else                    fill_rails_g(lg + WORDS * f, f, 0);
    }
    /* the suite's pixels are in the T5 biased domain; omc_enc reads true 10-bit code values */
    for (size_t i = 0; i < WORDS * (size_t)NFL; i++) {
        int v = (int)lg[i] - OMC_PIX_BIAS;
        lg[i] = (uint16_t)(v < 0 ? 0 : v > 1023 ? 1023 : v);
    }
    FILE *fo = fopen(path, "wb");
    if (!fo) { free(lg); return 1; }
    size_t n = fwrite(lg, 2, WORDS * (size_t)NFL, fo);
    fclose(fo); free(lg);
    printf("cut24 arm written: %s (%dx%d 4:2:2 10-bit, %d frames, cut every %d)\n", path, W, H, NFL, CUTEVERY);
    return n == WORDS * (size_t)NFL ? 0 : 1;
}

int main(int argc, char **argv)
{
    if (argc == 3 && !strcmp(argv[1], "--dump-cut24")) return dump_cut24(argv[2]);   /* [V537-BUDGET] */
    omc_config_t c; cfg_init(&c);
    size_t fb = (size_t)(c.bits_per_slice / 8) * (H / SH);
    uint16_t *pix = malloc(WORDS * 2 * NF);
    uint16_t *dec1 = malloc(WORDS * 2 * NF), *dec2 = malloc(WORDS * 2 * NF);
    uint16_t *dec3 = malloc(WORDS * 2 * NF), *decx = malloc(WORDS * 2 * NF);
    uint8_t *bs1 = malloc(fb * NF), *bs2 = malloc(fb * NF);
    uint8_t *bs3 = malloc(fb * NF), *bsx = malloc(fb * NF);
    if (!pix || !dec1 || !dec2 || !dec3 || !decx || !bs1 || !bs2 || !bs3 || !bsx)
        { printf("FAIL: alloc\n"); return 1; }
    for (int f = 0; f < NF; f++) fill(pix + WORDS * f, 12345u, f);

    /* ------------------------------------------------------- G-T5-XSL1 */
    unsetenv("OMC_XSL"); unsetenv("OMC_XSL_NOEDIT");
    unsetenv("OMC_XSL_NODISP"); unsetenv("OMC_XSL_LIM");
    run_chain(&c, pix, bs1, dec1);
    setenv("OMC_XSL", "0", 1);          /* the old off switch ... */
    setenv("OMC_XSL_NOEDIT", "1", 1);   /* ... and the old edit-skip hook */
    setenv("OMC_XSL_NODISP", "1", 1);
    run_chain(&c, pix, bsx, decx);
    unsetenv("OMC_XSL"); unsetenv("OMC_XSL_NOEDIT"); unsetenv("OMC_XSL_NODISP");
    CHECK(memcmp(bs1, bsx, fb * NF) == 0 && memcmp(dec1, decx, WORDS * 2 * NF) == 0,
          "G-T5-XSL1 the XSL off/skip environment levers are inert (always on)");

    /* ------------------------------------------------------- G-T5-XSL2/3 */
    /* generation 2: re-encode the decode; generation 3: re-encode that */
    run_chain(&c, dec1, bs2, dec2);
    CHECK(memcmp(dec1, dec2, WORDS * 2 * NF) == 0,
          "G-T5-XSL2 generation-2 pixels reproduce generation-1 byte-for-byte "
          "(inter frames and both R=2 barrier phases included)");
    run_chain(&c, dec2, bs3, dec3);
    CHECK(memcmp(dec2, dec3, WORDS * 2 * NF) == 0,
          "G-T5-XSL3a generation-3 pixels hold");
    CHECK(memcmp(bs2, bs3, fb * NF) == 0,
          "G-T5-XSL3b generation-3 stream is byte-identical to generation 2");

    /* un-blend inverse, directly: un-blending the decode and re-applying the
     * chain must be what generation 2 did — spot-check the exported function
     * agrees with itself (undo twice != undo once). */
    memcpy(decx, dec1, WORDS * 2 * NF);
    for (int f = 0; f < NF; f++) {
        omc_frame_t fr; planes(&fr, decx + WORDS * f);
        omc_xsl_unblend(&fr, &c, f);
    }
    size_t edited = 0;
    for (size_t i = 0; i < WORDS * NF; i++) edited += (decx[i] != dec1[i]);
    CHECK(edited > 0, "G-T5-XSL2b the boundary edit actually fires "
                      "(un-blend changes samples)");

    /* ------------------------------------------------------ G-T5-GEOM */
    {
        /* The baseband-safe verdict must not certify a geometry the pad rule
         * does not cover.  Found by adversarial audit: horizontally padded
         * rasters and visible runs with v mod 4 were reported safe while their
         * chains drifted.  A confidently wrong safety report is worse than
         * none, so the verdict is gated on geometry as well as gamut. */
        omc_config_t g; cfg_init(&g);
        g.display_width = W; g.display_height = DH;      /* vertical pad only */
        omc_enc_t *ge = omc_enc_create(&g);
        int ok_vert = omc_enc_geom_baseband_safe(ge);
        omc_enc_destroy(ge);
        cfg_init(&g); g.display_width = W - 4; g.display_height = H; /* h-pad */
        ge = omc_enc_create(&g);
        int ok_horiz = omc_enc_geom_baseband_safe(ge);
        omc_enc_destroy(ge);
        cfg_init(&g); g.display_width = W; g.display_height = H - SH + 2; /* v mod 4 */
        ge = omc_enc_create(&g);
        int ok_odd = omc_enc_geom_baseband_safe(ge);
        omc_enc_destroy(ge);
        CHECK(ok_vert == 1, "G-T5-GEOM1 a vertically padded raster the rule "
                            "covers reports baseband-safe geometry");
        CHECK(ok_horiz == 0, "G-T5-GEOM2 a HORIZONTALLY padded raster reports "
                             "NOT baseband-safe (the rule does not cover it)");
        CHECK(ok_odd == 0, "G-T5-GEOM3 a visible run the rule cannot express "
                           "(v mod 4) reports NOT baseband-safe");
    }

    /* ------------------------------------------------------- G-T5-PAD */
    {
        int repl_new = 0, repl_old = 0;
        int ok_new = pad_chain(0, &repl_new);
        int ok_old = pad_chain(1, &repl_old);
        CHECK(repl_new == 1,
              "G-T5-PAD1 committed pad rows are a replication of the committed "
              "last visible row (a pure function of the visible picture)");
        CHECK(ok_new == 1,
              "G-T5-PAD2 crop to the display raster, re-pad by replication and "
              "re-encode reproduces the committed visible picture byte-for-byte");
        CHECK(ok_old == 0,
              "G-T5-PAD3 the gate is NON-VACUOUS: with the pre-minor-11 pad "
              "behaviour reintroduced the same chain FAILS");
    }

    /* ----------------------------------------------------- G-T5-GAMUT */
    {
        size_t fb = (size_t)(c.bits_per_slice / 8) * (H / SH);
        uint16_t *rp = malloc(WORDS * 2 * NF);
        uint16_t *ga = malloc(WORDS * 2 * NF), *gb = malloc(WORDS * 2 * NF);
        uint16_t *gc = malloc(WORDS * 2 * NF);
        uint8_t *ba = malloc(fb * NF), *bb = malloc(fb * NF), *bc = malloc(fb * NF);
        int64_t oob_off = 0, oob_on = 0;
        if (rp && ga && gb && gc && ba && bb && bc) {
            for (int f = 0; f < NF; f++) fill_rails(rp + WORDS * f, f);
            run_strict(&c, rp, 0, ba, ga, &oob_off);
            run_strict(&c, rp, GM_PASS, bb, gb, &oob_on);
            /* generation 2 over BASEBAND: the decode is fed straight back in.
             * (These rasters are unpadded and the decode is already in the
             * biased domain the encoder takes, so the decode IS the baseband
             * hand-off, clipping included -- nothing to crop or re-pad.) */
            /* The contract is the one G-T5-XSL3 states: PIXELS equal from
             * generation 1, STREAMS equal from generation 2 -- generation 1
             * codes a master and generation 2 codes a reconstruction, so their
             * bytes are not required to agree.  Hence a third generation. */
            int64_t ignore = 0;
            uint16_t *gd = malloc(WORDS * 2 * NF);
            uint8_t *bd = malloc(fb * NF);
            run_strict(&c, gb, GM_PASS, bc, gc, &ignore);
            run_strict(&c, gc, GM_PASS, bd, gd, &ignore);
            int pix_same = memcmp(gb, gc, WORDS * 2 * NF) == 0 &&
                           memcmp(gc, gd, WORDS * 2 * NF) == 0;
            int str_same = memcmp(bc, bd, fb * NF) == 0;
            free(gd); free(bd);
            CHECK(oob_off > 0,
                  "G-T5-GAMUT1 the gate is NON-VACUOUS: with the mode OFF, "
                  "rail-touching content commits samples outside legal range");
            CHECK(oob_on == 0,
                  "G-T5-GAMUT2a with --gamut-strict the committed picture stays "
                  "inside the legal range on that same content");
            /* The pathological arm: a ONE-ROW rail feature walking across slice
             * boundaries.  The XSL boundary edit is unconditional and can always
             * carry such a sample one code out (12.22.11), so this arm asserts a
             * near-total reduction rather than zero -- and asserting the weaker
             * thing here is the point: it is the case the mode does NOT close,
             * and a gate that pretended otherwise would be the lie. */
            {
                uint16_t *hp = malloc(WORDS * 2 * NF);
                uint8_t *hb = malloc(fb * NF);
                uint16_t *hd = malloc(WORDS * 2 * NF);
                int64_t h_off = 0, h_on = 0;
                if (hp && hb && hd) {
                    for (int f = 0; f < NF; f++) fill_rails_g(hp + WORDS * f, f, 1);
                    run_strict(&c, hp, 0, hb, hd, &h_off);
                    run_strict(&c, hp, GM_PASS, hb, hd, &h_on);
                    /* the same content with the fallback of 12.22.3i turned
                     * off, so the gate can assert that the fallback is what
                     * closes this case rather than merely asserting that it is
                     * closed */
                    int64_t h_nofb = 0;
                    int keepfb = omc_gm_fallback_on;
                    omc_gm_fallback_on = 0;
                    run_strict(&c, hp, GM_PASS, hb, hd, &h_nofb);
                    omc_gm_fallback_on = keepfb;
                    printf("   pathological arm: %lld samples out of range with "
                           "the repair off, %lld with it on, %lld with the "
                           "fallback disabled\n",
                           (long long)h_off, (long long)h_on, (long long)h_nofb);
                    CHECK(h_off > 0 && h_on == 0,
                          "G-T5-GAMUT2c the PATHOLOGICAL arm (one-row rail "
                          "features walked across slice boundaries) is CLOSED: "
                          "every excursion removed, not merely 99% of them");
                    CHECK(h_nofb > 0,
                          "G-T5-GAMUT2d and the fallback is what closes it: "
                          "with the fallback disabled the same content leaves a "
                          "residue that more passes do not clear");
                }
                free(hp); free(hb); free(hd);
            }
            CHECK(pix_same && str_same,
                  "G-T5-GAMUT2b and its BASEBAND chain is byte-exact: "
                  "generation 2 reproduces both the picture and the stream");
            /* inert where it is not needed: ordinary textured content */
            int64_t o1 = 0, o2 = 0;
            run_strict(&c, pix, 0, ba, ga, &o1);
            run_strict(&c, pix, GM_PASS, bb, gb, &o2);
            CHECK(o1 == 0 && o2 == 0 && memcmp(ba, bb, fb * NF) == 0,
                  "G-T5-GAMUT3 the mode is INERT on content that never leaves "
                  "the legal range: byte-identical stream, on and off");
            CHECK(rt0_bad == 0,
                  "G-T5-GAMUT4 rt = 0 holds with the repair running: the "
                  "encoder's reconstruction equals the decoder's output");

            /* ------------------------------------------- G-T5-GAMUT5
             * DETERMINISM.  Every exactness result in 12.22 is a claim about
             * reproducing a stream, and none of them means anything if the
             * repair can reach two different answers from one input.  Two
             * things are asserted, for two different reasons.
             *
             * The OUTPUT must be byte-identical.  That is the property
             * actually needed: generation exactness and reproducibility both
             * follow from it and nothing stronger can be asserted about a
             * stream.
             *
             * The repair's INTERNAL COUNTS must match too, and that is not
             * redundant.  Two runs can take different numbers of passes and
             * still converge to the same lattice point, so the stream agrees
             * while the encoder is already nondeterministic -- a latent fault
             * waiting for an unrelated change to expose it.  Counts turn that
             * from invisible into a build failure.  (This is not idle: an
             * earlier revision of the repair restored a plane from an
             * uninitialised buffer when that plane was clean on one pass and
             * dirty on a later one, and the streams still matched.)
             *
             * The second encode is separated from the first by an encode of
             * DIFFERENT content in the same process.  Two fresh processes
             * would not catch state leaking through a global or a static,
             * which is exactly the class of bug this is guarding. */
            {
                uint16_t *da = malloc(WORDS * 2 * NF), *db = malloc(WORDS * 2 * NF);
                uint16_t *dx = malloc(WORDS * 2 * NF);
                uint8_t *pa = malloc(fb * NF), *pb = malloc(fb * NF);
                uint8_t *px = malloc(fb * NF);
                if (da && db && dx && pa && pb && px) {
                    int64_t o = 0;
                    run_strict(&c, rp, GM_PASS, pa, da, &o);
                    int64_t sa = gm_last_slices, ja = gm_last_passes,
                            ua = gm_last_unfixed;
                    run_strict(&c, pix, GM_PASS, px, dx, &o);   /* other content */
                    run_strict(&c, rp, GM_PASS, pb, db, &o);
                    CHECK(sa > 0 && ja > 0,
                          "G-T5-GAMUT5a the gate is NON-VACUOUS: the repair "
                          "actually fired on this content");
                    CHECK(memcmp(pa, pb, fb * NF) == 0 &&
                          memcmp(da, db, WORDS * 2 * NF) == 0,
                          "G-T5-GAMUT5b the same input re-encoded in the same "
                          "process, with other content coded in between, "
                          "produces a byte-identical stream and decode");
                    CHECK(sa == gm_last_slices && ja == gm_last_passes &&
                          ua == gm_last_unfixed,
                          "G-T5-GAMUT5c and it got there by the same internal "
                          "path: identical slices repaired, passes taken and "
                          "slices left unfixed");
                }
                /* and again with the ALIGNMENT VETO (mode 16) engaged, which
                 * reads a summed-area table of residuals and skips
                 * coefficients on a signed test -- more internal state to get
                 * wrong than any earlier shape, so it is gated separately
                 * rather than assumed to inherit the result above. */
                if (da && db && dx && pa && pb && px) {
                    int km = omc_gm_mode, kn = omc_gm_num, kd = omc_gm_den;
                    omc_gm_mode = 16; omc_gm_num = 15; omc_gm_den = 16;
                    int64_t o16a = 0, o16b = 0;
                    run_strict(&c, rp, GM_PASS, pa, da, &o16a);
                    int64_t sa = gm_last_slices, ja = gm_last_passes;
                    run_strict(&c, pix, GM_PASS, px, dx, &o16b);
                    run_strict(&c, rp, GM_PASS, pb, db, &o16b);
                    CHECK(sa > 0 && ja > 0 && o16a == 0,
                          "G-T5-GAMUT5d the alignment veto (mode 16) fires on "
                          "this content and still reaches zero out-of-range "
                          "samples inside the pass budget");
                    CHECK(memcmp(pa, pb, fb * NF) == 0 &&
                          memcmp(da, db, WORDS * 2 * NF) == 0 &&
                          sa == gm_last_slices && ja == gm_last_passes,
                          "G-T5-GAMUT5e and it is deterministic: same stream, "
                          "same decode and same internal path on a re-encode");
                    omc_gm_mode = km; omc_gm_num = kn; omc_gm_den = kd;
                }
                free(da); free(db); free(dx); free(pa); free(pb); free(px);
            }
        }
        free(rp); free(ga); free(gb); free(gc); free(ba); free(bb); free(bc);
    }

    /* -------------------------------------------------------- G-T5-CUT
     *
     * THE OPERATOR TEST.  Everything above encodes one kind of content at a
     * time, which is not how a broadcast chain is used.  A live chain cuts
     * between sources every few seconds and there is nobody at a console
     * changing the encoder's settings at each cut.  So this gate builds ONE
     * sequence that cuts between content whose demands on the in-gamut repair
     * are opposite, and encodes the whole thing as ONE stream at the DEFAULT
     * settings with nothing switched at the cuts.
     *
     * The two kinds are the two that actually occur in a programme: ordinary
     * textured footage GRADED TO THE RAILS, where highlights sit on the
     * container's white point and the repair has real work to do, cutting
     * against ordinary footage that never approaches those limits and where
     * the repair must do nothing at all.
     *
     * The last assertion covers the hard synthetic separately.  Black and
     * white plates at exactly 0 and maxv are content the repair does NOT fully
     * close (12.22.11), so requiring zero there would be asserting something
     * the mode never claimed.  What can be required, and is, is that CUTTING
     * costs nothing: the mixed sequence must be no worse than the plates on
     * their own.  Whatever residue is left is a property of the content and
     * not of the cut. */
    {
        uint16_t *cut = malloc(WORDS * 2 * NF);
        uint16_t *cd1 = malloc(WORDS * 2 * NF), *cd2 = malloc(WORDS * 2 * NF);
        uint16_t *cd3 = malloc(WORDS * 2 * NF);
        size_t cfb = (size_t)(c.bits_per_slice / 8) * (H / SH);
        uint8_t *cb1 = malloc(cfb * NF), *cb2 = malloc(cfb * NF);
        uint8_t *cb3 = malloc(cfb * NF);
        if (!cut || !cd1 || !cd2 || !cd3 || !cb1 || !cb2 || !cb3) {
            printf("FAIL: alloc (cut)\n"); fails++;
        } else {
            /* NF is 4, so this is three cuts in four frames -- deliberately
             * more abrupt than any real programme */
            for (int f = 0; f < NF; f++) {
                if (f & 1) fill(cut + WORDS * f, 12345u, f);  /* never near the rails */
                else fill_rails(cut + WORDS * f, f);          /* graded to the rails */
            }
            int64_t cut_oob = 0, ignore = 0, off_oob = 0;
            run_strict(&c, cut, GM_PASS, cb1, cd1, &cut_oob);
            run_strict(&c, cut, 0, cb2, cd2, &off_oob);
            CHECK(off_oob > 0,
                  "G-T5-CUT1 the gate is NON-VACUOUS: with the repair off, this "
                  "cut sequence does commit samples outside the legal range");
            CHECK(cut_oob == 0,
                  "G-T5-CUT2 one encode at the DEFAULT settings, across cuts "
                  "between rail-graded and ordinary footage, leaves NO committed "
                  "sample outside the legal range -- nothing is switched at the "
                  "cuts");
            run_strict(&c, cd1, GM_PASS, cb2, cd2, &ignore);
            run_strict(&c, cd2, GM_PASS, cb3, cd3, &ignore);
            CHECK(memcmp(cd1, cd2, WORDS * 2 * NF) == 0 &&
                  memcmp(cd2, cd3, WORDS * 2 * NF) == 0 &&
                  memcmp(cb2, cb3, cfb * NF) == 0,
                  "G-T5-CUT3 and that cut sequence survives a baseband "
                  "generation chain byte for byte");
            {   /* cutting must not make the HARD synthetic any worse */
                uint16_t *pl = malloc(WORDS * 2 * NF);
                int64_t plate_oob = 0, mixed_oob = 0;
                if (pl) {
                    for (int f = 0; f < NF; f++) fill_rails_g(pl + WORDS * f, f, 0);
                    run_strict(&c, pl, GM_PASS, cb2, cd2, &plate_oob);
                    for (int f = 0; f < NF; f++)
                        if (f == 1) fill(pl + WORDS * f, 12345u, f);
                    run_strict(&c, pl, GM_PASS, cb2, cd2, &mixed_oob);
                    printf("   hard plates alone leave %lld samples out of range; "
                           "cut with ordinary footage, %lld\n",
                           (long long)plate_oob, (long long)mixed_oob);
                    CHECK(plate_oob == 0 && mixed_oob == 0,
                          "G-T5-CUT4 hard black and white plates at the exact "
                          "rails close completely too, alone AND cut against "
                          "ordinary footage");
                }
                free(pl);
            }
        }
        free(cut); free(cd1); free(cd2); free(cd3);
        free(cb1); free(cb2); free(cb3);
    }
    /* ------------------------------------------- [A2-CUTPROBE6] long run */
    {
        const int NFL = 24;           /* long enough for two waves at period 8 */
        const int CUTEVERY = 6;       /* a cut every 6 frames: a programme shape */
        uint16_t *lg = malloc(WORDS * 2 * (size_t)NFL);
        uint16_t *ld = malloc(WORDS * 2 * (size_t)NFL);
        size_t lfb = (size_t)(c.bits_per_slice / 8) * (H / SH);
        uint8_t *lb = malloc(lfb * (size_t)NFL);
        if (lg && ld && lb) {
            for (int f = 0; f < NFL; f++) {
                if ((f / CUTEVERY) & 1) fill(lg + WORDS * f, 12345u, f);
                else                    fill_rails_g(lg + WORDS * f, f, 0);
            }
            long long cut24_oob = 0; int cut24_nondet = 0;
            int rr[6]; rr[0]=2; rr[1]=3; rr[2]=4; rr[3]=6; rr[4]=8;
            rr[5]=OMC_REFRESH_NONE;
            int save = c.refresh_r;
            printf("   [A2-CUTPROBE6] %d frames, cut every %d, sweep refresh_r:\n",
                   NFL, CUTEVERY);
            for (int t = 0; t < 6; t++) {
                int64_t o = 0, o2 = 0;
                c.refresh_r = (uint8_t)rr[t];
                run_strict_n(&c, lg, GM_PASS, lb, ld, &o, NFL);
                int64_t un = gm_last_unfixed;
                run_strict_n(&c, lg, GM_PASS, lb, ld, &o2, NFL);
                printf("     refresh_r=%-5s oob=%-6lld unfixed=%-4lld %s%s\n",
                       rr[t] == OMC_REFRESH_NONE ? "NONE" :
                         (rr[t]==2?"2":rr[t]==3?"3":rr[t]==4?"4":rr[t]==6?"6":"8"),
                       (long long)o, (long long)un,
                       o == o2 ? "" : "!NONDET!",
                       rr[t] == 8 ? "   <-- SHIPPED DEFAULT" : "");
                cut24_oob += o; cut24_nondet += (o != o2);
            }
            /* [V536] G-T5-CUT24: the 4-frame gates above cannot complete a refresh wave at the
             * shipped period (refresh_r 4..8 are literally the same encode there -- Agents 1, 2,
             * 4 and the codec expert, 2026-09-07).  At the shipped repair budget of 12 this
             * sequence committed 17 out-of-range samples (2 unclosable slices) at refresh_r = 8
             * on every tree measured (v54tree_int 14 / v54tree_g 26 / v5.3.5 17); one more pass
             * (OMC_GAMUT_DEFPASS = GM_PASS = 13) takes every row of the sweep to 0.  The gate
             * asserts the contract the mode makes -- oob = 0, unconditionally -- across two full
             * waves at the shipped period and at every other period including NONE. */
            /* [V537-BUDGET] the gate's budget, the library's default and therefore the CLI's must be ONE number */
            CHECK(omc_enc_gamut_default() == GM_PASS,
                  "G-T5-BUDGET the library default repair budget equals this suite's GM_PASS (the CLI takes the library's)");
            CHECK(cut24_oob == 0 && cut24_nondet == 0,
                  "G-T5-CUT24 two refresh waves at the SHIPPED period with cuts every 6 frames commit no out-of-range sample (any period, incl. NONE), deterministically");

            /* ---------------- [V15] G-T5-CAP1 / G-T5-CAP2 -----------------
             * The total-pass cap changes nothing at its real value, by design.
             * So the gate must first prove the cap is REACHABLE (CAP1, with the
             * probe lowering it), and only then that it is INERT at the real
             * value (CAP2).  A cap that cannot be shown to fire is a cap nobody
             * can trust. */
            c.refresh_r = 8;                       /* the shipped period */
            {
                int64_t o1 = 0;
                setenv("OMC_GAMUT_TOTALCAP_PROBE", "3", 1);
                run_strict_n(&c, lg, GM_PASS, lb, ld, &o1, NFL);
                int probe_max = gm_last_total_max, probe_cap = gm_last_total_cap;
                long long probe_stops = gm_last_capstops;
                int64_t probe_unfixed = gm_last_unfixed;
                unsetenv("OMC_GAMUT_TOTALCAP_PROBE");
                printf("   [V15] probe cap=%d total_max=%d capstops=%lld unfixed=%lld oob=%lld\n",
                       probe_cap, probe_max, probe_stops,
                       (long long)probe_unfixed, (long long)o1);
                /* The cap guards the FRESH-BUDGET paths, not the inner pass
                 * loop (C.3 keeps the per-attempt budget at gamut_strict).  So
                 * it bounds the number of granted budgets, and the total it
                 * yields is cap + at most one more full attempt -- a probe of 3
                 * gives ~15 at a budget of 13, not 3.  Asserting <= 3 would be
                 * asserting something this design cannot deliver.  What the
                 * gate must show is that the cap FIRES and BINDS: restarts were
                 * refused, and the total stayed inside cap + gamut_strict. */
                CHECK(probe_cap == 3 && probe_stops > 0 &&
                      probe_max <= 3 + GM_PASS,
                      "G-T5-CAP1 the total-pass cap is REACHABLE: with the probe at 3 the cap "
                      "refuses fresh budgets and the per-slice total stays inside cap + budget");
            }
            {
                int64_t o2 = 0;
                run_strict_n(&c, lg, GM_PASS, lb, ld, &o2, NFL);
                int real_max = gm_last_total_max, real_cap = gm_last_total_cap;
                long long real_stops = gm_last_capstops;
                unsigned long long h = dec_hash64(ld, (size_t)WORDS * (size_t)NFL);
                printf("   [V15] real cap=%d total_max=%d capstops=%lld oob=%lld dechash=%016llx\n",
                       real_cap, real_max, real_stops, (long long)o2, h);
                CHECK(real_cap == (3 + omc_gm_redomax) * GM_PASS &&
                      real_max <= real_cap && real_stops == 0 && o2 == 0,
                      "G-T5-CAP2 at the real cap ((3 + redomax) x budget) nothing is stopped, the "
                      "worst total stays inside it, and the arm still commits no out-of-range sample");
            }
            c.refresh_r = (uint8_t)save;
        }
        free(lg); free(ld); free(lb);
    }


    /* ------------------------------------------------------- G-T5-CALM */
    {
        omc_config_t cc; cfg_init(&cc);
        cc.bits_per_slice = W * SH / 2;      /* 0.25 bpp: a coarse step */
        cc.refresh_r = 8;
        size_t cfb = (size_t)(cc.bits_per_slice / 8) * (H / SH);
        uint16_t *cp = malloc(WORDS * 2 * NF);
        uint16_t *d0 = malloc(WORDS * 2 * NF), *d1 = malloc(WORDS * 2 * NF);
        uint16_t *d2 = malloc(WORDS * 2 * NF), *d3 = malloc(WORDS * 2 * NF);
        uint8_t *b0 = malloc(cfb * NF), *b1 = malloc(cfb * NF);
        uint8_t *b2 = malloc(cfb * NF), *b3 = malloc(cfb * NF);
        if (!cp || !d0 || !d1 || !d2 || !d3 || !b0 || !b1 || !b2 || !b3) {
            printf("FAIL: alloc (calm)\n"); fails++;
        } else {
            for (int f = 0; f < NF; f++) fill_flat(cp + WORDS * f, f);
            int keep = omc_calm;
            omc_calm = 0; run_chain(&cc, cp, b0, d0);
            omc_calm = keep ? keep : 1; run_chain(&cc, cp, b1, d1);
            int off = ants_tail(d0), on = ants_tail(d1);
            printf("   ants tail over the flat field: fix off %d.%02d %%, "
                   "fix on %d.%02d %% (of samples moving more than 6 codes)\n",
                   off / 100, off % 100, on / 100, on % 100);
            CHECK(off > 100,
                  "G-T5-CALM1a the gate is NON-VACUOUS: with the fix OFF a "
                  "source-static flat field moves in the decode");
            CHECK(on * 2 <= off,
                  "G-T5-CALM1b with the fix ON that movement is at least "
                  "halved");
            CHECK(memcmp(b0, b1, cfb * NF) != 0,
                  "G-T5-CALM1c the fix actually changed the stream (it is not "
                  "silently inert on this content)");
            run_chain(&cc, d1, b2, d2);
            run_chain(&cc, d2, b3, d3);
            CHECK(memcmp(d1, d2, WORDS * 2 * NF) == 0,
                  "G-T5-CALM2a generation-2 pixels reproduce generation 1 with "
                  "the calm kill firing");
            CHECK(memcmp(b2, b3, cfb * NF) == 0 &&
                  memcmp(d2, d3, WORDS * 2 * NF) == 0,
                  "G-T5-CALM2b and generation 3 reproduces generation 2's "
                  "stream byte-for-byte");
            omc_calm = keep;
        }
        free(cp); free(d0); free(d1); free(d2); free(d3);
        free(b0); free(b1); free(b2); free(b3);
    }

    free(pix); free(dec1); free(dec2); free(dec3); free(decx);
    free(bs1); free(bs2); free(bs3); free(bsx);
    printf("test_xsl: %s\n", fails ? "FAILURES" : "all ok");
    return fails != 0;
}
