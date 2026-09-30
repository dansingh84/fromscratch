/* Apply omc_xsl_unblend() to a raw picture.  Exists so the inverse can be tested
 * against ground truth: decoding an all-intra frame with the edit switched off
 * yields the un-edited reconstruction, and unblend(decode-with-edit) must equal
 * it byte for byte. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "omc1.h"
int main(int argc, char **argv)
{
    if (argc < 7) { fprintf(stderr, "usage: in out W H depth slice_h [refresh] [nframes] [bits_per_slice]\n"); return 2; }
    int W = atoi(argv[3]), H = atoi(argv[4]), depth = atoi(argv[5]), sh = atoi(argv[6]);
    int rr = argc > 7 ? atoi(argv[7]) : 8, nf = argc > 8 ? atoi(argv[8]) : 1;
    omc_config_t cfg; memset(&cfg, 0, sizeof cfg);
    cfg.width = (uint16_t)W; cfg.height = (uint16_t)H; cfg.bitdepth = (uint8_t)depth;
    cfg.chroma = OMC_CF_422; cfg.slice_h = (uint8_t)sh; cfg.refresh_r = (uint8_t)rr;
    cfg.bits_per_slice = argc > 9 ? (uint32_t)strtoul(argv[9], 0, 10)
                                  : (uint32_t)(2 * W * sh);  /* must MATCH the encoder: it selects the cap */
    size_t ysz = (size_t)W * H, csz = ysz / 2, words = ysz + 2 * csz;
    uint16_t *pix = malloc(words * 2);
    FILE *fi = fopen(argv[1], "rb"), *fo = fopen(argv[2], "wb");
    if (!fi || !fo || !pix) { fprintf(stderr, "io\n"); return 2; }
    for (int f = 0; f < nf; f++) {
        if (fread(pix, 2, words, fi) != words) break;
        omc_frame_t fr = {{pix, pix + ysz, pix + ysz + csz}, {W, W / 2, W / 2}};
        omc_xsl_unblend(&fr, &cfg, f);
        fwrite(pix, 2, words, fo);
    }
    fclose(fi); fclose(fo); free(pix); return 0;
}
