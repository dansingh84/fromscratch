/* omc_pixunpack — ST 2110-20 pgroups or the SDI 10-bit word layout ->
 * planar 16-bit LE (the codec's plane buffers), line by line.
 * Task D part 4, Agent 4.  Inverse of omc_pixpack; see tools/omc_pix.h.
 *
 * Usage: omc_pixunpack -i in.pix -o out.yuv -w W -h H [--fmt 422|444]
 *                      [--depth 10] [--layout 2110|sdi10] [--fps 60] [-n frames]
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "omc_pix.h"

/* [V536] bounds-checked option value (external adversarial review of v5.3.5, section 7): every
 * value-taking flag used argv[++i]; as the LAST token that is argv[argc] == NULL and the
 * following atoi()/strcmp() dereferenced it -- a segfault in all nine CLIs on a trailing
 * option.  NEXTARG() refuses with a usage error and exit status 1 instead. */
#define NEXTARG() ((i + 1 < argc) ? argv[++i] : \
    (fprintf(stderr, "%s: option %s needs a value\n", argv[0], argv[i]), exit(1), (char *)0))

static void die(const char *m) { fprintf(stderr, "omc_pixunpack: %s\n", m); exit(1); }

int main(int argc, char **argv)
{
    const char *inp = NULL, *outp = NULL;
    int W = 0, H = 0, c444 = 0, depth = 10, layout = OMC_PIXL_2110, nf = 0;
    double fps = 60.0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-i") && i + 1 < argc) inp = NEXTARG();
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) outp = NEXTARG();
        else if (!strcmp(argv[i], "-w") && i + 1 < argc) W = atoi(NEXTARG());
        else if (!strcmp(argv[i], "-h") && i + 1 < argc) H = atoi(NEXTARG());
        else if (!strcmp(argv[i], "-n") && i + 1 < argc) nf = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--fmt") && i + 1 < argc) c444 = atoi(NEXTARG()) == 444;
        else if (!strcmp(argv[i], "--depth") && i + 1 < argc) depth = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--fps") && i + 1 < argc) fps = atof(NEXTARG());
        else if (!strcmp(argv[i], "--layout") && i + 1 < argc)
            layout = strcmp(NEXTARG(), "sdi10") ? OMC_PIXL_2110 : OMC_PIXL_SDI10;
        else die("usage: -i in.pix -o out.yuv -w W -h H [--fmt 422|444] [--depth D] "
                 "[--layout 2110|sdi10] [--fps F] [-n N]");
    }
    if (!inp || !outp || W <= 0 || H <= 0) die("need -i -o -w -h");
    omc_pix_geom_t g;
    int rc = omc_pix_geom(layout, c444, depth, W, &g);
    if (rc < 0) { fprintf(stderr, "omc_pixunpack: unsupported layout/format (%d)\n", rc); return 2; }

    int Wc = c444 ? W : W / 2;
    size_t fw = (size_t)W * H + 2 * (size_t)Wc * H;
    FILE *fi = fopen(inp, "rb"); if (!fi) die("open input");
    FILE *fo = fopen(outp, "wb"); if (!fo) die("open output");
    uint16_t *fr = calloc(fw, 2);
    uint8_t *line = malloc((size_t)g.line_bytes);
    if (!fr || !line) die("oom");
    long frames = 0;
    while (nf <= 0 || frames < nf) {
        uint16_t *Y = fr, *CB = fr + (size_t)W * H, *CR = CB + (size_t)Wc * H;
        int r;
        for (r = 0; r < H; r++) {
            size_t got = fread(line, 1, (size_t)g.line_bytes, fi);
            if (got == 0 && r == 0) break;
            if (got != (size_t)g.line_bytes) die("short line in input");
            omc_pix_unpack_line(&g, line, Y + (size_t)r * W, CB + (size_t)r * Wc,
                                CR + (size_t)r * Wc);
        }
        if (r == 0) break;
        if (fwrite(fr, 2, fw, fo) != fw) die("write");
        frames++;
    }
    fclose(fi);
    if (fclose(fo) != 0) die("close output");
    double line_us = 1e6 / (fps * (double)H);
    fprintf(stderr, "PIX unpack layout=%s fmt=%s depth=%d %dx%d frames=%ld "
            "pgroup=%dB/%dpx line=%ldB line_time=%.3f us\n",
            layout == OMC_PIXL_SDI10 ? "sdi10" : "2110", c444 ? "444" : "422", depth,
            W, H, frames, g.pg_bytes, g.pg_pixels, g.line_bytes, line_us);
    return 0;
}
