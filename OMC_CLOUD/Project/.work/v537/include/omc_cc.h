/* OMC-CC — colour-space conversion for OMC-1.
 *
 * WHY THIS EXISTS.  An earlier draft of the delivery document said colour
 * conversion was "out of scope" and cited the project constraints.  That was an
 * overreach: B3 requires the codec to carry colour *without corrupting it* and
 * says nothing about converting it; C7 forbids side channels, and this needs
 * none, because the colour code points are already in the stream header where
 * the codec is supposed to read them; section D's scope boundary is about audio,
 * timecode and captions.  There is no rule.  So it is built.
 *
 * WHAT IT DOES.  The unambiguous part of colour conversion: a change of
 * PRIMARIES and/or MATRIX COEFFICIENTS, done properly -- that is, in LINEAR
 * LIGHT, which is the only place a primaries matrix is meaningful.
 *
 *     YCbCr --[matrix]--> R'G'B' --[EOTF]--> linear RGB
 *           --[3x3 primaries]--> linear RGB
 *           --[inverse EOTF]--> R'G'B' --[matrix]--> YCbCr
 *
 * Every stage is a table lookup or a constant multiply written as shift-adds,
 * so C3 holds: no dividers, no floating point, no data-dependent iteration
 * beyond a fixed 12-step binary search.  All constants are generated offline by
 * repro/gen_cc_tables.c and published in src/cc_tab.c.inc, exactly as the
 * polyphase bank is, so no libm call exists on any runtime path and two vendors
 * cannot disagree because their pow() differs.
 *
 * TONE MAPPING.  Off by default, and a transfer change with it off is REFUSED
 * (-2) rather than approximated -- converting HLG to gamma without a tone map
 * silently clips everything above the SDR range.  Turned ON explicitly, it runs
 * a DECLARED curve: ITU-R BT.2390's EETF, whose only inputs are the source's
 * peak luminance and the target display's, both stated by the caller rather
 * than guessed from the picture.  There is no scene analysis, no per-frame
 * adaptation and no hidden knob; the one taste parameter, a saturation
 * exponent, is a published constant per curve.  A tuple with no published curve
 * is refused (-3), for the same reason an undeclared scaling ratio is: a tone
 * map nobody has constants for is a tone map nobody can reproduce.
 *
 * That it is off by default is the important part.  Contribution is the first
 * link in the chain, so anything baked in here is inherited by everyone
 * downstream and cannot be undone.  The decision to tone map belongs to the
 * operator, is made once, and is visible in the configuration.
 *
 * The gain a tone map applies is a VARIABLE times a VARIABLE, which is exactly
 * the per-pixel multiplier C3 forbids, so the whole stage runs in the LOG
 * domain where a multiply is an add: log2 and exp2 are a priority encoder, a
 * shift and one lookup each.  Shifts, adds, compares and lookups, throughout.
 *
 * NOT REVERSIBLE.  A colour conversion is a matrix and two transfer lookups; it
 * has no exact integer inverse, and out-of-gamut colours clip.  This is stated
 * rather than quietly dropped -- the same disposition the rational scaling path
 * already carries, which also ships non-reversible because a facility that
 * needs it needs it more than it needs the round trip on that leg.
 */
#ifndef OMC_CC_H
#define OMC_CC_H

#include <stdint.h>

/* Colour primaries, matching the stream header's `primaries` code point. */
typedef enum {
    OMC_CC_P_BT709  = 1,
    OMC_CC_P_BT2020 = 9
} omc_cc_prim_t;

/* Transfer characteristic, matching the header's `transfer` code point. */
typedef enum {
    OMC_CC_T_GAMMA = 1,      /* BT.709 / BT.1886 display gamma */
    /* code point 16 (SMPTE ST 2084 / PQ) is NOT carried by this codec -- removed 2026-09-08 */
    OMC_CC_T_HLG   = 18      /* ITU-R BT.2100 hybrid log-gamma */
} omc_cc_trc_t;

/* Matrix coefficients, matching the header's `matrix` code point. */
typedef enum {
    OMC_CC_M_BT709  = 1,
    OMC_CC_M_BT601  = 6,
    OMC_CC_M_BT2020 = 9
} omc_cc_mtx_t;

/* Tone-mapping mode.  OFF is the default and the value a zeroed struct gets. */
typedef enum {
    OMC_CC_TM_OFF      = 0,  /* a transfer change is refused                  */
    OMC_CC_TM_DECLARED = 1   /* use the published curve for this tuple, or -3 */
} omc_cc_tm_t;

/* Primaries may also be supplied by the caller.  A media server driving LED
 * panels, or any display whose primaries are measured rather than standard,
 * needs a matrix that is not in any standard's table.  Computing a 3x3 from two
 * sets of chromaticities is offline arithmetic the control plane can do once;
 * what the codec must not do is invent one.  Set src_prim/dst_prim to
 * OMC_CC_P_CUSTOM and point prim_custom at a Q20 row-major 3x3 whose rows each
 * sum to exactly 1<<20 -- the row sum is checked, because a row that does not
 * sum to unity puts a permanent cast on every grey. */
#define OMC_CC_P_CUSTOM 255

typedef struct {
    uint8_t depth;             /* 8..12, both ends                            */
    uint8_t src_full_range;    /* 0 = video/limited range, 1 = full           */
    uint8_t dst_full_range;    /* limited <-> full is a conversion in itself   */
    uint8_t src_prim, dst_prim;
    uint8_t src_trc,  dst_trc;
    uint8_t src_mtx,  dst_mtx;
    uint8_t tone_map;          /* omc_cc_tm_t; 0 (off) unless asked for       */
    uint16_t src_peak;         /* declared nits; read only when tone_map != 0 */
    uint16_t dst_peak;
    const int32_t *prim_custom;  /* Q20 3x3, or NULL                          */
} omc_cc_t;

/* Validate a conversion.  Returns 0 if it is exactly defined, or:
 *   -1  an unknown code point, or a depth outside 8..12
 *   -2  src_trc != dst_trc with tone mapping OFF -- a transfer change needs a
 *       tone map, and turning one on is the operator's decision, not the
 *       codec's
 *   -3  tone mapping ON but no published curve for this
 *       (src_trc, src_peak) -> (dst_trc, dst_peak) tuple
 *   -4  OMC_CC_P_CUSTOM selected with no matrix, or with one whose rows do not
 *       sum to exactly 1<<20
 * A caller that cannot honour a refusal must not offer the conversion. */
int omc_cc_validate(const omc_cc_t *c);

/* Convert one frame in place-compatible planar form.
 *   y, cb, cr : 4:4:4 planes, w x h, stride in samples.
 * 4:2:2 input must be upsampled by the caller first: a primaries matrix mixes
 * the three components, so it is only meaningful where all three are co-sited.
 * Returns 0, or the omc_cc_validate() code. */
int omc_cc_convert(const omc_cc_t *c,
                   uint16_t *y, int ys, uint16_t *cb, int cbs,
                   uint16_t *cr, int crs, int w, int h);

/* Verify the published tables.  Returns 0, or:
 *   -1  a primaries row does not sum exactly to unity
 *   -2  an R'G'B' -> YCbCr row does not sum exactly to unity (luma) or zero
 *       (chroma) -- a chroma row summing to anything but zero puts colour on
 *       every grey
 *   -3  a transfer table is not monotonic, is non-zero at zero, or is flat
 *   -4  the two primaries matrices are not mutual inverses
 *   -5  a YCbCr -> R'G'B' luma column is not exactly unity -- this is the
 *       neutral-axis property, and it is NOT the row sum; see gen_cc_tables.c
 *   -6  the shift-add chain does not equal the multiply for some published
 *       coefficient, i.e. a coefficient has outgrown cc_mul_sa()'s bound
 * No libm.  Gated by tests/test_cc.c. */
int omc_cc_selfcheck(void);

/* Worst-case PIPELINE DEPTH of the conversion, in clock cycles, for a datapath
 * that retires one sample per clock.  There is no line store and no frame
 * store: the stage is pointwise (gated), so it adds NO vertical reach and NO
 * slice period, and this depth is its entire contribution to the A2 budget.
 *
 * The count is the sum of the stages: range normalise (3), YCbCr -> R'G'B' (3),
 * transfer lookup (2), primaries (3), the 12-step inverse-transfer search (13),
 * R'G'B' -> YCbCr (3), range denormalise and clamp (3) = 30; the tone-map stage
 * adds log2 (4), the luminance sum (3), the curve lookup (2), the saturation
 * multiply (3), the adds (2) and exp2 (3) = 17.  Rounded up to give a synthesis
 * run somewhere to put its own registers. */
int omc_cc_pipeline_clocks(int tone_map);

#endif
