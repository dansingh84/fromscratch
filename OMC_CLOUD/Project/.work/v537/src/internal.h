/* OMC-1 internal shared definitions. */
#ifndef OMC1_INTERNAL_H
#define OMC1_INTERNAL_H

#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "omc1.h"
#include "tables.h"

/* ---------- band geometry ----------
 * Per plane, slice buffer is sh x W (chroma: sh x Wc). After the in-place
 * Mallat arrangement, bands live at fixed rectangles. r2 = sh/4, r1 = sh/2.
 * id : name : rows          : cols
 *  0   LL5    [0, r2)         [0,     W/32)
 *  1   HL5    [0, r2)         [W/32,  W/16)
 *  2   HL4    [0, r2)         [W/16,  W/8)
 *  3   HL3    [0, r2)         [W/8,   W/4)
 *  4   LH2    [r2, 2*r2)      [0,     W/4)
 *  5   HL2    [0, r2)         [W/4,   W/2)
 *  6   HH2    [r2, 2*r2)      [W/4,   W/2)
 *  7   LH1    [r1, sh)        [0,     W/2)
 *  8   HL1    [0, r1)         [W/2,   W)
 *  9   HH1    [r1, sh)        [W/2,   W)
 */
typedef struct {
    int r0, c0, h, w; /* rectangle inside the slice buffer */
} omc_band_t;

static inline void omc_band_layout(int W, int sh, omc_band_t b[OMC_NBANDS])
{
    int r2 = sh / 4, r1 = sh / 2;
    b[0] = (omc_band_t){0, 0, r2, W / 32};
    b[1] = (omc_band_t){0, W / 32, r2, W / 32};
    b[2] = (omc_band_t){0, W / 16, r2, W / 16};
    b[3] = (omc_band_t){0, W / 8, r2, W / 8};
    b[4] = (omc_band_t){r2, 0, r2, W / 4};
    b[5] = (omc_band_t){0, W / 4, r2, W / 4};
    b[6] = (omc_band_t){r2, W / 4, r2, W / 4};
    b[7] = (omc_band_t){r1, 0, r1, W / 2};
    b[8] = (omc_band_t){0, W / 2, r1, W / 2};
    b[9] = (omc_band_t){r1, W / 2, r1, W / 2};
}

/* ---------- forward/inverse 5/3 (dwt.c) ---------- */
void omc_slice_fwd(int32_t *buf, int W, int sh, int32_t *tmp);
void omc_slice_inv(int32_t *buf, int W, int sh, int32_t *tmp);
/* pad-aware forms (minor 11): vv = visible rows of the slice, vv == sh for an
 * ordinary slice, in which case these are identical to the two above. */
void omc_slice_fwd_p(int32_t *buf, int W, int sh, int32_t *tmp, int vv,
                     const int32_t *d1m);
void omc_slice_inv_p(int32_t *buf, int W, int sh, int32_t *tmp, int vv,
                     const int32_t *d1m);

/* ---------- tANS (tans.c) ---------- */
typedef struct {
    /* decode: for state in [0, L) */
    uint8_t sym[OMC_TANS_L];
    uint8_t nbits[OMC_TANS_L];
    uint16_t base[OMC_TANS_L];
    /* encode */
    uint16_t delta_nbits_hi[OMC_NSYM];   /* (maxBitsOut<<16) - minStatePlus, split */
    int32_t delta_nbits[OMC_NSYM];
    int32_t delta_find[OMC_NSYM];
    uint16_t next_state[OMC_TANS_L];     /* indexed by deltaFind[s] + (state>>nb) */
} omc_tans_table_t;

void omc_tans_init(void);
void omc_crc_init(void); /* build all table sets (idempotent) */
extern omc_tans_table_t omc_tans[OMC_NTABLES][OMC_NCTX];             /* v4.4 */
extern omc_tans_table_t omc_tans_legacy[OMC_NTABLES_LEGACY][OMC_NCTX_LEGACY];
extern omc_tans_table_t omc_tans_q5[OMC_NQ5CTX];   /* Q5F skip-flag field */
extern omc_tans_table_t omc_tans_mv[6];            /* [A1-MVSIG] signalled block-motion field */
extern const uint16_t omc_tans_counts_mv[6][OMC_NSYM];
/* Q5F (env OMC_Q5FLAG): block-skip flag size K in coefficients, 0 = OFF.
 * NORMATIVE when non-zero -- both ends must hold the same value. */
extern int omc_q5flag;
extern int omc_q5measure;
extern int omc_q5greedy;
extern int omc_q5intra;
extern int omc_q5share;

/* v4.4 magnitude-context quantizer: 4 levels {0, 1, 2-3, >=4}.
 * Compares only - no multipliers (C3). */
static inline int omc_q2(int32_t a)
{
    return a == 0 ? 0 : a == 1 ? 1 : a <= 3 ? 2 : 3;
}

/* ---------- bit IO (bitio.c) ---------- */
typedef struct {
    uint8_t *buf;
    size_t cap;      /* bytes */
    uint64_t acc;
    int accbits;
    size_t bytepos;  /* next byte to write */
} omc_bw_t; /* forward LSB-first writer */

void omc_bw_init(omc_bw_t *w, uint8_t *buf, size_t cap);
void omc_bw_put(omc_bw_t *w, uint32_t v, int n);
size_t omc_bw_finish(omc_bw_t *w); /* returns total bits written */

typedef struct {
    const uint8_t *buf;
    int64_t bitpos; /* current end position; reads move it down */
} omc_br_t; /* backward reader: read n bits from the tail */

void omc_br_init(omc_br_t *r, const uint8_t *buf, size_t total_bits);
uint32_t omc_br_get(omc_br_t *r, int n);

/* forward reader for headers */
typedef struct {
    const uint8_t *buf;
    size_t bitpos;
} omc_fr_t;
void omc_fr_init(omc_fr_t *r, const uint8_t *buf);
uint32_t omc_fr_get(omc_fr_t *r, int n);

uint32_t omc_crc32(const uint8_t *p, size_t n);
uint32_t omc_crc32_ext(uint32_t crc_in, const uint8_t *p, size_t n);

/* ---------- quant helpers ---------- */
/* Encoder-side quantizer (decoder never quantizes). In --tune vmaf mode the
 * detail bands round with a slight upward bias (threshold 0.375*2^s instead
 * of 0.5*2^s for s>=3): retains more low-amplitude texture, which VIF/ADM
 * value above the MSE optimum. Fair mode rounds to nearest (MSE-neutral).
 * Reconstruction points stay q<<s either way, so idempotence holds: for
 * r = q<<s, (r + bias) >> s == q because bias < 2^s. */
/* F-2 deadzone (verified +5-8% on real 10-bit masters, no plane losing):
 * widen the zero zone of detail bands 4..9 to 9/16 of a step (from 1/2),
 * reconstruction points untouched (still q<<s) so idempotence and the
 * lattice generation-lock identity are unaffected. 9/16 is the mildest
 * setting that measures; more aggressive settings buy chroma with luma.
 * Off by default; enabled per-encoder via omc_dz_mode (env OMC_DZ=1).
 * Disabled under --tune vmaf at call sites (its 0.375 bias cancels it). */
extern int omc_vext;
extern int omc_vext_lvl;  /* dwt.c sect.55: vertical bottom-edge extension */
extern int omc_dz_mode; /* process default; per-encoder e->dz_enabled decides */
/* OMC_GR grain-replace knob (encoder-only; cfg.grain_replace or env OMC_GR=1): for finest-level
 * bands 7-9 only, coefficients whose PARENT (level-2 co-located) coefficient
 * is essentially zero in the source - i.e. energy with no coarser-scale
 * support, the inter-scale signature of noise rather than structure - get a
 * full-step zero zone instead of 9/16. The killed energy is NOT flattened:
 * the existing amplitude-matched grain fill regenerates it (the fill-bit
 * measurement includes these positions automatically). Structure (parent
 * nonzero) keeps the standard quantizer, LL and bands 1-6 are untouched, and
 * the LL activity gate already excludes flat regions - so gradients, skies
 * and graphics never see this path. Never conditioned on luminance. */
extern int omc_gr_mode;
extern int omc_gr_pthr;
extern int omc_gr_qmax;
extern int omc_gr_notemp;
extern int omc_gr_fillveto;
extern int omc_plan_hyst;
extern int omc_calm;
extern int omc_calm_thr;
extern int omc_calm_amp;
extern int omc_gm_dil;
extern int omc_gm_llhold;
extern int omc_gm_num, omc_gm_den;
extern int omc_gm_mode;
extern int omc_gm_nointra;
extern int omc_gm_replan;
extern int omc_gm_dthr;
extern int omc_gm_watch;
extern int omc_gr_dzoff;
extern int omc_gr_soft_coarse;
extern int omc_gr_intra;
extern int omc_fill_veto_coarse;
extern int omc_gr_soft;
extern int omc_gr_llthr;
extern int omc_gr_carpet;
extern int omc_gr_softcap;

static inline int32_t omc_quant1b_dz(int32_t c, int s, int texture, int dz_band)
{
    if (s == 0) return c;
    int32_t a = c < 0 ? -c : c;
    int32_t bias = (1 << (s - 1)) + ((texture && s >= 3) ? (1 << (s - 3)) : 0);
    int32_t q = (a + bias) >> s;
    if (dz_band && !texture && q == 1 &&
        ((int64_t)a << 4) < ((int64_t)9 << s))
        q = 0;
    return c < 0 ? -q : q;
}
static inline int32_t omc_quant1b(int32_t c, int s, int texture)
{
    if (s == 0) return c;
    int32_t a = c < 0 ? -c : c;
    int32_t bias = (1 << (s - 1)) + ((texture && s >= 3) ? (1 << (s - 3)) : 0);
    int32_t q = (a + bias) >> s;
    return c < 0 ? -q : q;
}
static inline int32_t omc_quant1(int32_t c, int s) { return omc_quant1b(c, s, 1); }
/* texture bias applies to the level-1/2 detail bands only */
#define OMC_BAND_TEXTURE(b) ((b) >= 4)
/* [A2-LOCKCAP] non-improving lock candidates tried before the walk stops.
 * Only counted after a lock exists, so it can never cause a missed lock.
 * 16 restores v4.9's bound; measured byte-identical on 26/26 arms cells. */
#define OMC_LOCK_MAXTRIES 16
extern int omc_recoff;   /* codec.c: centroid dequantisation, n/16 of a step */
/* [G-COEFSAT] Per-band signed width W_b of a dequantised (and, for inter bands,
 * prediction-added) coefficient, derived from the composed L1 analysis gain of
 * OMC's real tree (V1 5/3 | H1 (9,7)-M | V2 5/3 | H2 (9,7)-M | H3 H4 H5 5/3;
 * lowpass 3/2 per stage, highpass 2 for 5/3 and 9/4 for (9,7)-M) on the biased
 * prediction-path input range +-4096, plus the dequantiser overshoot delta/2 at
 * OMC_MAX_SHIFT (16384).  Codec expert reply 003 sect.2.1-2.5, Agent 4
 * notes/band_widths.py, ledger S5.94.  A conformant DECODER saturates every
 * reconstructed coefficient of band b to [-(2^(W_b-1)-1), 2^(W_b-1)-1]; on every
 * legal stream this is provably a no-op (the analysis bound is the reachable set
 * of a conformant encoder), so it cannot touch the generation fixed point; on a
 * corrupted stream it makes the failure bounded and identical across
 * implementations.  These are the numbers a datapath is sized from. */
static const int omc_band_wbits[OMC_NBANDS] = {18, 18, 18, 17, 17, 17, 17, 16, 16, 17};
static inline int32_t omc_sat_band(int32_t v, int b)
{
    const int32_t lim = (1 << (omc_band_wbits[b] - 1)) - 1;
    return v > lim ? lim : (v < -lim ? -lim : v);
}
static inline int32_t omc_dequant1(int32_t q, int s)
{
    int32_t a = q < 0 ? -q : q;
    a <<= s;
    /* CENTROID RECONSTRUCTION (normative when omc_recoff != 0).  The quantiser
     * rounds to nearest, so q<<s is the bin CENTRE.  Wavelet detail coefficients
     * are Laplacian, for which the MMSE reconstruction point lies TOWARD ZERO of
     * the centre — reconstructing at the centre systematically over-states
     * energy, which is exactly what the measured retention shows (finest luma
     * band 0.283 of source against JPEG XS's 0.080) and exactly what VMAF-NEG
     * refuses to credit.  Shift by n/16 of a step: shifts and adds only, and
     * with n < 8 the point stays inside its own bin, so re-quantising the
     * reconstruction still yields q — the generation lock is preserved. */
    if (omc_recoff && a) {
        int32_t d = (omc_recoff << s) >> 4;
        a -= d;
        if (a < 0) a = 0;
    }
    return q < 0 ? -a : a;
}
static inline int omc_cat(int32_t q) /* magnitude category = bit length of |q| */
{
    uint32_t a = (uint32_t)(q < 0 ? -q : q);
    int n = 0;
    while (a) { n++; a >>= 1; } /* per-coefficient priority-encoder in HW */
    return n;
}

/* ---------- normative allocation tables (tables.c) ---------- */
#define OMC_NPROFILES 4
extern const int8_t omc_off[OMC_NPROFILES][OMC_NPLANES][OMC_NBANDS]; /* per-band shift offsets */
extern const int8_t omc_off_c444[OMC_NBANDS];
extern const uint8_t omc_refine_order[][2];             /* (plane, band) steps */
extern const int omc_refine_steps;

/* motion regions per slice (v3.1): each slice is split into OMC_NREG equal
 * horizontal regions, each with its own half-pel motion vector. */
#define OMC_NREG 4
#define OMC_LAT_MAXCH 512 /* lattice work-buffer chunk capacity (per encoder instance) */

/* slice header size in bytes (fixed): 330 bits of fields, zero-padded to 44
 * bytes, then a 4-byte CRC-32 over header+payload at bytes [44, 48). */
#define OMC_SLICE_HDR_BYTES 48

/* ---------- v4 grain fill (bitstream 4.0) ----------
 * Rev. 6 eye-targeted coding: detail-band coefficients that reconstruct to
 * exactly 0 in a band whose header fill bit is set are reconstructed instead
 * as +/- quarter-step, with a normative pseudorandom sign and a local
 * flatness gate. Restores the amplitude/character of sub-threshold texture
 * (film grain) that MSE-optimal quantization erases. Deterministic at both
 * ends (in-loop: the temporal reference includes the fill), idempotent under
 * re-encoding (fill magnitude has tz = s-2, accepted by the generation-lock
 * lattice and requantized to 0, regenerating the identical fill).
 * Fill applies to bands 4..9 (levels 1-2 detail) with shift s >= 3. */
#define OMC_FILL_BANDS_FROM 4
#define OMC_FILL_MIN_SHIFT 3
#define OMC_FILL_GATE 12
/* The ants gate (minor 12): the flattest passing activity tier gets NO fill.
 * A multiplier of 1 is the pre-minor-12 behaviour; see the block comment in
 * fill_gate_g and docs/TEMPORAL_T5.md 13. */
#define OMC_FILL_ANTS_MUL (getenv("OMC_ANTGATE") ? atoi(getenv("OMC_ANTGATE")) : 2)
#define OMC_FILL_ANTS_GATE (OMC_FILL_ANTS_MUL * OMC_FILL_GATE) /* LL local-activity threshold (flat areas stay clean) */
extern int omc_antsgate;  /* codec.c sect.63: the same threshold, tunable */
extern int omc_antsavg;   /* codec.c sect.63b */
extern const int32_t *omc_pll;  /* codec.c sect.64 */
extern int omc_pllw, omc_antshyst;

extern uint32_t omc_sign_tile[256][8]; /* built by omc_tans_init (normative LCG) */
extern uint32_t omc_sign_tile_corr[256][8]; /* v4.5 correlated variant */

static inline int omc_fill_sign(int x, int y) /* 1 => +, 0 => - */
{
    return (int)((omc_sign_tile[y & 255][(x & 255) >> 5] >> (x & 31)) & 1u);
}
static inline int omc_fill_sign_sel(int x, int y, int corr)
{
    const uint32_t (*t)[8] = corr ? omc_sign_tile_corr : omc_sign_tile;
    return (int)((t[y & 255][(x & 255) >> 5] >> (x & 31)) & 1u);
}

/* per-(frame, slice, plane, band) tile offsets: grain animates at frame rate
 * and decorrelates across slices/planes/bands. shifts/adds only. */
static inline void omc_fill_offsets(int fidx8, int slice_idx, int p, int b,
                                    int *fox, int *foy)
{
    int f = fidx8 & 255;
    *fox = ((f << 6) + (f << 5) + f + (b << 4) + (b << 2) + b + (p << 7) - (p << 2)) & 255;
    *foy = ((f << 5) + (f << 4) + (f << 3) + (f << 2) + f +
            (slice_idx << 5) + (slice_idx << 2) + slice_idx) & 255;
}

#endif
