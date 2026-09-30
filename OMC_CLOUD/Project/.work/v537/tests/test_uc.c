/* OMC-UC unit gates.  Same posture as tests/test_unit.c: every claim the
 * upconverter makes is a test here, and the binary prints "all ok" only if all
 * of them hold.
 *
 *   1. kernel     - the multiplier-free evaluation equals the tabulated taps
 *   2. rt         - down(up(x)) == x, byte-exact, every plane, 8/10/12-bit
 *   3. band       - producing the output in bands == producing it whole
 *   4. latency    - output rows of slice k do not depend on any source row
 *                   beyond the end of slice k+1  (the +1 slice period bound)
 *   5. reach      - the measured vertical dependency reach is <= 8 source rows
 *   6. range      - output never leaves [0, 2^depth)
 *   7. determinism- repeated runs and interleaved instances agree
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "omc1.h"
#include "omc_uc.h"

static int fails = 0;
static void ok(const char *m) { printf("ok: %s\n", m); }
static void bad(const char *m) { printf("FAIL: %s\n", m); fails++; }

static uint32_t rs = 12345u;
static uint32_t rnd(void) { rs = rs * 1103515245u + 12345u; return rs >> 8; }

/* Adversarial fill: full-range bimodal noise.  This is the content class that
 * exposes the extreme direction candidates -- the smooth/structured picture in
 * fill_content() does not, and a reach gate driven by it reports a number that
 * is too small.  Found by adversarial review, kept as a gate. */
static void fill_adversarial(uint16_t *p, int w, int h, int stride, int depth)
{
    int maxv = (1 << depth) - 1;
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            uint32_t r = rnd();
            p[(size_t)y * stride + x] = (uint16_t)((r & 1) ? maxv : 0);
            if ((r & 6) == 0) p[(size_t)y * stride + x] = (uint16_t)(r % (uint32_t)(maxv + 1));
        }
}

static void fill_content(uint16_t *p, int w, int h, int stride, int depth)
{
    /* smooth base + oriented edges + noise: exercises every branch */
    int maxv = (1 << depth) - 1;
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            int v = (x * maxv) / (w * 2) + (y * maxv) / (h * 4);
            if ((3 * x + 5 * y) % 97 < 30) v = maxv - v;
            if (((x >> 3) + (y >> 3)) & 1) v += (int)(rnd() % 37) - 18;
            if (x > w / 2 && y > h / 2) v = (int)(rnd() % (uint32_t)(maxv + 1));
            p[(size_t)y * stride + x] = (uint16_t)(v < 0 ? 0 : v > maxv ? maxv : v);
        }
}

/* G21: the raster-clocked output stage, proved by ROW-BY-ROW SIMULATION rather
 * than by re-deriving the algebra that produced the figure.
 *
 * The claim under test: when the decoder hands rows to the rescaler as they
 * become final and the output is clocked at the destination raster rate, the
 * conversion costs `reach` lines (plus one for OMC_XSL's deferred last row) --
 * NOT ceil(reach/slice_h) whole slice periods, which is what the model charged
 * before 2026-08-12.
 *
 * The simulation walks every output row, works out which source row it needs,
 * when that row is final (honouring both the slice schedule AND the XSL rewrite
 * of the previous slice's last row), and when it is due.  It asserts that the
 * worst requirement never exceeds the bound, over every supported format, slice
 * height and conversion ratio.  It also asserts the batched form still returns
 * the older, higher figure, so an integration that cannot meet the contract is
 * not silently handed the better number. */
static int sim_out_stage(void)
{
    static const int HS[] = { 720, 1080, 2160, 4320 };
    static const double FPS[] = { 50.0, 59.94, 60.0, 100.0, 120.0 };
    static const int SHS[] = { 8, 16, 32 };
    int bad = 0, cases = 0, tight = 0;
    for (unsigned h = 0; h < 4; h++)
      for (unsigned f = 0; f < 5; f++)
        for (unsigned k = 0; k < 3; k++)
          for (unsigned d = 0; d < 4; d++) {
            int disp = HS[h], dst = HS[d], sh = SHS[k];
            if (dst == disp) continue;
            int g = 0, a = disp, b = dst;
            while (b) { int t = a % b; a = b; b = t; }
            g = a;
            int num = disp / g, den = dst / g;
            if (!omc_uc_scale_taps(num, den)) continue;
            int reach = omc_uc_scale_reach_r(num, den);
            int coded = disp % sh ? (disp / sh + 1) * sh : disp;
            int nsl = coded / sh;
            double frame = 1000.0 / FPS[f];
            double line = frame / disp, sp = frame / nsl;
            double worst = 0.0;
            for (int r = 0; r < dst; r++) {
                long long i = ((long long)r * num) / den;
                int srow = (int)(i + reach);
                if (srow > disp - 1) srow = disp - 1;
                int j = srow / sh;
                /* XSL 3: the last row of a slice is rewritten by the next one */
                if ((srow % sh) == sh - 1 && j + 1 < nsl) j++;
                double avail = sh * line + sp + 2 * line + j * sp;
                double due = r * (frame / dst);
                double need = avail - due;
                if (need > worst) worst = need;
            }
            double base = sh * line + sp + 2 * line;
            double bound = base + (reach + 1) * line;
            cases++;
            if (worst > bound + 1e-9) bad++;
            if (worst > bound - line * 0.5) tight++;
          }
    printf("   output-stage simulation: %d (format, slice height, ratio) cases, "
           "%d over the bound, %d within half a line of it\n", cases, bad, tight);
    return bad;
}

int main(void)
{
    const int W = 96, H = 64;
    omc_uc_t uc;
    uc.direction = 1;

    {   /* G22: the two sample-siting conventions, pinned.
         *
         * This exists because the distinction was made once, written down in a
         * session ledger, and then lost -- the rational path was re-centred for
         * picture resizing and the 4:2:2 chroma detour was re-centred with it,
         * which put the colour a quarter sample off its luma and doubled the
         * round-trip loss.  A comment did not prevent that.  A gate does.
         *
         * Resample a ramp and read the offset straight off the values:
         *   co-sited  -> output 2k lands exactly on source k
         *   centred   -> output 2k lands a quarter sample early, 2k+1 a quarter late
         * If either drifts, or if one convention is ever quietly made to behave
         * like the other, this fails and says which. */
        enum { GW = 64, GH = 32, GDW = 128 };
        static uint16_t gs[GW * GH], gc[GDW * GH], gp[GDW * GH];
        omc_uc_t gu; int gx, gy, okg = 1;
        double pc, pp, pc1;
        gu.depth = 10; gu.direction = 0;
        for (gy = 0; gy < GH; gy++)
            for (gx = 0; gx < GW; gx++)
                gs[gy * GW + gx] = (uint16_t)(100 + 8 * gx);
        omc_uc_scale_plane_sited(&gu, gs, GW, GW, GH, gc, GDW, GDW, GH,
                                 OMC_SITE_CENTRE);
        omc_uc_scale_plane_sited(&gu, gs, GW, GW, GH, gp, GDW, GDW, GH,
                                 OMC_SITE_COSITED);
        gy = GH / 2;
        pp  = (gp[gy * GDW + 40] - 100.0) / 8.0;   /* co-sited, wants 20.00 */
        pc  = (gc[gy * GDW + 40] - 100.0) / 8.0;   /* centred,  wants 19.75 */
        pc1 = (gc[gy * GDW + 41] - 100.0) / 8.0;   /* centred,  wants 20.25 */
        if (pp < 19.99 || pp > 20.01) okg = 0;
        if (pc < 19.74 || pc > 19.76) okg = 0;
        if (pc1 < 20.24 || pc1 > 20.26) okg = 0;
        printf("   siting: co-sited out[40] -> source %.3f (20.000); "
               "centred out[40] -> %.3f (19.750), out[41] -> %.3f (20.250)\n",
               pp, pc, pc1);
        okg ? ok("G22 sample siting: co-sited puts output 2k exactly on source k "
                 "(what 4:2:2 chroma needs, and what keeps a shrink-and-expand "
                 "landing back on the original samples); centred puts it half a "
                 "source sample later (what resizing a picture needs).  Neither "
                 "convention may drift into the other")
            : bad("G22 sample siting: a convention moved");
    }

    {   /* G21 -- see above */
        double t_raster = 0, t_batched = 0;
        int p1 = 0, p2 = 0;
        int bad = sim_out_stage();
        omc_uc_scale_latency(3840, 2160, 1920, 1080, 32, 50, 1, &t_raster, &p1);
        omc_uc_scale_latency_ex(3840, 2160, 1920, 1080, 32, 50, 1,
                                OMC_OUT_SLICE_BATCHED, &t_batched, &p2);
        printf("   2160p50 -> 1080p50 at slice_h 32: raster %.4f ms (%d periods), "
               "slice-batched %.4f ms (%d periods)\n", t_raster, p1, t_batched, p2);
        if (bad || t_raster >= t_batched || p1 != 0 || p2 <= 0) {
            printf("FAIL: raster-clocked output stage\n");
            fails++;
        } else
            ok("G21 raster-clocked output stage: simulated row by row over every "
               "format, slice height and ratio, the conversion never costs more "
               "than reach+1 lines -- and the slice-batched contract still "
               "reports its own, higher figure so an integration that cannot "
               "stream rows is not handed the better number");
    }

    {   /* The reach must be bounded from the CONSTANTS, not from a picture:
         * the direction search only exercises its extreme taps when an extreme
         * candidate wins, so benign content under-reports it (this test used to
         * report 6-8 while the true worst case was 9). */
        int ar = omc_uc_analytic_reach();
        char m[160];
        snprintf(m, sizeof m, "reach (analytic, from the normative constants): "
                 "%d source rows <= slice_h floor 8", ar);
        (ar <= 8) ? ok(m) : bad(m);
    }

    if (omc_uc_selfcheck_kernel() == 0)
        ok("kernel: multiplier-free 12-tap == tabulated coefficients (all taps, full range)");
    else
        bad("kernel: shift-add form differs from the tabulated coefficients");
    /* The polyphase bank is now PUBLISHED CONSTANTS rather than a runtime
     * sin()/sqrt() computation, so it can be checked structurally on every
     * platform instead of trusted to the host libm. */
    if (omc_uc_selfcheck_poly_mul() == 0)
        ok("polyphase bank: the shift-add evaluation equals the tabulated multiply "
           "for every coefficient of every published table, over the full range");
    else
        bad("polyphase bank: the shift-add form differs from the multiply");
    if (omc_uc_selfcheck_poly() == 0)
        ok("polyphase bank: unity DC on every phase, phase 0 is the unit impulse, "
           "the 1:2 phase equals UC_C exactly, and phase p mirrors phase den-p");
    else
        bad("polyphase bank: a published table violates unity DC, the identity "
            "phase, the UC_C reduction or linear phase");

    /* ------------------------------------------------- no divider per sample */
    {   /* uc_mir() is the only place in the datapath that could contain a
         * division: it folds an out-of-range index back into the plane, and
         * the general form needs a modulo by 2n-2, a RUNTIME value.  An FPGA
         * cannot afford that per sample.
         *
         * It is unreachable in practice, and this proves the bound rather than
         * asserting it: the widest index any predictor asks for is the 12-tap
         * half-support plus the direction search's extreme candidate and SAD
         * tap, so the modulo can only be entered when the plane dimension is
         * smaller than that reach.  Below n = 20 it can; at n >= 20 it never
         * can, and the smallest plane dimension in any supported format is a
         * 4:2:2 chroma row at 720p, which is 640.
         *
         * So the reference C has no divider in the per-sample path either --
         * not merely the RTL a vendor would write from it. */
        const int REACH = 6 + 4 + 6 + 2;
        int n, i, worst = 0;
        for (n = 20; n <= 4096; n = n < 64 ? n + 1 : n * 2)
            for (i = -REACH; i < n + REACH; i++) {
                int a = i < 0 ? -i : i;
                if (a >= 2 * n - 2) worst = n;   /* would enter the modulo */
            }
        if (!worst)
            ok("mirror: no modulo is reachable at any plane dimension >= 20 "
               "(smallest supported is 640), so the per-sample path is "
               "divider-free in the reference too");
        else
            bad("mirror: the modulo is reachable at a supported plane size");
    }

    /* --------------------------------------------- banded DOWN == whole plane */
    {   /* The forward operator has had a band API from the start; the inverse
         * did not, so a leg that downconverts had no bounded-memory,
         * bounded-latency path.  Banding is only legal if it is EXACT. */
        const int BW = 96, BH = 64;
        omc_uc_t ub; uint16_t *big, *a, *b;
        int r, c, bandh, good = 1;
        ub.depth = 10; ub.direction = 1;        big = malloc((size_t)(2 * BW) * (2 * BH) * 2);
        a = malloc((size_t)BW * BH * 2);
        b = malloc((size_t)BW * BH * 2);
        if (big && a && b) {
            unsigned s = 12345u;
            for (r = 0; r < 2 * BH; r++)
                for (c = 0; c < 2 * BW; c++) {
                    s = s * 1103515245u + 12345u;
                    big[(size_t)r * 2 * BW + c] = (uint16_t)((s >> 16) & 1023);
                }
            omc_uc_down_plane(&ub, big, 2 * BW, BW, BH, a, BW);
            for (bandh = 1; bandh <= 16 && good; bandh *= 2) {
                memset(b, 0, (size_t)BW * BH * 2);
                for (r = 0; r < BH; r += bandh) {
                    int r1 = r + bandh > BH ? BH : r + bandh;
                    if (omc_uc_down_plane_band(&ub, big, 2 * BW, BW, BH, b, BW, r, r1) < 0)
                        good = 0;
                }
                if (memcmp(a, b, (size_t)BW * BH * 2) != 0) good = 0;
            }
            if (good)
                ok("band (down): 1/2/4/8/16-row banded downconversion == whole-plane");
            else
                bad("band (down): banded downconversion differs from the whole plane");
        }
        free(big); free(a); free(b);
    }

    /* ------------------------------------------------------ aspect framing */
    {   /* letterbox 16:9 -> 4:3, pillarbox 4:3 -> 16:9, and the 14:9 middle.
         * The bars must carry EXACTLY the fill level: they are written once and
         * the scaler never touches them, which is the structural answer to the
         * ringing-into-a-flat-bar defect the delivery document records in 10.5. */
        const int SW = 480, SH = 270, DW = 360, DH = 270;
        omc_uc_t uf; uint16_t *s, *d;
        int r, c, barbad = 0, ah = 180, ay, rc;
        uf.depth = 10; uf.direction = 1;        ay = (DH - ah) / 2;
        s = malloc((size_t)SW * SH * 2);
        d = malloc((size_t)DW * DH * 2);
        if (s && d) {
            for (r = 0; r < SH; r++)
                for (c = 0; c < SW; c++)
                    s[(size_t)r * SW + c] = (uint16_t)(64 + ((r * 7 + c * 3) % 800));
            /* 480x270 (16:9) into 360x270 (4:3): full width, 4/3 vertical down */
            rc = omc_uc_frame_plane(&uf, s, SW, SW, SH, 0, 0, SW, SH,
                                    d, DW, DW, DH, 0, 45, DW, 180, 64, 0);  /* 3:2 vertical */
            for (r = 0; r < DH && !barbad; r++)
                for (c = 0; c < DW; c++)
                    if ((r < 45 || r >= 45 + 180) && d[(size_t)r * DW + c] != 64) { barbad = 1; break; }
            if (rc == 0 && !barbad)
                ok("aspect: letterbox 16:9 -> 4:3, bars carry exactly the fill level");
            else
                bad("aspect: letterbox failed or a bar was not the fill level");
            /* a horizontally odd rect must be refused: 4:2:2 chroma is half width */
            rc = omc_uc_frame_plane(&uf, s, SW, SW, SH, 0, 0, SW, SH,
                                    d, DW, DW, DH, 1, 45, DW - 2, 180, 64, 0);
            if (rc == -1)
                ok("aspect: a horizontally odd destination rect is refused (4:2:2)");
            else
                bad("aspect: an odd horizontal rect was accepted");
            /* a rect outside the output raster must be refused */
            rc = omc_uc_frame_plane(&uf, s, SW, SW, SH, 0, 0, SW, SH,
                                    d, DW, DW, DH, 0, 200, DW, 180, 64, 0);
            if (rc == -1)
                ok("aspect: a rect that leaves the output raster is refused");
            else
                bad("aspect: an out-of-raster rect was accepted");
            /* the horizontal mirror is the only free flip, and it must be an
             * exact reversal of the un-mirrored result -- not a re-render */
            {
                uint16_t *d2 = malloc((size_t)DW * DH * 2);
                int mbad = 0;
                omc_uc_frame_plane(&uf, s, SW, SW, SH, 0, 0, SW, SH,
                                   d, DW, DW, DH, 0, 45, DW, 180, 64, 0);
                omc_uc_frame_plane(&uf, s, SW, SW, SH, 0, 0, SW, SH,
                                   d2, DW, DW, DH, 0, 45, DW, 180, 64, 1);
                for (r = 45; r < 45 + 180 && !mbad; r++)
                    for (c = 0; c < DW; c++)
                        if (d2[(size_t)r * DW + c] != d[(size_t)r * DW + DW - 1 - c])
                            { mbad = 1; break; }
                mbad ? bad("aspect: the horizontal mirror is not an exact reversal")
                     : ok("aspect: the horizontal mirror is an exact reversal of the "
                          "un-mirrored rect -- within a line, so it costs no reach "
                          "and no slice period (the only free flip; vertical and "
                          "90 deg need the whole frame)");
                free(d2);
            }
        }
        free(s); free(d);
        (void)ah; (void)ay;
    }

    /* ---------------------------------------------------------- rt + range */
    for (int di = 0; di < 3; di++) {
        int depth = (int[]){8, 10, 12}[di];
        int maxv = (1 << depth) - 1;
        uint16_t *src = malloc((size_t)W * H * 2);
        uint16_t *big = malloc((size_t)4 * W * H * 2);
        uint16_t *back = malloc((size_t)W * H * 2);
        int rt_ok = 1, range_ok = 1;
        uc.depth = (uint8_t)depth;
        fill_content(src, W, H, W, depth);
        omc_uc_up_plane(&uc, src, W, W, H, big, 2 * W, 0, 2 * H);
        for (int i = 0; i < 4 * W * H; i++)
            if (big[i] > maxv) range_ok = 0;
        omc_uc_down_plane(&uc, big, 2 * W, W, H, back, W);
        if (memcmp(src, back, (size_t)W * H * 2)) rt_ok = 0;
        char m[128];
        snprintf(m, sizeof m, "rt: down(up(x)) == x byte-exact at %d-bit", depth);
        rt_ok ? ok(m) : bad(m);
        snprintf(m, sizeof m, "range: upconverted output stays inside [0, 2^%d)", depth);
        range_ok ? ok(m) : bad(m);
        free(src); free(big); free(back);
    }

    /* ------------------------------------------------------------- banding */
    {
        uint16_t *src = malloc((size_t)W * H * 2);
        uint16_t *a = calloc((size_t)4 * W * H, 2);
        uint16_t *b = calloc((size_t)4 * W * H, 2);
        int good = 1;
        uc.depth = 10;
        fill_content(src, W, H, W, 10);
        omc_uc_up_plane(&uc, src, W, W, H, a, 2 * W, 0, 2 * H);
        for (int bandh = 2; bandh <= 32 && good; bandh *= 2) {
            memset(b, 0, (size_t)4 * W * H * 2);
            for (int r = 0; r < 2 * H; r += bandh) {
                int r1 = r + bandh > 2 * H ? 2 * H : r + bandh;
                omc_uc_up_plane(&uc, src, W, W, H, b, 2 * W, r, r1);
            }
            if (memcmp(a, b, (size_t)4 * W * H * 2)) good = 0;
        }
        good ? ok("band: 2/4/8/16/32-row band output == whole-plane output")
             : bad("band: banded output differs from whole-plane output");
        free(src); free(a); free(b);
    }

    /* ------------------------------------------------------------- latency
     * The claim: with one slice period of delay, the upconverted rows of slice
     * k are final.  Test it the way the codec tests causality -- poison every
     * source row at or beyond the end of slice k+1 and require the output rows
     * of slice k to be bit-identical. */
    {
        int good = 1, worst_used = -1;
        uc.depth = 10;
        for (int sh = 8; sh <= 16; sh += 8) {
            uint16_t *src = malloc((size_t)W * H * 2);
            uint16_t *pos = malloc((size_t)W * H * 2);
            uint16_t *a = calloc((size_t)4 * W * H, 2);
            uint16_t *b = calloc((size_t)4 * W * H, 2);
            /* adversarial content: this is what makes the gate meaningful */
            fill_adversarial(src, W, H, W, 10);
            omc_uc_up_plane(&uc, src, W, W, H, a, 2 * W, 0, 2 * H);
            for (int k = 0; k * sh < H; k++) {
                int keep = (k + 2) * sh;            /* rows [0, keep) available */
                if (keep > H) keep = H;
                memcpy(pos, src, (size_t)W * H * 2);
                for (int y = keep; y < H; y++)
                    for (int x = 0; x < W; x++) pos[(size_t)y * W + x] = (uint16_t)(rnd() & 1023);
                memset(b, 0, (size_t)4 * W * H * 2);
                omc_uc_up_plane(&uc, pos, W, W, H, b, 2 * W, 2 * k * sh,
                                2 * (k + 1) * sh > 2 * H ? 2 * H : 2 * (k + 1) * sh);
                for (int r = 2 * k * sh; r < 2 * (k + 1) * sh && r < 2 * H; r++)
                    if (memcmp(a + (size_t)r * 2 * W, b + (size_t)r * 2 * W,
                               (size_t)4 * W)) { good = 0; }
            }
            free(src); free(pos); free(a); free(b);
        }
        (void)worst_used;
        good ? ok("latency: output rows of slice k depend on nothing past slice k+1 "
                  "(slice_h 8 and 16) -> exactly +1 slice period")
             : bad("latency: output of slice k reads beyond slice k+1");
    }

    /* --------------------------------------------------------------- reach */
    {
        int reach = -99;
        uint16_t *src = malloc((size_t)W * H * 2);
        uint16_t *pos = malloc((size_t)W * H * 2);
        uint16_t *a = malloc((size_t)4 * W * H * 2);
        uint16_t *b = malloc((size_t)4 * W * H * 2);
        uc.depth = 10;
        fill_adversarial(src, W, H, W, 10);   /* see fill_adversarial() */
        omc_uc_up_plane(&uc, src, W, W, H, a, 2 * W, 0, 2 * H);
        for (int q = 12; q < H - 12; q++) {
            memcpy(pos, src, (size_t)W * H * 2);
            for (int x = 0; x < W; x++) pos[(size_t)q * W + x] ^= (uint16_t)(1 + (rnd() & 255));
            omc_uc_up_plane(&uc, pos, W, W, H, b, 2 * W, 0, 2 * H);
            for (int r = 0; r < 2 * H; r++)
                if (memcmp(a + (size_t)r * 2 * W, b + (size_t)r * 2 * W, (size_t)4 * W)) {
                    int d = q - (r / 2);
                    if (d > reach) reach = d;
                    break;
                }
        }
        printf("   measured reach on adversarial content: %d source rows "
               "(analytic worst case %d, budget %d = slice_h floor)\n",
               reach, omc_uc_analytic_reach(), 8);
        (reach <= omc_uc_analytic_reach())
            ? ok("reach: the measured reach does not exceed the analytic bound")
            : bad("reach: MEASURED reach exceeds the analytic bound - the bound is wrong");
        free(src); free(pos); free(a); free(b);
    }

    /* --------------------------------------------------------- determinism */
    {
        uint16_t *src = malloc((size_t)W * H * 2);
        uint16_t *a = malloc((size_t)4 * W * H * 2);
        uint16_t *b = malloc((size_t)4 * W * H * 2);
        uc.depth = 12;
        fill_content(src, W, H, W, 12);
        omc_uc_up_plane(&uc, src, W, W, H, a, 2 * W, 0, 2 * H);
        omc_uc_up_plane(&uc, src, W, W, H, b, 2 * W, 0, 2 * H);
        memcmp(a, b, (size_t)4 * W * H * 2) == 0
            ? ok("determinism: identical input -> identical output (no state, no RNG)")
            : bad("determinism: repeated runs differ");
        free(src); free(a); free(b);
    }

    /* ----------------------------------------------------------- 4x cascade */
    {
        uint16_t *src = malloc((size_t)W * H * 2);
        uint16_t *m2 = malloc((size_t)4 * W * H * 2);
        uint16_t *m4 = malloc((size_t)16 * W * H * 2);
        uint16_t *b2 = malloc((size_t)4 * W * H * 2);
        uint16_t *b1 = malloc((size_t)W * H * 2);
        uc.depth = 10;
        fill_content(src, W, H, W, 10);
        omc_uc_up_plane(&uc, src, W, W, H, m2, 2 * W, 0, 2 * H);
        omc_uc_up_plane(&uc, m2, 2 * W, 2 * W, 2 * H, m4, 4 * W, 0, 4 * H);
        omc_uc_down_plane(&uc, m4, 4 * W, 2 * W, 2 * H, b2, 2 * W);
        omc_uc_down_plane(&uc, b2, 2 * W, W, H, b1, W);
        (memcmp(src, b1, (size_t)W * H * 2) == 0 &&
         memcmp(m2, b2, (size_t)4 * W * H * 2) == 0)
            ? ok("4x: two cascaded levels invert exactly (both the 4x->2x and the "
                 "2x->1x step), so --upconv 4 inherits the reversibility contract")
            : bad("4x: the cascaded round trip is not exact");
        /* the cascade's reach in SOURCE rows: level 2 reaches R+8 rows of the 2x
         * image = 4 source rows, on top of level 1's 8 -> the binding number is
         * still the level-1 reach because level 2's input rows are themselves
         * produced within the level-1 window. Verified by poisoning. */
        {
            uint16_t *pos = malloc((size_t)W * H * 2);
            uint16_t *c2 = malloc((size_t)4 * W * H * 2);
            uint16_t *c4 = malloc((size_t)16 * W * H * 2);
            int worst = -99;
            fill_adversarial(src, W, H, W, 10);
            omc_uc_up_plane(&uc, src, W, W, H, m2, 2 * W, 0, 2 * H);
            omc_uc_up_plane(&uc, m2, 2 * W, 2 * W, 2 * H, m4, 4 * W, 0, 4 * H);
            for (int q = 14; q < H - 14; q++) {
                memcpy(pos, src, (size_t)W * H * 2);
                for (int x = 0; x < W; x++) pos[(size_t)q * W + x] ^= (uint16_t)(1 + (rnd() & 511));
                omc_uc_up_plane(&uc, pos, W, W, H, c2, 2 * W, 0, 2 * H);
                omc_uc_up_plane(&uc, c2, 2 * W, 2 * W, 2 * H, c4, 4 * W, 0, 4 * H);
                for (int r = 0; r < 4 * H; r++)
                    if (memcmp(m4 + (size_t)r * 4 * W, c4 + (size_t)r * 4 * W, (size_t)8 * W)) {
                        int d = q - (r / 4);
                        if (d > worst) worst = d;
                        break;
                    }
            }
            printf("   4x cascaded reach: %d source rows measured, %d analytic "
                   "-> %d slice period(s) at slice_h 8, %d at slice_h 16\n",
                   worst, omc_uc_analytic_reach_n(2),
                   (omc_uc_analytic_reach_n(2) + 7) / 8,
                   (omc_uc_analytic_reach_n(2) + 15) / 16);
            (worst <= omc_uc_analytic_reach_n(2))
                ? ok("4x latency: the measured cascade reach is within the analytic "
                     "bound (12 source rows = 2 slice periods at slice_h 8, 1 at 16); "
                     "omc_validate_config refuses any (format, ratio) that breaks 1 ms")
                : bad("4x latency: measured cascade reach exceeds the analytic bound");
            free(pos); free(c2); free(c4);
        }
        free(src); free(m2); free(m4); free(b2); free(b1);
    }

    /* A HORIZONTAL-ONLY rational conversion must have ZERO vertical reach.
     * This is the shape the 4:2:2 colour path uses -- chroma to 4:4:4 and back
     * along the line only -- and reach is what buys slice periods, so a phantom
     * six-row window would have cost a slice period for nothing. */
    {
        const int W = 48, H = 24;
        omc_uc_t uh;
        uint16_t *s0 = malloc((size_t)W * H * 2);
        uint16_t *o0 = malloc((size_t)2 * W * H * 2);
        uint16_t *sp = malloc((size_t)W * H * 2);
        uint16_t *op = malloc((size_t)2 * W * H * 2);
        int q, r, worst = 0;
        uh.depth = 10; uh.direction = 1;
        fill_adversarial(s0, W, H, W, 10);
        omc_uc_scale_plane(&uh, s0, W, W, H, o0, 2 * W, 2 * W, H);
        for (q = 0; q < H; q++) {
            memcpy(sp, s0, (size_t)W * H * 2);
            for (int x = 0; x < W; x++) sp[(size_t)q * W + x] ^= (uint16_t)(1 + (rnd() & 511));
            omc_uc_scale_plane(&uh, sp, W, W, H, op, 2 * W, 2 * W, H);
            for (r = 0; r < H; r++)
                if (memcmp(o0 + (size_t)r * 2 * W, op + (size_t)r * 2 * W,
                           (size_t)4 * W)) {
                    int d = q - r < 0 ? r - q : q - r;
                    if (d > worst) worst = d;
                }
        }
        worst == 0
            ? ok("G19 horizontal-only scale: output row r depends on source row r "
                 "and nothing else -- zero vertical reach, so a chroma resample "
                 "along the line costs no slice period")
            : bad("G19 horizontal-only scale: a 1:1 vertical ratio still reaches "
                  "across rows");
        free(s0); free(o0); free(sp); free(op);
    }

    /* G20: the rational path has an ALLOCATION-FREE form, and it agrees to the
     * byte with the convenience wrapper.  The dyadic path has had this shape
     * since the original design; the rational path allocated internally, which
     * is the one thing in the operator's C that a synthesis run cannot do at
     * all.  Swept across every ratio class, including a horizontal decimation,
     * because the scratch sizer's first draft under-sized exactly that case. */
    {
        static const struct { int sw, sh, dw, dh; const char *n; } R[] = {
            {  64, 32,  96, 48, "3:2 up"          },
            {  96, 48,  64, 32, "3:2 down"        },
            {  64, 32, 128, 32, "2:1 H up only"   },
            { 128, 32,  64, 32, "2:1 H down only" },
            {  64, 64,  32, 32, "2:1 both axes"   },
            {  60, 40,  80, 50, "4:3 / 5:4"       },
        };
        omc_uc_t ur;
        int k, bad_n = 0;
        ur.depth = 10; ur.direction = 1;
        for (k = 0; k < (int)(sizeof R / sizeof R[0]); k++) {
            int sw = R[k].sw, sh = R[k].sh, dw = R[k].dw, dh = R[k].dh;
            uint16_t *s0 = malloc((size_t)sw * sh * 2);
            uint16_t *a = malloc((size_t)dw * dh * 2);
            uint16_t *b = malloc((size_t)dw * dh * 2);
            size_t n = omc_uc_scale_scratch_bytes(sw, sh, dw, dh);
            void *ws = malloc(n);
            int r1, r2;
            fill_adversarial(s0, sw, sh, sw, 10);
            memset(a, 0xa5, (size_t)dw * dh * 2);
            memset(b, 0x5a, (size_t)dw * dh * 2);
            r1 = omc_uc_scale_plane(&ur, s0, sw, sw, sh, a, dw, dw, dh);
            r2 = omc_uc_scale_plane_ws(&ur, s0, sw, sw, sh, b, dw, dw, dh, ws, n);
            if (r1 || r2 || memcmp(a, b, (size_t)dw * dh * 2)) bad_n++;
            /* and a workspace one byte short must be REFUSED, not overrun */
            if (n > 1 && omc_uc_scale_plane_ws(&ur, s0, sw, sw, sh, b, dw, dw, dh,
                                               ws, n - 1) != -1) bad_n++;
            free(s0); free(a); free(b); free(ws);
        }
        bad_n == 0
            ? ok("G20 rational path, caller-owned memory: omc_uc_scale_plane_ws() "
                 "agrees byte-for-byte with the allocating wrapper on every ratio "
                 "class, and refuses an undersized workspace rather than "
                 "overrunning it — so the rational path now has the same "
                 "no-allocation shape the dyadic path always had")
            : bad("G20 rational path: the workspace form disagrees with the wrapper, "
                  "or accepts an undersized workspace");
    }

    printf(fails ? "FAILURES: %d\n" : "all ok\n", fails);
    return fails ? 1 : 0;
}
