"""OMC-UC hardware budget (C3): arithmetic, memory, bandwidth, parallelism.

The op counts are ANALYTIC, derived from the normative constants in
include/omc_uc.h and src/upconv.c (kernel length, candidate lists, SAD tap
lists).  Each line below names the code it counts so the count can be audited
against the source rather than trusted.  Memory and bandwidth follow the same
structure the codec's own docs/HARDWARE.md uses, so the two add up.

Run: python3 harness/uc_hw_budget.py
"""

# ---- normative constants (must match include/omc_uc.h and src/upconv.c) ----
KTAPS = 12                       # UC_C
NCAND_V, NSAD_V = 13, 5          # UC_CAND_V, UC_SAD_V
NCAND_H, NSAD_H = 11, 3          # UC_CAND_H, UC_SAD_H

# ---- arithmetic, per PREDICTED sample -------------------------------------
# uc_tap12(): 6 symmetry folds + 9 coefficient shift-adds + 5 accumulates.
#   -1: 0 adds | 8: 0 (pure shift) | 27 = 32-4-1: 2 | 72 = 64+8: 1
#   -177 = -(128+32+16+1): 3 | 637 = 512+128-4+1: 3      -> 9
TAP12 = 6 + 9 + 5

# uc_halflat(): one add + one shift per half-sample position, two lines,
# amortised over the samples that reuse them.
HALFLAT = 2

# uc_direct(), per position:
#   cost(0) + roughness loop: nsad * (1 sub + 1 abs) for the straight cost,
#   plus nsad * 2 * (1 sub + 1 abs + 1 add) for the roughness of both lines.
#   candidate loop: (ncand-1) * nsad * (1 sub + 1 abs + 1 accumulate)
#                   + (ncand-1) compares for the running argmin.
#   monotonicity: 3 subs + 3 abs + 2 adds + 1 sub + 1 abs + 1 compare.
#   two gate compares (margin, roughness ratio).
#   3-tap median: 4 compare/selects.
#   correction: 2 adds (pd), 1 add (pv), 1 sub, 2 clamp compares, 1 add.
#   limiter: 2 compares (min/max), 1 sub, 1 shift, 1 add, 4 clamp compares.
def direct_ops(ncand, nsad):
    straight = nsad * 2
    rough = nsad * 2 * 3
    cands = (ncand - 1) * nsad * 3 + (ncand - 1)
    mono = 3 + 3 + 2 + 1 + 1 + 1
    gates = 2
    median = 4
    corr = 2 + 1 + 1 + 2 + 1
    lim = 2 + 1 + 1 + 1 + 4
    return straight + rough + cands + mono + gates + median + corr + lim


PRED_V = TAP12 + HALFLAT + direct_ops(NCAND_V, NSAD_V)
PRED_H = TAP12 + HALFLAT + direct_ops(NCAND_H, NSAD_H)

# Per SOURCE sample the 2x operator predicts:
#   1 sample in the vertical pass  (the new row)
#   2 samples in the horizontal pass (one per output row of the pair)
# and copies 1 sample (free).  Per OUTPUT sample, divide by 4.
PER_SRC = PRED_V + 2 * PRED_H
PER_OUT = PER_SRC / 4.0

LUT_PER_OP = 18          # a 16-bit add/compare/abs stage in modern FPGA fabric

FORMATS = [
    # name, src W, src H, fps, slice_h, chroma
    ("720p50 -> 1440p50", 1280, 720, 50.0, 8, "4:2:2"),
    ("1080p60 -> 2160p60", 1920, 1080, 60.0, 8, "4:2:2"),
    ("2160p60 -> 4320p60", 3840, 2160, 60.0, 16, "4:2:2"),
    ("2160p120 -> 4320p120", 3840, 2160, 120.0, 16, "4:2:2"),
]


def report():
    print("OMC-UC hardware budget (C3)\n" + "=" * 78)
    print("\n1. ARITHMETIC  (adds / subtracts / compares / shifts; DSP blocks: ZERO)\n")
    print(f"   separable 12-tap kernel (uc_tap12)          {TAP12:6d} ops/predicted sample")
    print(f"   half-sample lattice (uc_halflat)            {HALFLAT:6d}")
    print(f"   direction+gates+limiter, V pass ({NCAND_V} cand x {NSAD_V} taps)"
          f"  {direct_ops(NCAND_V, NSAD_V):6d}")
    print(f"   direction+gates+limiter, H pass ({NCAND_H} cand x {NSAD_H} taps)"
          f"  {direct_ops(NCAND_H, NSAD_H):6d}")
    print(f"   ---------------------------------------------------")
    print(f"   per predicted sample, vertical pass         {PRED_V:6d}")
    print(f"   per predicted sample, horizontal pass       {PRED_H:6d}")
    print(f"   per SOURCE sample (1 V + 2 H predictions)   {PER_SRC:6d}")
    print(f"   per OUTPUT sample                           {PER_OUT:6.1f}")

    # ---- the RATIONAL (non-dyadic) path -------------------------------------
    # Previously unbudgeted: harness and document both sized the dyadic operator
    # only, while 720p -> 1080p -- one of the most common conversions in
    # European broadcast -- goes through this path.
    #
    # Per output sample, per pass: KTAPS taps of the polyphase bank (each a
    # hard-wired shift-add chain per phase, exactly as UC_C is for the dyadic
    # kernel: `den` distinct chains, selected by a phase counter, never a
    # runtime multiply), + KTAPS-1 accumulates, + the same limiter as the
    # dyadic path.  The VERTICAL pass additionally carries the direction stage;
    # the horizontal pass cannot afford the reach and does not have it.
    POLY_TAP = 9 + (KTAPS - 1)        # shift-adds for a 12-tap /1024 phase
    LIMIT = 10                        # min/max, allowance, 4 clamp compares
    FRAC = 6                          # uc_fsamp: 2 mults by a /16 constant + shift
    RAT_H = POLY_TAP + LIMIT
    RAT_V = POLY_TAP + LIMIT + HALFLAT + direct_ops(NCAND_V, NSAD_V) + FRAC
    print()
    print("   RATIONAL (non-dyadic) path, per OUTPUT sample")
    print(f"   polyphase tap chain + accumulate            {POLY_TAP:6d}")
    print(f"   overshoot limiter                           {LIMIT:6d}")
    print(f"   vertical pass, incl. direction + fractional {RAT_V:6d}")
    print(f"   horizontal pass (linear spine only)         {RAT_H:6d}")
    print(f"   per OUTPUT sample (1 V + 1 H)               {RAT_V + RAT_H:6d}")
    print()
    print("   Phase-table storage: sum over den of den*KTAPS coefficients.")
    tot = sum(d * KTAPS for d in range(1, 17))
    print(f"   den = 1..16 -> {tot} int16 entries = {tot*2/1024:.1f} KB of ROM,")
    print("   built once per configuration and never per pixel.  Every entry is a")
    print("   constant, so a target that only ships 3/2 and 4/3 carries 84 of them.")
    print(f"\n   For comparison, docs/HARDWARE.md section 1 puts the existing codec")
    print(f"   datapath at ~20 add/shift per sample per direction.  The upconverter")
    print(f"   is ~{PER_OUT:.0f} per OUTPUT sample; at 2x it runs on 4x as many samples,")
    print(f"   so it is the larger of the two blocks and must be sized deliberately.")
    print(f"\n   No multipliers: every coefficient is a shift-add chain, proved exact")
    print(f"   over the full datapath range by omc_uc_selfcheck_kernel() (tests/test_uc.c).")
    print(f"   No dividers, no adaptive state, no data-dependent iteration: the op count")
    print(f"   above is the worst case AND the typical case.")

    print("\n2. THROUGHPUT AND FABRIC\n")
    print(f"   {'format':24s}{'out Mpix/s':>12}{'engines':>9}{'engines':>9}{'LUTs':>10}")
    print(f"   {'':24s}{'':>12}{'@300MHz':>9}{'@500MHz':>9}{'@500MHz':>10}")
    for name, w, h, fps, sh, cf in FORMATS:
        out_pix = 4.0 * w * h * fps / 1e6            # luma output samples/s
        rate = out_pix * (2.0 if cf == "4:2:2" else 3.0)   # + chroma at half width
        e300 = int(-(-rate // 300.0))
        e500 = int(-(-rate // 500.0))
        luts = e500 * PER_OUT * LUT_PER_OP
        print(f"   {name:24s}{out_pix:12.0f}{e300:9d}{e500:9d}{luts:10.0f}")
    print(f"\n   'engines' = parallel copies of the 1-sample/clock pipeline needed to")
    print(f"   sustain the output rate including chroma.  Slices are independent, so")
    print(f"   parallelism is free structurally (the same property the codec already")
    print(f"   relies on).  LUT estimate = engines x ops x {LUT_PER_OP} LUTs per 16-bit stage.")

    print("\n3. MEMORY  (incremental over the decoder's existing budget)\n")
    print(f"   {'format':24s}{'delay slice':>13}{'intermediate':>14}{'total on-chip':>15}")
    for name, w, h, fps, sh, cf in FORMATS:
        # +1 slice of the decoder's reconstruction (the latency, materialised).
        # May live in the existing DDR frame store instead, at +1x read bandwidth.
        delay = sh * w * 2 * 2 / 1024.0                     # luma+chroma, 2 bytes
        # H pass reads intermediate rows R-7..R+7; the even ones ARE source rows
        # (already resident), so only the 8 odd ones need storing.
        inter = 8 * w * 2 * 2 / 1024.0
        print(f"   {name:24s}{delay:11.0f} KB{inter:12.0f} KB{delay + inter:13.0f} KB")
    print(f"\n   docs/HARDWARE.md section 2 puts the decoder at ~297 KB on-chip plus")
    print(f"   slice buffers (720 KB at 8K).  The delay slice can be read back from")
    print(f"   the DDR reference store the decoder already maintains, in which case")
    print(f"   the incremental ON-CHIP cost is only the intermediate line store.")

    print("\n4. BANDWIDTH\n")
    print("   Decode loop: UNCHANGED.  The upconverter is an output-stage block; it")
    print("   never writes the temporal reference and never changes what the decoder")
    print("   reads.  It adds at most one extra read of the delayed slice at the")
    print("   CODED resolution (+1x video rate) if that slice is not kept on-chip.")
    print("   The 4x output sample rate lands on the video interface, not on memory.")

    print("\n5. WHOLE-DEVICE TOTAL: CODEC + UPCONVERTER TOGETHER\n")
    print("   docs/HARDWARE.md sizes the decoder at ~20 add/shift per sample per")
    print("   direction, ~297 KB on-chip plus slice buffers (720 KB at 8K), one")
    print("   reference frame in DDR, and 1 sample/cycle per pipeline.\n")
    print(f"   {'target':26s}{'decoder':>10}{'OMC-UC':>10}{'TOTAL':>10}{'of a 230k-LUT part':>21}")
    for name, w, h, fps, sh, cf in FORMATS:
        out_pix = 4.0 * w * h * fps / 1e6
        rate = out_pix * 2.0
        e500 = int(-(-rate // 500.0))
        uc_luts = e500 * PER_OUT * LUT_PER_OP
        # decoder runs at the CODED rate (a quarter of the output rate)
        dec_rate = w * h * fps / 1e6 * 2.0
        dec_eng = int(-(-dec_rate // 500.0))
        dec_luts = dec_eng * 20 * LUT_PER_OP * 3      # x3: entropy + control + datapath
        tot = dec_luts + uc_luts
        print(f"   {name:26s}{dec_luts:10.0f}{uc_luts:10.0f}{tot:10.0f}"
              f"{100.0 * tot / 230000:20.1f}%")
    print("\n   Memory, worst supported target (2160p60 -> 4320p60):")
    print("     decoder on-chip (slice buffers, 8K sizing)   ~720 KB")
    print("     decoder other on-chip (tables, line buffers) ~297 KB")
    print("     OMC-UC delay slice + intermediate lines      ~360 KB")
    print("     ------------------------------------------------------")
    print("     TOTAL on-chip                              ~1.38 MB")
    print("   A mid-range broadcast part (Zynq UltraScale+ ZU7EV) carries 11 Mb BRAM")
    print("   + 27 Mb URAM = ~4.75 MB, so the pair sits at ~29% of on-chip memory and")
    print("   ~15% of logic at the top supported format.  DDR: one reference frame and")
    print("   2x video rate, unchanged by the upconverter.")

    cc_report()

    print("\n7. LEVERS IF A TARGET PART IS TIGHT (each measured in the delivery doc)\n")
    print("   * --uc-no-direction drops the direction search: op count falls from")
    print(f"     {PER_OUT:.0f} to {(TAP12 + 2 * TAP12) / 4.0 + 5:.0f} per output sample (~85% saving), at the cost of the")
    print("     staircase improvement (edge wander 0.29 -> 0.48 output px).  Quality")
    print("     still beats bicubic and lanczos3 on every other measure.")
    print("   * The V-pass candidate list is the single largest term; halving it")
    print("     costs measurable staircase performance (documented sweep) and should")
    print("     not be done without re-running harness/uc_verify.py.")


# ---- OMC-CC: the colour stage ---------------------------------------------
#
# Counted the same way as the upconverter above: from the normative constants
# in src/colour.c, naming the code each line counts.  The stage is POINTWISE --
# it reads no neighbour in either axis (gated in tests/test_cc.c) -- so it has
# no line store, no delay slice, and no slice period.  What it costs is
# arithmetic and table memory.

CC_MATRICES = 3          # Y2R, primaries, R2Y -- 9 constant multiplies each
CC_TERMS = 9

def cc_shift_add_luts(nbits):
    """A constant multiply written as a shift-add chain: on average half the
    coefficient's bits are set, each set bit past the first costing one adder.
    An adder of w bits costs w LUTs.  Widths are the datapath's, not the
    coefficient's."""
    return (nbits / 2.0 - 1) * 32


def cc_report():
    print("\n6. OMC-CC, THE COLOUR STAGE (src/colour.c)\n")
    print("   Per sample, per component:")
    print("     range normalise            1 constant multiply (Q15)")
    print("     YCbCr -> R'G'B'            3 constant multiplies (Q15)")
    print("     transfer -> linear         1 table lookup (4096 x 32b)")
    print("     primaries                  3 constant multiplies (Q20)")
    print("     linear -> transfer         12 compares + 12 lookups (binary search)")
    print("     R'G'B' -> YCbCr            3 constant multiplies (Q15)")
    print("     range denormalise + clamp  1 constant multiply + 4 compares")
    mults = 1 + 3 + 3 + 3 + 1
    print(f"   -> {mults} constant multiplies, 13 lookups, ~20 compares per component.")
    print("   NO dividers and NO variable-by-variable multipliers anywhere: the two")
    print("   reciprocals are configuration constants formed once per frame, and the")
    print("   tone map's data-dependent gain is applied in the LOG domain, where it")
    print("   is an add.")
    print("\n   Tone mapping adds, per sample:")
    print("     log2 (R, G, B, Y)          4 x (priority encoder + 1 lookup + 1 add)")
    print("     luminance                  3 constant multiplies")
    print("     curve                      1 shift + 1 lookup (4096 x 16b)")
    print("     saturation                 3 constant multiplies")
    print("     exp2 (R, G, B)             3 x (1 lookup + 1 shift)")
    # A 3x3 matrix is 9 constant multiplies and produces all THREE outputs, so
    # the components are already counted -- multiplying by 3 again would double
    # count, which an earlier draft of this table did.
    mat_luts = CC_MATRICES * CC_TERMS * cc_shift_add_luts(15)
    rng_luts = 6 * cc_shift_add_luts(15)      # 2 reciprocals x 3 components
    tot_luts = mat_luts + rng_luts + 1200 + 2000
    print("\n   Logic estimate, 4:4:4, one sample per clock:")
    print(f"     3 matrices x 9 constant multiplies, shift-add     ~{mat_luts/1000:.1f}k LUTs")
    print(f"     range normalise/denormalise, 6 multiplies         ~{rng_luts/1000:.1f}k LUTs")
    print("     binary search x 3 components (12 stages, compare)   ~1.2k LUTs")
    print("     log/exp + tone map datapath                         ~2.0k LUTs")
    print("     ------------------------------------------------------------")
    print(f"     TOTAL, one lane                                  ~{tot_luts/1000:.1f}k LUTs")
    print("\n   Memory:")
    print("     3 transfer tables      3 x 4096 x 32b   =  48 KB")
    print("     log2 + exp2            2 x 4096 x 32b   =  32 KB")
    print("     6 tone curves          6 x 4096 x 16b   =  48 KB")
    print("     ------------------------------------------------------------")
    print("     TOTAL table memory                        128 KB  (~32 BRAM36)")
    print("   The binary search wants a table copy per pipeline stage.  At three")
    print("   components time-multiplexed on a fabric clock a few times the pixel")
    print("   clock that is ~12 copies of the 16 KB transfer table, ~48 BRAM36 on top")
    print("   of the 32 above.  On a ZU7EV (11 Mb BRAM + 27 Mb URAM) the whole colour")
    print("   stage is ~4% of on-chip memory.")
    print("\n   THROUGHPUT, which is the real constraint and is stated rather than")
    print("   assumed: 2160p60 4:4:4 is 498 Mpixel/s.  One sample per clock would")
    print("   need a 498 MHz datapath, which mid-range fabric will not give.  Four")
    print("   parallel lanes at 125 MHz will, and the stage is pointwise so the lanes")
    print(f"   need no communication at all -- the cost is 4x the logic above (~{4*tot_luts/1000:.0f}k")
    print("   LUTs, ~17% of a ZU7EV) and the SAME tables, since they are read-only")
    print("   and shareable.  At 1080p60 4:2:2 (124 Mpixel/s of luma) one lane")
    print("   suffices and the stage is ~4% of the device.")
    print("\n   LATENCY: 32 clocks without tone mapping, 64 with -- pipeline depth")
    print("   only, no line store.  At 74.25 MHz that is 0.86 microseconds, 0.09% of")
    print("   the A2 budget, and it adds ZERO slice periods.  tests/test_cc.c sweeps")
    print("   every cross-conversion from 720p to 4320p with this term included.")


if __name__ == "__main__":
    report()
