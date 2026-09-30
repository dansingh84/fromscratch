/* basis.c -- measure the synthesis basis of every band of the OMC transform.
 *
 * For each band, put a single impulse in an interior coefficient, run the
 * inverse transform, and report:
 *   peak |g|      -- the largest pixel the coefficient can move, per unit
 *   ||g||^2       -- the energy that unit puts into the picture
 *   leverage      -- peak|g| / ||g||^2, the correction bought per unit of damage
 *
 * These are properties of the transform, not of any content, and they are what
 * the least-norm in-gamut correction is built on: the optimal reduction of a
 * coefficient is proportional to g_k(p)/||g_k||^2 and does NOT depend on the
 * coefficient's own magnitude.  The lifting is integer and therefore not quite
 * linear, so the impulse is large and the result divided back down.
 *
 * Build:  cc -O2 -Iinclude -o basis tests/basis.c src/dwt.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "omc1.h"
#include "../src/internal.h"

int main(int argc, char **argv)
{
    int W  = argc > 1 ? atoi(argv[1]) : 1920;
    int sh = argc > 2 ? atoi(argv[2]) : 16;
    int A  = argc > 3 ? atoi(argv[3]) : 4096;   /* impulse amplitude */
    omc_band_t b[OMC_NBANDS];
    omc_band_layout(W, sh, b);
    size_t n = (size_t)W * sh;
    int32_t *buf = calloc(n, sizeof(int32_t));
    int32_t *tmp = calloc(n + 4 * (size_t)W, sizeof(int32_t));
    printf("W=%d slice_h=%d impulse=%d\n", W, sh, A);
    printf("band  w     h    peak|g|   ||g||^2      leverage=peak/||g||^2\n");
    double gmin = 1e30, gmax = 0; int nsamp = 0;
    double *all = malloc(sizeof(double) * OMC_NBANDS * 64);
    for (int k = 0; k < OMC_NBANDS; k++) {
        /* sample several phases per band: ||g||^2 varies with position as well
         * as with band, and the spread across ALL coefficients is the number
         * the least-norm ranking depends on */
        for (int ph = 0; ph < 8; ph++) {
            memset(buf, 0, n * sizeof(int32_t));
            int rr = b[k].r0 + b[k].h / 2 + (ph & 1);
            int cc = b[k].c0 + b[k].w / 2 + (ph >> 1);
            if (rr >= b[k].r0 + b[k].h) rr = b[k].r0 + b[k].h - 1;
            if (cc >= b[k].c0 + b[k].w) cc = b[k].c0 + b[k].w - 1;
            buf[(size_t)rr * W + cc] = A;
            omc_slice_inv(buf, W, sh, tmp);
            double ee = 0;
            for (size_t i = 0; i < n; i++) { double v = (double)buf[i] / A; ee += v * v; }
            if (ee > 0) { if (ee < gmin) gmin = ee; if (ee > gmax) gmax = ee; all[nsamp++] = ee; }
        }
        memset(buf, 0, n * sizeof(int32_t));
        int r = b[k].r0 + b[k].h / 2, c = b[k].c0 + b[k].w / 2;
        buf[(size_t)r * W + c] = A;
        omc_slice_inv(buf, W, sh, tmp);
        double peak = 0, e2 = 0;
        for (size_t i = 0; i < n; i++) {
            double v = (double)buf[i] / A;
            if (v < 0) { if (-v > peak) peak = -v; } else if (v > peak) peak = v;
            e2 += v * v;
        }
        printf("%3d  %5d %5d   %8.4f  %10.4f   %10.4f\n",
               k, b[k].w, b[k].h, peak, e2, e2 > 0 ? peak / e2 : 0.0);
    }
    for (int i = 1; i < nsamp; i++) { double t = all[i]; int j = i - 1;
        while (j >= 0 && all[j] > t) { all[j + 1] = all[j]; j--; } all[j + 1] = t; }
    printf("\n||g||^2 over %d sampled coefficients: min %.4f  max %.4f  "
           "median %.4f  SPAN %.1fx\n", nsamp, gmin, gmax, all[nsamp / 2],
           gmin > 0 ? gmax / gmin : 0.0);
    free(all); free(buf); free(tmp);
    return 0;
}
