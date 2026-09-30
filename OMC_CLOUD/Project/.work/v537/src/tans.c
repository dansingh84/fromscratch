/* Static-table tANS entropy coder (tabled Asymmetric Numeral Systems).
 * Provenance: ANS by Jarek Duda (2013, released to public domain intent,
 * arXiv:1311.2540); table construction and state machine implemented from
 * the published algorithm description. No adaptive arithmetic coding: all
 * tables are fixed normative constants (tables.c), selected per band by a
 * signaled id. Decode = one table lookup + bit read per symbol. C1/C3-clean.
 */
#include "internal.h"

omc_tans_table_t omc_tans[OMC_NTABLES][OMC_NCTX];
omc_tans_table_t omc_tans_legacy[OMC_NTABLES_LEGACY][OMC_NCTX_LEGACY];
omc_tans_table_t omc_tans_q5[OMC_NQ5CTX];   /* Q5F skip-flag field */
static int tans_ready = 0;

static int highbit(uint32_t v) /* floor(log2(v)), v >= 1 */
{
    int n = 0;
    while (v > 1) { v >>= 1; n++; }
    return n;
}

static void build_table(const uint16_t counts[OMC_NSYM], omc_tans_table_t *t)
{
    const int L = OMC_TANS_L;
    uint8_t spread[OMC_TANS_L];
    /* spread symbols over the state table */
    int step = (L >> 1) + (L >> 3) + 3;
    int pos = 0;
    for (int s = 0; s < OMC_NSYM; s++) {
        for (int i = 0; i < counts[s]; i++) {
            spread[pos] = (uint8_t)s;
            pos = (pos + step) & (L - 1);
        }
    }
    /* decode table */
    uint16_t next[OMC_NSYM];
    for (int s = 0; s < OMC_NSYM; s++) next[s] = counts[s];
    for (int i = 0; i < L; i++) {
        int s = spread[i];
        uint32_t x = next[s]++;
        int nb = OMC_TANS_LBITS - highbit(x);
        t->sym[i] = (uint8_t)s;
        t->nbits[i] = (uint8_t)nb;
        t->base[i] = (uint16_t)((x << nb) - L);
    }
    /* encode table */
    int cumul = 0;
    uint16_t cpos[OMC_NSYM];
    for (int s = 0; s < OMC_NSYM; s++) {
        int c = counts[s];
        if (c == 0) { t->delta_nbits[s] = 0; t->delta_find[s] = 0; continue; }
        int max_bits = (c == 1) ? OMC_TANS_LBITS : (OMC_TANS_LBITS - highbit((uint32_t)c - 1));
        t->delta_nbits[s] = (max_bits << 16) - (c << max_bits);
        t->delta_find[s] = cumul - c;
        cpos[s] = (uint16_t)cumul;
        cumul += c;
    }
    (void)cpos;
    uint16_t fill[OMC_NSYM];
    cumul = 0;
    for (int s = 0; s < OMC_NSYM; s++) { fill[s] = (uint16_t)cumul; cumul += counts[s]; }
    for (int i = 0; i < L; i++) {
        int s = spread[i];
        t->next_state[fill[s]++] = (uint16_t)(L + i);
    }
}

/* v4 grain-fill sign tile (normative). Built once from the fixed LCG below
 * (init-time only - no per-pixel multipliers ever run): 256x256 sign bits,
 * bit (y, x) = bit 30 of the LCG stream. Both ends build the identical tile. */
uint32_t omc_sign_tile[256][8];
uint32_t omc_sign_tile_corr[256][8]; /* v4.5: correlated variant (film grain) */

static void build_sign_tile(void)
{
    uint32_t x = 0x4F4D4331u; /* "OMC1" */
    for (int r = 0; r < 256; r++)
        for (int w = 0; w < 8; w++) {
            uint32_t v = 0;
            for (int bit = 0; bit < 32; bit++) {
                x = x * 1103515245u + 12345u;
                v |= ((x >> 30) & 1u) << bit;
            }
            omc_sign_tile[r][w] = v;
        }
}

/* Correlated sign tile: sign(2x2 box sum of the white +/-1 field) then a
 * checkerboard flip. Yields lag-1 correlation ~ -0.33 horizontal/vertical and
 * positive diagonal - the measured signature of organic film grain (REPORT
 * 17.3: cow -0.34, couch -0.32). Built once at init; both ends identical. */
static void build_sign_tile_corr(void)
{
    for (int y = 0; y < 256; y++)
        for (int x = 0; x < 256; x++) {
            int sum = 0;
            for (int dy = 0; dy < 2; dy++)
                for (int dx = 0; dx < 2; dx++) {
                    int yy = (y + dy) & 255, xx = (x + dx) & 255;
                    sum += ((omc_sign_tile[yy][xx >> 5] >> (xx & 31)) & 1u) ? 1 : -1;
                }
            int b = (sum > 0) || (sum == 0 && ((omc_sign_tile[y][x >> 5] >> (x & 31)) & 1u));
            b ^= (x + y) & 1; /* checkerboard flip: +corr -> -corr h/v */
            if (b) omc_sign_tile_corr[y][x >> 5] |= 1u << (x & 31);
        }
}

/* [A1-MVSIG] MEMO 004: dedicated tANS tables for the signalled block-motion
 * field.  Six tables, all counts summing to OMC_TANS_L (1024):
 *   0..3  block flag, binary, context = 2*l2 + l1 (the two blocks to the left,
 *         the same context shape the Q5F block-skip flags use);
 *   4     dx magnitude category (omc_cat), 5 dy.
 * Built from constants in this file, so both ends build the identical tables;
 * nothing is trained at run time and nothing is carried in the stream.  Every
 * symbol has at least one slot, so no legal value can hit a zero-count symbol.
 * The counts are a first cut: the measured field cost is in the memo, and
 * retuning them is a table change on both ends, not a design change. */
const uint16_t omc_tans_counts_mv[6][OMC_NSYM] = {
    /* Retuned once from the measured symbol histogram of soccer2 and dng 720p at
     * 0.5 bpp (61,472 symbols); the first cut is in the memo with its bit cost. */
    /* flag, no flagged neighbour        */ {856, 154, 1,1,1,1,1,1,1,1,1,1,1,1,1,1},
    /* flag, left flagged                */ {389, 621, 1,1,1,1,1,1,1,1,1,1,1,1,1,1},
    /* flag, left-but-one flagged        */ {626, 384, 1,1,1,1,1,1,1,1,1,1,1,1,1,1},
    /* flag, both flagged                */ {325, 685, 1,1,1,1,1,1,1,1,1,1,1,1,1,1},
    /* dx category                       */ {132, 300, 296, 183, 76, 27, 1,1,1,1,1,1,1,1,1,1},
    /* dy category                       */ {404, 276, 171, 109, 53,  1, 1,1,1,1,1,1,1,1,1,1},
};
omc_tans_table_t omc_tans_mv[6];

void omc_tans_init(void)
{
    if (tans_ready) return;
    for (int x = 0; x < 6; x++) build_table(omc_tans_counts_mv[x], &omc_tans_mv[x]);
    for (int i = 0; i < OMC_NTABLES; i++)
        for (int x = 0; x < OMC_NCTX; x++)
            build_table(omc_tans_counts_v4[i][x], &omc_tans[i][x]);
    for (int i = 0; i < OMC_NTABLES_LEGACY; i++)
        for (int x = 0; x < OMC_NCTX_LEGACY; x++)
            build_table(omc_tans_counts_legacy[i][x], &omc_tans_legacy[i][x]);
    for (int x = 0; x < OMC_NQ5CTX; x++)
        build_table(omc_tans_counts_q5[x], &omc_tans_q5[x]);
    build_sign_tile();
    build_sign_tile_corr();
    tans_ready = 1;
}
