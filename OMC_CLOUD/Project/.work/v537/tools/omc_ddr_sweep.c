/* omc_ddr_sweep — drive the DDR service model over the constraint set without
 * needing a master for every format.  The traffic geometry is a pure function
 * of (W, H, chroma, depth, slice_h, fps) and is cross-checked against real
 * encoder/decoder runs at the formats we do have masters for.
 *
 * Usage:
 *   omc_ddr_sweep --w 3840 --h 2160 --fmt 422 --depth 10 --fps 60 \
 *                 [--side dec|enc] [--frames 4] [--refresh 8]
 * All model parameters come from the OMC_DDR_* environment (see ddr_model.h).
 * Task D, Agent 4.
 */
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../src/ddr_model.h"

/* [V536] bounds-checked option value (external adversarial review of v5.3.5, section 7): every
 * value-taking flag used argv[++i]; as the LAST token that is argv[argc] == NULL and the
 * following atoi()/strcmp() dereferenced it -- a segfault in all nine CLIs on a trailing
 * option.  NEXTARG() refuses with a usage error and exit status 1 instead. */
#define NEXTARG() ((i + 1 < argc) ? argv[++i] : \
    (fprintf(stderr, "%s: option %s needs a value\n", argv[0], argv[i]), exit(1), (char *)0))

int main(int argc, char **argv)
{
    int W = 1920, H = 1080, fmt = 422, depth = 10, frames = 4, sh = 0, R = 8;
    double fps = 60.0;
    const char *side = "dec";
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--w") && i + 1 < argc) W = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--h") && i + 1 < argc) H = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--fmt") && i + 1 < argc) fmt = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--depth") && i + 1 < argc) depth = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--fps") && i + 1 < argc) fps = atof(NEXTARG());
        else if (!strcmp(argv[i], "--frames") && i + 1 < argc) frames = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--sh") && i + 1 < argc) sh = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--refresh") && i + 1 < argc) R = atoi(NEXTARG());
        else if (!strcmp(argv[i], "--side") && i + 1 < argc) side = NEXTARG();
        else { fprintf(stderr, "unknown arg %s\n", argv[i]); return 2; }
    }
    if (!getenv("OMC_DDR")) { fprintf(stderr, "set OMC_DDR=1\n"); return 2; }
    setenv("OMC_DDR_SYNTH", "1", 1);
    if (!sh) sh = (H <= 720) ? 8 : 16;
    /* coded height: the codec pads to a whole number of slices */
    int Hc = ((H + sh - 1) / sh) * sh;
    int nslices = Hc / sh;
    int Wc = (fmt == 444) ? W : W / 2;
    int enc = !strcmp(side, "enc");

    omc_ddr_init(W, Hc, Wc, fmt == 444, depth, sh, nslices, fps, side);
    for (int p = 0; p < 3; p++) {
        omc_ddr_bind_synth(OMC_DDR_BIND_PREV, p, p ? Wc : W, Hc);
        if (enc) omc_ddr_bind_synth(OMC_DDR_BIND_PREV2, p, p ? Wc : W, Hc);
    }
    for (int f = 0; f < frames; f++) {
        omc_ddr_frame_begin(f);
        for (int s = 0; s < nslices; s++) {
            omc_ddr_slice_header(s);
            /* the encoder's motion derivation runs on every slice that is not
             * intra-refreshed this frame (rolling wave of period R) */
            if (enc && f >= 2 && (R <= 0 || (f % R) != (s % R)))
                omc_ddr_mv_band(s);
            omc_ddr_pixel_dma(s);
            omc_ddr_admit(s);
            omc_ddr_commit(s);
        }
    }
    omc_ddr_finish();
    return 0;
}
