/* omc_pack — slice-aligned packetiser for the OMC-1 elementary stream.
 *
 * Task D part 4, Agent 4.  One or more packets per slice, MTU-bounded, with an
 * RTP-style header (sequence number, timestamp, slice index, first/last flags).
 * Nothing here is codec-specific beyond finding slice boundaries, and nothing
 * in the codec changes: the packetiser is a transport-side tool (constraint D:
 * packetisation is the transport layer's job; the codec stays video-in,
 * bitstream-out).
 *
 * IP: the header is our own 20-byte layout.  It is RTP-SHAPED (the same fields
 * an RTP sender carries) but this tool does not implement RTP, and no
 * SMPTE/IETF payload format is copied.  RTP itself (RFC 3550) and SMPTE
 * ST 2110 are open standards; if the product later carries OMC over RTP the
 * mapping is a specification job, not a licence.
 *
 * Container: every packet on disk is preceded by a 4-byte little-endian
 * length, so the file is a replayable packet trace.
 *
 * The --net-* options are a CHANNEL SIMULATOR for the gates (loss, reordering,
 * duplication).  They are not part of the packetiser; they impair the trace
 * after it is built, which is what a lossy network does.
 *
 * Usage:
 *   omc_pack -i in.omc -o out.pkt [--mtu 1440] [--ticks 90000] [--fps 60]
 *            [--net-loss P] [--net-burst N] [--net-reorder N] [--net-dup P]
 *            [--seed S] [-v]
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "omc_pkt.h"

/* [V536] bounds-checked option value (external adversarial review of v5.3.5, section 7): every
 * value-taking flag used argv[++i]; as the LAST token that is argv[argc] == NULL and the
 * following atoi()/strcmp() dereferenced it -- a segfault in all nine CLIs on a trailing
 * option.  NEXTARG() refuses with a usage error and exit status 1 instead. */
#define NEXTARG() ((i + 1 < argc) ? argv[++i] : \
    (fprintf(stderr, "%s: option %s needs a value\n", argv[0], argv[i]), exit(1), (char *)0))

static void die(const char *m) { fprintf(stderr, "omc_pack: %s\n", m); exit(1); }

/* deterministic 32-bit PRNG (xorshift): the impairment traces must reproduce */
static uint32_t rng_s;
static uint32_t rnd(void) { rng_s ^= rng_s << 13; rng_s ^= rng_s >> 17; rng_s ^= rng_s << 5; return rng_s; }

int main(int argc, char **argv)
{
    const char *inp = NULL, *outp = NULL;
    int mtu = 1440, verbose = 0, reorder_win = 0, net_burst = 1, protect_param = 1;
    double net_loss = 0.0, net_dup = 0.0, fps = 60.0;
    const char *net_lose = NULL;
    uint32_t ticks = 90000;
    rng_s = 12345u;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-i") && i + 1 < argc) inp = NEXTARG();
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) outp = NEXTARG();
        else if (!strcmp(argv[i], "--mtu") && i + 1 < argc) mtu = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--ticks") && i + 1 < argc) ticks = (uint32_t)atoi(NEXTARG());
        else if (!strcmp(argv[i], "--fps") && i + 1 < argc) fps = atof(NEXTARG());
        else if (!strcmp(argv[i], "--net-loss") && i + 1 < argc) net_loss = atof(NEXTARG());
        else if (!strcmp(argv[i], "--net-burst") && i + 1 < argc) net_burst = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--net-reorder") && i + 1 < argc) reorder_win = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--net-dup") && i + 1 < argc) net_dup = atof(NEXTARG());
        else if (!strcmp(argv[i], "--seed") && i + 1 < argc) rng_s = (uint32_t)atoi(NEXTARG()) | 1u;
        else if (!strcmp(argv[i], "--net-drop-param")) protect_param = 0;
        else if (!strcmp(argv[i], "--net-lose") && i + 1 < argc) net_lose = NEXTARG();
        else if (!strcmp(argv[i], "-v")) verbose = 1;
        else die("usage: -i in.omc -o out.pkt [--mtu N] [--net-loss P] "
                 "[--net-burst N] [--net-reorder N] [--net-dup P] [--seed S] [-v]");
    }
    if (!inp || !outp) die("need -i and -o");
    if (mtu <= OMC_PKT_HDR + 16) die("mtu too small");

    FILE *fi = fopen(inp, "rb");
    if (!fi) die("open input");
    if (fseek(fi, 0, SEEK_END) != 0) die("seek");
    long flen = ftell(fi);
    if (flen < OMC_STREAM_HDR32) die("stream shorter than its header");
    rewind(fi);
    uint8_t *buf = malloc((size_t)flen);
    if (!buf) die("oom");
    if (fread(buf, 1, (size_t)flen, fi) != (size_t)flen) die("short read");
    fclose(fi);

    /* frame geometry straight out of the 32-byte stream header, without
     * linking the codec: bits_per_slice and the slice count give frame_bytes. */
    omc_stream_geom_t g;
    if (omc_parse_stream_header(buf, &g) < 0) die("bad stream header");
    if (verbose)
        fprintf(stderr, "stream %dx%d fmt%d depth%d sh=%d slices=%d slice_bytes=%u frame_bytes=%u\n",
                g.width, g.height, g.chroma, g.depth, g.slice_h, g.nslices,
                g.slice_bytes, g.frame_bytes);
    long body = flen - OMC_STREAM_HDR32;
    if (g.frame_bytes == 0 || body % g.frame_bytes)
        die("stream body is not a whole number of frames (geometry mismatch)");
    int nframes = (int)(body / g.frame_bytes);

    /* ---- build the packet list ---- */
    typedef struct { uint8_t *p; int len; int frame, slice; } pk_t;
    pk_t *pks = NULL; int npk = 0, cappk = 0;
    #define PUSH(ptr, l) do { if (npk == cappk) { cappk = cappk ? cappk*2 : 1024; \
        pks = realloc(pks, (size_t)cappk*sizeof(pk_t)); } \
        pks[npk].p = (ptr); pks[npk].len = (l); \
        pks[npk].frame = cur_frame; pks[npk].slice = cur_slice; npk++; } while (0)

    uint16_t seq = 0;
    /* parameter-set generation: one value for a stream whose header never
     * changes, incremented by a sender that changes format mid-stream. */
    unsigned param_gen = 0;
    int cur_frame = 0, cur_slice = -1;
    int payload_max = mtu - OMC_PKT_HDR;
    long slices_seen = 0, frag_total = 0;
    for (int f = 0; f < nframes; f++) {
        const uint8_t *fb = buf + OMC_STREAM_HDR32 + (long)f * g.frame_bytes;
        cur_frame = f; cur_slice = -1;
        uint32_t ts = (uint32_t)((double)f * (double)ticks / fps);
        /* (1) the parameter packet, repeated every frame: it carries the
         * 32-byte stream header plus the frame geometry, so a receiver that
         * joins mid-stream can rebuild frames from the next frame on. */
        {
            int pl = OMC_STREAM_HDR32 + 6;
            uint8_t *pkt = malloc((size_t)(OMC_PKT_HDR + pl));
            omc_pkt_hdr_t h = {0};
            h.type = OMC_PKT_PARAM; h.seq = seq++; h.ts = ts; h.fidx8 = fb[4];
            h.slice = 0xFFFF; h.flags = OMC_PF_FIRST | OMC_PF_LAST;
            h.offset = 0; h.len = (uint16_t)pl; h.gen = (uint16_t)param_gen;
            omc_pkt_put(pkt, &h);
            memcpy(pkt + OMC_PKT_HDR, buf, OMC_STREAM_HDR32);
            uint32_t fbb = g.frame_bytes; uint16_t ns = (uint16_t)g.nslices;
            memcpy(pkt + OMC_PKT_HDR + OMC_STREAM_HDR32, &fbb, 4);
            memcpy(pkt + OMC_PKT_HDR + OMC_STREAM_HDR32 + 4, &ns, 2);
            PUSH(pkt, OMC_PKT_HDR + pl);
        }
        /* (2) one or more packets per slice.  Slice boundaries come from the
         * slice headers themselves: sync word, then used_bits at bit 86. */
        uint32_t off = 0;
        int s_seen = 0;
        while (off + OMC_SLICE_HDR48 <= g.frame_bytes && s_seen < g.nslices) {
            uint32_t sync;
            memcpy(&sync, fb + off, 4);
            if (sync != OMC_SYNC32) break;                 /* end-of-frame pad */
            int sidx = omc_le16(fb + off + 5);             /* bits 40..55 */
            int is_intra = omc_slice_is_intra(fb + off);
            uint32_t used_bits = omc_bits_at(fb + off, 86, 24);
            uint32_t wire = OMC_SLICE_HDR48 + (used_bits + 7) / 8;
            if (off + wire > g.frame_bytes) die("slice runs past the frame");
            cur_slice = sidx;
            uint32_t done = 0;
            while (done < wire) {
                uint32_t take = wire - done;
                if (take > (uint32_t)payload_max) take = (uint32_t)payload_max;
                uint8_t *pkt = malloc((size_t)(OMC_PKT_HDR + take));
                omc_pkt_hdr_t h = {0};
                h.type = OMC_PKT_SLICE; h.seq = seq++; h.ts = ts; h.fidx8 = fb[off + 4];
                h.slice = (uint16_t)sidx;
                h.flags = (done == 0 ? OMC_PF_FIRST : 0) |
                          (done + take >= wire ? OMC_PF_LAST : 0) |
                          ((s_seen == g.nslices - 1 && done + take >= wire) ? OMC_PF_MARKER : 0) |
                          (is_intra ? OMC_PF_INTRA : 0);
                h.offset = off + done; h.len = (uint16_t)take;
                h.gen = (uint16_t)param_gen;
                omc_pkt_put(pkt, &h);
                memcpy(pkt + OMC_PKT_HDR, fb + off + done, take);
                PUSH(pkt, (int)(OMC_PKT_HDR + take));
                done += take; frag_total++;
            }
            off += wire; s_seen++; slices_seen++;
        }
        if (s_seen != g.nslices)
            fprintf(stderr, "omc_pack: WARNING frame %d: found %d slices, expected %d\n",
                    f, s_seen, g.nslices);
    }

    /* ---- channel simulator (gates only) ---- */
    int dropped = 0, duped = 0, moved = 0;
    /* targeted drop: every packet of the named frame:slice ranges, in exactly
     * the syntax omc_dec --lose takes.  This is what makes the depacketiser's
     * loss path comparable, case for case, with the decoder's own loss hook. */
    if (net_lose) {
        const char *q = net_lose;
        while (*q) {
            int f = atoi(q); const char *col = strchr(q, ':');
            if (!col) break;
            int s0 = atoi(col + 1), s1 = s0;
            const char *dsh = strchr(col + 1, '-'), *cm = strchr(col + 1, ',');
            if (dsh && (!cm || dsh < cm)) s1 = atoi(dsh + 1);
            for (int i = 0; i < npk; i++)
                if (pks[i].p && pks[i].frame == f &&
                    pks[i].slice >= s0 && pks[i].slice <= s1) {
                    free(pks[i].p); pks[i].p = NULL; dropped++;
                }
            const char *nx = strchr(q, ','); if (!nx) break; q = nx + 1;
        }
    }
    if (net_loss > 0.0) {
        int i = 0;
        while (i < npk) {
            if ((double)(rnd() >> 8) / 16777216.0 < net_loss) {
                for (int b = 0; b < net_burst && i < npk; b++, i++) {
                    /* PARAM packets are protected by default.  A real
                     * deployment carries the format description out of band
                     * (an SDP-style session description) or repeats it; losing
                     * it costs every frame until the next one arrives, which
                     * this simulator showed the first time it was run.  Use
                     * --net-drop-param to reproduce that. */
                    if (protect_param && pks[i].p && (pks[i].p[1] & 0x0F) == OMC_PKT_PARAM) continue;
                    if (pks[i].p) { free(pks[i].p); pks[i].p = NULL; dropped++; }
                }
            } else i++;
        }
    }
    if (net_dup > 0.0) {
        int n0 = npk;
        for (int i = 0; i < n0; i++)
            if (pks[i].p && (double)(rnd() >> 8) / 16777216.0 < net_dup) {
                uint8_t *c = malloc((size_t)pks[i].len);
                memcpy(c, pks[i].p, (size_t)pks[i].len);
                PUSH(c, pks[i].len); duped++;
                /* place the duplicate near the original */
                pk_t t = pks[npk-1];
                int j = i + 1 + (int)(rnd() % 4); if (j >= npk) j = npk - 1;
                for (int k = npk - 1; k > j; k--) pks[k] = pks[k-1];
                pks[j] = t;
            }
    }
    if (reorder_win > 1) {
        /* BOUNDED reorder: each packet is given a delay of 0..N-1 slots and the
         * trace is stably re-sorted by (arrival index + delay).  Displacement
         * is then at most N-1 -- which is what a network with a bounded
         * reordering depth does, and what the receiver's window is sized
         * against.  (An earlier version swapped neighbours repeatedly; that
         * compounds and lets a packet drift arbitrarily far, so it tested the
         * late-drop path instead of the reorder path.  Kept as a note because
         * it is exactly the kind of test that would have "passed" wrongly.) */
        typedef struct { int idx; long key; } ro_t;
        ro_t *ro = malloc((size_t)npk * sizeof(ro_t));
        for (int i = 0; i < npk; i++) {
            ro[i].idx = i;
            ro[i].key = (long)i * 1024 + (long)(rnd() % (uint32_t)reorder_win) * 1024 + i;
        }
        for (int i = 1; i < npk; i++) {            /* insertion sort: stable */
            ro_t t = ro[i]; int j = i - 1;
            while (j >= 0 && ro[j].key > t.key) { ro[j + 1] = ro[j]; j--; }
            ro[j + 1] = t;
        }
        pk_t *np = malloc((size_t)npk * sizeof(pk_t));
        for (int i = 0; i < npk; i++) {
            np[i] = pks[ro[i].idx];
            if (ro[i].idx != i) moved++;
        }
        memcpy(pks, np, (size_t)npk * sizeof(pk_t));
        free(np); free(ro);
    }

    FILE *fo = fopen(outp, "wb");
    if (!fo) die("open output");
    long wrote = 0;
    for (int i = 0; i < npk; i++) {
        if (!pks[i].p) continue;
        uint32_t l = (uint32_t)pks[i].len;
        if (fwrite(&l, 4, 1, fo) != 1) die("write");
        if (fwrite(pks[i].p, 1, (size_t)l, fo) != (size_t)l) die("write");
        wrote++;
    }
    if (fclose(fo) != 0) die("close output");
    fprintf(stderr, "omc_pack: frames=%d slices=%ld fragments=%ld packets_built=%d "
            "written=%ld mtu=%d payload_max=%d dropped=%d duped=%d reordered=%d\n",
            nframes, slices_seen, frag_total, npk, wrote, mtu, payload_max,
            dropped, duped, moved);
    return 0;
}
