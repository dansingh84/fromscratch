/* omc_depack — depacketiser + receive filter for the OMC-1 slice packet
 * stream.  Task D part 4, Agent 4.
 *
 * What it does, in the order it does it:
 *   1. reorders arriving packets inside a BOUNDED window (--window packets);
 *      a packet later than the window is treated as lost and never waited for
 *      -- that is what keeps the receive path's added latency bounded and
 *      deterministic (A2);
 *   2. detects loss by sequence-number gap;
 *   3. drops duplicates and late packets (a sequence older than the last
 *      delivered), so a duplicate or a packet re-ordered past the window can
 *      never corrupt an already-assembled slice;
 *   4. rebuilds each frame at its exact byte layout from the fragments'
 *      absolute frame offsets, leaving a lost slice as a hole of zeros --
 *      byte for byte what `omc_dec --lose` produces;
 *   5. emits the per-slice loss flags: a `--lose`-syntax line for the decoder
 *      hook and a per-frame/per-slice flag file, which is what the Task C
 *      control plane carries back up the return path.
 *
 * Usage:
 *   omc_depack -i in.pkt -o out.omc [--window 32] [--loss-report r.txt]
 *              [--flags flags.txt] [-v]
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

static void die(const char *m) { fprintf(stderr, "omc_depack: %s\n", m); exit(1); }

#define NFSLOT 4

typedef struct {
    int      used;
    uint32_t ts;
    uint8_t  fidx8;
    uint8_t *buf;
    uint32_t *got, *lo, *hi;
    uint8_t  *sawfirst, *sawlast;
    long      order;
} frame_t;

/* ---- file-scope receiver state (one receiver per process) ---- */
static frame_t FR[NFSLOT];
static long frame_order = 0, out_fidx = 0, frames_out = 0;
static long slices_lost_total = 0, slices_total = 0;
static omc_stream_geom_t G;
static int have_geom = 0, verbose = 0;
static FILE *FO, *FL, *FF;
static char *lose_acc; static size_t lose_n;

static int slice_complete(const frame_t *F, int s)
{
    return F->sawfirst[s] && F->sawlast[s] && F->got[s] == (F->hi[s] - F->lo[s]);
}

static void frame_free(frame_t *F)
{
    free(F->buf); free(F->got); free(F->sawfirst);
    free(F->sawlast); free(F->lo); free(F->hi);
    memset(F, 0, sizeof *F);
}

static void frame_flush(int slot)
{
    frame_t *F = &FR[slot];
    if (!F->used) return;
    int runs = 0, s = 0;
    while (s < G.nslices) {
        if (slice_complete(F, s)) { s++; continue; }
        int e = s;
        while (e + 1 < G.nslices && !slice_complete(F, e + 1)) e++;
        char tmp[64];
        if (e == s) snprintf(tmp, sizeof tmp, "%s%ld:%d", lose_n ? "," : "", out_fidx, s);
        else        snprintf(tmp, sizeof tmp, "%s%ld:%d-%d", lose_n ? "," : "", out_fidx, s, e);
        size_t tl = strlen(tmp);
        if (lose_n + tl + 1 < (1u << 16)) { memcpy(lose_acc + lose_n, tmp, tl + 1); lose_n += tl; }
        slices_lost_total += e - s + 1; runs++; s = e + 1;
    }
    slices_total += G.nslices;
    /* A slice that did not arrive whole must leave a HOLE OF ZEROS, not the
     * fragments that did arrive: stray tail bytes of an incomplete slice are
     * meaningless to the decoder and they move its sync-word resync, so the
     * loss report would no longer describe what the decoder actually finds.
     * (Measured: without this the report was right on 11 of 12 frames and 12
     * slices out on the twelfth.)  The span to clear is the gap between the
     * bracketing COMPLETE slices, which the fragments' absolute frame offsets
     * give exactly. */
    {
        int q = 0;
        while (q < G.nslices) {
            if (slice_complete(F, q)) { q++; continue; }
            int e = q;
            while (e + 1 < G.nslices && !slice_complete(F, e + 1)) e++;
            uint32_t lo = 0, hi = G.frame_bytes;
            for (int t = q - 1; t >= 0; t--)
                if (slice_complete(F, t)) { lo = F->hi[t]; break; }
            for (int t = e + 1; t < G.nslices; t++)
                if (slice_complete(F, t)) { hi = F->lo[t]; break; }
            if (hi > lo && hi <= G.frame_bytes) memset(F->buf + lo, 0, hi - lo);
            q = e + 1;
        }
    }
    if (FF) {
        fprintf(FF, "frame %ld fidx8 %u flags ", out_fidx, (unsigned)F->fidx8);
        for (int q = 0; q < G.nslices; q++) fputc(slice_complete(F, q) ? '.' : 'X', FF);
        fputc('\n', FF);
    }
    if (fwrite(F->buf, 1, G.frame_bytes, FO) != G.frame_bytes) die("write frame");
    frames_out++; out_fidx++;
    if (verbose && runs) fprintf(stderr, "omc_depack: frame %ld: %d lost run(s)\n", out_fidx - 1, runs);
    frame_free(F);
}

/* pull the lowest sequence number currently in the reorder window */
static int take_lowest(uint8_t **pk, int *pl, int *win, int *wn)
{
    int best = 0;
    omc_pkt_hdr_t a, b;
    memset(&a, 0, sizeof a); memset(&b, 0, sizeof b);
    for (int q = 1; q < *wn; q++) {
        if (omc_pkt_get(pk[win[q]], pl[win[q]], &a) != 0) continue;
        if (omc_pkt_get(pk[win[best]], pl[win[best]], &b) != 0) { best = q; continue; }
        if ((uint16_t)(a.seq - b.seq) > 32768) best = q;
    }
    int idx = win[best];
    for (int q = best; q + 1 < *wn; q++) win[q] = win[q + 1];
    (*wn)--;
    return idx;
}

static int frame_slot(uint32_t ts, uint8_t fidx8)
{
    for (int q = 0; q < NFSLOT; q++) if (FR[q].used && FR[q].ts == ts) return q;
    int slot = -1;
    for (int q = 0; q < NFSLOT; q++) if (!FR[q].used) { slot = q; break; }
    if (slot < 0) {
        slot = 0;
        for (int q = 1; q < NFSLOT; q++) if (FR[q].order < FR[slot].order) slot = q;
        frame_flush(slot);
    }
    FR[slot].used = 1; FR[slot].ts = ts; FR[slot].fidx8 = fidx8;
    FR[slot].order = frame_order++;
    FR[slot].buf      = calloc(G.frame_bytes, 1);
    FR[slot].got      = calloc((size_t)G.nslices, 4);
    FR[slot].lo       = calloc((size_t)G.nslices, 4);
    FR[slot].hi       = calloc((size_t)G.nslices, 4);
    FR[slot].sawfirst = calloc((size_t)G.nslices, 1);
    FR[slot].sawlast  = calloc((size_t)G.nslices, 1);
    if (!FR[slot].buf || !FR[slot].got) die("oom");
    return slot;
}

int main(int argc, char **argv)
{
    const char *inp = NULL, *outp = NULL, *lossp = NULL, *flagp = NULL;
    int window = 32;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-i") && i + 1 < argc) inp = NEXTARG();
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) outp = NEXTARG();
        else if (!strcmp(argv[i], "--window") && i + 1 < argc) window = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--loss-report") && i + 1 < argc) lossp = NEXTARG();
        else if (!strcmp(argv[i], "--flags") && i + 1 < argc) flagp = NEXTARG();
        else if (!strcmp(argv[i], "-v")) verbose = 1;
        else die("usage: -i in.pkt -o out.omc [--window N] [--loss-report f] [--flags f] [-v]");
    }
    if (!inp || !outp) die("need -i and -o");
    if (window < 1) window = 1;

    FILE *fi = fopen(inp, "rb");
    if (!fi) die("open input");
    uint8_t **pk = NULL; int *pl = NULL; int npk = 0, cap = 0;
    for (;;) {
        uint8_t lb[4];
        size_t r = fread(lb, 1, 4, fi);
        if (r == 0) break;
        if (r != 4) die("truncated length prefix");
        uint32_t l = omc_le32(lb);
        if (l < OMC_PKT_HDR || l > (1u << 20)) die("implausible packet length");
        uint8_t *p = malloc(l);
        if (!p || fread(p, 1, l, fi) != l) die("truncated packet");
        if (npk == cap) { cap = cap ? cap * 2 : 1024;
                          pk = realloc(pk, (size_t)cap * sizeof *pk);
                          pl = realloc(pl, (size_t)cap * sizeof *pl); }
        pk[npk] = p; pl[npk] = (int)l; npk++;
    }
    fclose(fi);

    FO = fopen(outp, "wb");
    if (!FO) die("open output");
    FL = lossp ? fopen(lossp, "w") : NULL;
    FF = flagp ? fopen(flagp, "w") : NULL;
    if (lossp && !FL) die("open loss report");
    if (flagp && !FF) die("open flags file");
    lose_acc = malloc(1 << 16); lose_acc[0] = 0; lose_n = 0;

    int *win = malloc((size_t)window * sizeof(int)); int wn = 0;
    long delivered = 0, dropped_dup = 0, dropped_late = 0, gaps = 0, lost_seq = 0;
    int have_last = 0, have_shdr = 0; uint16_t last_seq = 0;
    uint8_t *seen = calloc(65536, 1);
    uint8_t shdr[OMC_STREAM_HDR32];
    if (!win || !seen) die("oom");

    /* deliver one packet from the window */
    int i;

    for (i = 0; i <= npk; i++) {
        if (i < npk) {
            omc_pkt_hdr_t h;
            if (omc_pkt_get(pk[i], pl[i], &h) != 0) continue;
            if (seen[h.seq]) { dropped_dup++; continue; }
            seen[h.seq] = 1;
            win[wn++] = i;
            if (wn < window) continue;
        } else if (wn == 0) break;
        while (wn > 0) {
            int idx = take_lowest(pk, pl, win, &wn);
            omc_pkt_hdr_t h;
            if (omc_pkt_get(pk[idx], pl[idx], &h) != 0) break;
            if (have_last) {
                int adv = (int)(uint16_t)(h.seq - last_seq);
                if (adv == 0 || adv > 32768) { dropped_late++; break; }
                if (adv > 1) { gaps++; lost_seq += adv - 1; }
            }
            last_seq = h.seq; have_last = 1; delivered++;
            if (h.type == OMC_PKT_PARAM) {
                if (!have_geom && h.len >= OMC_STREAM_HDR32 + 6) {
                    memcpy(shdr, pk[idx] + OMC_PKT_HDR, OMC_STREAM_HDR32);
                    if (omc_parse_stream_header(shdr, &G) < 0) die("bad stream header in PARAM");
                    have_geom = 1; have_shdr = 1;
                    if (fwrite(shdr, 1, OMC_STREAM_HDR32, FO) != OMC_STREAM_HDR32) die("write header");
                }
            } else if (have_geom) {
                int slot = frame_slot(h.ts, h.fidx8);
                frame_t *F = &FR[slot];
                if (h.slice < G.nslices && h.offset + h.len <= G.frame_bytes) {
                    memcpy(F->buf + h.offset, pk[idx] + OMC_PKT_HDR, h.len);
                    F->got[h.slice] += h.len;
                    if (h.flags & OMC_PF_FIRST) { F->sawfirst[h.slice] = 1; F->lo[h.slice] = h.offset; }
                    if (h.flags & OMC_PF_LAST)  { F->sawlast[h.slice] = 1; F->hi[h.slice] = h.offset + h.len; }
                }
            }
            if (i < npk) break;          /* steady state: one in, one out */
        }
    }
    for (;;) {
        int oldest = -1;
        for (int q = 0; q < NFSLOT; q++)
            if (FR[q].used && (oldest < 0 || FR[q].order < FR[oldest].order)) oldest = q;
        if (oldest < 0) break;
        frame_flush(oldest);
    }
    if (fclose(FO) != 0) die("close output");
    if (FL) { fprintf(FL, "%s\n", lose_acc); fclose(FL); }
    if (FF) fclose(FF);
    if (!have_shdr) die("no PARAM packet: cannot rebuild the stream");

    fprintf(stderr, "omc_depack: packets=%d delivered=%ld dup_dropped=%ld late_dropped=%ld "
            "seq_gaps=%ld seq_lost=%ld frames=%ld slices=%ld slices_lost=%ld window=%d\n",
            npk, delivered, dropped_dup, dropped_late, gaps, lost_seq,
            frames_out, slices_total, slices_lost_total, window);
    if (lose_n) fprintf(stderr, "omc_depack: --lose \"%s\"\n", lose_acc);
    return 0;
}
