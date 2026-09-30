/* omc_enc - OMC-1 encoder CLI (T5).
 * Input: raw planar Y'CbCr, little-endian 16-bit container (8/10/12-bit
 * levels), 4:2:2 or 4:4:4 — either a plain master (values in [0, 2^depth))
 * or, with --cdr-in, a coded-domain raw (CDR) as written by omc_dec --cdr:
 * biased by OMC_PIX_BIAS, unclipped, at CODED geometry (padded).  CDR is the
 * T5 generation-chain interchange format; re-encoding a CDR decode is
 * byte-exact through unlimited generations.  Output: .omc bitstream.
 * Optional --recon writes the encoder-side reconstruction in CDR form.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "omc1.h"
#include "omc_uc.h"   /* [A5-M3-RATIONAL] omc_uc_scale_latency_ex */

/* [V536] bounds-checked option value (external adversarial review of v5.3.5, section 7): every
 * value-taking flag used argv[++i]; as the LAST token that is argv[argc] == NULL and the
 * following atoi()/strcmp() dereferenced it -- a segfault in all nine CLIs on a trailing
 * option.  NEXTARG() refuses with a usage error and exit status 1 instead. */
#define NEXTARG() ((i + 1 < argc) ? argv[++i] : \
    (fprintf(stderr, "%s: option %s needs a value\n", argv[0], argv[i]), exit(1), (char *)0))

extern int omc_xsl;   /* set by omc_global_init from OMC_XSL; --xsl overrides */

/* Assemble the padded, coded-geometry planes from a true-dimension input frame
 * (edge replication for the pad, optional RCT).  Factored out of the frame loop
 * so the --xsl auto probe can build frame 0 the same way the encoder will. */
static void assemble(uint16_t *pix, const uint16_t *inbuf, int W, int H, int Wc,
                     int iW, int iH, int iWc, int mono, int rgb,
                     int32_t mid_c, int32_t yoff, size_t ysz, size_t csz)
{
    const uint16_t *sp[3];
    sp[0] = inbuf;
    sp[1] = mono ? NULL : inbuf + (size_t)iW * iH;
    sp[2] = mono ? NULL : inbuf + (size_t)iW * iH + (size_t)iWc * iH;
    for (int p = 0; p < 3; p++) {
        int pw = p == 0 ? W : Wc;
        int ipw = p == 0 ? iW : iWc;
        uint16_t *dst = pix + (p == 0 ? 0 : (p == 1 ? ysz : ysz + csz));
        for (int r = 0; r < H; r++) {
            int sr = r < iH ? r : iH - 1;
            for (int x = 0; x < pw; x++) {
                int sx = x < ipw ? x : (ipw ? ipw - 1 : 0);
                uint16_t v;
                if (mono && p > 0) v = (uint16_t)mid_c;
                else if (rgb) {
                    size_t si = (size_t)sr * iW + sx;
                    int32_t R = sp[0][si], G = sp[1][si], B = sp[2][si];
                    int32_t Y = (R + 2 * G + B) >> 2;
                    if (p == 0) v = (uint16_t)(Y + yoff);
                    else if (p == 1) v = (uint16_t)(B - G + mid_c);
                    else v = (uint16_t)(R - G + mid_c);
                } else
                    v = sp[p][(size_t)sr * ipw + sx];
                /* T5: the codec's pixel domain is biased (omc1.h) */
                dst[(size_t)r * pw + x] = (uint16_t)(v + OMC_PIX_BIAS);
            }
        }
    }
}

static void die(const char *m) { fprintf(stderr, "omc_enc: %s\n", m); exit(1); }

int main(int argc, char **argv)
{
    const char *inp = NULL, *outp = NULL, *reconp = NULL;
    int rgb = 0, mono = 0, verbose_ll = 0, lossless_frames = 0, bpp_set = 0;
    int dispw_arg = 0, disph_arg = 0;   /* --display-w/--display-h (CDR re-encode) */
    int start_frame = 0;                /* --start-frame: mod-256 phase to resume */
    int dbg_oldpads = 0;
    int out_w = 0, out_h = 0;   /* [A5-M3-RATIONAL] declared output raster */
    int gamut_explicit = 0;   /* the flag was given on the command line */
    int64_t gamut_oob = 0;    /* what the mode could not clear; drives the
                               * exit status, see the end of main */                /* TEST ONLY: pre-minor-11 pad behaviour */
    int gamut_strict = omc_enc_gamut_default();   /* [V537-BUDGET] ON BY DEFAULT, the LIBRARY's budget -- see omc_enc_create.
                                           --gamut-strict 0 turns it off.
                                           --gamut-strict [passes]: keep the
                                           committed picture inside legal range
                                           so a BASEBAND chain is exact */
    int cdr_in = 0;     /* input is coded-domain raw (biased, coded geometry) */
    /* [S3-REFRESH] test stand-in for the control plane: "f:s[-s2],..." asks
     * for slices s..s2 to be refreshed in frame f (before that frame is
     * encoded).  "f:*" asks for every slice.  Repeatable via commas. */
    const char *refresh_req_list = NULL;
    omc_config_t cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.fill_grain = 1;   /* sect.65: grain fill defaults ON; --no-fill disables */
    cfg.bitdepth = 10;
    cfg.chroma = OMC_CF_422;
    cfg.slice_h = 0; /* 0 = auto: 16 if height allows, else 8 */
    /* [A5-M2-A2STRICT] A2 admits no exceptions from the 720p floor up, so the
     * product build ENFORCES the bar rather than reporting it.  Before this,
     * a2_strict defaulted to 0 and four configurations reachable from this very
     * CLI encoded happily at 1.19-2.15 ms: --slice-h 32 (1.793 ms at 720p50),
     * --slice-h 16 --uc-ratio 1 (1.194), --slice-h 16 --uc-ratio 2 (1.306) and
     * --slice-h 32 --uc-ratio 2 (2.147).  A bar that warns and encodes anyway is
     * not a bar.  --a2-permissive restores the old reporting behaviour for a
     * bench leg that has been told the figure and accepts it.
     *
     * ARMED BELOW, once the raster is known, and ONLY for a raster that meets
     * B4's 720p floor.  A2 binds "from the 720p floor upward"; a 448x256 bench
     * clip has a slow line rate and models at 1.406 ms, and refusing it would
     * be "EXACTLY the mistake this review already recorded once -- the A2 guard
     * that broke G15 by enforcing a deployment rule on a 48x24 test picture"
     * (tools/omc_uc_tool.c).  My first cut of this change did precisely that
     * and the byte-identity gate caught it on cf_gfx. */
    int a2_want = 1;
    cfg.fps_num = 50; cfg.fps_den = 1;
    cfg.color = (omc_colorimetry_t){1, 1, 1, 0}; /* BT.709 SDR limited */
    double bpp = 2.0;
    int nframes = -1;

    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-i")) inp = NEXTARG();
        else if (!strcmp(argv[i], "-o")) outp = NEXTARG();
        else if (!strcmp(argv[i], "--uc-ratio")) cfg.uc_ratio = (uint8_t)atoi(NEXTARG());
        else if (!strcmp(argv[i], "--recon")) reconp = NEXTARG();
        else if (!strcmp(argv[i], "-w")) cfg.width = (uint16_t)atoi(NEXTARG());
        else if (!strcmp(argv[i], "-h")) cfg.height = (uint16_t)atoi(NEXTARG());
        else if (!strcmp(argv[i], "--depth")) cfg.bitdepth = (uint8_t)atoi(NEXTARG());
        else if (!strcmp(argv[i], "--fmt")) cfg.chroma = atoi(NEXTARG()) == 444 ? OMC_CF_444 : OMC_CF_422;
        else if (!strcmp(argv[i], "--slice-h")) cfg.slice_h = (uint8_t)atoi(NEXTARG());
        else if (!strcmp(argv[i], "--bpp")) { bpp = atof(NEXTARG()); bpp_set = 1; }
        else if (!strcmp(argv[i], "--fps")) cfg.fps_num = (uint16_t)atoi(NEXTARG());
        else if (!strcmp(argv[i], "-n")) nframes = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--primaries")) cfg.color.primaries = (uint8_t)atoi(NEXTARG());
        else if (!strcmp(argv[i], "--transfer")) cfg.color.transfer = (uint8_t)atoi(NEXTARG());
        else if (!strcmp(argv[i], "--matrix")) cfg.color.matrix = (uint8_t)atoi(NEXTARG());
        else if (!strcmp(argv[i], "--tune")) cfg.tune_vmaf = !strcmp(NEXTARG(), "vmaf");
        else if (!strcmp(argv[i], "--refresh")) {
            /* [S3-REFRESH] period in frames, or "none": no scheduled wave */
            const char *rv = NEXTARG();
            cfg.refresh_r = !strcmp(rv, "none") ? OMC_REFRESH_NONE
                                                : (uint8_t)atoi(rv);
        }
        else if (!strcmp(argv[i], "--refresh-req")) refresh_req_list = NEXTARG();
        else if (!strcmp(argv[i], "--no-fill")) { cfg.fill_grain = 0; cfg.fill_grain_explicit = 1; }
        else if (!strcmp(argv[i], "--fill")) { cfg.fill_grain = 1; cfg.fill_grain_explicit = 1; }
        else if (!strcmp(argv[i], "--cdr-in")) cdr_in = 1;
        else if (!strcmp(argv[i], "--no-deadzone")) cfg.no_deadzone = 1;
        else if (!strcmp(argv[i], "--grain-replace")) cfg.grain_replace = 1;
        else if (!strcmp(argv[i], "--grain-corr")) cfg.grain_corr = 1;
        else if (!strcmp(argv[i], "--fill-static")) { /* minor 12: the
            frame-independent fill tile is the ONLY behaviour, so this flag
            is accepted and does nothing.  Kept so command lines written
            against the minor-11 build still run. */ }
        else if (!strcmp(argv[i], "--debug-oldpads")) dbg_oldpads = 1;
        else if (!strcmp(argv[i], "--a2-permissive")) a2_want = 0;  /* [A5-M2-A2STRICT] */
        else if (!strcmp(argv[i], "--out-w")) out_w = atoi(NEXTARG());   /* [A5-M3-RATIONAL] */
        else if (!strcmp(argv[i], "--out-h")) out_h = atoi(NEXTARG());   /* [A5-M3-RATIONAL] */
        else if (!strcmp(argv[i], "--no-gamut-strict")) {
            /* Alias for --gamut-strict 0.  Kept because it reads as the
             * negation of a default that is now ON, which is what an operator
             * declining the baseband guarantee is actually expressing. */
            gamut_strict = 0;
        }
        else if (!strcmp(argv[i], "--gamut-strict")) {
            /* optional numeric argument = per-slice repair budget; 0 turns the
             * mode off.  Passing the flag at all counts as an EXPLICIT request,
             * which is what makes the --cdr-in contradiction below an error
             * rather than a silent stand-down. */
            if (i + 1 < argc && argv[i + 1][0] >= '0' && argv[i + 1][0] <= '9')
                gamut_strict = atoi(NEXTARG());
            else gamut_strict = omc_enc_gamut_default();   /* [V537-BUDGET] */
            if (gamut_strict < 0) gamut_strict = 0;
            gamut_explicit = 1;
        }
        else if (!strcmp(argv[i], "--start-frame")) start_frame = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--display-w")) dispw_arg = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--display-h")) disph_arg = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--rgb")) rgb = 1;   /* planar R,G,B in; RCT applied */
        else if (!strcmp(argv[i], "--mono")) mono = 1; /* single plane in; flat chroma */
        else if (!strcmp(argv[i], "--lossless")) { cfg.lossless_pref = 1; cfg.fill_grain = 0; }
        else if (!strcmp(argv[i], "--lossless-verbose")) { cfg.lossless_pref = 1; cfg.fill_grain = 0; verbose_ll = 1; }
        else die("unknown arg");
    }
    if (!inp || !outp || !cfg.width || !cfg.height)
        die("usage: -i in.yuv -o out.omc -w W -h H [--fmt 422|444] [--depth 10]\n"
            "       [--bpp 2.0] [--slice-h 8|16|32] [--uc-ratio 0|1|2]\n"
            "       [--recon rec.cdr] [--cdr-in] [--fill|--no-fill] [--lossless]\n"
            "       [--refresh R|none] [--refresh-req f:s[-s2],...]\n"
            "\n"
            "  --refresh    scheduled intra-refresh period in frames (default 8;\n"
            "               1 = stateless); 'none' = no scheduled wave, slices are\n"
            "               refreshed only on request (control plane; a return path\n"
            "               is required -- multicast/join links keep a period).\n"
            "  --refresh-req  test stand-in for the control plane: request slices\n"
            "               s..s2 (or '*') to be intra-coded in frame f.\n"
            "\n"
            "  --cdr-in     the input is a coded-domain raw (CDR) as written by\n"
            "               omc_dec --cdr: biased by 2048, unclipped, at CODED\n"
            "               geometry.  This is the T5 generation-chain format:\n"
            "               re-encoding a CDR decode reproduces it byte-exactly,\n"
            "               through unlimited generations.  -w/-h give the CODED\n"
            "               dims here (as reported by omc_dec).\n"
            "\n"
            "  --gamut-strict [N]  ON BY DEFAULT (N = the library budget, 13 in this release).  Keeps the committed\n"
            "               picture inside the legal range so an ORDINARY\n"
            "               (legal-range, cropped) baseband hand-off is exact\n"
            "               through unlimited generations, not only the CDR one.\n"
            "               N is the per-slice repair budget, max 16; N = 0 turns\n"
            "               the mode off.  It is on by default because it is not\n"
            "               a content-dependent choice: a broadcast chain cuts\n"
            "               between content types in seconds and nobody is at a\n"
            "               console deciding.  Encoder-side only: the bitstream,\n"
            "               the decoder and the generation lock are unchanged.\n"
            "               Byte-identical to having it off on content that never\n"
            "               reaches the rails, stands down entirely on --cdr-in,\n"
            "               and inert from generation 2 onwards.  On a fixed slice\n"
            "               period, LOWER N rather than switching it off: what it\n"
            "               cannot finish it still reports -- and omc_enc then\n"
            "               EXITS 2, so an automated pipeline cannot silently\n"
            "               lose baseband exactness. Exit 0 means it delivered.\n"
            "\n"
            "  T5 notes: the temporal engine is rebuilt (motion derived from\n"
            "  reconstruction history; frame-buffer reference), the cross-slice\n"
            "  boundary blend (XSL) is always on and exactly reversible, and the\n"
            "  in-loop temporal filter of v4.8 is REMOVED.  Streams are minor 10.");
    if (rgb && mono) die("--rgb and --mono are mutually exclusive");
    if (cdr_in && (rgb || mono)) die("--cdr-in carries coded planes; --rgb/--mono do not apply");
    /* A CDR is at CODED geometry and carries no display dims, so a padded
     * raster cannot be inferred from it.  Guessing wrong does not fail loudly:
     * it silently drifts (the last slice codes its pad rows as content and
     * never locks to the previous generation's picture).  For a contract whose
     * whole value is exactness, an explicit statement is required rather than
     * a default -- pass the display height, or pass the coded height to assert
     * that the raster is unpadded.  omc_dec prints the exact flags. */
    if (cdr_in && !disph_arg)
        die("--cdr-in requires --display-h (and --display-w): a CDR is at CODED "
            "geometry and cannot describe a padded raster. Pass the display "
            "dims omc_dec reports; if the raster is unpadded pass the coded "
            "dims. Guessing silently drifts at generation 2.");
    if (cfg.lossless_pref && !bpp_set) {
        /* [A5-M9-LLRATE] the flat 16.0 here was the REAL blocker on lossless,
         * not only the validator ceiling: 16 bpp is below the raw sample rate
         * of half the formats we support, so --lossless silently produced a
         * lossy stream.  MEASURED at the old default, 2 frames of dng 1080p:
         *   4:2:2  8-bit (raw 16)  2/2 bit-exact      4:4:4  8-bit (raw 24)  2/2
         *   4:2:2 10-bit (raw 20)  2/2                4:4:4 10-bit (raw 30)  0/2
         *   4:2:2 12-bit (raw 24)  0/2                4:4:4 12-bit (raw 36)  0/2
         * THREE of six formats could not reach lossless at all.  Minimum rate
         * that does work, measured: 22, 24 and 32 bpp respectively -- i.e.
         * 0.80-0.92 of the raw rate, so the raw rate is always sufficient and
         * is the only principled choice (a codec can store raw at worst).
         *
         * max(16, .) so no format that already worked gets a LOWER budget.
         * NOTE FOR REVIEW: this does RAISE the default budget for 4:2:2 10-bit
         * (16 -> 20) and 4:4:4 8-bit (16 -> 24), which already reached
         * bit-exactness at 16.  Exact CBR pads to the budget, so their lossless
         * streams get larger.  That is a deliberate trade -- a --lossless that
         * silently is not lossless is worse than a larger file -- but it is a
         * default-output-size change and belongs to the coordinator, not me. */
        int spp_ll = (cfg.chroma == OMC_CF_444) ? 3 : 2;
        double raw_ll = (double)spp_ll * (double)cfg.bitdepth;
        bpp = raw_ll > 16.0 ? raw_ll : 16.0;
    }
    int comp_depth = cfg.bitdepth; /* true component depth of the input */
    if (rgb) {
        cfg.chroma = OMC_CF_444; cfg.rct = 1;
        if (comp_depth > 10) die("--rgb supports 8/10-bit components only");
        cfg.bitdepth = (uint8_t)(comp_depth + 2); /* container promotion */
    }
    if (mono) cfg.chroma = OMC_CF_422;
    /* v4.2 pad-and-crop: -w/-h are TRUE picture dims; code at the next
     * compliant size, record display dims, pad by edge replication. */
    uint16_t dispW = cfg.width, dispH = cfg.height;
    {
        int wal = cfg.chroma == OMC_CF_422 ? 64 : 32;
        uint16_t cw = (uint16_t)((cfg.width + wal - 1) / wal * wal);
        /* slice_h DEFAULTS TO 16 (--slice-h overrides).  The one exception
         * is a hard one: 720p-class heights MUST use 8, because 16-line
         * slices put 720p50 at ~1.17 ms and A2 is not negotiable
         * (docs/LATENCY.md, BITSTREAM sec 7).  Heights that do not divide by
         * 16 -- 1080 above all -- are coded at the next multiple and cropped
         * on output by the existing pad-and-crop path (BITSTREAM sec 8); the
         * old rule dropped those to 8 instead, which cost ~10 % of rate at
         * 1.0 bpp and ~16 % at 0.5 for an arithmetic reason. */
        if (!cfg.slice_h) cfg.slice_h = (cfg.height <= 720) ? 8 : 16;
        uint16_t chh = (uint16_t)((cfg.height + cfg.slice_h - 1) / cfg.slice_h * cfg.slice_h);
        if (cdr_in) {
            /* CDR input is already at coded geometry; -w/-h must match it */
            if (cw != cfg.width || chh != cfg.height)
                die("--cdr-in: -w/-h must be the CODED dims (already aligned)");
        } else if (cw != cfg.width || chh != cfg.height) {
            cfg.display_width = dispW; cfg.display_height = dispH;
            cfg.width = cw; cfg.height = chh;
        }
        /* Explicit display geometry.  REQUIRED to re-encode a CDR of a padded
         * raster (1080 coded as 1088): the CDR is at coded geometry, so the
         * true raster cannot be inferred from it, and the pad-neutralization
         * rule of minor 11 is keyed off it.  omc_dec prints the value to pass. */
        if (dispw_arg) cfg.display_width = (uint16_t)dispw_arg;
        if (disph_arg) cfg.display_height = (uint16_t)disph_arg;
        if (cfg.display_height > cfg.height || cfg.display_width > cfg.width)
            die("--display-w/-h must not exceed the coded dims");
    }
    int nsl = cfg.height / cfg.slice_h;
    double bits_frame = bpp * cfg.width * cfg.height;
    cfg.bits_per_slice = nsl ? (uint32_t)((int64_t)(bits_frame / nsl) / 8 * 8) : 0;
    /* [A5-M2-A2STRICT] arm the bar only for a DEPLOYED format (B4's 720p
     * floor).  Below it the A2 figure is reported, never enforced. */
    cfg.a2_strict = (a2_want && omc_uc_format_supported(cfg.width, dispH)) ? 1 : 0;
    {
        char verr[160];
        if (omc_validate_config(&cfg, verr, sizeof verr) != 0) die(verr);
    }
    /* A2 is a hard product mandate: sub-1 ms end to end INCLUDING any output
     * resolution conversion.  The validator only REFUSES when a2_strict is
     * set, so an over-budget configuration used to encode silently.  Report it
     * always, with the figure, so nobody ships a leg that breaches the bar
     * without having been told.  slice_h 32 is the usual cause below 2160p:
     * it costs 32 line periods of slice assembly, which at 720p50 is 1.79 ms
     * before any conversion, and at 1080p50 1.21 ms. */
    {
        double lat_ms = 0.0; int lat_per = 0;
        int over = omc_config_latency(&cfg, &lat_ms, &lat_per);
        /* [A5-M3-RATIONAL] omc_config_latency() only knows cfg.uc_ratio, i.e.
         * the DYADIC 2x/4x path.  The rational scaler has its own checker,
         * omc_uc_scale_latency_ex(), and until now NO product code path called
         * it -- only omc_uc_tool, the tests and a probe.  So a leg that will be
         * rationally rescaled (720p50 -> 1080p50 is 1.139 ms at slice_h 16) was
         * not covered by the encoder's A2 check at all.  If the caller declares
         * the output raster, check it. */
        if (out_w > 0 && out_h > 0 &&
            (out_w != (int)cfg.width || out_h != (int)dispH)) {
            double rms = 0.0; int rper = 0;
            int rrc = omc_uc_scale_latency_ex((int)cfg.width, dispH, out_w, out_h,
                                              cfg.slice_h, cfg.fps_num, cfg.fps_den,
                                              cfg.uc_out_batched, &rms, &rper);
            if (rrc == -4)
                fprintf(stderr, "omc_enc: WARNING: declared output %dx%d is below "
                        "the 720p floor (B4)\n", out_w, out_h);
            else if (rrc < 0)
                fprintf(stderr, "omc_enc: WARNING: declared output %dx%d is not a "
                        "supported conversion ratio\n", out_w, out_h);
            else if (rms >= 1.0) {
                if (cfg.a2_strict) {
                    char m3[240];
                    snprintf(m3, sizeof m3,
                             "the declared output conversion %ux%d -> %dx%d would "
                             "take %.3f ms total, over the 1 ms A2 bar; run at "
                             "--slice-h 8, change the output raster, or pass "
                             "--a2-permissive",
                             cfg.width, dispH, out_w, out_h, rms);
                    die(m3);
                }
                fprintf(stderr, "omc_enc: WARNING A2: the declared output "
                        "conversion %ux%d -> %dx%d takes %.3f ms total\n",
                        cfg.width, dispH, out_w, out_h, rms);
            } else
                fprintf(stderr, "omc_enc: declared output conversion %ux%d -> "
                        "%dx%d: %.3f ms total, within the A2 bar\n",
                        cfg.width, dispH, out_w, out_h, rms);
        }
        if (over > 0)
            fprintf(stderr, "omc_enc: WARNING A2: this configuration takes "
                    "%.3f ms (slice_h %u at %ux%u@%u%s) -- the mandate is "
                    "under 1 ms including output conversion. slice_h 32 is "
                    "intended for 2160p and 4320p only.\n",
                    lat_ms, cfg.slice_h, cfg.width, cfg.height, cfg.fps_num,
                    cfg.uc_ratio ? ", with conversion" : ", no conversion");
    }

    int W = cfg.width, H = cfg.height, Wc = omc_chroma_width(&cfg);
    size_t ysz = (size_t)W * H, csz = (size_t)Wc * H;
    size_t frame_words = ysz + 2 * csz;
    uint16_t *pix = malloc(frame_words * 2);
    /* input geometry (true dims, pre-pad; mono reads 1 plane, rgb reads 3
     * full; CDR reads the coded planes verbatim) */
    int iW = cdr_in ? W : dispW, iH = cdr_in ? H : dispH;
    int iWc = mono ? 0 : (rgb ? iW : (cdr_in ? Wc
                       : (cfg.chroma == OMC_CF_422 ? (iW + 1) / 2 : iW)));
    size_t in_words = (size_t)iW * iH + 2 * (size_t)iWc * iH;
    uint16_t *inbuf = malloc(in_words * 2);
    int32_t mid_c = 1 << (cfg.bitdepth - 1);           /* container midpoint */
    int32_t yoff = mid_c - (1 << (comp_depth - 1));    /* RCT plane-0 offset */
    /* The reconstruction buffer is allocated ALWAYS: the encoder's gamut
     * report (baseband-safe verdict) is measured on the emitted picture, so
     * it needs somewhere to emit.  --recon only decides whether it is also
     * written to a file. */
    uint16_t *rec = malloc(frame_words * 2);
    size_t slice_bytes = cfg.bits_per_slice / 8;
    uint8_t *bs = malloc(slice_bytes * (size_t)nsl);

    FILE *fi = fopen(inp, "rb");
    if (!fi) die("open input");
    {   /* raw-input guard: the encoder ingests uncompressed planar frames
         * only (C7). Refuse known container signatures loudly instead of
         * encoding container bytes as pixels, and warn when the file size
         * is not a whole number of frames (geometry mismatch). */
        uint8_t sig[12] = {0};
        size_t got = fread(sig, 1, 12, fi);
        if (got == 12 &&
            (!memcmp(sig + 4, "ftyp", 4) || !memcmp(sig + 4, "moov", 4) ||
             !memcmp(sig + 4, "mdat", 4) || !memcmp(sig + 4, "wide", 4) ||
             !memcmp(sig, "\x06\x0e\x2b\x34", 4) ||
             !memcmp(sig, "\x1a\x45\xdf\xa3", 4) ||
             !memcmp(sig, "RIFF", 4)))
            die("input is a compressed container (MOV/MP4/MXF/MKV/AVI), not "
                "raw video - decode upstream first, e.g.\n  ffmpeg -i in.mov "
                "-f rawvideo -pix_fmt yuv422p10le out.yuv");
        if (got == 12 && (!memcmp(sig, "1CMO", 4) || !memcmp(sig, "OMC1", 4)))
            die("input is an OMC bitstream, not raw video - decode it first:"
                "\n  omc_dec -i in.omc -o out.yuv");
        fseek(fi, 0, SEEK_END);
        long long fsz = ftell(fi);
        fseek(fi, 0, SEEK_SET);
        long long fbytes = (long long)in_words * 2;
        if (fsz > 0 && (fsz % fbytes) != 0)
            fprintf(stderr, "omc_enc: WARNING: input size %lld bytes is not a "
                    "whole number of %lld-byte frames - check -w/-h/--fmt/"
                    "--depth against the source geometry\n", fsz, fbytes);
    }
    FILE *fo = fopen(outp, "wb");
    if (!fo) die("open output");
    FILE *fr = reconp ? fopen(reconp, "wb") : NULL;

    uint8_t shdr[OMC_STREAM_HDR_BYTES];
    omc_global_init();
    /* T5: tf_mode does not exist (removed with the old temporal engine) and
     * XSL is always on — nothing to probe, nothing to signal beyond the
     * minor.  uc_ratio remains the encoder's RECOMMENDATION to the output
     * port (output-stage only; orthogonal to the coding loop). */
    cfg.tf_mode = 0;
    omc_write_stream_header(&cfg, shdr);
    fwrite(shdr, 1, OMC_STREAM_HDR_BYTES, fo);

    omc_enc_t *enc = omc_enc_create(&cfg);
    if (enc && cdr_in) omc_enc_set_cdr_input(enc, 1);
    if (cdr_in) {
        /* Not a preference -- a contract.  A CDR is a committed picture: it is
         * allowed to sit outside the legal range and must be re-encoded
         * verbatim, and the CDR chain is exact without any help from this mode.
         * Repairing it would break the one guarantee that holds
         * unconditionally.
         *
         * Since the mode is now ON BY DEFAULT, --cdr-in STANDS IT DOWN rather
         * than failing: a default is not a request, and an operator who asks
         * for CDR input has said everything needed.  A default that turned a
         * working command line into an error would be the same operator burden
         * this mode exists to remove.  An EXPLICIT --gamut-strict alongside
         * --cdr-in is still refused, because that is a contradiction the
         * operator typed and should see. */
        if (gamut_explicit && gamut_strict)
            die("--gamut-strict is a BASEBAND-input policy and must not be "
                "combined with --cdr-in: a committed picture is reproduced "
                "verbatim, and the CDR chain is already exact through "
                "unlimited generations");
        gamut_strict = 0;
    }
    /* The flag wins; failing that the environment; failing that the default.
     * Working this out HERE rather than letting the library and the tool each
     * apply their own default is what keeps the reported figure equal to the
     * figure actually in force -- an earlier version of this had the tool's
     * default silently beat OMC_GAMUT_STRICT, so the variable stopped being
     * able to turn the mode off while the report still said it was on. */
    if (!gamut_explicit) {
        const char *gs = getenv("OMC_GAMUT_STRICT");
        if (gs) gamut_strict = atoi(gs);
    }
    if (gamut_strict < 0) gamut_strict = 0;
    omc_enc_set_gamut_strict(enc, gamut_strict);
    if (dbg_oldpads && enc) {
        omc_enc_debug_oldpads(enc, 1);
        fprintf(stderr, "omc_enc: WARNING --debug-oldpads: pad neutralization "
                "DISABLED; this stream is NOT minor-11 conforming (test hook "
                "for the pad gate only)\n");
    }
    omc_frame_t fin = {{pix, pix + ysz, pix + ysz + csz}, {W, Wc, Wc}};
    omc_frame_t frec = {{rec, rec ? rec + ysz : NULL, rec ? rec + ysz + csz : NULL}, {W, Wc, Wc}};

    /* Frame phase.  The refresh wave ((fidx8 % R) == (slice % R)) and the fill
     * tile animation are both functions of frame_idx & 255 and of nothing else,
     * so re-encoding a decode exactly requires resuming that phase.  A whole-clip
     * re-encode gets it for free (both runs start at 0); a MID-STREAM joiner
     * reads fidx8 out of any slice header (omc_dec prints it) and passes it
     * here.  Because both consumers are mod 256 and fidx8 IS the low 8 bits,
     * the phase is fully recoverable from the stream -- there is no residual
     * ambiguity. */
    int fidx = start_frame;
    while (nframes < 0 || fidx < nframes) {
        if (fread(inbuf, 2, in_words, fi) != in_words) break;
        if (refresh_req_list) {   /* [S3-REFRESH] control-plane stand-in */
            const char *q = refresh_req_list;
            while (*q) {
                int f = atoi(q); const char *col = strchr(q, ':');
                if (!col) break;
                if (f == fidx) {
                    int s0, s1;
                    if (col[1] == '*') { s0 = 0; s1 = nsl - 1; }
                    else { s0 = atoi(col + 1); const char *d = strchr(col + 1, '-');
                           const char *cm = strchr(col + 1, ',');
                           s1 = (d && (!cm || d < cm)) ? atoi(d + 1) : s0; }
                    if (s1 >= nsl) s1 = nsl - 1;
                    if (s0 <= s1) omc_enc_request_refresh(enc, s0, s1 - s0 + 1);
                }
                const char *nx = strchr(q, ','); if (!nx) break; q = nx + 1;
            }
        }
        if (cdr_in)
            /* CDR input: coded geometry, already biased — planes verbatim.
             * The mandatory T5 un-blend happens INSIDE omc_enc_frame. */
            memcpy(pix, inbuf, frame_words * 2);
        else
            assemble(pix, inbuf, W, H, Wc, iW, iH, iWc, mono, rgb,
                     mid_c, yoff, ysz, csz);
        int64_t n = omc_enc_frame(enc, &fin, fidx, bs, slice_bytes * (size_t)nsl,
                                  rec ? &frec : NULL);
        if (n < 0) die("encode failed");
        fwrite(bs, 1, (size_t)n, fo);
        if (fr) fwrite(rec, 2, frame_words, fr);
        if (cfg.lossless_pref) {
            /* verify bit-exactness of this frame from the rt=0 recon */
            int ll = (memcmp(pix, rec, frame_words * 2) == 0);
            lossless_frames += ll;
            if (verbose_ll)
                fprintf(stderr, "  frame %d: %s\n", fidx,
                        ll ? "LOSSLESS" : "lossy (fit CBR budget)");
        }
        fidx++;
    }
    fprintf(stderr, "omc_enc: %d frames, %u bits/slice, %d slices/frame (%.4f bpp)\n",
            fidx, cfg.bits_per_slice, nsl,
            (double)cfg.bits_per_slice * nsl / ((double)W * H));
    if (cfg.lossless_pref)
        fprintf(stderr, "omc_enc: lossless-preferred: %d/%d frames bit-exact\n",
                lossless_frames, fidx);
    {
        int64_t oob = omc_enc_oob(enc);
        int geom = omc_enc_geom_baseband_safe(enc);
        gamut_oob = oob;
        if (gamut_strict)
            fprintf(stderr, "omc_enc: gamut-strict: %d passes max, %lld slices "
                    "repaired in %lld passes (%lld fell back to the harsh "
                    "rule), %lld slices still out of gamut\n",
                    gamut_strict,
                    (long long)omc_enc_gamut_slices(enc),
                    (long long)omc_enc_gamut_repairs(enc),
                    (long long)omc_enc_gamut_fallbacks(enc),
                    (long long)omc_enc_gamut_unfixed(enc));
        /* [V15] the per-attempt budget above is not the worst-case work: every
         * restart and redo hands the slice a fresh budget.  This is the ENFORCED
         * per-slice total and what hardware must provision per slice period. */
        if (gamut_strict)
            fprintf(stderr, "omc_enc: gamut-strict: worst total passes %d of cap "
                    "%d (p50 %d p90 %d p99 %d over %lld repaired slices)\n",
                    omc_enc_gamut_total_max(enc), omc_enc_gamut_total_cap(enc),
                    omc_enc_gamut_total_pct(enc, 50), omc_enc_gamut_total_pct(enc, 90),
                    omc_enc_gamut_total_pct(enc, 99),
                    (long long)omc_enc_gamut_total_n(enc));
        omc_enc_gamut_stat_report();   /* [LEGACY-REPAIR] */
        { extern void omc_enc_latt_report(void); omc_enc_latt_report(); }   /* S2 step */
        if (oob < 0)
            fprintf(stderr, "omc_enc: gamut: NOT MEASURED (no reconstruction "
                    "buffer)\n");
        else
            fprintf(stderr, "omc_enc: gamut: %lld committed samples outside "
                    "legal range\n", (long long)oob);
        if (oob == 0 && geom)
            fprintf(stderr, "omc_enc: baseband-safe: yes\n");
        else
            fprintf(stderr, "omc_enc: baseband-safe: NO (%s%s%s) -- CDR "
                    "interchange required for exact chains\n",
                    oob < 0 ? "gamut not measured"
                            : (oob ? "out-of-gamut committed samples" : ""),
                    (oob && !geom) ? "; " : "",
                    geom ? "" : "geometry not recoverable from a cropped "
                                "picture: horizontal padding, or a visible row "
                                "run this rule cannot express");
    }
    omc_enc_destroy(enc);
    fclose(fi); fclose(fo); if (fr) fclose(fr);
    free(pix); free(rec); free(bs);
    /* EXIT STATUS.
     *
     *   0  the encode succeeded and, if the in-gamut mode was in force, it
     *      delivered what it promises: nothing committed outside the legal
     *      range, so an ordinary baseband hand-off is exact.
     *   2  the encode succeeded but the in-gamut mode could NOT clear every
     *      sample.  The stream is valid and plays correctly; what is not
     *      available is generation exactness over a baseband link.
     *   1  the encode failed (die(), everywhere else in this file).
     *
     * Status 2 exists because a line on stderr is easy to miss in an automated
     * pipeline, and the consequence of missing it does not show up at
     * origination -- it shows up at the second hop, in somebody else's
     * facility, as a picture that no longer matches.  Generation exactness is a
     * predicate and not a quantity: four stray samples break the chain exactly
     * as completely as fifteen hundred do, so 'nearly' has to be reported as a
     * failure of the guarantee rather than as a successful encode with a
     * remark.  A pipeline that does not need baseband exactness can ignore the
     * distinction; one that does need it now cannot silently lose it.
     *
     * Only the gamut condition is reported this way.  A raster whose geometry
     * is not recoverable from a cropped picture is a property of the job the
     * operator set up, known before a single frame is read, and it is reported
     * on its own line -- it is not an encode that went wrong. */
    if (gamut_strict && gamut_oob > 0) {
        fprintf(stderr, "omc_enc: EXACTNESS NOT DELIVERED: %lld committed "
                "samples are outside the legal range after %d repair passes. "
                "This stream plays correctly, but a baseband hand-off of it "
                "will NOT re-encode byte-exactly. Raise --gamut-strict, or "
                "carry CDR between hops. Exit status 2.\n",
                (long long)gamut_oob, gamut_strict);
        return 2;
    }
    /* sect.59: dead-chunk census (OMC_CHUNKSTAT), diagnostic only */
    if (getenv("OMC_CHUNKSTAT")) {
        extern int64_t omc_cs_tot[10], omc_cs_dead[10], omc_cs_n[10],
                       omc_cs_nz[10], omc_cs_inter[10];
        int64_t ti = 0, td = 0, tn = 0, tz = 0;
        fprintf(stderr, "chunkstat: 256-coefficient chunks, INTER bands only\n");
        fprintf(stderr, "  band    all chunks  inter chunks      dead      dead%%\n");
        for (int b = 0; b < 10; b++) {
            if (!omc_cs_tot[b]) continue;
            fprintf(stderr, "  %4d %13lld %13lld %9lld %9.2f%%\n", b,
                    (long long)omc_cs_tot[b], (long long)omc_cs_inter[b],
                    (long long)omc_cs_dead[b],
                    omc_cs_inter[b] ? 100.0 * (double)omc_cs_dead[b] / (double)omc_cs_inter[b] : 0.0);
            ti += omc_cs_inter[b]; td += omc_cs_dead[b];
            tn += omc_cs_n[b]; tz += omc_cs_nz[b];
        }
        if (ti) {
            fprintf(stderr, "  TOTAL %13lld %9lld %9.2f%%   live-chunk density %.4f\n",
                    (long long)ti, (long long)td, 100.0 * (double)td / (double)ti,
                    ti > td ? (double)tz / (double)((ti - td) * 256) : 0.0);
            /* band_scan emits exactly ONE tANS symbol per coefficient with no
             * run-length, so a dead chunk costs 256 symbols and the symbol
             * share is exact rather than modelled. */
            fprintf(stderr, "  SYMBOLS: %lld total in counted chunks, %lld in dead "
                            "chunks = %.2f%% of the coded symbol stream\n",
                    (long long)tn, (long long)td * 256,
                    tn ? 100.0 * (double)(td * 256) / (double)tn : 0.0);
        }
    }

    return 0;
}
