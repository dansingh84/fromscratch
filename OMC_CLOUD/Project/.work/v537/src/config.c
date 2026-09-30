/* omc_validate_config - the single shared validation authority for codec
 * configurations. The reference CLI, the control-plane API, and hardware
 * firmware are all expected to call THIS function (or a bit-exact port of
 * it), so that a configuration accepted by any layer is accepted by all.
 * Every rule cites its origin; ranges marked "measured" come from
 * docs/REPORT.md and are policy floors, not physical limits.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "internal.h"
#include "omc_uc.h"

#define FAIL(...) do { \
        if (err && errlen) snprintf(err, errlen, __VA_ARGS__); \
        return -1; \
    } while (0)

int omc_validate_config(const omc_config_t *cfg, char *err, size_t errlen)
{
    if (!cfg) FAIL("config is NULL");

    /* --- format geometry (BITSTREAM.md section 7) --- */
    if (cfg->chroma != OMC_CF_422 && cfg->chroma != OMC_CF_444)
        FAIL("chroma must be 4:2:2 or 4:4:4 (got %d)", (int)cfg->chroma);
    int walign = cfg->chroma == OMC_CF_422 ? 64 : 32;
    if (cfg->width == 0 || cfg->width % walign)
        FAIL("width %u must be a nonzero multiple of %d for this chroma format",
             cfg->width, walign);
    if (cfg->width > 8192)
        FAIL("width %u exceeds the validated maximum 8192", cfg->width);

    int sh = cfg->slice_h;
    if (sh == 0) sh = (cfg->height <= 720) ? 8 : 16; /* default 16; 720p-class -> 8 (A2) */
    if (sh != 8 && sh != 16 && sh != 32)
        FAIL("slice_h must be 8, 16, 32 or 0 (auto, = 16 above 720p and 8 at "
             "720p-class); got %u", cfg->slice_h);
    if (cfg->height == 0 || cfg->height % sh)
        FAIL("height %u must be a nonzero multiple of slice_h %d "
             "(interlaced 1080i fields use the 4.2 padding convention, "
             "docs/INTERLACE_CONVENTION.md)", cfg->height, sh);
    if (cfg->height > 4352)
        FAIL("height %u exceeds the validated maximum 4352", cfg->height);

    if (cfg->bitdepth != 8 && cfg->bitdepth != 10 && cfg->bitdepth != 12)
        FAIL("bitdepth must be 8, 10 or 12 (got %u)", cfg->bitdepth);

    if (cfg->fps_num == 0 || cfg->fps_den == 0)
        FAIL("fps %u/%u invalid: numerator and denominator must be nonzero",
             cfg->fps_num, cfg->fps_den);

    /* --- rate (bits_per_slice is the normative CBR quantum) --- */
    if (cfg->bits_per_slice == 0 || cfg->bits_per_slice % 8)
        FAIL("bits_per_slice %u must be a nonzero multiple of 8",
             cfg->bits_per_slice);
    /* F-3 (verified defect): when bits_per_slice < the per-slice wire floor
     * (header + minimum payload), the CBR frame induction fails and
     * omc_enc_frame's closing memset underflows (SIGSEGV on the shipped
     * binary at 64x64 0.40-0.50 bpp). Refuse the configuration up front. */
    if (cfg->bits_per_slice < (OMC_SLICE_HDR_BYTES + 32) * 8)
        FAIL("bits_per_slice %u is below the %d-bit per-slice wire floor "
             "(header %d bytes + 32-byte minimum payload)",
             cfg->bits_per_slice, (OMC_SLICE_HDR_BYTES + 32) * 8,
             OMC_SLICE_HDR_BYTES);
    {
        /* MECHANICAL LIMIT, NOT A PRODUCT FLOOR.  Below ~0.3 bpp a slice
         * cannot fit its 48-byte header plus minimum payload inside the 2x
         * wire cap (REPORT 11m), so the encoder would refuse anyway; this
         * refuses early and cleanly instead.  Validate against the equivalent
         * per-slice bit count.
         *
         * 2026-09-05: labelled explicitly because a reader of this file would
         * otherwise infer that 0.3 bpp is where the product starts.  It is
         * not.  0.3 is where the WIRE stops fitting.  The product's guarantees
         * -- deterministic worst-case latency, and flatness up to 4K -- begin
         * at 0.5 bpp (owner rulings 2026-09-05 and 2026-09-02).  Rates between
         * 0.3 and 0.5 encode and decode normally and are simply unpromised.
         * See docs/HARDWARE.md 7b and 7c. */
        long long floor_bits =
            (long long)(0.3 * (double)cfg->width * (double)sh);
        if ((long long)cfg->bits_per_slice < floor_bits)
            FAIL("bits_per_slice %u is below the 0.3 bpp mechanical limit "
                 "(%lld bits for %ux%d slices); encoder would refuse",
                 cfg->bits_per_slice, floor_bits, cfg->width, sh);
        /* [A5-M9-LLCEIL] sanity ceiling.  It exists to catch a caller passing
         * bits instead of bits-per-slice, so it only has to be far above any
         * legitimate rate -- but a FLAT 24 bpp is below the raw sample rate of
         * the widest format we support.  4:4:4 12-bit is 3 x 12 = 36 bits per
         * pixel, so `--lossless` there could never reach bit-exact: the encoder
         * refused the configuration before it could try (measured: 0/2 frames
         * bit-exact at the highest rate the guard allowed).  Scale the ceiling
         * with the format's own raw rate plus headroom for the wavelet's
         * expansion; a unit error is still orders of magnitude away. */
        int spp_ceil = (cfg->chroma == OMC_CF_444) ? 3 : 2;
        double ceil_bpp = (double)spp_ceil * (double)cfg->bitdepth + 8.0;
        long long ceil_bits =
            (long long)(ceil_bpp * (double)cfg->width * (double)sh);
        if ((long long)cfg->bits_per_slice > ceil_bits)
            FAIL("bits_per_slice %u exceeds the %.0f bpp ceiling for this "
                 "format (%d samples/pixel x %u-bit + 8) - likely a "
                 "unit error in the caller", cfg->bits_per_slice, ceil_bpp,
                 spp_ceil, cfg->bitdepth);
    }

    /* --- loss-recovery window (measured cost table: REPORT 12e) --- */
    if (cfg->refresh_r > 64 && cfg->refresh_r != OMC_REFRESH_NONE)
        FAIL("refresh_r %u out of range [0..64] (0 = default 8; 1 = "
             "stateless; 255 = no scheduled wave, refresh on demand)",
             cfg->refresh_r);

    /* --- colorimetry: accept the documented code points only --- */
    {
        uint8_t p = cfg->color.primaries, t = cfg->color.transfer,
                m = cfg->color.matrix;
        if (p != 0 && p != 1 && p != 9)
            FAIL("primaries code %u unsupported (0/1=BT.709, 9=BT.2020)", p);
        if (t != 0 && t != 1 && t != 18)
            FAIL("transfer code %u unsupported (0/1=BT.709, 18=HLG; 16 = PQ is not carried by this codec)", t);
        if (m != 0 && m != 1 && m != 9)
            FAIL("matrix code %u unsupported (0/1=BT.709, 9=BT.2020ncl)", m);
        if (cfg->color.full_range > 1)
            FAIL("full_range must be 0 or 1");
    }

    /* --- lossless-preferred ---- */
    if (cfg->lossless_pref && cfg->fill_grain)
        FAIL("lossless_pref forbids fill_grain (lossless cannot regenerate grain)");

    /* --- v4.2 extensions --- */
    if (cfg->rct) {
        if (cfg->chroma != OMC_CF_444)
            FAIL("RCT requires 4:4:4 (RGB planes are full resolution)");
        if (cfg->bitdepth != 10 && cfg->bitdepth != 12)
            FAIL("RCT container depth must be 10 or 12 (= RGB component depth "
                 "8 or 10 promoted by 2; datapath decision in "
                 "docs/MEDIA_SERVER_MARKET.md)");
    }
    if (cfg->display_width && cfg->display_width > cfg->width)
        FAIL("display_width %u exceeds coded width %u",
             cfg->display_width, cfg->width);
    if (cfg->display_height && cfg->display_height > cfg->height)
        FAIL("display_height %u exceeds coded height %u",
             cfg->display_height, cfg->height);
    /* The coded height must be the display height rounded UP to a whole slice
     * -- no more.  A larger gap means whole slices below the picture, which
     * minor 11's pad rule does not describe: it neutralizes the pad run of the
     * LAST slice only, so the committed pads of any slice above it would not
     * be a function of the visible rows and a cropped picture could not be
     * re-padded to the committed one.  Reachable from omc_enc --display-h and
     * from the library API; found by adversarial audit, where it silently
     * produced pads that were not replications. */
    if (cfg->display_height &&
        (uint32_t)cfg->height !=
            ((uint32_t)cfg->display_height + sh - 1) / sh * sh)
        FAIL("coded height %u is not display_height %u rounded up to the slice "
             "height %d (expected %u)", cfg->height, cfg->display_height, sh,
             ((uint32_t)cfg->display_height + sh - 1) / sh * sh);

    /* --- OMC-TF in-loop temporal filter: operating envelope ---
     *
     * The filter assumes the previous frame is an INDEPENDENT noisy look at the
     * same truth, so averaging attenuates the noise.  That assumption only holds
     * while the codec is rate-starved.  Given enough rate, inter prediction
     * REFINES — each frame is a strictly better estimate than the last
     * (docs/DESIGN.md 1b, "prediction refines toward transparency") — and
     * averaging a better estimate with a worse one brakes that convergence.
     * Measured on static content at 2.0 bpp, Y PSNR per frame:
     *
     *     filter off   48.06  52.88  55.25  56.42  57.81  58.18   (converging)
     *     filter on    48.06  52.14  54.25  55.01  55.30  55.38   (braked)
     *
     * harness/tf_rate.py sweeps the crossover across the corpus; the binding
     * sequence is the real cine footage, which stops benefiting above 0.5 bpp.
     * The envelope is therefore enforced here rather than left as advice, and
     * it is expressed in bits_per_slice — a field BOTH ENDS read from the
     * header — so the encoder and the decoder evaluate the same rule with no
     * new signalling.
     *
     *     bpp = bits_per_slice / (width * slice_h)
     */
    /* [G-TFDEL] The OMC-TF rate validator lived here (env OMC_TF). OMC-TF was
     * removed from the codec with the old temporal engine (T5) and its offline
     * tool, filter and test were deleted 2026-09-06 (legal review action 3). */

    /* --- OMC-UC output conversion (stream byte 26) --- */
    if (cfg->uc_ratio > 2)
        FAIL("uc_ratio %u invalid (0 = none, 1 = 2x, 2 = 4x)", cfg->uc_ratio);
    if (cfg->uc_ratio && (long)cfg->width * (1 << cfg->uc_ratio) > 32768)
        FAIL("uc_ratio %u would produce an output width beyond 32768", cfg->uc_ratio);
    if (cfg->a2_strict) {
        /* A2 is a hard bar ONLY when the caller asks for it to be.  The model
         * below is docs/LATENCY.md verbatim and the figure is available to
         * anyone through omc_config_latency(); what changed is the policy.  A
         * conversion this operator performs correctly, at a latency the caller
         * has been told, is not an error -- it is a conversion with a number
         * attached, and refusing it made a usable 720p50 leg unavailable for a
         * bar that binds the contribution product rather than every leg.
         * a2_strict = 1 restores the refusal for a facility that needs the
         * guarantee enforced rather than declared. */
        int reach = cfg->uc_ratio ? omc_uc_analytic_reach_n(cfg->uc_ratio) : 0;
        int nsl = (int)(cfg->height / sh);
        double frame_ms = 1000.0 * (double)cfg->fps_den / (double)cfg->fps_num;
        double line_ms = frame_ms / (double)cfg->height;
        double slice_ms = frame_ms / (double)nsl;
        /* the decoder's output stage decides what the rescaler's reach costs;
         * see omc1.h OMC_OUT_RASTER / OMC_OUT_SLICE_BATCHED */
        int periods = (reach + sh - 1) / sh;
        double conv = cfg->uc_out_batched ? periods * slice_ms
                                          : (reach ? (reach + 1) * line_ms : 0.0);
        /* no banking overdraft term since 2026-08-12: OD_CAP_PCT = 0 */
        double total = sh * line_ms + slice_ms + 2 * line_ms + conv;
        if (total >= 1.0)
            FAIL("uc_ratio %u at %ux%u@%u/%u would take %.3f ms total "
                 "(%d-source-row reach at slice_h %d, charged as %s); "
                 "A2 requires < 1 ms (the codec term alone is charged even "
                 "with no conversion configured)",
                 cfg->uc_ratio, cfg->width, cfg->height, cfg->fps_num,
                 cfg->fps_den, total, reach, sh,
                 cfg->uc_out_batched ? "whole slice periods (slice-batched "
                 "output stage)" : "lines (raster-clocked output stage)");
    }

    /* --- decode-side stream version --- */
    if (cfg->ver_minor > OMC_VERSION_MINOR)
        FAIL("stream minor version %u newer than this implementation (%d)",
             cfg->ver_minor, OMC_VERSION_MINOR);

    if (err && errlen) err[0] = '\0';
    return 0;
}

/* docs/LATENCY.md verbatim, with the upconverter's extra slice periods.  The
 * same arithmetic omc_validate_config() uses, exposed so a caller can obtain
 * the figure WITHOUT having to provoke a failure to see it. */
int omc_config_latency(const omc_config_t *cfg, double *total_ms, int *periods)
{
    int sh, nsl, reach = 0, per = 0;
    double frame_ms, line_ms, slice_ms, total;
    if (!cfg || cfg->height < 1 || !cfg->fps_num || !cfg->fps_den) return -1;
    /* the SAME auto rule the validator uses (they disagreed: this said 8
     * unconditionally while the validator says 16 above 720p, so the figure
     * reported to a caller was for a slice height the encoder would not use) */
    sh = omc_resolve_slice_h(cfg);
    nsl = (int)(cfg->height / sh);
    if (nsl < 1) return -1;
    if (cfg->uc_ratio) {
        reach = omc_uc_analytic_reach_n(cfg->uc_ratio);
        per = (reach + sh - 1) / sh;
    }
    frame_ms = 1000.0 * (double)cfg->fps_den / (double)cfg->fps_num;
    line_ms = frame_ms / (double)cfg->height;
    slice_ms = frame_ms / (double)nsl;
    /* and the SAME conversion charge: raster-clocked output (the product's
     * contract and the default) costs reach LINES plus the deferred row, not
     * whole slice periods.  Reporting the batched figure for a raster decoder
     * overcharged every converting configuration. */
    total = sh * line_ms + slice_ms + 2 * line_ms
            + (cfg->uc_out_batched ? per * slice_ms
                                   : (reach ? (reach + 1) * line_ms : 0.0));
    if (total_ms) *total_ms = total;
    if (periods) *periods = per;
    return total < 1.0 ? 0 : 1;
}
