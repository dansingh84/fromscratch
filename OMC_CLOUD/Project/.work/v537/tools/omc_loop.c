/* [S3-REFRESH] omc_loop — the closed loop in one process: encoder, a lossy
 * link, decoder, and the control plane's return path (decoder state report ->
 * encoder refresh request after a round-trip delay).  Measures, per frame,
 * which slices of the decoder's emitted picture differ from the encoder's.
 *
 * usage: omc_loop -i in.yuv -w W -h H [--fmt 422|444] [--depth 10] [--bpp B]
 *                 [-n N] [--refresh none|R] [--lose f:s[-s2],...] [--rtt F]
 *                 [--no-feedback] [--freeze]
 *   --rtt F        frames between a decoder flag and the encoder acting on it
 *   --no-feedback  the return path is cut (measures the damage left alone)
 *   --freeze       decoder concealment = freeze instead of MC + spatial */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>
#include "../include/omc1.h"

/* [V536] bounds-checked option value (external adversarial review of v5.3.5, section 7): every
 * value-taking flag used argv[++i]; as the LAST token that is argv[argc] == NULL and the
 * following atoi()/strcmp() dereferenced it -- a segfault in all nine CLIs on a trailing
 * option.  NEXTARG() refuses with a usage error and exit status 1 instead. */
#define NEXTARG() ((i + 1 < argc) ? argv[++i] : \
    (fprintf(stderr, "%s: option %s needs a value\n", argv[0], argv[i]), exit(1), (char *)0))

static void die(const char *m) { fprintf(stderr, "omc_loop: %s\n", m); exit(1); }

/* parse "f:s[-s2],..." — returns 1 and fills s0/s1 for entries with frame == f */
static int spec_for_frame(const char *list, int f, int *s0, int *s1, int nsl, int *cursor)
{
    if (!list) return 0;
    const char *q = list;
    int idx = 0;
    while (*q) {
        int ff = atoi(q); const char *col = strchr(q, ':');
        if (!col) return 0;
        if (ff == f && idx >= *cursor) {
            const char *d = strchr(col + 1, '-'), *cm = strchr(col + 1, ',');
            if (col[1] == '*') { *s0 = 0; *s1 = nsl - 1; }
            else { *s0 = atoi(col + 1); *s1 = (d && (!cm || d < cm)) ? atoi(d + 1) : *s0; }
            if (*s1 >= nsl) *s1 = nsl - 1;
            *cursor = idx + 1;
            return 1;
        }
        const char *nx = strchr(q, ','); if (!nx) return 0; q = nx + 1; idx++;
    }
    return 0;
}

int main(int argc, char **argv)
{
    const char *inp = NULL, *lose = NULL;
    int nframes = -1, rtt = 2, feedback = 1, freeze = 0;
    double bpp = 1.0;
    omc_config_t cfg; memset(&cfg, 0, sizeof cfg);
    cfg.fill_grain = 1; cfg.bitdepth = 10; cfg.chroma = OMC_CF_422;
    cfg.fps_num = 50; cfg.fps_den = 1;
    cfg.color = (omc_colorimetry_t){1, 1, 1, 0};
    cfg.refresh_r = OMC_REFRESH_NONE;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-i")) inp = NEXTARG();
        else if (!strcmp(argv[i], "-w")) cfg.width = (uint16_t)atoi(NEXTARG());
        else if (!strcmp(argv[i], "-h")) cfg.height = (uint16_t)atoi(NEXTARG());
        else if (!strcmp(argv[i], "--depth")) cfg.bitdepth = (uint8_t)atoi(NEXTARG());
        else if (!strcmp(argv[i], "--fmt")) cfg.chroma = atoi(NEXTARG()) == 444 ? OMC_CF_444 : OMC_CF_422;
        else if (!strcmp(argv[i], "--bpp")) bpp = atof(NEXTARG());
        else if (!strcmp(argv[i], "-n")) nframes = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--refresh")) { i++; cfg.refresh_r = !strcmp(argv[i], "none") ? OMC_REFRESH_NONE : (uint8_t)atoi(argv[i]); }
        else if (!strcmp(argv[i], "--lose")) lose = NEXTARG();
        else if (!strcmp(argv[i], "--rtt")) rtt = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--no-feedback")) feedback = 0;
        else if (!strcmp(argv[i], "--freeze")) freeze = 1;
        else die("unknown arg");
    }
    if (!inp || !cfg.width || !cfg.height) die("usage: -i in.yuv -w W -h H [--bpp B] [-n N] [--lose f:s-s2,...] [--rtt F] [--refresh none|R] [--no-feedback]");
    uint16_t dispW = cfg.width, dispH = cfg.height;
    {
        int wal = cfg.chroma == OMC_CF_422 ? 64 : 32;
        uint16_t cw = (uint16_t)((cfg.width + wal - 1) / wal * wal);
        if (!cfg.slice_h) cfg.slice_h = (cfg.height <= 720) ? 8 : 16;
        uint16_t chh = (uint16_t)((cfg.height + cfg.slice_h - 1) / cfg.slice_h * cfg.slice_h);
        if (cw != cfg.width || chh != cfg.height) {
            cfg.display_width = dispW; cfg.display_height = dispH;
            cfg.width = cw; cfg.height = chh;
        }
    }
    int nsl = cfg.height / cfg.slice_h;
    double bits_frame = bpp * cfg.width * cfg.height;
    cfg.bits_per_slice = (uint32_t)((int64_t)(bits_frame / nsl) / 8 * 8);
    { char verr[160]; if (omc_validate_config(&cfg, verr, sizeof verr) != 0) die(verr); }
    int W = cfg.width, H = cfg.height, Wc = omc_chroma_width(&cfg), sh = cfg.slice_h;
    size_t ysz = (size_t)W * H, csz = (size_t)Wc * H, fw = ysz + 2 * csz;
    int iW = dispW, iH = dispH, iWc = cfg.chroma == OMC_CF_422 ? (iW + 1) / 2 : iW;
    size_t in_words = (size_t)iW * iH + 2 * (size_t)iWc * iH;
    uint16_t *inbuf = malloc(in_words * 2), *pix = malloc(fw * 2), *rec = malloc(fw * 2), *dpix = malloc(fw * 2);
    size_t slice_bytes = cfg.bits_per_slice / 8, frame_bytes = slice_bytes * (size_t)nsl;
    uint8_t *bs = malloc(frame_bytes), *fb = malloc(frame_bytes);
    uint8_t *flags = calloc((size_t)nsl, 1), *pending = calloc((size_t)nsl, 1), *reqnow = calloc((size_t)nsl, 1);
    int *due = calloc((size_t)nsl, sizeof(int));
    if (!inbuf || !pix || !rec || !dpix || !bs || !fb || !flags || !pending || !due) die("oom");
    FILE *fi = fopen(inp, "rb"); if (!fi) die("open input");
    omc_enc_t *enc = omc_enc_create(&cfg); if (!enc) die("enc create");
    omc_enc_set_gamut_strict(enc, 12);
    omc_dec_t *dec = omc_dec_create(&cfg); if (!dec) die("dec create");
    omc_dec_set_conceal(dec, freeze ? 0 : 1);
    {   uint16_t midy = (uint16_t)((1 << (cfg.bitdepth - 1)) + OMC_PIX_BIAS);
        for (size_t i = 0; i < fw; i++) dpix[i] = midy; }
    omc_frame_t fin = {{pix, pix + ysz, pix + ysz + csz}, {W, Wc, Wc}};
    omc_frame_t frec = {{rec, rec + ysz, rec + ysz + csz}, {W, Wc, Wc}};
    omc_frame_t fout = {{dpix, dpix + ysz, dpix + ysz + csz}, {W, Wc, Wc}};
    printf("omc_loop: %dx%d coded, %d slices of %d, %.2f bpp, refresh %s, rtt %d, feedback %s\n",
           W, H, nsl, sh, bpp, cfg.refresh_r == OMC_REFRESH_NONE ? "none" : "scheduled", rtt, feedback ? "on" : "off");
    int f = 0, tot_bad_frames = 0;
    while (nframes < 0 || f < nframes) {
        if (fread(inbuf, 2, in_words, fi) != in_words) break;
        /* assemble (pad by replication, bias) */
        for (int p = 0; p < 3; p++) {
            int pw = p == 0 ? W : Wc, ipw = p == 0 ? iW : iWc;
            const uint16_t *sp = inbuf + (p == 0 ? 0 : (p == 1 ? (size_t)iW * iH : (size_t)iW * iH + (size_t)iWc * iH));
            uint16_t *dst = pix + (p == 0 ? 0 : (p == 1 ? ysz : ysz + csz));
            for (int r = 0; r < H; r++) {
                int sr = r < iH ? r : iH - 1;
                for (int x = 0; x < pw; x++) {
                    int sx = x < ipw ? x : ipw - 1;
                    dst[(size_t)r * pw + x] = (uint16_t)(sp[(size_t)sr * ipw + sx] + OMC_PIX_BIAS);
                }
            }
        }
        /* control plane: requests whose round trip has elapsed reach the encoder now */
        int nreq = 0; char reqs[256] = "";
        memset(reqnow, 0, (size_t)nsl);
        for (int s = 0; s < nsl; s++)
            if (pending[s] && due[s] <= f) {
                omc_enc_request_refresh(enc, s, 1); pending[s] = 0; reqnow[s] = 1; nreq++;
                if (strlen(reqs) < 240) snprintf(reqs + strlen(reqs), 16, " %d", s);
            }
        int64_t n = omc_enc_frame(enc, &fin, f, bs, frame_bytes, &frec);
        if (n < 0) die("encode failed");
        /* the link */
        memcpy(fb, bs, frame_bytes);
        char losts[256] = "";
        { int s0, s1, cur = 0;
          while (spec_for_frame(lose, f, &s0, &s1, nsl, &cur))
              for (int s = s0; s <= s1; s++) {
                  memset(fb + (size_t)s * slice_bytes, 0, slice_bytes);
                  if (strlen(losts) < 240) snprintf(losts + strlen(losts), 16, " %d", s);
              } }
        int64_t good = omc_dec_frame(dec, fb, frame_bytes, &fout);
        int nflag = omc_dec_state_report(dec, flags, nsl);
        char flg[256] = "";
        for (int s = 0; s < nsl; s++) if (flags[s]) {
            if (strlen(flg) < 240) snprintf(flg + strlen(flg), 16, " %d", s);
            /* a flag in the frame a slice was refreshed refers to the rows
             * BEFORE the refresh (the hash lags one frame): not a new fault */
            if (feedback && !pending[s] && !reqnow[s]) { pending[s] = 1; due[s] = f + rtt; }
        }
        /* compare emitted pictures per slice (luma) + chroma count */
        int nbad = 0, mx = 0; char bads[256] = ""; double psnr = 0;
        for (int s = 0; s < nsl; s++) {
            int d = 0;
            for (int r = s * sh; r < (s + 1) * sh; r++)
                for (int x = 0; x < W; x++) {
                    int v = (int)rec[(size_t)r * W + x] - (int)dpix[(size_t)r * W + x];
                    if (v < 0) v = -v;
                    if (v > d) d = v;
                }
            if (d) { nbad++; if (d > mx) mx = d; if (strlen(bads) < 240) snprintf(bads + strlen(bads), 16, " %d", s); }
        }
        size_t cdiff = 0;
        for (size_t i = ysz; i < fw; i++) cdiff += rec[i] != dpix[i];
        /* encoder-side luma PSNR against the input: the cost of a heal frame */
        double se = 0; { int mxv = (1 << cfg.bitdepth) - 1;
          for (size_t i = 0; i < ysz; i++) { double v = (double)rec[i] - (double)pix[i]; se += v * v; }
          se = se / (double)ysz; psnr = se > 0 ? 10.0 * log10((double)mxv * mxv / se) : 99.0; }
        if (nbad) tot_bad_frames++;
        printf("frame %2d: decoded %2lld/%d lost[%s] flagged %d[%s] requested %d[%s] | differing luma slices %d[%s] max|d| %d chroma %zu | enc PSNR %.2f\n",
               f, (long long)good, nsl, losts, nflag, flg, nreq, reqs, nbad, bads, mx, cdiff, psnr);
        f++;
    }
    printf("omc_loop: %d frames, %d with a differing picture\n", f, tot_bad_frames);
    omc_enc_destroy(enc); omc_dec_destroy(dec); fclose(fi);
    return 0;
}
