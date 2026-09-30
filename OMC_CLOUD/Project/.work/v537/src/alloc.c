/* Normative rate-allocation tables for OMC v2.
 *
 * Effective band shift = clamp(Q + omc_off[profile][plane][band]
 *                              (+ omc_off_c444[band] for chroma in 4:4:4), 0, 15),
 * minus refinement steps applied in the fixed omc_refine_order; the LL band is
 * hard-capped at OMC_LL_CAP (anti-banding, G2). The decoder derives all shifts
 * from (profile, Q, n_steps, partial_chunks) alone.
 *
 * Profiles 0-1 are PLANE-FAIR (default): chroma uses the same ladder as luma,
 * so quality is matched across Y/Cb/Cr at every rate. Profiles 2-3 are the
 * luma-weighted pair (encoder --tune vmaf): chroma mid/high bands sit coarser,
 * buying luma fidelity that luma-only metrics reward. Within each pair, the
 * second profile is the "texture" variant (finer level-1 luma bands for
 * sparse-grain content, chosen per slice by the encoder heuristic).
 */
#include "internal.h"

/* band order: LL5 HL5 HL4 HL3 LH2 HL2 HH2 LH1 HL1 HH1 */
const int8_t omc_off[OMC_NPROFILES][OMC_NPLANES][OMC_NBANDS] = {
    { /* profile 0: fair / balanced (chroma one step finer at mid/high:
         chroma is smoother and half-width, so equal visible fidelity sits
         one rung finer - mirrors the incumbent's plane split) */
        {-4, -3, -3, -2, -1, -1,  0,  0,  0, 1}, /* Y  */
        {-4, -3, -3, -2, -1, -1,  0,  0,  0, 1}, /* Cb */
        {-4, -3, -3, -2, -1, -1,  0,  0,  0, 1}, /* Cr */
    },
    { /* profile 1: fair / texture */
        {-4, -3, -3, -2, -1, -1, -1, -1, -1, 0}, /* Y  */
        {-4, -3, -3, -2, -1, -1,  0,  0,  0, 1}, /* Cb */
        {-4, -3, -3, -2, -1, -1,  0,  0,  0, 1}, /* Cr */
    },
    { /* profile 2: luma-weighted / balanced */
        {-4, -3, -3, -2, -1, -1,  0,  0,  0, 1}, /* Y  */
        {-4, -3, -2, -1,  0,  1,  2,  2,  2, 3}, /* Cb */
        {-4, -3, -2, -1,  0,  1,  2,  2,  2, 3}, /* Cr */
    },
    { /* profile 3: luma-weighted / texture */
        {-4, -3, -3, -2, -1, -1, -1, -1, -1, 0}, /* Y  */
        {-4, -3, -2, -1,  0,  1,  2,  2,  2, 3}, /* Cb */
        {-4, -3, -2, -1,  0,  1,  2,  2,  2, 3}, /* Cr */
    },
};

/* Additional chroma-plane shift delta applied in 4:4:4 (chroma carries twice
 * the samples of 4:2:2 in the same pipe). */
const int8_t omc_off_c444[OMC_NBANDS] = {0, 0, 1, 1, 1, 1, 1, 1, 1, 1};

/* Greedy refinement schedule: each entry lowers that band's shift by one.
 * Plane-fair interleave (luma first within each tier, chroma immediately
 * after); three rounds, low-to-high frequency. */
const uint8_t omc_refine_order[][2] = {
    /* round 1: mid bands, luma first within each tier */
    {0, 3}, {0, 4}, {0, 5}, {1, 3}, {2, 3}, {1, 4}, {1, 5}, {2, 4}, {2, 5},
    {0, 6}, {1, 6}, {2, 6},
    /* round 1: high bands */
    {0, 7}, {0, 8}, {1, 7}, {1, 8}, {2, 7}, {2, 8}, {0, 9}, {1, 9}, {2, 9},
    /* round 2 */
    {0, 3}, {0, 4}, {0, 5}, {1, 3}, {2, 3}, {1, 4}, {1, 5}, {2, 4}, {2, 5},
    {0, 6}, {1, 6}, {2, 6},
    {0, 7}, {0, 8}, {1, 7}, {1, 8}, {2, 7}, {2, 8}, {0, 9}, {1, 9}, {2, 9},
    /* round 3: luma only */
    {0, 3}, {0, 4}, {0, 5}, {0, 6}, {0, 7}, {0, 8}, {0, 9},
};
const int omc_refine_steps = (int)(sizeof(omc_refine_order) / sizeof(omc_refine_order[0]));
