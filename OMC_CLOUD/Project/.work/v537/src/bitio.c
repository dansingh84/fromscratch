/* Bit IO for OMC-1.
 * Payload streams are written forward LSB-first (encoder walks symbols in
 * reverse), and read BACKWARD from the tail by the decoder — the standard
 * stream-ANS discipline. Headers use a plain forward MSB-first packer.
 */
#include "internal.h"

void omc_bw_init(omc_bw_t *w, uint8_t *buf, size_t cap)
{
    w->buf = buf;
    w->cap = cap;
    w->acc = 0;
    w->accbits = 0;
    w->bytepos = 0;
}

void omc_bw_put(omc_bw_t *w, uint32_t v, int n)
{
    w->acc |= (uint64_t)(v & ((n == 32) ? 0xFFFFFFFFu : ((1u << n) - 1))) << w->accbits;
    w->accbits += n;
    while (w->accbits >= 8) {
        if (w->bytepos < w->cap) w->buf[w->bytepos] = (uint8_t)(w->acc & 0xFF);
        w->bytepos++;
        w->acc >>= 8;
        w->accbits -= 8;
    }
}

size_t omc_bw_finish(omc_bw_t *w)
{
    size_t bits = w->bytepos * 8 + (size_t)w->accbits;
    if (w->accbits > 0) {
        if (w->bytepos < w->cap) w->buf[w->bytepos] = (uint8_t)(w->acc & 0xFF);
        w->bytepos++;
        w->acc = 0;
        w->accbits = 0;
    }
    return bits;
}

/* backward reader over a bit string of length total_bits (write order LSB-first) */
void omc_br_init(omc_br_t *r, const uint8_t *buf, size_t total_bits)
{
    r->buf = buf;
    r->bitpos = (int64_t)total_bits;
}

uint32_t omc_br_get(omc_br_t *r, int n)
{
    if (n == 0) return 0;
    r->bitpos -= n;
    int64_t p = r->bitpos;
    if (p < 0) return 0; /* underflow: corrupt stream; caller CRC-guards */
    size_t byte = (size_t)(p >> 3);
    int off = (int)(p & 7);
    uint64_t window = 0;
    for (int i = 0; i < 6; i++) window |= (uint64_t)r->buf[byte + i] << (8 * i);
    return (uint32_t)((window >> off) & ((n == 32) ? 0xFFFFFFFFu : ((1u << n) - 1)));
}

void omc_fr_init(omc_fr_t *r, const uint8_t *buf)
{
    r->buf = buf;
    r->bitpos = 0;
}

uint32_t omc_fr_get(omc_fr_t *r, int n)
{
    /* LSB-first, mirroring omc_bw_put exactly */
    uint32_t v = 0;
    for (int i = 0; i < n; i++) {
        size_t p = r->bitpos++;
        v |= (uint32_t)((r->buf[p >> 3] >> (p & 7)) & 1) << i;
    }
    return v;
}

/* CRC-32 (IEEE 802.3 polynomial, reflected 0xEDB88320) - table lookup per byte. */
static uint32_t crc_tab[256];
static int crc_ready = 0;

void omc_crc_init(void)
{
    if (crc_ready) return;
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t c = i;
        for (int k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
        crc_tab[i] = c;
    }
    crc_ready = 1;
}

uint32_t omc_crc32_ext(uint32_t crc_in, const uint8_t *p, size_t n)
{
    omc_crc_init();
    uint32_t c = crc_in ^ 0xFFFFFFFFu;
    for (size_t i = 0; i < n; i++) c = crc_tab[(c ^ p[i]) & 0xFF] ^ (c >> 8);
    return c ^ 0xFFFFFFFFu;
}

uint32_t omc_crc32(const uint8_t *p, size_t n) { return omc_crc32_ext(0, p, n); }
