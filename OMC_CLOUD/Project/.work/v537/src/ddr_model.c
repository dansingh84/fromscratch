/* ddr_model.c — see ddr_model.h.  MEASUREMENT INSTRUMENT; must never change a
 * decoded byte.  Task D, Agent 4, 2026-09-04.
 *
 * Three things live here:
 *   1. a DDR service model  — a single-channel, in-order-with-QoS server whose
 *      service time per request is data time + page misses + read/write
 *      turnaround + refresh stalls + a contention term, all deterministic;
 *   2. a BRAM window cache  — a sliding band of rows of the previous-frame
 *      store, per plane, wide enough to hold the reference windows of the
 *      slices in flight; the predictor reads THROUGH it, so a window that is
 *      too small aborts the run instead of quietly producing a number;
 *   3. a slice-ahead prefetch scheduler with an admission rule — slice k is
 *      admitted only when its window is resident, and the wait is recorded.
 */
#define _POSIX_C_SOURCE 200809L
#include "ddr_model.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define MAXP 3

/* ------------------------------------------------------------------ config */

static omc_ddr_cfg_t G;
static int g_inited = 0, g_on = -1;

static double envd(const char *k, double d)
{ const char *v = getenv(k); return v ? atof(v) : d; }
static int envi(const char *k, int d)
{ const char *v = getenv(k); return v ? atoi(v) : d; }

int omc_ddr_active(void)
{
    if (g_on < 0) { const char *v = getenv("OMC_DDR"); g_on = (v && atoi(v)) ? 1 : 0; }
    return g_on;
}

const omc_ddr_cfg_t *omc_ddr_get_cfg(void) { return &G; }
void omc_ddr_set_cfg(const omc_ddr_cfg_t *c) { G = *c; }

/* ------------------------------------------------------- geometry / state */

typedef struct {
    uint16_t *rows;       /* band_rows * pw samples                     */
    const uint16_t *base; /* the frame store this band mirrors          */
    int synth;            /* 1 = charge traffic only, copy nothing      */
    int pw, H;
    int y0, y1;           /* resident row range, inclusive; y1<y0 = empty */
} band_t;

static struct {
    int W, H, Wc, c444, depth, sh, nslices, is_enc;
    double fps;
    char side[8];
    int band_rows;
    int up, dn;                   /* vertical halo above / below            */
    band_t b[2][MAXP];            /* [OMC_DDR_BIND_*][plane]                */
    int frame_idx;
    double t_slice;               /* one slice period, ns                   */
    double t_frame;
    /* server */
    double now, busy_until;
    int    last_dir;              /* 0 read, 1 write, -1 none               */
    long   last_page;
    double refresh_next;
    /* statistics */
    double bytes[OMC_DDR_NKIND];
    double bytes_frame[OMC_DDR_NKIND];
    double peak_frame_bytes, sum_frame_bytes; int nframes;
    double peak_slice_bytes;
    double slice_bytes_acc;
    double worst_wait, sum_wait; long nwait, nstall;
    double worst_wait_ss; long nstall_ss;   /* steady state: frame 0 excluded */
    double win_done[4096];        /* completion time per slice, this frame  */
    double nwin[4096];            /* ... for the NEXT frame's band, prefilled */
    int    shadow_y1;             /* rows of the next frame's band already got */
    long   requests, bursts, refreshes, pagemisses, turns;
    long   resident_hits, resident_miss;
    int    refburst_slice;
    /* compute jitter (Agent 5's question): the encoder pipeline can stall on a
     * slice by an order of magnitude and then sprint to catch up.  pipe_t is
     * where the PIPELINE actually is; the prefetch issue clock is separate. */
    double pipe_t;
    int    reported;
} S;

/* pending request queue */
typedef struct { double issue; int kind, dir; double bytes; int slice; int win; long page0; } req_t;
static req_t *Q; static int qn, qcap, qhead;

static void q_push(double issue, int kind, int dir, double bytes, int slice, int win, long page0)
{
    if (qn >= qcap) { qcap = qcap ? qcap * 2 : 4096; Q = realloc(Q, (size_t)qcap * sizeof(req_t)); }
    Q[qn].issue = issue; Q[qn].kind = kind; Q[qn].dir = dir;
    Q[qn].bytes = bytes; Q[qn].slice = slice; Q[qn].win = win; Q[qn].page0 = page0; qn++;
}

/* --------------------------------------------------------- service model */

static int g_page_bytes = 2048;
static int g_pack = 0;
static int g_pixdma = 1;
static int g_pingpong = 1;
static int g_refburst = 0;
static int g_missevery = 0;
static int g_bankilv = 1;
static int g_packbits = 0;
static int g_bgilv = 1;
static int g_channels = 1;
static double g_stall_x = 0.0;   /* stall multiplier on the stalled slices     */
static int    g_stall_every = 0; /* stall every Nth slice (0 = none)           */
static double g_duty = 0.15;     /* steady compute time as a fraction of T_slice */
static int    g_prefetch_pipe = 0; /* 1 = prefetch follows the PIPELINE (wrong) */

/* N independent DDR channels: the data rate scales with N, and so does the
 * COMMAND rate -- each channel has its own command bus, so the tCCD floor is
 * per channel and N channels can issue N column commands in the same window.
 * (Modelling two channels as one double-width bus, as the first version did,
 * gets the data rate right and the command rate wrong; with tCCD in the model
 * that distinction is the difference between passing and failing at 8K.) */
static double burst_data_ns(void)
{
    return (double)G.burst_bytes
           / ((double)G.bus_bytes * (double)g_channels * G.mt_per_s) * 1e9;
}

/* service one request starting at `start`; returns completion time */
static double service(const req_t *r, double start)
{
    long nb = (long)ceil(r->bytes / (double)G.burst_bytes);
    if (nb < 1) nb = 1;
    double t = start + G.t_base_ns;
    /* read/write turnaround when the bus direction changes */
    if ((S.last_dir >= 0 && S.last_dir != r->dir) || G.model == OMC_DDR_ADVERSARIAL)
        { t += G.t_turn_ns; S.turns++; }
    S.last_dir = r->dir;

    double bd = burst_data_ns();
    /* tCCD — the COLUMN-to-COLUMN command separation, added 2026-09-05 after the
     * codec expert's review.  Within one DDR4 bank group consecutive column
     * commands are separated by tCCD_L = max(5 tCK, 5 ns); across bank groups by
     * tCCD_S = 4 tCK.  At DDR4-3200 the 5 ns floor dominates, so a sequential run
     * that stays inside one bank group runs at ~50 % of pin rate however good the
     * page locality is.  Bank groups exist precisely to expose this, and whether
     * a run rotates through them is a property of the CONTROLLER'S ADDRESS MAP,
     * not of our access pattern -- vendor defaults are often tuned for page-hit
     * locality rather than bank-group rotation.  OMC_DDR_BGILV=1 (default)
     * assumes a bank-group-interleaved map; =0 charges tCCD_L on every burst,
     * which is the honest pessimistic arm. */
    {
        double tck = 2.0 / G.mt_per_s * 1e9;          /* DDR: 2 transfers per clock */
        double tccd_s = 4.0 * tck;
        double tccd_l = 5.0 * tck; if (tccd_l < 5.0) tccd_l = 5.0;
        double floor_ns = (g_bgilv ? tccd_s : tccd_l) / (double)g_channels;
        if (bd < floor_ns) bd = floor_ns;
    }
    if (G.contend_frac > 0.0 && G.contend_frac < 0.95)
        bd /= (1.0 - G.contend_frac);         /* other masters steal bus time */

    long bpp_ = g_page_bytes / G.burst_bytes; if (bpp_ < 1) bpp_ = 1;
    /* tiled layout: a page miss at every tile-row segment boundary */
    long seg_bursts = bpp_;
    if (G.tile_rows > 0) { long sb = 512 / G.burst_bytes; if (sb < 1) sb = 1; seg_bursts = sb; }

    /* Page (row) misses.
     *
     * A reference window in OMC is a set of WHOLE PLANE ROWS, and the frame
     * store is row-major, so one request is a long sequential run: it opens a
     * row, streams it, and crosses a page boundary every page/burst bursts.
     * That is the `seg_bursts` term.
     *
     * The adversarial arm adds ONE more miss per request, for a bank conflict
     * with the interleaved write stream or another master -- the worst a
     * 16-bank DDR4 part can do to a sequential reader that owns its own banks.
     *
     * OMC_DDR_MISSEVERY = N forces a miss every N bursts regardless.  N = 1 is
     * the layout-catastrophe bound (every 64-byte burst lands in a different
     * row): it is what a badly TILED or swizzled frame store would give, and
     * it is reported separately because it is a statement about the layout,
     * not about the codec. */
    long misses;
    if (g_missevery > 0) misses = (nb + g_missevery - 1) / g_missevery;
    else {
        long crossings = (nb - 1) / seg_bursts;   /* page boundaries inside the run */
        misses = 1;                               /* the first ACTIVATE is always paid */
        /* BANK INTERLEAVE.  With the standard address mapping that puts
         * consecutive pages in different banks, a long SEQUENTIAL run
         * ACTIVATEs the next row in another bank while the current one is
         * still streaming, so the page-crossing latency is hidden and only
         * tRRD/tFAW can bite.  One page at burst size b lasts
         * (page/b) * burst_time; while that exceeds tFAW/4 every activate
         * hides.  This is why DDR4 reaches 85-95 % on long reads, and the
         * first cut of this model was wrong to serialise those activates: at
         * 8K it charged 6 page misses per row request and turned a 70 %-of-pin
         * design into a failing one.
         *
         * A TILED store breaks the run into short segments whose addresses are
         * not consecutive, so nothing hides -- that is exactly the cost the
         * tile arm exists to price. */
        int hidden = g_bankilv && G.tile_rows == 0 &&
                     ((double)seg_bursts * bd >= G.t_faw_ns / 4.0);
        if (!hidden) misses += crossings;
        if (G.model == OMC_DDR_ADVERSARIAL) misses += 1;  /* bank conflict with another stream */
    }
    t += (double)misses * G.t_pagemiss_ns;
    S.pagemisses += misses;

    t += (double)nb * bd;
    S.bursts += nb;

    /* Refresh stalls.  A rank refreshes every t_REFI and is unavailable for
     * t_RFC; those are counted by ELAPSED TIME, because the DRAM cannot issue
     * refreshes faster than its own interval no matter what the traffic does.
     * (The first cut of this model forced two refreshes into every row
     * request, which charged ~3x more refresh time than the part can spend
     * refreshing -- an impossible worst case, not a conservative one.)
     *
     * The adversarial arm instead uses the real mechanism that CAN bunch
     * refreshes: DDR4 lets a controller postpone up to 8 refreshes and then
     * issue them back to back.  OMC_DDR_REFBURST of them are placed at the
     * worst moment -- immediately before the request that a window's deadline
     * depends on -- once per window, which is Part 5's "two refresh stalls
     * coincide with a page miss and a contention burst" attack. */
    long nref = 0;
    if (G.t_refi_ns > 0) {
        while (S.refresh_next < t) { nref++; S.refresh_next += G.t_refi_ns; }
    }
    if (g_refburst > 0 && r->win && r->slice != S.refburst_slice) {
        S.refburst_slice = r->slice;
        nref += g_refburst;
    }
    t += (double)nref * G.t_rfc_ns;
    S.refreshes += nref;

    /* the completion of a WINDOW request is what the admission rule waits on */
    if (r->win == 1 && r->slice >= 0 && r->slice < 4096 && t > S.win_done[r->slice])
        S.win_done[r->slice] = t;
    else if (r->win == 2 && r->slice >= 0 && r->slice < 4096 && t > S.nwin[r->slice])
        S.nwin[r->slice] = t;
    S.requests++;
    S.bytes[r->kind] += r->bytes;
    S.bytes_frame[r->kind] += r->bytes;
    S.slice_bytes_acc += r->bytes;
    return t;
}

/* run the server until every request issued at or before `until` is done;
 * returns the completion time of the LAST request belonging to slice `slice`
 * (-1 if none seen). */
static void drain(double until)
{
    while (qhead < qn) {
        /* pick the next request to serve */
        int pick = -1;
        for (int i = qhead; i < qn; i++) {
            if (Q[i].issue > until) continue;
            if (pick < 0) { pick = i; continue; }
            if (G.qos) {   /* reference reads preempt writes */
                int pr_i = (Q[i].kind == OMC_DDR_REF_READ || Q[i].kind == OMC_DDR_MV_READ);
                int pr_p = (Q[pick].kind == OMC_DDR_REF_READ || Q[pick].kind == OMC_DDR_MV_READ);
                if (pr_i && !pr_p) { pick = i; continue; }
                if (pr_p && !pr_i) continue;
            }
            if (Q[i].issue < Q[pick].issue) pick = i;
        }
        if (pick < 0) break;
        double start = S.busy_until > Q[pick].issue ? S.busy_until : Q[pick].issue;
        double done = service(&Q[pick], start);
        S.busy_until = done;
        /* compact: swap the served one to the head */
        req_t tmp = Q[qhead]; Q[qhead] = Q[pick]; Q[pick] = tmp;
        qhead++;
    }
    if (qhead == qn) { qhead = qn = 0; }
}

/* --------------------------------------------------------------- geometry */

int omc_ddr_window_rows(int slice_h, int lead, int mvcap)
{
    int up, dn;
    if (mvcap > 0) { up = mvcap; dn = mvcap + 1; }
    else           { up = 16;    dn = 16; }        /* header field: iy in [-16,15], +1 half-pel tap */
    return (lead + 1) * slice_h + up + dn;
}

/* Bits per stored sample.
 *
 * CORRECTED 2026-09-04 (Fable MEMO 002 5.1).  The first version stored the
 * sample bias-removed in `depth` bits, on the strength of a MEASUREMENT that
 * the committed picture is exactly bias + [0, maxv] over the gamut.  That is
 * what OUR encoder emits; it is not what the FORMAT permits, and a decoder
 * must decode any conformant stream.  The normative bound is the wide-domain
 * clamp the decoder itself enforces in reconstruct_slice():
 *
 *     0 <= committed sample <= maxv + 2 * OMC_REF_BIAS
 *
 * = 4351 / 5119 / 8191 at 8 / 10 / 12-bit, i.e. **13 bits at every depth**.
 * A resource bound that depends on what an encoder chooses to emit is not a
 * bound.  OMC_DDR_PACKBITS overrides for A/B only. */
static int store_bits(void)
{
    if (!g_pack) return 16;
    if (g_packbits > 0) return g_packbits;
    int maxv = (1 << S.depth) - 1;
    int hi = maxv + 2 * 2048;              /* OMC_REF_BIAS */
    int b = 0; while ((1 << b) <= hi) b++;
    return b;
}

static int row_bytes(int pw)
{
    int b = (pw * store_bits() + 7) / 8;
    return ((b + 63) / 64) * 64;
}

/* ------------------------------------------------------------- lifecycle */

void omc_ddr_init(int W, int H, int Wc, int chroma444, int bitdepth,
                  int slice_h, int nslices, double fps, const char *side)
{
    if (!omc_ddr_active() || g_inited) return;
    memset(&S, 0, sizeof S);
    memset(&G, 0, sizeof G);
    G.enabled = 1;
    G.burst_bytes   = envi("OMC_DDR_BURST",   64);
    G.bus_bytes     = envi("OMC_DDR_BUS",     4);
    G.mt_per_s      = envd("OMC_DDR_MTPS",    2400e6);
    G.t_rfc_ns      = envd("OMC_DDR_TRFC",    350.0);
    G.t_refi_ns     = envd("OMC_DDR_TREFI",   7812.5);
    G.t_base_ns     = envd("OMC_DDR_TBASE",   40.0);
    G.t_pagemiss_ns = envd("OMC_DDR_TPAGE",   30.0);
    G.t_turn_ns     = envd("OMC_DDR_TTURN",   10.0);
    G.t_faw_ns      = envd("OMC_DDR_TFAW",    25.0);
    G.contend_frac  = envd("OMC_DDR_CONTEND", 0.0);
    G.model         = envi("OMC_DDR_MODEL",   OMC_DDR_NOMINAL);
    G.lead_slices   = envi("OMC_DDR_LEAD",    1);
    G.tile_rows     = envi("OMC_DDR_TILE",    0);
    G.qos           = envi("OMC_DDR_QOS",     1);
    G.mvcap         = envi("OMC_DDR_MVCAP",   0);
    G.fps           = fps > 0 ? fps : envd("OMC_DDR_FPS", 60.0);
    G.seed          = (unsigned)envi("OMC_DDR_SEED", 1);
    g_page_bytes    = envi("OMC_DDR_PAGE",    2048);
    g_pack          = envi("OMC_DDR_PACK",    0);
    g_pixdma        = envi("OMC_DDR_PIXDMA",  1);
    g_pingpong      = envi("OMC_DDR_PINGPONG", 1);
    /* postponed refreshes bunched at the worst moment: DDR4 allows 8 */
    g_missevery     = envi("OMC_DDR_MISSEVERY", 0);
    g_bankilv       = envi("OMC_DDR_BANKILV",  1);
    g_packbits      = envi("OMC_DDR_PACKBITS", 0);
    g_bgilv         = envi("OMC_DDR_BGILV",   1);
    g_channels      = envi("OMC_DDR_CHANNELS", 1);
    if (g_channels < 1) g_channels = 1;
    g_stall_x       = envd("OMC_DDR_STALLX",  0.0);
    g_stall_every   = envi("OMC_DDR_STALLEVERY", 0);
    g_duty          = envd("OMC_DDR_DUTY",    0.15);
    g_prefetch_pipe = envi("OMC_DDR_PREFETCH_PIPE", 0);
    g_refburst      = envi("OMC_DDR_REFBURST",
                           G.model == OMC_DDR_ADVERSARIAL ? 2 : 0);
    if (G.model == OMC_DDR_CONTENDED && G.contend_frac == 0.0) G.contend_frac = 0.30;

    S.W = W; S.H = H; S.Wc = Wc; S.c444 = chroma444; S.depth = bitdepth;
    S.sh = slice_h; S.nslices = nslices; S.fps = G.fps;
    snprintf(S.side, sizeof S.side, "%s", side ? side : "?");
    S.is_enc = (side && side[0] == 'e');
    if (G.mvcap > 0) { S.up = G.mvcap; S.dn = G.mvcap + 1; }
    else             { S.up = 16;      S.dn = 16; }
    S.band_rows = omc_ddr_window_rows(slice_h, G.lead_slices, G.mvcap);
    S.t_frame = 1e9 / S.fps;
    S.t_slice = S.t_frame / (double)nslices;
    S.last_dir = -1; S.last_page = -1; S.shadow_y1 = -1; S.refburst_slice = -12345;
    S.refresh_next = G.t_refi_ns;
    S.worst_wait = 0;
    for (int w = 0; w < 2; w++)
        for (int p = 0; p < MAXP; p++) {
            int pw = (p == 0) ? W : Wc;
            S.b[w][p].pw = pw; S.b[w][p].H = H;
            S.b[w][p].rows = envi("OMC_DDR_SYNTH", 0) ? NULL
                             : malloc((size_t)S.band_rows * (size_t)pw * 2);
            S.b[w][p].y0 = 0; S.b[w][p].y1 = -1;
        }
    g_inited = 1;
}

void omc_ddr_bind(int which, int plane, const uint16_t *base, int pw, int H)
{
    if (!g_inited || which < 0 || which > 1 || plane < 0 || plane >= MAXP) return;
    S.b[which][plane].base = base; S.b[which][plane].pw = pw; S.b[which][plane].H = H;
    S.b[which][plane].synth = 0;
}

void omc_ddr_bind_synth(int which, int plane, int pw, int H)
{
    if (!g_inited || which < 0 || which > 1 || plane < 0 || plane >= MAXP) return;
    S.b[which][plane].base = (const uint16_t *)1; /* never dereferenced */
    S.b[which][plane].pw = pw; S.b[which][plane].H = H;
    S.b[which][plane].synth = 1;
}

/* fetch rows (y1+1 .. upto) of every plane of band `which`, issued at `issue`,
 * charged to traffic class `kind`, attributed to slice `slice`. */
static void band_fetch(int which, int upto, double issue, int kind, int slice, int win)
{
    if (upto > S.H - 1) upto = S.H - 1;
    for (int p = 0; p < MAXP; p++) {
        band_t *b = &S.b[which][p];
        if (!b->base) continue;
        int from = b->y1 + 1;
        if (from < 0) from = 0;
        for (int y = from; y <= upto; y++) {
            if (!b->synth) {
                int slot = y % S.band_rows;
                memcpy(b->rows + (size_t)slot * b->pw, b->base + (size_t)y * b->pw,
                       (size_t)b->pw * 2);
            }
            /* which slice's window does row y complete?  The window of slice s
             * ends at s*sh + sh - 1 + dn, so row y is owned by the first s
             * whose window reaches it.  Tagging per row (not per fetch) is what
             * makes the frame-boundary refill charge the right deadlines. */
            int tag = slice;
            if (win) {
                int num = y - S.sh + 1 - S.dn;
                tag = num <= 0 ? 0 : (num + S.sh - 1) / S.sh;
                if (tag >= S.nslices) tag = S.nslices - 1;
            }
            q_push(issue, kind, 0, row_bytes(b->pw), tag, win, (long)y);
        }
        if (upto > b->y1) b->y1 = upto;
        if (b->y1 - b->y0 + 1 > S.band_rows) b->y0 = b->y1 - S.band_rows + 1;
    }
}

void omc_ddr_frame_begin(int frame_idx)
{
    if (!g_inited) return;
    if (S.nframes > 0 || frame_idx > 0) {
        if (S.bytes_frame[0] + S.bytes_frame[1] + S.bytes_frame[2] +
            S.bytes_frame[3] + S.bytes_frame[4] > 0) {
            double tot = 0; for (int k = 0; k < OMC_DDR_NKIND; k++) tot += S.bytes_frame[k];
            if (tot > S.peak_frame_bytes) S.peak_frame_bytes = tot;
            S.sum_frame_bytes += tot; S.nframes++;
        }
    }
    memset(S.bytes_frame, 0, sizeof S.bytes_frame);
    S.frame_idx = frame_idx;
    /* the reference picture changes: the band restarts at the top of the frame.
     * Rows [0 .. band_rows-1] of the new reference were committed early in the
     * PREVIOUS frame, so a real design refills them during that frame's last
     * slices through a second (ping-pong) band.  Modelled as issued one band
     * fill-time before the frame starts; the cost is counted either way. */
    for (int w = 0; w < 2; w++)
        for (int p = 0; p < MAXP; p++) { S.b[w][p].y0 = 0; S.b[w][p].y1 = -1; }
    double t0 = (double)frame_idx * S.t_frame;
    S.now = t0;
    int need = (G.lead_slices + 1) * S.sh - 1 + S.dn;
    /* OMC_DDR_PINGPONG=1 (default): a second band buffer lets the top of the
     * NEXT reference picture be refilled at the steady rate during the last
     * `fill_slices` slices of the current frame (issued by slice_header
     * below), so the frame boundary costs no burst -- 2x band BRAM.
     * =0: one band only, and the whole refill lands in one slice period at
     * the frame boundary, which is where the peak comes from. */
    if (g_pingpong && S.shadow_y1 >= need) {
        for (int k = 0; k < S.nslices && k < 4096; k++) S.win_done[k] = S.nwin[k];
        for (int p = 0; p < MAXP; p++) {
            band_t *b = &S.b[OMC_DDR_BIND_PREV][p];
            if (!b->base) continue;
            /* rows were charged during the previous frame; mirror them now */
            if (!b->synth)
                for (int y = 0; y <= need && y <= S.H - 1; y++)
                    memcpy(b->rows + (size_t)(y % S.band_rows) * b->pw,
                           b->base + (size_t)y * b->pw, (size_t)b->pw * 2);
            b->y1 = (need > S.H - 1) ? S.H - 1 : need;
            if (b->y1 - b->y0 + 1 > S.band_rows) b->y0 = b->y1 - S.band_rows + 1;
        }
    } else {
        for (int k = 0; k < S.nslices && k < 4096; k++) S.win_done[k] = 0;
        band_fetch(OMC_DDR_BIND_PREV, need, t0, OMC_DDR_REF_READ, 0, 1);
    }
    for (int k = 0; k < S.nslices && k < 4096; k++) S.nwin[k] = 0;
    S.shadow_y1 = -1;
}

void omc_ddr_slice_header(int slice_idx)
{
    if (!g_inited) return;
    /* THE RULE (made explicit after Agent 5's question): the prefetch is issued
     * on the REAL-TIME slice schedule, not on the pipeline's own progress.  A
     * pipeline that stalls and then sprints to catch up therefore finds its
     * windows already resident and reads them from BRAM; the prefetch can
     * never be dragged into a sprint.  OMC_DDR_PREFETCH_PIPE=1 builds the
     * wrong design (prefetch chained to the pipeline) so the difference can be
     * measured rather than argued. */
    double rt = (double)S.frame_idx * S.t_frame + (double)slice_idx * S.t_slice;
    double t = g_prefetch_pipe ? (S.pipe_t > rt ? S.pipe_t : rt) : rt;
    S.now = t;
    int s = slice_idx + G.lead_slices;
    if (s < S.nslices) {
        int upto = s * S.sh + S.sh - 1 + S.dn;
        S.win_done[s] = 0;
        band_fetch(OMC_DDR_BIND_PREV, upto, t, OMC_DDR_REF_READ, s, 1);
    }
    /* cross-frame prefetch: over the last `fill_slices` slices of this frame,
     * pull the top `need` rows of the NEXT reference picture into the shadow
     * band at the steady rate.  Those rows were committed early in THIS frame,
     * so they exist.  Charged to the same channel; deadlines land on the next
     * frame's slice windows (S.nwin). */
    if (g_pingpong) {
        int need = (G.lead_slices + 1) * S.sh - 1 + S.dn;

        int fill_slices = (S.band_rows + S.sh - 1) / S.sh;
        int first = S.nslices - fill_slices; if (first < 0) first = 0;
        if (slice_idx >= first) {
            int step = slice_idx - first + 1;
            int target = (int)(((long)need + 1) * step / (S.nslices - first)) - 1;
            if (target > need) target = need;
            if (target > S.H - 1) target = S.H - 1;
            band_t *b = &S.b[OMC_DDR_BIND_PREV][0];
            for (int y = S.shadow_y1 + 1; y <= target; y++) {
                int num = y - S.sh + 1 - S.dn;
                int tag = num <= 0 ? 0 : (num + S.sh - 1) / S.sh;
                if (tag >= S.nslices) tag = S.nslices - 1;
                for (int p = 0; p < MAXP; p++) {
                    band_t *bp = &S.b[OMC_DDR_BIND_PREV][p];
                    if (!bp->base) continue;
                    q_push(t, OMC_DDR_REF_READ, 0, row_bytes(bp->pw), tag, 2, (long)y);
                }
                (void)b;
            }
            if (target > S.shadow_y1) S.shadow_y1 = target;
        }
    }
}

double omc_ddr_admit(int slice_idx)
{
    if (!g_inited) return 0.0;
    /* Where the PIPELINE actually reaches this slice.  With no jitter this is
     * the real-time schedule and nothing changes. */
    double rt = (double)S.frame_idx * S.t_frame + (double)slice_idx * S.t_slice;
    double deadline = rt;
    if (g_stall_every > 0 && g_stall_x > 0.0) {
        if (slice_idx == 0 && S.frame_idx == 0) S.pipe_t = 0.0;
        double compute = g_duty * S.t_slice;
        if (g_stall_every > 0 && (slice_idx % g_stall_every) == 0)
            compute *= g_stall_x;
        double start = S.pipe_t > rt ? S.pipe_t : rt;   /* never before its data */
        deadline = start;
        S.pipe_t = start + compute;
    }
    drain(deadline);
    double done = 0.0;   /* a window is resident only when every row up to it is */
    for (int k = 0; k <= slice_idx && k < 4096; k++)
        if (S.win_done[k] > done) done = S.win_done[k];
    double wait = 0.0;
    if (done > deadline) wait = done - deadline;
    if (wait > S.worst_wait) S.worst_wait = wait;
    S.sum_wait += wait; S.nwait++;
    if (wait > 0) S.nstall++;
    /* frame 0 has no previous picture at all (every slice is intra and no
     * reference is read); its band fill is a stream-start transient, so the
     * steady-state figures exclude it. */
    if (S.frame_idx > 0) {
        if (wait > S.worst_wait_ss) S.worst_wait_ss = wait;
        if (wait > 0) S.nstall_ss++;
    }
    if (S.slice_bytes_acc > S.peak_slice_bytes) S.peak_slice_bytes = S.slice_bytes_acc;
    S.slice_bytes_acc = 0;
    return wait;
}

const uint16_t *omc_ddr_ref_row(int plane, int y, const uint16_t *fallback)
{
    if (!g_inited || plane < 0 || plane >= MAXP) return fallback;
    band_t *b = &S.b[OMC_DDR_BIND_PREV][plane];
    if (!b->base) return fallback;
    if (y < b->y0 || y > b->y1) {
        S.resident_miss++;
        fprintf(stderr, "OMC_DDR FATAL: reference row %d not resident "
                "(band %d..%d, %d rows, slice_h %d, lead %d, mvcap %d)\n",
                y, b->y0, b->y1, S.band_rows, S.sh, G.lead_slices, G.mvcap);
        abort();
    }
    S.resident_hits++;
    return b->rows + (size_t)(y % S.band_rows) * b->pw;
}

void omc_ddr_mv_band(int slice_idx)
{
    /* The encoder's derive_mv reads slice k's rows of N-1 (already resident in
     * the prediction band: no extra DDR traffic) against the SAME band of the
     * N-2 store, which is a second frame store and therefore real traffic.
     * Luma only -- the search never touches chroma. */
    if (!g_inited) return;
    double t = (double)S.frame_idx * S.t_frame + (double)slice_idx * S.t_slice;
    band_t *b = &S.b[OMC_DDR_BIND_PREV2][0];
    if (!b->base) return;
    int upto = slice_idx * S.sh + S.sh - 1 + S.dn;
    if (upto > S.H - 1) upto = S.H - 1;
    int from = b->y1 + 1; if (from < 0) from = 0;
    for (int y = from; y <= upto; y++)
        q_push(t, OMC_DDR_MV_READ, 0, row_bytes(b->pw), slice_idx, 0, (long)y);
    if (upto > b->y1) b->y1 = upto;
    if (b->y1 - b->y0 + 1 > S.band_rows) b->y0 = b->y1 - S.band_rows + 1;
}

void omc_ddr_commit(int slice_idx)
{
    if (!g_inited) return;
    double t = (double)S.frame_idx * S.t_frame + (double)slice_idx * S.t_slice;
    for (int p = 0; p < MAXP; p++) {
        int pw = (p == 0) ? S.W : S.Wc;
        for (int r = 0; r < S.sh; r++)
            q_push(t + S.t_slice, OMC_DDR_RECON_WR, 1, row_bytes(pw), slice_idx, 0, 0);
    }
}

/* The capture / output pixel paths.
 *
 * OMC_DDR_PIXDMA = 1 (default, and what MEMO 001 part 4 asks to include):
 * the SoC stages video through DDR on both sides -- the encoder's capture DMA
 * writes the incoming frame and the transform reads it back; the decoder's
 * output DMA reads the committed frame for the display raster.
 *
 * OMC_DDR_PIXDMA = 0: both are line-buffered on chip.  That is legitimate for
 * OMC because the codec's own cadence IS the line cadence -- the encoder
 * consumes exactly slice_h source lines per slice period and the decoder
 * produces exactly slice_h lines per slice period -- so a 2*slice_h line
 * buffer on each side replaces a whole frame's round trip.  Both arms are
 * measured; see the tables in the memo. */
void omc_ddr_pixel_dma(int slice_idx)
{
    if (!g_inited || !g_pixdma) return;
    double t = (double)S.frame_idx * S.t_frame + (double)slice_idx * S.t_slice;
    for (int p = 0; p < MAXP; p++) {
        int pw = (p == 0) ? S.W : S.Wc;
        for (int r = 0; r < S.sh; r++) {
            if (S.is_enc) {
                q_push(t, OMC_DDR_CAP_WR, 1, row_bytes(pw), slice_idx, 0, 0);
                q_push(t, OMC_DDR_OUT_RD, 0, row_bytes(pw), slice_idx, 0, 0); /* source read-back */
            } else {
                q_push(t, OMC_DDR_OUT_RD, 0, row_bytes(pw), slice_idx, 0, 0); /* display read */
            }
        }
    }
}

void omc_ddr_finish(void)
{
    if (!g_inited || S.reported) return;
    S.reported = 1;
    drain(1e18);
    double tot = 0; for (int k = 0; k < OMC_DDR_NKIND; k++) tot += S.bytes_frame[k];
    if (tot > 0) { if (tot > S.peak_frame_bytes) S.peak_frame_bytes = tot;
                   S.sum_frame_bytes += tot; S.nframes++; }
    FILE *f = stderr;
    const char *lg = getenv("OMC_DDR_LOG");
    if (lg) { FILE *g = fopen(lg, "a"); if (g) f = g; }

    const char *kn[] = { "refread", "mvread", "reconwr", "capwr", "outrd" };
    fprintf(f, "DDR side=%s %dx%d sh=%d ns=%d fps=%.2f band=%drows lead=%d "
               "burst=%d bus=x%d model=%d contend=%.2f qos=%d mvcap=%d pack=%d pixdma=%d pp=%d refburst=%d missevery=%d bankilv=%d bgilv=%d ch=%d storebits=%d\n",
            S.side, S.W, S.H, S.sh, S.nslices, S.fps, S.band_rows, G.lead_slices,
            G.burst_bytes, G.bus_bytes * 8, G.model, G.contend_frac, G.qos, G.mvcap, g_pack, g_pixdma, g_pingpong, g_refburst, g_missevery, g_bankilv, g_bgilv, g_channels, store_bits());
    for (int k = 0; k < OMC_DDR_NKIND; k++)
        fprintf(f, "DDR bytes %-8s %.0f\n", kn[k], S.bytes[k]);
    double mean_frame = S.nframes ? S.sum_frame_bytes / S.nframes : 0;
    fprintf(f, "DDR frames=%d meanframebytes=%.0f peakframebytes=%.0f peakslicebytes=%.0f\n",
            S.nframes, mean_frame, S.peak_frame_bytes, S.peak_slice_bytes);
    fprintf(f, "DDR bw_mean_GBs=%.3f bw_peak_GBs=%.3f peak_pinrate_GBs=%.3f\n",
            mean_frame * S.fps / 1e9, S.peak_frame_bytes * S.fps / 1e9,
            (double)G.bus_bytes * (double)g_channels * G.mt_per_s / 1e9);
    fprintf(f, "DDR t_slice_ns=%.1f worstwait_ns=%.1f meanwait_ns=%.2f stalls=%ld/%ld margin_ns=%.1f\n",
            S.t_slice, S.worst_wait_ss, S.nwait ? S.sum_wait / S.nwait : 0.0,
            S.nstall_ss, S.nwait, (double)G.lead_slices * S.t_slice - S.worst_wait_ss);
    fprintf(f, "DDR startup_wait_ns=%.1f startup_stalls=%ld\n",
            S.worst_wait, S.nstall);
    fprintf(f, "DDR requests=%ld bursts=%ld refreshes=%ld pagemisses=%ld turnarounds=%ld "
               "rowhits=%ld rowmiss=%ld\n",
            S.requests, S.bursts, S.refreshes, S.pagemisses, S.turns,
            S.resident_hits, S.resident_miss);
    /* BRAM accounting.
     *
     * Steady state the cache is a sliding band of (lead+1)*sh + up + dn rows.
     * At a FRAME BOUNDARY two pictures are live at once: the last slices of
     * the outgoing frame still read its bottom window (sh + up + dn rows)
     * while the cross-frame prefetch is already pulling the top of the
     * incoming one ((lead+1)*sh + dn + 1 rows).  The ring must hold both, so
     * the part is sized on
     *
     *   ring_rows = max( band_rows , (sh + up + dn) + ((lead+1)*sh + dn + 1) )
     *
     * which at sh 16, lead 1 and the full +-16 px vector range is 96 rows, not
     * 64.  Reporting the steady band alone understates the BRAM by 1.5x.
     *
     * The samples are stored BIAS-REMOVED, `depth` bits each: the committed
     * picture measured over the gamut is exactly bias + [0, maxv] (the
     * legality-by-construction step guarantees it), so no guard bit is needed
     * while that step is in the build. */
    /* With the cross-frame prefetch (ping-pong) the ring must hold the
     * outgoing picture's bottom window AND the incoming picture's top at the
     * same time.  WITHOUT it the ring is just the steady band and the frame
     * boundary is paid as a stall instead -- which is a real trade, not a free
     * one, and the margin line above is what prices it. */
    int ring_rows = S.band_rows;
    if (g_pingpong) {
        int bound = (S.sh + S.up + S.dn) + ((G.lead_slices + 1) * S.sh + S.dn + 1);
        if (bound > ring_rows) ring_rows = bound;
    }
    double band_bits = 0, ring_bits = 0;
    for (int p = 0; p < MAXP; p++) {
        int pw = (p == 0) ? S.W : S.Wc;
        band_bits += (double)S.band_rows * pw * store_bits();
        ring_bits += (double)ring_rows   * pw * store_bits();
    }
    fprintf(f, "DDR bram_band_bits=%.0f (%.2f Mbit, %d rows) "
               "bram_ring_bits=%.0f (%.2f Mbit, %d rows incl. the frame boundary)\n",
            band_bits, band_bits / 1e6, S.band_rows,
            ring_bits, ring_bits / 1e6, ring_rows);
    if (f != stderr) fclose(f);
}
