/* OMC-UC — normative resolution upconversion for OMC-1 (bitstream v4.8).
 *
 * A decoder OUTPUT-STAGE conversion, not a coding tool: the coded picture, the
 * temporal reference, rate control and every existing conformance hash are
 * untouched.  The upconverter takes the decoder's reconstruction at coded
 * resolution and emits 2x (or 4x, by iteration) in both dimensions.
 *
 * Structure — one reversible lifting level per dimension:
 *
 *     up:   x[2i]   = s[i] - ((H[i-1] + H[i] + 2) >> 2)     (inverse update)
 *           x[2i+1] = H[i] + P(x_even, i)                   (inverse predict)
 *     down: H[i]    = x[2i+1] - P(x_even, i)                (predict)
 *           s[i]    = x[2i]   + ((H[i-1] + H[i] + 2) >> 2)  (update)
 *
 * P reads ONLY the even lattice, so `down` is the exact integer inverse of `up`
 * for ANY detail band H — including the direction-adaptive, overshoot-limited,
 * range-clamped nonlinear P used here.  Consequence (the contribution-grade
 * property): an upconverted picture downconverts BIT-EXACTLY back to the
 * transmitted picture with a fixed, published, multiplier-free operator.
 *
 * Reference mode (normative default) sets H == 0: the output carries no signal
 * that was not in the source — no synthesised texture, no invented detail
 * (DESIGN.md §6b posture).  The H port is specified and reserved.
 *
 * Per-pixel datapath: adds, shifts, compares and table lookups only (C3).
 * Measured vertical dependency reach: 6 source rows (tests/test_uc.c), so the
 * upconverted output of slice k depends on nothing later than slice k+1 —
 * exactly one extra slice period of latency at every supported format.
 */
#ifndef OMC_UC_H
#define OMC_UC_H

#include <stdint.h>

#define OMC_UC_KTAPS 12               /* separable half-band predictor length   */
#define OMC_UC_KSHIFT 10              /* coefficient denominator = 1 << 10      */
#define OMC_UC_REACH 8                /* worst-case source rows of look-ahead;
                                       * must be <= slice_h (8) or the delay
                                       * becomes two slice periods. Computed
                                       * from the constants by
                                       * omc_uc_analytic_reach(). */
#define OMC_UC_NCAND 13               /* direction candidates (vertical pass)    */

typedef struct {
    uint8_t depth;     /* 8..12 — output range clamp [0, (1<<depth)-1]          */
    uint8_t direction; /* 1 = direction-adaptive predictor (normative default)  */
} omc_uc_t;

/* Upconvert one plane by 2x in both dimensions.
 *   src : h x w  samples, row stride `ss`   (the decoder's reconstruction)
 *   dst : 2h x 2w samples, row stride `ds`
 *   r0,r1: destination row band to produce, [r0, r1) of [0, 2h).  Producing a
 *          band gives bit-identical results to producing the whole plane
 *          (verified by tests/test_uc.c) — this is what makes slice-wise
 *          operation legal.
 * Returns 0, or -1 on an invalid argument. */
int omc_uc_up_plane(const omc_uc_t *u, const uint16_t *src, int ss, int w, int h,
                    uint16_t *dst, int ds, int r0, int r1);

/* Downconvert one plane by 2x — the exact integer inverse of omc_uc_up_plane.
 *   src : (2h) x (2w), stride ss ;  dst : h x w, stride ds. */
int omc_uc_down_plane(const omc_uc_t *u, const uint16_t *src, int ss, int w, int h,
                      uint16_t *dst, int ds);

/* Downconvert a BAND of destination rows [r0, r1).  Producing a band gives
 * bit-identical results to producing the whole plane (verified by
 * tests/test_uc.c), which is what makes a slice-wise schedule legal for the
 * inverse as well as the forward direction -- the forward operator had this
 * from the start and the inverse did not, so a facility leg that downconverts
 * had no bounded-memory, bounded-latency path at all. */
int omc_uc_down_plane_band(const omc_uc_t *u, const uint16_t *src, int ss,
                           int w, int h, uint16_t *dst, int ds, int r0, int r1);

/* Scratch sizing for a band request: bytes of int32 workspace the caller must
 * supply, or 0 to let the functions allocate internally. */
size_t omc_uc_scratch_bytes(int w, int h);

/* Verify that the multiplier-free kernel evaluation equals the tabulated
 * coefficients exactly (C3 evidence). Returns 0 on success. */
int omc_uc_selfcheck_kernel(void);

/* Worst-case vertical dependency reach in SOURCE rows, derived from the
 * normative constants (NOT measured -- a benign test picture under-reports it).
 * The latency contract requires this to be <= slice_h. */
int omc_uc_analytic_reach(void);

/* Reach of a cascade of `levels` 2x stages (levels = 2 is the 4x path).
 * Cascading is NOT free: 4x reaches 12 source rows, which needs two slice
 * periods at slice_h = 8. omc_validate_config() enforces the resulting latency
 * rule so an unsupportable (format, ratio) pair is refused up front. */
int omc_uc_analytic_reach_n(int levels);

/* Rational (non-dyadic) conversion, e.g. 720p -> 1080p. Single-stage 12-tap
 * polyphase, one fixed coefficient set per phase; the number of phases is the
 * denominator of dh/sh (and dw/sw) in lowest terms, which is small for every
 * broadcast ratio. Co-siting: output sample n maps to source position
 * n*num/den, so at ratio 2 it reduces exactly to the dyadic path.
 * NOT REVERSIBLE -- down(up(x)) == x is a dyadic-only guarantee.
 * Returns 0, -1 on a bad argument, -2 if the ratio needs more than 16 phases. */
/* Sample siting for the rational scaler.  Two different jobs need two different
 * answers and they are not interchangeable:
 *
 *   OMC_SITE_CENTRE  — the output grid is centred on the source grid.  This is
 *      what RESIZING A PICTURE wants: 1080p -> 2160p keeps the picture where it
 *      was instead of shifting it half a source sample.
 *   OMC_SITE_COSITED — output sample 0 lands exactly on source sample 0.  This
 *      is what CHROMA SITING wants: in 4:2:2, chroma sample k is co-sited with
 *      luma sample 2k (BITSTREAM's own [1,2,1]/4 convention), so re-centring the
 *      chroma grid puts the colour a quarter sample off the luma it belongs to.
 *
 * It is a PARAMETER and not a field of omc_uc_t for the same reason `mirror`
 * is: a flag inside the operator config is one a caller can forget to set, and
 * a stack-allocated omc_uc_t with a garbage byte in it would then resample to
 * the wrong grid at random. */
#define OMC_SITE_CENTRE  0
#define OMC_SITE_COSITED 1

int omc_uc_scale_plane(const omc_uc_t *u, const uint16_t *src, int ss, int sw, int sh,
                       uint16_t *dst, int ds, int dw, int dh);

/* The same, with the siting stated.  omc_uc_scale_plane() above is the
 * OMC_SITE_CENTRE form, because resizing a picture is the common case. */
int omc_uc_scale_plane_sited(const omc_uc_t *u, const uint16_t *src, int ss,
                             int sw, int sh, uint16_t *dst, int ds,
                             int dw, int dh, int siting);

/* Aspect framing: scale a source CROP into a destination RECT and fill the rest
 * of the output with `fill` (pillarbox, letterbox, 14:9, centre cut).  The bars
 * are written once and the scaler never touches them, so they carry exactly the
 * level asked for; the crop is honoured by the scaler's own edge extension.
 * The rect's horizontal placement and width must be even so a 4:2:2 chroma
 * plane carries the same geometry at half width; the vertical is free, because
 * the standard 16:9-into-4:3 letterbox has 135-line bars. */
int omc_uc_frame_plane(const omc_uc_t *u,
                       const uint16_t *src, int ss, int sw, int sh,
                       int sx, int sy, int scw, int sch,
                       uint16_t *dst, int ds, int dw, int dh,
                       int dx, int dy, int dcw, int dch,
                       uint16_t fill, int mirror);
/* `mirror` != 0 flips the framed rect horizontally.  It is a parameter rather
 * than a field of omc_uc_t on purpose: a flag inside the operator config is one
 * a caller can forget to initialise, and a stack-allocated omc_uc_t with a
 * garbage byte in it would mirror at random.  It is also the ONLY geometric
 * flip offered, because it is the only free one: a horizontal reversal happens
 * within a line, so it adds no vertical reach and no slice period.  A vertical
 * flip, a 180-degree rotation and a 90-degree rotation all need the LAST source
 * line before the FIRST output line -- a whole frame of latency, 20 ms at 50p
 * against a 1 ms budget -- and are therefore not offered at any price.
 * On a 4:2:2 plane a mirror also reverses the chroma co-siting convention by
 * half a luma sample; use 4:4:4 where that matters. */

/* Worst-case vertical reach of the rational path, in source rows.  The no-arg
 * form is the INTERPOLATION case (6); use the _r form for a decimation, whose
 * aperture -- and therefore reach and latency -- scales with the ratio. */
int omc_uc_scale_reach(void);
int omc_uc_scale_taps(int num, int den);
int omc_uc_scale_reach_r(int num, int den);

/* Verify the published polyphase bank: unity DC on every phase, phase 0 the
 * unit impulse, the 1:2 phase equal to UC_C, and phase p the mirror of phase
 * den-p.  Returns 0, or -(table index + 1).  No libm anywhere. */
int omc_uc_selfcheck_poly(void);

/* Proof that the rational bank's shift-add evaluation equals the tabulated
 * multiply, for every coefficient of every published table over the whole
 * datapath range -- the rational path's equivalent of
 * omc_uc_selfcheck_kernel().  Returns 0, or -(table index + 1). */
int omc_uc_selfcheck_poly_mul(void);

/* Scratch bytes the RATIONAL path needs, and the allocation-free form of it.
 * The dyadic path has had this shape from the start (omc_uc_up_plane_ws +
 * omc_uc_scratch_bytes); the rational path allocated internally, which was the
 * one place the operator's C did not look like the hardware it describes -- a
 * synthesis run cannot call malloc at all.  omc_uc_scale_plane() remains as a
 * convenience wrapper and the two are gated byte-identical. */
size_t omc_uc_scale_scratch_bytes(int sw, int sh, int dw, int dh);
int omc_uc_scale_plane_ws(const omc_uc_t *u, const uint16_t *src, int ss, int sw, int sh,
                          uint16_t *dst, int ds, int dw, int dh, void *ws, size_t wsz);
int omc_uc_scale_plane_ws_sited(const omc_uc_t *u, const uint16_t *src, int ss,
                                int sw, int sh, uint16_t *dst, int ds, int dw,
                                int dh, void *ws, size_t wsz, int siting);

/* B4's floor: "the supported range starts at 720p and scales upward". */
#define OMC_UC_MIN_HEIGHT 720

/* Is (w, h) inside the mandated operating range?  B4 sets the supported range
 * as "starts at 720p and scales upward", and 720p is a first-class format
 * rather than a reduced-latency tier.  A conversion whose OUTPUT falls below
 * that floor is refused as a FORMAT limit, not a latency one -- offering it
 * would be building something the codec itself does not carry.
 *
 * The floor is on the vertical dimension, because that is what B4 names and
 * what the raster is described by; width follows the aspect the caller asks
 * for.  Returns 1 if supported, 0 if below the floor. */
int omc_uc_format_supported(int w, int h);

/* Latency of a rational conversion.  Always writes the total and the extra
 * slice periods when the conversion is possible at all.  Returns:
 *    0  the conversion holds sub-1 ms -- A2 met
 *   +1  the conversion is CORRECT AND AVAILABLE but exceeds 1 ms; the caller
 *       must declare the figure it was just given
 *   -3  the ratio is outside the declared set (steeper than the aperture cap,
 *       or more than 16 phases) -- not available at any latency
 *   -4  the OUTPUT raster is below B4's 720p floor -- a format refusal, and it
 *       is checked first, because "the codec does not carry that format" and
 *       "that conversion is slow" are not the same answer
 *
 * The sign carries the distinction, and it is a real one.  "Cannot" and "can,
 * but not in a millisecond" are different answers, and an earlier revision
 * returned -1 for both, which made a perfectly good 720p50 -> 360p conversion
 * look like an unsupported ratio.  A2 binds the contribution product; a leg
 * that can afford 1.06 ms should get its conversion, with the number in front
 * of it.  Callers that need the guarantee ask for it explicitly (omc_cfg_t's
 * a2_strict, or omc_uc_tool's --enforce-a2).
 *
 * DOWNCONVERSION IS A DECIMATION: its aperture, reach and latency all scale
 * with the ratio, so this must be consulted rather than assuming the
 * interpolating path's one slice period. */
int omc_uc_scale_latency(int sw, int sh, int dw, int dh, int slice_h,
                         int fps_num, int fps_den, double *total_ms, int *periods);

/* The same, with the decoder's output-stage contract stated explicitly:
 * `batched` = OMC_OUT_RASTER (0) charges `reach` lines plus one for the XSL
 * deferred row; OMC_OUT_SLICE_BATCHED (1) charges ceil(reach/slice_h) whole
 * slice periods, which is what the model assumed before 2026-08-12.  The
 * no-suffix form above is the raster-clocked one, because that is the product's
 * decoder.  `*periods` is meaningful only in the batched case and is 0
 * otherwise -- the raster charge is in LINES and is already in the total. */
int omc_uc_scale_latency_ex(int sw, int sh, int dw, int dh, int slice_h,
                            int fps_num, int fps_den, int batched,
                            double *total_ms, int *periods);

#endif
