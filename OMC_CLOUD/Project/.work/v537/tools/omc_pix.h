/* omc_pix.h — pixel packing / unpacking between the codec's plane buffers and
 * the two layouts a broadcast FPGA actually meets on its pins.
 * Task D part 4, Agent 4.  Transport/interface side only (constraint D).
 *
 * LAYOUT "2110" — SMPTE ST 2110-20 pgroups.  A pgroup is the smallest whole
 * number of pixels that occupies a whole number of octets; samples inside it
 * are concatenated MSB-first with no padding, in the sampling system's sample
 * order (C'B, Y'0, C'R, Y'1 for 4:2:2; C'B, Y', C'R for 4:4:4).
 *
 *   fmt   depth   pgroup      pixels   samples
 *   4:2:2   8      4 bytes      2         4
 *   4:2:2  10      5 bytes      2         4
 *   4:2:2  12      6 bytes      2         4
 *   4:4:4   8      3 bytes      1         3
 *   4:4:4  10     15 bytes      4        12
 *   4:4:4  12      9 bytes      2         6
 *
 * LAYOUT "sdi10" — what an SDI receiver hands the fabric: the 10-bit words in
 * SDI multiplex order, one word per 16-bit lane, little-endian, value in the
 * low 10 bits.  Two bytes per sample, no bit packing.  Included because it is
 * the other interface the encoder's capture side and the decoder's output side
 * meet, and its buffer/latency cost differs from 2110's.
 *
 * ST 2110 is an open SMPTE standard and this is an implementation of a public
 * octet layout, not of anyone's codec internals (C1).
 *
 * Codec side is planar 16-bit little-endian, value right-justified: exactly
 * what omc_enc reads and omc_dec writes.
 */
#ifndef OMC_PIX_H
#define OMC_PIX_H

#include <stdint.h>
#include <string.h>

#define OMC_PIXL_2110  0
#define OMC_PIXL_SDI10 1

typedef struct {
    int layout, chroma444, depth, width;
    int pg_pixels, pg_bytes, pg_samples;
    long line_bytes;
    long line_samples;
} omc_pix_geom_t;

static inline int omc_pix_geom(int layout, int chroma444, int depth, int width,
                               omc_pix_geom_t *g)
{
    memset(g, 0, sizeof *g);
    g->layout = layout; g->chroma444 = chroma444; g->depth = depth; g->width = width;
    if (depth != 8 && depth != 10 && depth != 12) return -1;
    if (width <= 0) return -2;
    if (!chroma444 && (width & 1)) return -3;
    if (layout == OMC_PIXL_SDI10) {
        if (depth != 10) return -4;
        g->pg_pixels = chroma444 ? 1 : 2;
        g->pg_samples = chroma444 ? 3 : 4;
        g->pg_bytes = g->pg_samples * 2;
    } else {
        if (!chroma444) { g->pg_pixels = 2; g->pg_samples = 4;
                          g->pg_bytes = depth == 8 ? 4 : (depth == 10 ? 5 : 6); }
        else if (depth == 8)  { g->pg_pixels = 1; g->pg_samples = 3;  g->pg_bytes = 3; }
        else if (depth == 10) { g->pg_pixels = 4; g->pg_samples = 12; g->pg_bytes = 15; }
        else                  { g->pg_pixels = 2; g->pg_samples = 6;  g->pg_bytes = 9; }
    }
    if (width % g->pg_pixels) return -5;
    g->line_bytes  = (long)(width / g->pg_pixels) * g->pg_bytes;
    g->line_samples = chroma444 ? (long)width * 3 : (long)width * 2;
    return 0;
}

static inline void omc_pbw(uint8_t *b, size_t bitpos, int n, uint32_t v)
{
    for (int i = n - 1; i >= 0; i--) {
        size_t p = bitpos++;
        uint8_t m = (uint8_t)(0x80u >> (p & 7));
        if ((v >> i) & 1u) b[p >> 3] |= m; else b[p >> 3] = (uint8_t)(b[p >> 3] & ~m);
    }
}
static inline uint32_t omc_pbr(const uint8_t *b, size_t bitpos, int n)
{
    uint32_t v = 0;
    for (int i = 0; i < n; i++) {
        size_t p = bitpos + (size_t)i;
        v = (v << 1) | (uint32_t)((b[p >> 3] >> (7 - (p & 7))) & 1u);
    }
    return v;
}

static inline void omc_pix_pack_line(const omc_pix_geom_t *g,
                                     const uint16_t *y, const uint16_t *cb,
                                     const uint16_t *cr, uint8_t *out)
{
    int W = g->width, d = g->depth;
    uint32_t mask = (uint32_t)((1u << d) - 1u);
    if (g->layout == OMC_PIXL_SDI10) {
        long o = 0;
        for (int x = 0; x < W; x++) {
            if (g->chroma444) {
                uint16_t s[3] = { (uint16_t)(cb[x] & mask), (uint16_t)(y[x] & mask),
                                  (uint16_t)(cr[x] & mask) };
                for (int k = 0; k < 3; k++) { out[o++] = (uint8_t)s[k]; out[o++] = (uint8_t)(s[k] >> 8); }
            } else if ((x & 1) == 0) {
                uint16_t s[4] = { (uint16_t)(cb[x >> 1] & mask), (uint16_t)(y[x] & mask),
                                  (uint16_t)(cr[x >> 1] & mask), (uint16_t)(y[x + 1] & mask) };
                for (int k = 0; k < 4; k++) { out[o++] = (uint8_t)s[k]; out[o++] = (uint8_t)(s[k] >> 8); }
            }
        }
        return;
    }
    memset(out, 0, (size_t)g->line_bytes);
    size_t bit = 0;
    if (!g->chroma444) {
        for (int x = 0; x < W; x += 2) {
            omc_pbw(out, bit, d, cb[x >> 1] & mask); bit += d;
            omc_pbw(out, bit, d, y[x]       & mask); bit += d;
            omc_pbw(out, bit, d, cr[x >> 1] & mask); bit += d;
            omc_pbw(out, bit, d, y[x + 1]   & mask); bit += d;
        }
    } else {
        for (int x = 0; x < W; x++) {
            omc_pbw(out, bit, d, cb[x] & mask); bit += d;
            omc_pbw(out, bit, d, y[x]  & mask); bit += d;
            omc_pbw(out, bit, d, cr[x] & mask); bit += d;
        }
    }
}

static inline void omc_pix_unpack_line(const omc_pix_geom_t *g, const uint8_t *in,
                                       uint16_t *y, uint16_t *cb, uint16_t *cr)
{
    int W = g->width, d = g->depth;
    if (g->layout == OMC_PIXL_SDI10) {
        long o = 0;
        for (int x = 0; x < W; x++) {
            if (g->chroma444) {
                cb[x] = (uint16_t)(in[o] | (in[o+1] << 8)); o += 2;
                y[x]  = (uint16_t)(in[o] | (in[o+1] << 8)); o += 2;
                cr[x] = (uint16_t)(in[o] | (in[o+1] << 8)); o += 2;
            } else if ((x & 1) == 0) {
                cb[x >> 1] = (uint16_t)(in[o] | (in[o+1] << 8)); o += 2;
                y[x]       = (uint16_t)(in[o] | (in[o+1] << 8)); o += 2;
                cr[x >> 1] = (uint16_t)(in[o] | (in[o+1] << 8)); o += 2;
                y[x + 1]   = (uint16_t)(in[o] | (in[o+1] << 8)); o += 2;
            }
        }
        return;
    }
    size_t bit = 0;
    if (!g->chroma444) {
        for (int x = 0; x < W; x += 2) {
            cb[x >> 1] = (uint16_t)omc_pbr(in, bit, d); bit += d;
            y[x]       = (uint16_t)omc_pbr(in, bit, d); bit += d;
            cr[x >> 1] = (uint16_t)omc_pbr(in, bit, d); bit += d;
            y[x + 1]   = (uint16_t)omc_pbr(in, bit, d); bit += d;
        }
    } else {
        for (int x = 0; x < W; x++) {
            cb[x] = (uint16_t)omc_pbr(in, bit, d); bit += d;
            y[x]  = (uint16_t)omc_pbr(in, bit, d); bit += d;
            cr[x] = (uint16_t)omc_pbr(in, bit, d); bit += d;
        }
    }
}

#endif
