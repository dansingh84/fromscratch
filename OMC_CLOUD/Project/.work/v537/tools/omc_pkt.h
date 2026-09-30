/* omc_pkt.h — the OMC-1 slice packet header, and just enough stream-header
 * parsing to find slice boundaries without linking the codec.
 * Task D part 4, Agent 4.  Transport-side only (constraint D).
 *
 * PACKET HEADER — 20 bytes, little-endian, our own layout.  It carries the
 * same information an RTP sender carries (sequence, timestamp, marker) plus
 * the two things a slice-aligned video codec needs to rebuild a frame from
 * out-of-order fragments: the slice index and the fragment's byte offset
 * inside the frame.  Because the offset is absolute, ANY subset of packets
 * rebuilds the frame correctly at the right addresses, and a missing slice is
 * exactly a hole -- which is what the decoder's --lose hook makes.
 *
 *   off size field
 *   0    1   magic 0x4F ('O')
 *   1    1   version (high nibble, = 1) | type (low nibble)
 *   2    2   sequence number, wraps at 2^16
 *   4    4   timestamp (ticks; one value per frame, like an RTP video frame)
 *   8    1   fidx8 -- the frame phase the slice header itself carries
 *   9    1   flags: b0 first-of-slice, b1 last-of-slice, b2 last-of-frame,
 *              b3 INTRA (this slice codes no inter band)
 *   10   2   slice index (0xFFFF on a parameter packet)
 *   12   4   byte offset of this payload inside the frame
 *   16   2   payload length
 *   18   2   parameter-set generation (PARAM packets: increments whenever the
 *              stream header changes; SLICE packets: the generation they belong
 *              to, so a receiver can reject slices from before a format change)
 *
 * type 0 (SLICE): payload is a fragment of one slice's wire bytes.
 * type 1 (PARAM): payload is the 32-byte OMC stream header, then u32
 *                 frame_bytes, then u16 nslices.  Repeated once per frame so a
 *                 mid-stream join needs no out-of-band description.
 */
#ifndef OMC_PKT_H
#define OMC_PKT_H

#include <stdint.h>
#include <string.h>

#define OMC_PKT_HDR        20
#define OMC_PKT_SLICE       0
#define OMC_PKT_PARAM       1
#define OMC_PKT_VER         1
#define OMC_PF_FIRST     0x01
#define OMC_PF_LAST      0x02
#define OMC_PF_MARKER    0x04
#define OMC_PF_INTRA     0x08   /* the slice codes no inter band: a safe start point */
#define OMC_STREAM_HDR32   32
#define OMC_SLICE_HDR48    48
#define OMC_SYNC32  0x4F4D5331u
#define OMC_MAGIC32 0x4F4D4331u

typedef struct {
    uint8_t  type, flags, fidx8;
    uint16_t seq, slice, len, gen;
    uint32_t ts, offset;
} omc_pkt_hdr_t;

static inline uint16_t omc_le16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static inline uint32_t omc_le32(const uint8_t *p)
{ return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24); }
static inline void omc_pl16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static inline void omc_pl32(uint8_t *p, uint32_t v)
{ p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24); }

static inline void omc_pkt_put(uint8_t *d, const omc_pkt_hdr_t *h)
{
    d[0] = 0x4F;
    d[1] = (uint8_t)((OMC_PKT_VER << 4) | (h->type & 0x0F));
    omc_pl16(d + 2, h->seq);
    omc_pl32(d + 4, h->ts);
    d[8] = h->fidx8;
    d[9] = h->flags;
    omc_pl16(d + 10, h->slice);
    omc_pl32(d + 12, h->offset);
    omc_pl16(d + 16, h->len);
    omc_pl16(d + 18, h->gen);
}

static inline int omc_pkt_get(const uint8_t *d, int avail, omc_pkt_hdr_t *h)
{
    if (avail < OMC_PKT_HDR) return -1;
    if (d[0] != 0x4F) return -1;
    if ((d[1] >> 4) != OMC_PKT_VER) return -1;
    h->type   = (uint8_t)(d[1] & 0x0F);
    h->seq    = omc_le16(d + 2);
    h->ts     = omc_le32(d + 4);
    h->fidx8  = d[8];
    h->flags  = d[9];
    h->slice  = omc_le16(d + 10);
    h->offset = omc_le32(d + 12);
    h->len    = omc_le16(d + 16);
    h->gen    = omc_le16(d + 18);
    if (h->len > avail - OMC_PKT_HDR) return -1;
    return 0;
}

/* Is this slice intra?  The slice header's 30-bit mode mask sits at bit 246
 * (sync 32 + fidx8 8 + slice 16 + Q 4 + prof 2 + n_steps 8 + partial 16 +
 * used_bits 24 + tANS state 16 + 30 group ids x 3 + hash 16 + reserved 14);
 * a zero mask means no band of any plane is inter, i.e. the slice is a safe
 * point for a late joiner or a recovering receiver to start from. */
static inline uint32_t omc_bits_at(const uint8_t *b, size_t pos, int n);
static inline int omc_slice_is_intra(const uint8_t *sl)
{ return omc_bits_at(sl, 246, 30) == 0; }

/* n bits at bit position `pos`, LSB-first inside each byte -- the convention
 * of src/bitio.c's omc_fr_get, which is what wrote the slice header. */
static inline uint32_t omc_bits_at(const uint8_t *b, size_t pos, int n)
{
    uint32_t v = 0;
    for (int i = 0; i < n; i++) {
        size_t p = pos + (size_t)i;
        v |= (uint32_t)((b[p >> 3] >> (p & 7)) & 1u) << i;
    }
    return v;
}

typedef struct {
    int width, height, depth, chroma, slice_h, nslices, refresh_r;
    int fps_num, fps_den, display_width, display_height;
    uint32_t slice_bytes, frame_bytes;
} omc_stream_geom_t;

/* Parse the 32-byte OMC stream header (layout: src/codec.c
 * omc_write_stream_header).  Returns 0, or <0 if the magic is wrong or the
 * geometry is unusable. */
static inline int omc_parse_stream_header(const uint8_t *h, omc_stream_geom_t *g)
{
    if (omc_le32(h) != OMC_MAGIC32) return -1;
    memset(g, 0, sizeof *g);
    g->width   = omc_le16(h + 6);
    g->height  = omc_le16(h + 8);
    g->depth   = h[10];
    g->chroma  = h[11];
    g->slice_h = h[12];
    g->fps_num = omc_le16(h + 13);
    g->fps_den = omc_le16(h + 15);
    uint32_t bps = omc_le32(h + 21);
    g->refresh_r = h[25];
    g->display_height = omc_le16(h + 28);
    g->display_width  = omc_le16(h + 30);
    if (!g->slice_h) g->slice_h = (g->height <= 720) ? 8 : 16;   /* auto */
    if (g->width <= 0 || g->height <= 0 || g->slice_h <= 0) return -2;
    if (bps == 0 || (bps & 7)) return -3;
    g->nslices = g->height / g->slice_h;
    if (g->nslices <= 0) return -4;
    g->slice_bytes = bps / 8;
    g->frame_bytes = g->slice_bytes * (uint32_t)g->nslices;
    return 0;
}

#endif
