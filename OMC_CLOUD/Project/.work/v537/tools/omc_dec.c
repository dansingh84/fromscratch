/* omc_dec - OMC-1 decoder CLI (T5). Reads .omc bitstream (minor 10), writes
 * raw planar LE16.  Two output modes:
 *   default        display raw: bias removed, clipped to [0, 2^depth), RCT
 *                  inverted and picture cropped to display dims — what a
 *                  viewer or metric consumes.  NOT suitable for re-encoding.
 *   --cdr          coded-domain raw: the decoder's committed picture verbatim
 *                  (biased by 2048, unclipped, coded geometry, no crop/RCT).
 *                  THE generation-chain interchange: feed it back with
 *                  omc_enc --cdr-in and the re-encode is byte-exact forever.
 * Concealment for slices that fail CRC (A5) is on by default; a clean stream
 * decodes identically either way.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "omc1.h"
#include "omc_uc.h"

/* [V536] bounds-checked option value (external adversarial review of v5.3.5, section 7): every
 * value-taking flag used argv[++i]; as the LAST token that is argv[argc] == NULL and the
 * following atoi()/strcmp() dereferenced it -- a segfault in all nine CLIs on a trailing
 * option.  NEXTARG() refuses with a usage error and exit status 1 instead. */
#define NEXTARG() ((i + 1 < argc) ? argv[++i] : \
    (fprintf(stderr, "%s: option %s needs a value\n", argv[0], argv[i]), exit(1), (char *)0))

static void die(const char *m) { fprintf(stderr, "omc_dec: %s\n", m); exit(1); }

int main(int argc, char **argv)
{
    const char *inp = NULL, *outp = NULL;
    int conceal = 1, verbose = 0;
    int cdr = 0;       /* 1 = coded-domain raw out (generation chains) */
    int ucf = -1;      /* -1 = follow the stream's uc_ratio; else 1 / 2 / 4  */
    int uc_bands = 0;  /* produce the output in slice-sized bands            */
    int uc_dir = 1;    /* direction-adaptive predictor (normative default)   */
    /* [S3-REFRESH] LOSS INJECTION (test only): "f:s[-s2],..." — the bytes of
     * slices s..s2 of frame f are zeroed before decoding, so the decoder loses
     * them exactly as a damaged link would (sync-word resync + concealment). */
    const char *lose_list = NULL;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-i")) inp = NEXTARG();
        else if (!strcmp(argv[i], "-o")) outp = NEXTARG();
        else if (!strcmp(argv[i], "--no-conceal")) conceal = 0;
        else if (!strcmp(argv[i], "--cdr")) cdr = 1;
        else if (!strcmp(argv[i], "-v")) verbose = 1;
        else if (!strcmp(argv[i], "--upconv")) ucf = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--uc-bands")) uc_bands = 1;
        else if (!strcmp(argv[i], "--uc-no-direction")) uc_dir = 0;
        else if (!strcmp(argv[i], "--lose")) lose_list = NEXTARG();
        else die("usage: -i in.omc -o out.yuv [--cdr] [--no-conceal] [-v] "
                 "[--upconv 1|2|4] [--uc-bands] [--uc-no-direction] "
                 "[--lose f:s[-s2],...]");
    }
    if (!inp || !outp) die("usage: -i in.omc -o out.yuv");

    FILE *fi = fopen(inp, "rb");
    if (!fi) die("open input");
    uint8_t shdr[OMC_STREAM_HDR_BYTES];
    if (fread(shdr, 1, OMC_STREAM_HDR_BYTES, fi) != OMC_STREAM_HDR_BYTES) die("short stream");
    omc_config_t cfg;
    if (omc_read_stream_header(shdr, &cfg) < 0) die("bad stream header");

    int W = cfg.width, H = cfg.height, Wc = omc_chroma_width(&cfg);
    int nsl = omc_num_slices(&cfg);
    size_t slice_bytes = cfg.bits_per_slice / 8;
    size_t ysz = (size_t)W * H, csz = (size_t)Wc * H;
    size_t frame_words = ysz + 2 * csz;
    uint16_t *pix = calloc(frame_words, 2);
    uint8_t *sb = malloc(slice_bytes);
    if (!pix || !sb) die("out of memory");

    /* mid-gray init so first-frame concealment is neutral, not black
     * (T5: the decode buffer lives in the biased domain) */
    {
        uint16_t midy = (uint16_t)((1 << (cfg.bitdepth - 1)) + OMC_PIX_BIAS);
        for (size_t i = 0; i < frame_words; i++) pix[i] = midy;
    }

    /* omc_dec_create() takes the filter state from cfg.tf_mode, i.e. from the
     * stream header, so nothing here needs to guess. */
    omc_dec_t *dec = omc_dec_create(&cfg);
    omc_dec_set_conceal(dec, conceal); /* 1 = MC+spatial (default), 0 = freeze */
    omc_frame_t fout = {{pix, pix + ysz, pix + ysz + csz}, {W, Wc, Wc}};
    FILE *fo = fopen(outp, "wb");
    if (!fo) die("open output");

    size_t frame_bytes = slice_bytes * (size_t)nsl;
    uint8_t *fb = malloc(frame_bytes);
    int fidx = 0, bad = 0;
    (void)sb;
    /* v4.2 output stage: inverse RCT and/or crop to display dims (both are
     * wrapper-level; the coding core and its outputs are untouched) */
    int oW = cfg.display_width ? cfg.display_width : W;
    int oH = cfg.display_height ? cfg.display_height : H;
    int oWc = cfg.chroma == OMC_CF_422 ? (oW + 1) / 2 : oW;
    int comp_depth = cfg.rct ? cfg.bitdepth - 2 : cfg.bitdepth;
    int32_t mid_c = 1 << (cfg.bitdepth - 1);
    int32_t yoff = mid_c - (1 << (comp_depth - 1));
    int32_t cmax = (1 << comp_depth) - 1;

    /* ---- OMC-UC output stage (v4.8, stream byte 26 / --upconv).
     * Strictly a post-process on the OUTPUT path: it runs on the coded planes
     * after reconstruction, so the decode loop, the temporal reference store,
     * rate control and every conformance hash are untouched.  --uc-bands
     * produces the output in slice-sized bands, which is the schedule real
     * hardware uses (one slice period of delay); the result is bit-identical
     * to the whole-frame call, which is what makes that schedule legal. */
    int ucn = 1;
    if (ucf < 0) ucn = cfg.uc_ratio == 2 ? 4 : cfg.uc_ratio == 1 ? 2 : 1;
    else if (ucf == 1 || ucf == 2 || ucf == 4) ucn = ucf;
    else die("--upconv must be 1, 2 or 4");
    omc_uc_t ucc;
    uint16_t *upix = NULL, *utmp = NULL;
    ucc.depth = cfg.bitdepth;
    ucc.direction = (uint8_t)uc_dir;
    if (ucn > 1) {
        size_t big = (size_t)ucn * ucn * frame_words;
        upix = malloc(big * 2);
        if (ucn == 4) utmp = malloc(4 * frame_words * 2);
        if (!upix || (ucn == 4 && !utmp)) die("out of memory");
        oW *= ucn; oH *= ucn; oWc *= ucn;
        if (verbose)
            fprintf(stderr, "omc_dec: OMC-UC %dx -> %dx%d out\n", ucn, oW, oH);
    }
    uint16_t *obuf = malloc(((size_t)oW * oH * 3) * 2);
    uint16_t *disp = cdr ? NULL : malloc(frame_words * 2);
    if (!obuf || (!cdr && !disp)) die("out of memory");
    int first_fidx8 = -1;
    for (;;) {
        if (fread(fb, 1, frame_bytes, fi) != frame_bytes) break;
        /* slice header: 32-bit sync, then the 8-bit frame phase (fidx8) */
        if (first_fidx8 < 0 && frame_bytes > 4) first_fidx8 = fb[4];
        if (lose_list) {   /* [S3-REFRESH] loss injection */
            const char *q = lose_list;
            while (*q) {
                int f = atoi(q); const char *col = strchr(q, ':');
                if (!col) break;
                if (f == fidx) {
                    int s0 = atoi(col + 1), s1 = s0;
                    const char *d = strchr(col + 1, '-'), *cm = strchr(col + 1, ',');
                    if (d && (!cm || d < cm)) s1 = atoi(d + 1);
                    if (s1 >= nsl) s1 = nsl - 1;
                    /* [G-LOSEWALK] slices are VARIABLE length on the wire:
                     * 48 + ceil(used_bits/8) bytes (used_bits = 24 bits at
                     * bit 86 of the header, LSB-first).  A fixed stride of
                     * slice_bytes zeroed the WRONG bytes from slice 1 on --
                     * "--lose 4:34" damaged slices 34 AND 35 and cascaded to
                     * 12 slices over 7 frames (Agent 5, 2026-09-06).  Walk the
                     * true extents on the UNDAMAGED frame first, then zero. */
                    size_t off = 0, ext_o[4096]; size_t ext_n[4096];
                    int walked = 0;
                    for (int s = 0; s < nsl && s < 4096; s++) {
                        if (off + 48 > frame_bytes) break;
                        const uint8_t *h = fb + off;
                        uint32_t sync = h[0] | (h[1] << 8) | (h[2] << 16) | ((uint32_t)h[3] << 24);
                        if (sync != 0x4F4D5331u) break;
                        uint32_t ub = 0;
                        for (int b = 0; b < 24; b++) {
                            int bit = 86 + b;
                            ub |= (uint32_t)((h[bit >> 3] >> (bit & 7)) & 1) << b;
                        }
                        size_t ln = 48 + ((size_t)ub + 7) / 8;
                        if (off + ln > frame_bytes) break;
                        ext_o[s] = off; ext_n[s] = ln; off += ln; walked = s + 1;
                    }
                    if (walked < nsl) die("--lose: lost sync walking slice extents");
                    for (int s = s0; s <= s1; s++)
                        memset(fb + ext_o[s], 0, ext_n[s]);
                }
                const char *nx = strchr(q, ','); if (!nx) break; q = nx + 1;
            }
        }
        int64_t good = omc_dec_frame(dec, fb, frame_bytes, &fout);
        if (verbose) {   /* [S3-HASH] state report */
            uint8_t *sb_ = malloc((size_t)nsl); int nb = omc_dec_state_report(dec, sb_, nsl);
            if (nb) { fprintf(stderr, "frame %d: STATE MISMATCH on %d slice(s):", fidx, nb); for (int s = 0; s < nsl; s++) if (sb_[s]) fprintf(stderr, " %d", s); fprintf(stderr, "\n"); }
            free(sb_);
        }
        if (good < nsl) {
            bad += nsl - (int)good;
            if (verbose) fprintf(stderr, "frame %d: %d damaged slice(s) concealed\n",
                                 fidx, nsl - (int)good);
        }
        if (cdr) {
            /* T5 coded-domain raw: the committed picture verbatim (biased,
             * unclipped, coded geometry).  The ONLY output that a next
             * generation may re-encode. */
            fwrite(pix, 2, frame_words, fo);
            fidx++;
            continue;
        }
        /* display projection (non-normative): remove the bias and clip to
         * the legal range before crop/RCT/upconversion */
        {
            int32_t dmax = (1 << cfg.bitdepth) - 1;
            for (size_t i = 0; i < frame_words; i++) {
                int32_t v = (int32_t)pix[i] - OMC_PIX_BIAS;
                disp[i] = (uint16_t)(v < 0 ? 0 : (v > dmax ? dmax : v));
            }
        }
        /* the output stage reads oSrc at oSW x oSH; identical to disp when
         * the upconverter is off, so the pre-v4.8 paths below are unchanged */
        const uint16_t *oSrc = disp;
        int oSW = W, oSWc = Wc, oSH = H;
        size_t oSy = ysz, oSc = csz, oSwords = frame_words;
        if (ucn > 1) {
            const uint16_t *cur = disp;
            uint16_t *nxt = (ucn == 4) ? utmp : upix;
            int cW = W, cWc = Wc, cH = H;
            for (int stage = 0; stage < (ucn == 4 ? 2 : 1); stage++) {
                size_t cy = (size_t)cW * cH, cc = (size_t)cWc * cH;
                const uint16_t *sp[3] = {cur, cur + cy, cur + cy + cc};
                uint16_t *dp[3] = {nxt, nxt + 4 * cy, nxt + 4 * cy + 4 * cc};
                int sw[3] = {cW, cWc, cWc};
                for (int pl = 0; pl < 3; pl++) {
                    int rows = 2 * cH, bh = uc_bands ? 2 * cfg.slice_h : rows;
                    for (int r = 0; r < rows; r += bh) {
                        int r1 = r + bh > rows ? rows : r + bh;
                        if (omc_uc_up_plane(&ucc, sp[pl], sw[pl], sw[pl], cH,
                                            dp[pl], 2 * sw[pl], r, r1) < 0)
                            die("upconversion failed");
                    }
                }
                cur = nxt; nxt = upix; cW *= 2; cWc *= 2; cH *= 2;
            }
            oSrc = cur; oSW = cW; oSWc = cWc; oSH = cH;
            oSy = (size_t)cW * cH; oSc = (size_t)cWc * cH;
            oSwords = oSy + 2 * oSc;
        }
        if (!cfg.rct && oW == oSW && oH == oSH) {
            fwrite(oSrc, 2, oSwords, fo); /* fast path: 4.1 behavior */
        } else if (cfg.rct) {
            /* inverse RCT (planar R,G,B out at display dims) */
            for (int r = 0; r < oH; r++)
                for (int x = 0; x < oW; x++) {
                    int32_t Y  = (int32_t)oSrc[(size_t)r * oSW + x] - yoff;
                    int32_t Cb = (int32_t)oSrc[oSy + (size_t)r * oSWc + x] - mid_c;
                    int32_t Cr = (int32_t)oSrc[oSy + oSc + (size_t)r * oSWc + x] - mid_c;
                    int32_t G = Y - ((Cb + Cr) >> 2);
                    int32_t B = Cb + G, R = Cr + G;
                    R = R < 0 ? 0 : (R > cmax ? cmax : R);
                    G = G < 0 ? 0 : (G > cmax ? cmax : G);
                    B = B < 0 ? 0 : (B > cmax ? cmax : B);
                    obuf[(size_t)r * oW + x] = (uint16_t)R;
                    obuf[(size_t)oW * oH + (size_t)r * oW + x] = (uint16_t)G;
                    obuf[2 * (size_t)oW * oH + (size_t)r * oW + x] = (uint16_t)B;
                }
            fwrite(obuf, 2, (size_t)oW * oH * 3, fo);
        } else {
            /* crop only */
            for (int r = 0; r < oH; r++)
                memcpy(obuf + (size_t)r * oW, oSrc + (size_t)r * oSW, (size_t)oW * 2);
            for (int pI = 1; pI <= 2; pI++)
                for (int r = 0; r < oH; r++)
                    memcpy(obuf + (size_t)oW * oH + (size_t)(pI - 1) * oWc * oH + (size_t)r * oWc,
                           oSrc + oSy + (size_t)(pI - 1) * oSc + (size_t)r * oSWc,
                           (size_t)oWc * 2);
            fwrite(obuf, 2, (size_t)oW * oH + 2 * (size_t)oWc * oH, fo);
        }
        fidx++;
    }
    fprintf(stderr, "omc_dec: %d frames decoded, %d damaged slices%s\n", fidx, bad,
            bad && conceal ? " (concealed)" : "");
    /* Coded vs display geometry: a re-encode of the CDR must be told BOTH (the
     * CDR is at coded geometry, and minor 11's pad neutralization is keyed off
     * the display height).  Print the exact flags to pass. */
    if (first_fidx8 >= 0)
        fprintf(stderr, "omc_dec: frame phase of the first slice: fidx8=%d "
                "(re-encode with --start-frame %d to resume it)\n",
                first_fidx8, first_fidx8);
    if (oH != H || oW != W)
        fprintf(stderr, "omc_dec: coded %dx%d, display %dx%d -- re-encode a CDR "
                "with: -w %d -h %d --display-w %d --display-h %d\n",
                W, H, oW, oH, W, H, oW, oH);
    omc_dec_destroy(dec);
    fclose(fi); fclose(fo);
    free(pix); free(sb); free(fb); free(obuf); free(disp); free(upix); free(utmp);
    { extern long long omc_fc_fire, omc_fc_tot;
      if (getenv("OMC_FILLCORR_STAT") && omc_fc_tot)
        fprintf(stderr, "FILLCORR fires %lld/%lld = %.2f%%\n", omc_fc_fire, omc_fc_tot, 100.0*omc_fc_fire/omc_fc_tot); }
    if (getenv("OMC_FILLSTAT")) {
        extern int64_t omc_fill_hits, omc_fill_slots;
        fprintf(stderr, "fillstat: %lld positions filled of %lld candidate slots (%.2f%%)\n",
                (long long)omc_fill_hits, (long long)omc_fill_slots,
                omc_fill_slots ? 100.0 * (double)omc_fill_hits / (double)omc_fill_slots : 0.0);
    }

    return 0;
}

