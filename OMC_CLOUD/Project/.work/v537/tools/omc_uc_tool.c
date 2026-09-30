/* omc_uc_tool - standalone driver for the OMC-UC upconverter / downconverter.
 *
 *   omc_uc_tool up   -i in.yuv  -o out.yuv -w W -h H --fmt 422|444 --depth D
 *                    [--frames N] [--no-direction] [--band K]
 *   omc_uc_tool down -i in.yuv  -o out.yuv -w W -h H --fmt 422|444 --depth D
 *                    [--frames N] [--no-direction]
 *
 * `up`   reads WxH planar LE16 frames and writes 2Wx2H.
 * `down` reads 2Wx2H and writes WxH (W,H are the SMALL dimensions).
 * `--band K` produces the output in K-row bands instead of one call, which must
 * give byte-identical output (the slice-wise legality check).
 *
 *   omc_uc_tool colour -i in.yuv -o out.yuv -w W -h H --fmt 422|444 --depth D
 *                      --src-prim 709|2020 --dst-prim 709|2020
 *                      [--src-mtx 709|601|2020] [--dst-mtx ...]
 *                      [--src-trc gamma|pq|hlg] [--dst-trc ...] [--trc ...]
 *                      [--src-range limited|full] [--dst-range limited|full]
 *                      [--tone-map --src-peak NITS --dst-peak NITS]
 *
 * `colour` changes PRIMARIES and/or MATRIX COEFFICIENTS in linear light.  It
 * does not change the transfer -- that is a tone map, and OMC-CC refuses it;
 * see include/omc_cc.h.  4:2:2 input is upsampled to 4:4:4 with the codec's own
 * polyphase filter, converted, and decimated back, because a primaries matrix
 * mixes the three components and is only meaningful where they are co-sited.
 * That is the reason the mode exists here at all: omc_cc_convert() being
 * library-only would repeat the exact defect this review records against
 * uc_ratio and against omc_uc_frame_plane().
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "omc1.h"
#include "omc_uc.h"
#include "omc_cc.h"

/* [V536] bounds-checked option value (external adversarial review of v5.3.5, section 7): every
 * value-taking flag used argv[++i]; as the LAST token that is argv[argc] == NULL and the
 * following atoi()/strcmp() dereferenced it -- a segfault in all nine CLIs on a trailing
 * option.  NEXTARG() refuses with a usage error and exit status 1 instead. */
#define NEXTARG() ((i + 1 < argc) ? argv[++i] : \
    (fprintf(stderr, "%s: option %s needs a value\n", argv[0], argv[i]), exit(1), (char *)0))

static void die(const char *m) { fprintf(stderr, "omc_uc_tool: %s\n", m); exit(1); }

/* Colour code points by name.  Numbers would be terser but a mistyped "2" is a
 * silently wrong picture, whereas a mistyped "2020" is an error message. */
static int cc_prim_arg(const char *s)
{
    if (!strcmp(s, "709")) return OMC_CC_P_BT709;
    if (!strcmp(s, "2020")) return OMC_CC_P_BT2020;
    die("--src-prim/--dst-prim: expected 709 or 2020");
    return 0;
}
static int cc_mtx_arg(const char *s)
{
    if (!strcmp(s, "709")) return OMC_CC_M_BT709;
    if (!strcmp(s, "601")) return OMC_CC_M_BT601;
    if (!strcmp(s, "2020")) return OMC_CC_M_BT2020;
    die("--src-mtx/--dst-mtx: expected 709, 601 or 2020");
    return 0;
}
static int cc_trc_arg(const char *s)
{
    if (!strcmp(s, "gamma")) return OMC_CC_T_GAMMA;
    if (!strcmp(s, "hlg")) return OMC_CC_T_HLG;
    die("--trc: expected gamma, pq or hlg");
    return 0;
}

int main(int argc, char **argv)
{
    const char *inp = NULL, *outp = NULL, *mode = NULL;
    int W = 0, H = 0, depth = 10, c444 = 0, frames = 1 << 30, band = 0, dir = 1;
    int ow = 0, oh = 0;   /* rational output size for mode 'scale' */
    int fps = 50;         /* worst-case line rate for the A2 check          */
    int cx = 0, cy = 0, cw = 0, ch = 0;   /* source crop, mode "frame"     */
    int rx = 0, ry = 0, rw = 0, rh = 0;   /* destination rect              */
    int fillv = -1;                       /* bar level; default video black*/
    /* A2 is a property of a DEPLOYED format, not of an arbitrary bench raster,
     * so the tool reports the figure always and refuses only when asked.  The
     * enforcement point that matters is omc_uc_scale_latency() in the library,
     * which a decoder or a control plane calls before offering a conversion --
     * the same division the codec already uses between omc_validate_config()
     * and the CLI.  A ratio steeper than the aperture cap is a capability
     * limit, not a latency one, and is always refused. */
    int enforce = 0;
    int mirror = 0;      /* horizontal flip of the framed rect */
    /* colour mode */
    int sprim = OMC_CC_P_BT709, dprim = OMC_CC_P_BT709;
    int smtx = -1, dmtx = -1, trc = OMC_CC_T_GAMMA, strc = -1, dtrc = -1, fullr = 0;
    int srange = -1, drange = -1, tmap = 0, speak = 0, dpeak = 0;
    int i, f, pl;

    if (argc < 2) die("usage: up|down|scale|frame|colour -i in -o out -w W -h H [--fmt 422|444] "
            "[--depth D] [--out-w W --out-h H] "
            "[--crop-x/-y/-w/-h] [--rect-x/-y/-w/-h] [--fill V]");
    mode = argv[1];
    for (i = 2; i < argc; i++) {
        if (!strcmp(argv[i], "-i")) inp = NEXTARG();
        else if (!strcmp(argv[i], "-o")) outp = NEXTARG();
        else if (!strcmp(argv[i], "-w")) W = atoi(NEXTARG());
        else if (!strcmp(argv[i], "-h")) H = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--depth")) depth = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--fmt")) c444 = !strcmp(NEXTARG(), "444");
        else if (!strcmp(argv[i], "--frames")) frames = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--band")) band = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--no-direction")) dir = 0;
        else if (!strcmp(argv[i], "--mirror")) mirror = 1;
        else if (!strcmp(argv[i], "--out-w")) ow = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--crop-x")) cx = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--crop-y")) cy = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--crop-w")) cw = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--crop-h")) ch = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--rect-x")) rx = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--rect-y")) ry = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--rect-w")) rw = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--rect-h")) rh = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--fill")) fillv = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--fps")) fps = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--enforce-a2")) enforce = 1;
        else if (!strcmp(argv[i], "--out-h")) oh = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--src-prim")) sprim = cc_prim_arg(NEXTARG());
        else if (!strcmp(argv[i], "--dst-prim")) dprim = cc_prim_arg(NEXTARG());
        else if (!strcmp(argv[i], "--src-mtx")) smtx = cc_mtx_arg(NEXTARG());
        else if (!strcmp(argv[i], "--dst-mtx")) dmtx = cc_mtx_arg(NEXTARG());
        else if (!strcmp(argv[i], "--trc")) trc = cc_trc_arg(NEXTARG());
        else if (!strcmp(argv[i], "--src-trc")) strc = cc_trc_arg(NEXTARG());
        else if (!strcmp(argv[i], "--dst-trc")) dtrc = cc_trc_arg(NEXTARG());
        else if (!strcmp(argv[i], "--full-range")) fullr = 1;
        else if (!strcmp(argv[i], "--src-range")) srange = !strcmp(NEXTARG(), "full");
        else if (!strcmp(argv[i], "--dst-range")) drange = !strcmp(NEXTARG(), "full");
        else if (!strcmp(argv[i], "--tone-map")) tmap = 1;
        else if (!strcmp(argv[i], "--src-peak")) speak = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--dst-peak")) dpeak = atoi(NEXTARG());
        else die("bad argument");
    }
    if (!inp || !outp || W < 2 || H < 2) die("need -i -o -w -h");

    {
        omc_uc_t uc;
        int Wc = c444 ? W : W / 2;
        int up = !strcmp(mode, "up");
        int scale = !strcmp(mode, "scale");
        int frame = !strcmp(mode, "frame");
        int colour = !strcmp(mode, "colour");
        size_t small = (size_t)W * H + 2 * (size_t)Wc * H;
        size_t big = 4 * small;
        uint16_t *sm = malloc(small * 2), *bg = malloc(big * 2);
        FILE *fi = fopen(inp, "rb"), *fo = fopen(outp, "wb");
        uint16_t *sp[3], *bp[3];
        int pw[3], ph[3];

        uc.depth = (uint8_t)depth;
        uc.direction = (uint8_t)dir;
        if (!sm || !bg || !fi || !fo) die("io/alloc");
        sp[0] = sm; sp[1] = sm + (size_t)W * H; sp[2] = sp[1] + (size_t)Wc * H;
        bp[0] = bg; bp[1] = bg + (size_t)4 * W * H; bp[2] = bp[1] + (size_t)4 * Wc * H;
        pw[0] = W; pw[1] = pw[2] = Wc;
        ph[0] = ph[1] = ph[2] = H;

        if (scale) {
            /* rational (non-dyadic) conversion, e.g. 720p -> 1080p.
             * NOT reversible: a rational resampling is not a lifting step. */
            int owc = c444 ? ow : ow / 2;
            size_t osz = (size_t)ow * oh + 2 * (size_t)owc * oh;
            uint16_t *o = malloc(osz * 2);
            uint16_t *op[3];
            if (ow < 2 || oh < 2) die("scale needs --out-w and --out-h");
            {   /* A2 is a hard bar.  A DECIMATION's aperture -- and therefore
                 * its reach and its latency -- scale with the ratio, so the
                 * conversion is checked rather than assumed.  slice_h follows
                 * docs/LATENCY.md (8 below 2160p, 16 at and above it) and the
                 * frame rate defaults to 50, the slowest line rate and hence
                 * the worst case. */
                double ms = 0; int per = 0;
                /* [A5-M4-SLICEH] ONE slice-height rule, and it is the
                 * product's: 8 at 720p-class heights, 16 above (BITSTREAM 7).
                 * This tool used `H >= 2160 && H % 16 == 0`, which models
                 * 1080p at slice_h 8 -- a raster the product codes at 16 --
                 * so every 1080p figure it printed was for a configuration
                 * the encoder never emits, and it read LOW because 8-line
                 * slices have the shorter pipeline. */
                int slh = (H <= 720) ? 8 : 16;
                int rc = omc_uc_scale_latency(W, H, ow, oh, slh, fps, 1, &ms, &per);
                char msg[256];
                /* The 720p floor is a property of a DEPLOYED FORMAT, not of an
                 * arbitrary bench raster, and refusing it here unconditionally
                 * is EXACTLY the mistake this review already recorded once --
                 * the A2 guard that broke G15 by enforcing a deployment rule on
                 * a 48x24 test picture.  The enforcement point is the library
                 * (and omc_validate_config), which a decoder or a control plane
                 * consults before OFFERING a conversion.  The tool reports it,
                 * and refuses only when asked to.  The ratio refusal below is
                 * different in kind: there are no coefficients, so there is no
                 * picture to produce at any raster size. */
                if (rc == -4 && enforce)
                    die("scale: the output raster is below the 720p floor. B4 "
                        "sets the supported range as starting at 720p, so this "
                        "is a format the codec does not carry -- not a slow "
                        "conversion, an unsupported one");
                if (rc == -3)
                    die("scale: ratio unsupported (steeper than the aperture "
                        "cap, or more than 16 phases)");
                if (rc > 0 && enforce) {
                    snprintf(msg, sizeof msg,
                             "scale: %dx%d -> %dx%d at %d fps would take %.3f ms "
                             "(%d extra slice period(s) at slice_h %d); "
                             "A2 requires < 1 ms",
                             W, H, ow, oh, fps, ms, per, slh);
                    die(msg);
                }
                fprintf(stderr, "omc_uc_tool: %dx%d -> %dx%d, %d extra slice "
                        "period(s), %.3f ms total%s\n",
                        W, H, ow, oh, per, ms,
                        rc == -4 ? "  <-- NOTICE: the output raster is below "
                                   "the 720p floor B4 sets; this is a bench "
                                   "raster, not a deployable format "
                                   "(--enforce-a2 refuses it instead)"
                        : rc > 0 ? "  <-- NOTICE: this conversion is CORRECT and "
                                   "AVAILABLE but is NOT sub-1 ms; declare the "
                                   "figure above on any leg that uses it "
                                   "(--enforce-a2 refuses it instead)"
                                 : "  (A2 < 1 ms)");
            }
            if (!o) die("alloc");
            op[0] = o; op[1] = o + (size_t)ow * oh; op[2] = op[1] + (size_t)owc * oh;
            for (f = 0; f < frames; f++) {
                if (fread(sm, 2, small, fi) != small) break;
                for (pl = 0; pl < 3; pl++) {
                    int dwp = pl ? owc : ow;
                    int rc = omc_uc_scale_plane(&uc, sp[pl], pw[pl], pw[pl], ph[pl],
                                                op[pl], dwp, dwp, oh);
                    if (rc == -2) die("ratio needs more than 16 phases");
                    if (rc < 0) die("scale failed");
                }
                if (fwrite(o, 2, osz, fo) != osz) die("write");
            }
            fprintf(stderr, "omc_uc_tool: %d frame(s) scaled to %dx%d\n", f, ow, oh);
            fclose(fi); fclose(fo); free(sm); free(bg); free(o);
            return 0;
        }

        if (colour) {
            /* The matrix mixes R, G and B, so all three must exist at the same
             * site.  4:2:2 chroma does not, so it is interpolated to 4:4:4 with
             * the codec's own polyphase bank, converted, and decimated back with
             * the codec's own 2:1 decimator -- not replicated and box-averaged,
             * which would put the conversion's error budget below the
             * resampler's.  4:4:4 skips both passes entirely. */
            omc_cc_t cc;
            uint16_t *u444 = NULL, *v444 = NULL;
            int rc, noop;
            cc.depth = (uint8_t)depth;
            cc.src_full_range = (uint8_t)(srange >= 0 ? srange : fullr);
            cc.dst_full_range = (uint8_t)(drange >= 0 ? drange : fullr);
            cc.tone_map  = (uint8_t)(tmap ? OMC_CC_TM_DECLARED : OMC_CC_TM_OFF);
            cc.src_peak  = (uint16_t)speak;
            cc.dst_peak  = (uint16_t)dpeak;
            cc.prim_custom = 0;
            cc.src_prim = (uint8_t)sprim; cc.dst_prim = (uint8_t)dprim;
            /* --trc declares the transfer; --src-trc/--dst-trc exist so the
             * refusal is REACHABLE from the CLI rather than being a claim only
             * the library can make. */
            cc.src_trc = (uint8_t)(strc >= 0 ? strc : trc);
            cc.dst_trc = (uint8_t)(dtrc >= 0 ? dtrc : trc);
            cc.src_mtx = (uint8_t)(smtx >= 0 ? smtx :
                                   (sprim == OMC_CC_P_BT2020 ? OMC_CC_M_BT2020
                                                             : OMC_CC_M_BT709));
            cc.dst_mtx = (uint8_t)(dmtx >= 0 ? dmtx :
                                   (dprim == OMC_CC_P_BT2020 ? OMC_CC_M_BT2020
                                                             : OMC_CC_M_BT709));
            rc = omc_cc_validate(&cc);
            if (rc == -2)
                die("colour: a transfer change is a tone map.  It is OFF by "
                    "default and must be asked for: add --tone-map with "
                    "--src-peak and --dst-peak in nits");
            if (rc == -3)
                die("colour: no published curve for that (transfer, peak) tuple. "
                    "Declared: SDR100 -> HLG1000 (BT.2408 reference-white alignment); "
                    "HLG1000 -> HLG1000 container identity.  PQ (ST 2084) is not carried.");
            if (rc)
                die("colour: unsupported conversion (primaries must be 709 or "
                    "2020; matrix 709, 601 or 2020; depth 8..12)");
            /* A no-op conversion must not go near the chroma resamplers: the
             * 4:2:2 detour is not itself lossless, so a pass-through leg would
             * soften the chroma for nothing.  omc_cc_convert() already refuses
             * to touch the samples; the tool must not either. */
            noop = (cc.src_prim == cc.dst_prim && cc.src_mtx == cc.dst_mtx &&
                    cc.src_trc == cc.dst_trc &&
                    cc.src_full_range == cc.dst_full_range && !cc.tone_map);
            if (!c444 && !noop) {
                u444 = malloc((size_t)W * H * 2);
                v444 = malloc((size_t)W * H * 2);
                if (!u444 || !v444) die("alloc");
            }
            for (f = 0; f < frames; f++) {
                if (fread(sm, 2, small, fi) != small) break;
                if (noop) {
                    /* nothing to do -- and doing nothing is the correct answer */
                } else if (c444) {
                    if (omc_cc_convert(&cc, sp[0], W, sp[1], W, sp[2], W, W, H))
                        die("colour: conversion failed");
                } else {
                    /* CO-SITED, not centre-aligned: in 4:2:2 chroma sample k
                     * belongs to luma sample 2k, so re-centring the chroma grid
                     * would put the colour a quarter sample off its luma. */
                    if (omc_uc_scale_plane_sited(&uc, sp[1], Wc, Wc, H, u444, W, W, H, OMC_SITE_COSITED) < 0 ||
                        omc_uc_scale_plane_sited(&uc, sp[2], Wc, Wc, H, v444, W, W, H, OMC_SITE_COSITED) < 0)
                        die("colour: chroma upsample failed");
                    if (omc_cc_convert(&cc, sp[0], W, u444, W, v444, W, W, H))
                        die("colour: conversion failed");
                    if (omc_uc_scale_plane_sited(&uc, u444, W, W, H, sp[1], Wc, Wc, H, OMC_SITE_COSITED) < 0 ||
                        omc_uc_scale_plane_sited(&uc, v444, W, W, H, sp[2], Wc, Wc, H, OMC_SITE_COSITED) < 0)
                        die("colour: chroma decimate failed");
                }
                if (fwrite(sm, 2, small, fo) != small) die("write");
            }
            fprintf(stderr, "omc_uc_tool: %d frame(s) converted, primaries %d -> "
                    "%d, matrix %d -> %d, transfer %d -> %d, range %s -> %s%s%s\n",
                    f, sprim, dprim, cc.src_mtx, cc.dst_mtx, cc.src_trc, cc.dst_trc,
                    cc.src_full_range ? "full" : "limited",
                    cc.dst_full_range ? "full" : "limited",
                    tmap ? " (TONE MAPPED, declared peaks)" : "",
                    noop ? " (identity: picture untouched)"
                         : c444 ? "" : " (4:2:2 via 4:4:4)");
            fclose(fi); fclose(fo); free(sm); free(bg); free(u444); free(v444);
            return 0;
        }

        if (frame) {
            /* Aspect framing: scale a source CROP into a destination RECT and
             * fill the rest with `fill`.  Pillarbox, letterbox, 14:9, centre
             * cut.  Without this the primitive was library-only and therefore
             * unexercisable from the shipped tools -- the same defect this
             * review records against uc_ratio, which had no encoder flag. */
            int owc = c444 ? ow : ow / 2;
            size_t osz = (size_t)ow * oh + 2 * (size_t)owc * oh;
            uint16_t *o = malloc(osz * 2);
            uint16_t *op[3];
            int fv;
            if (ow < 2 || oh < 2) die("frame needs --out-w and --out-h");
            if (!cw) cw = W;
            if (!ch) ch = H;
            if (!rw) rw = ow;
            if (!rh) rh = oh;
            fv = fillv >= 0 ? fillv : (16 << (depth - 8));   /* video black */
            if (!o) die("alloc");
            op[0] = o; op[1] = o + (size_t)ow * oh; op[2] = op[1] + (size_t)owc * oh;
            for (f = 0; f < frames; f++) {
                if (fread(sm, 2, small, fi) != small) break;
                for (pl = 0; pl < 3; pl++) {
                    int sub = !c444 && pl > 0;
                    int dwp = pl ? owc : ow;
                    int q = sub ? 2 : 1;
                    if (omc_uc_frame_plane(&uc, sp[pl], pw[pl], pw[pl], ph[pl],
                                           cx / q, cy, cw / q, ch,
                                           op[pl], dwp, dwp, oh,
                                           rx / q, ry, rw / q, rh,
                                           (uint16_t)(pl ? (1 << (depth - 1)) : fv),
                                           mirror) < 0)
                        die("frame failed (check the crop/rect geometry and that the "
                            "resulting ratio is in the declared set)");
                }
                if (fwrite(o, 2, osz, fo) != osz) die("write");
            }
            fprintf(stderr, "omc_uc_tool: %d frame(s) framed: crop %dx%d+%d+%d -> "
                    "rect %dx%d+%d+%d in %dx%d\n", f, cw, ch, cx, cy,
                    rw, rh, rx, ry, ow, oh);
            fclose(fi); fclose(fo); free(sm); free(bg); free(o);
            return 0;
        }

        for (f = 0; f < frames; f++) {
            if (up) {
                if (fread(sm, 2, small, fi) != small) break;
                for (pl = 0; pl < 3; pl++) {
                    int rows = 2 * ph[pl], r0 = 0;
                    if (band <= 0) {
                        if (omc_uc_up_plane(&uc, sp[pl], pw[pl], pw[pl], ph[pl],
                                            bp[pl], 2 * pw[pl], 0, rows) < 0)
                            die("up failed");
                    } else {
                        for (r0 = 0; r0 < rows; r0 += band) {
                            int r1 = r0 + band > rows ? rows : r0 + band;
                            if (omc_uc_up_plane(&uc, sp[pl], pw[pl], pw[pl], ph[pl],
                                                bp[pl], 2 * pw[pl], r0, r1) < 0)
                                die("up failed");
                        }
                    }
                }
                if (fwrite(bg, 2, big, fo) != big) die("write");
            } else {
                if (fread(bg, 2, big, fi) != big) break;
                for (pl = 0; pl < 3; pl++) {
                    /* The inverse MUST use the identical predictor, so the
                     * plane geometry has to match the forward call exactly or
                     * the round trip stops being exact. */
                    if (omc_uc_down_plane(&uc, bp[pl], 2 * pw[pl], pw[pl], ph[pl],
                                          sp[pl], pw[pl]) < 0)
                        die("down failed");
                }
                if (fwrite(sm, 2, small, fo) != small) die("write");
            }
        }
        fprintf(stderr, "omc_uc_tool: %d frame(s) %s\n", f, up ? "upconverted" : "downconverted");
        fclose(fi); fclose(fo); free(sm); free(bg);
    }
    return 0;
}
