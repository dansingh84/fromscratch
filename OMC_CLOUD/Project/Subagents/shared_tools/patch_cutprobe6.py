#!/usr/bin/env python3
"""[A2-CUTPROBE6] Does the SHIPPED default refresh period breach?

The gate runs 4 frames at refresh_r=2.  At a period of 4 or more a 4-frame
sequence cannot complete a refresh wave, so the gate's zeros at refresh_r 4..8
are the SAME ENCODE (identical stream hashes) and say nothing about the product
default of 8.  This adds a 24-frame sequence that cuts between rail-graded
plates and ordinary footage every 6 frames -- a programme shape -- and sweeps
the refresh period across it, including 8 and NONE.

Adds run_strict_n() (run_strict with an explicit frame count) so the existing
NF=4 gates are untouched.
"""
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text()

# 1) add run_strict_n right after run_strict
anchor = "/* ---------------------------------------------------------- G-T5-CALM ----"
assert anchor in s
helper = r'''/* [A2-CUTPROBE6] run_strict with an explicit frame count */
static void run_strict_n(const omc_config_t *c, const uint16_t *pix, int passes,
                         uint8_t *bs, uint16_t *dec, int64_t *oob, int nf)
{
    size_t fb = (size_t)(c->bits_per_slice / 8) * (H / SH);
    omc_enc_t *e = omc_enc_create(c);
    omc_dec_t *d = omc_dec_create(c);
    omc_enc_set_gamut_strict(e, passes);
    uint16_t *rcb = malloc(WORDS * 2);
    for (int f = 0; f < nf; f++) {
        omc_frame_t fr; planes(&fr, (uint16_t *)pix + WORDS * f);
        omc_frame_t rc; planes(&rc, rcb);
        omc_enc_frame(e, &fr, f, bs + fb * f, fb, &rc);
        omc_frame_t fo; planes(&fo, dec + WORDS * f);
        omc_dec_frame(d, bs + fb * f, fb, &fo);
    }
    free(rcb);
    if (oob) *oob = omc_enc_oob(e);
    gm_last_unfixed = omc_enc_gamut_unfixed(e);
    omc_enc_destroy(e);
    omc_dec_destroy(d);
}

'''
s = s.replace(anchor, helper + anchor, 1)

# 2) add the long-sequence block INSIDE the function, right after the CUT block
#    (the G-T5-CALM banner is at file scope, so anchoring there puts the block
#     outside any function and it will not compile)
s2c = s
blk = r'''    /* ------------------------------------------- [A2-CUTPROBE6] long run */
    {
        const int NFL = 24;           /* long enough for two waves at period 8 */
        const int CUTEVERY = 6;       /* a cut every 6 frames: a programme shape */
        uint16_t *lg = malloc(WORDS * 2 * (size_t)NFL);
        uint16_t *ld = malloc(WORDS * 2 * (size_t)NFL);
        size_t lfb = (size_t)(c.bits_per_slice / 8) * (H / SH);
        uint8_t *lb = malloc(lfb * (size_t)NFL);
        if (lg && ld && lb) {
            for (int f = 0; f < NFL; f++) {
                if ((f / CUTEVERY) & 1) fill(lg + WORDS * f, 12345u, f);
                else                    fill_rails_g(lg + WORDS * f, f, 0);
            }
            int rr[6]; rr[0]=2; rr[1]=3; rr[2]=4; rr[3]=6; rr[4]=8;
            rr[5]=OMC_REFRESH_NONE;
            int save = c.refresh_r;
            printf("   [A2-CUTPROBE6] %d frames, cut every %d, sweep refresh_r:\n",
                   NFL, CUTEVERY);
            for (int t = 0; t < 6; t++) {
                int64_t o = 0, o2 = 0;
                c.refresh_r = (uint8_t)rr[t];
                run_strict_n(&c, lg, GM_PASS, lb, ld, &o, NFL);
                int64_t un = gm_last_unfixed;
                run_strict_n(&c, lg, GM_PASS, lb, ld, &o2, NFL);
                printf("     refresh_r=%-5s oob=%-6lld unfixed=%-4lld %s%s\n",
                       rr[t] == OMC_REFRESH_NONE ? "NONE" :
                         (rr[t]==2?"2":rr[t]==3?"3":rr[t]==4?"4":rr[t]==6?"6":"8"),
                       (long long)o, (long long)un,
                       o == o2 ? "" : "!NONDET!",
                       rr[t] == 8 ? "   <-- SHIPPED DEFAULT" : "");
            }
            c.refresh_r = (uint8_t)save;
        }
        free(lg); free(ld); free(lb);
    }

'''
tail = ("        free(cut); free(cd1); free(cd2); free(cd3);\n"
        "        free(cb1); free(cb2); free(cb3);\n"
        "    }\n")
assert tail in s2c, "CUT-block tail anchor not found"
s = s.replace(tail, tail + blk, 1)
p.write_text(s); print("  patched")
