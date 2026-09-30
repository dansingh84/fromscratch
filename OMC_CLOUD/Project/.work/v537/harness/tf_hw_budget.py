"""OMC-TF hardware budget (C3): arithmetic, memory, bandwidth, latency.

The op counts are ANALYTIC, derived from the normative constants in
include/omc_tf.h and the loops in src/tfilt.c.  Each line names the code it
counts so it can be audited against the source rather than trusted.  This
mirrors harness/uc_hw_budget.py so the two blocks add up on one device.

Honesty calibration, identical to docs/HARDWARE.md section 9a and to the
upconverter's budget: the OPERATION COUNTS are certain (they are read off fixed
loops with no data-dependent iteration); the LUTs-per-operation figure and the
achievable clock are ESTIMATES, and nothing here has been through synthesis.

Run: python3 harness/tf_hw_budget.py
"""

# ---- normative constants (must match include/omc_tf.h and src/tfilt.c) ----
BW, BH = 8, 4                      # OMC_TF_BW, OMC_TF_BH
PAD = 8                            # OMC_TF_PAD
NX, NY = 17, 5                     # OMC_TF_SEARCH_NX / NY
DECX, DECY = 4, 2                  # OMC_TF_SEARCH_DECX / DECY
LUT_PER_OP = 18                    # same estimate the upconverter budget uses

# ---- arithmetic, per CODED sample -----------------------------------------
# prev_at(): integer position is 1 clamped load; a half-pel position costs at
# most 3 adds + 1 shift.  Vectors are half-pel only when the encoder signalled
# or the search chose a half-pel offset, so 2 is a fair amortised figure and 4
# is the worst case; the worst case is used.
PREV_AT = 4

# gate 1 evidence, per sample (src/tfilt.c, the `sad`/`act` loop):
#   sad: 1 compare-select + 1 subtract + 1 accumulate      = 3
#   act: 2 subtracts + 2 abs + 2 accumulates               = 6
#   pblk store                                             = 1
GATE1 = PREV_AT + 3 + 6 + 1

# gate 1 decision, per BLOCK: sad*k is a shift for k=2, plus afloor*n (a
# constant per block size, precomputed), one add and one compare.
GATE1_BLOCK = 3

# gate 2 + blend, per sample (only in admitted blocks; counted for all samples
# because the worst case is what has to be built):
#   1 subtract, 1 abs, 2 threshold compares, half_sym/quarter_sym
#   (1 abs + 1 add + 1 shift + 1 sign-restore = 4), 1 subtract, 1 store
GATE2 = 1 + 1 + 2 + 4 + 1 + 1

# residual search, per sample: (NX + NY - 1) candidates, each costing
# PREV_AT + 3 ops, evaluated on 1/(DECX*DECY) of the samples, once per REGION.
SEARCH = (NX + NY - 1) * (PREV_AT + 3) / float(DECX * DECY)

PER_SAMPLE = GATE1 + GATE1_BLOCK / float(BW * BH) + GATE2 + SEARCH

FORMATS = [
    # name, W, H, fps, slice_h
    ("1080p60  4:2:2", 1920, 1080, 60.0, 16),
    ("2160p60  4:2:2", 3840, 2160, 60.0, 16),
    ("2160p120 4:2:2", 3840, 2160, 120.0, 16),
]


def report():
    print("OMC-TF hardware budget (C3)\n" + "=" * 74)
    print("\n1. ARITHMETIC  (adds / subtracts / compares / shifts; DSP blocks: ZERO)\n")
    print("   motion-compensated fetch (prev_at, worst case)   %6.1f ops/sample" % PREV_AT)
    print("   gate 1 evidence: sad + activity                  %6.1f" % GATE1)
    print("   gate 1 decision, amortised over an %dx%d block     %6.2f"
          % (BW, BH, GATE1_BLOCK / float(BW * BH)))
    print("   gate 2 outlier test + convex blend               %6.1f" % GATE2)
    print("   residual search (%d+%d cands, decimated %dx%d, per region) %6.2f"
          % (NX, NY - 1, DECX, DECY, SEARCH))
    print("   " + "-" * 52)
    print("   TOTAL per CODED sample                           %6.1f" % PER_SAMPLE)
    print("""
   Context: docs/HARDWARE.md section 1 puts the existing decoder datapath at
   ~20 add/shift per sample per direction, and harness/uc_hw_budget.py puts the
   upconverter at ~161 per OUTPUT sample.  OMC-TF runs at the CODED rate — a
   quarter of the upconverter's sample rate at 2x — so it is by far the
   cheapest of the three blocks.

   No multipliers: k = 2 is a shift, the blend weights 1/2 and 1/4 are shifts,
   and the half-pel taps are the codec's own (a+b+1)>>1 / (a+b+c+d+2)>>2.
   No dividers.  No data-dependent iteration: every loop bound above is a
   compile-time constant, so this count is the worst case AND the typical case.""")

    print("\n2. THROUGHPUT AND FABRIC\n")
    print("   %-17s%12s%10s%12s" % ("format", "coded Mpix/s", "engines", "LUTs"))
    print("   %-17s%12s%10s%12s" % ("", "(incl chroma)", "@500MHz", "@500MHz"))
    for name, w, h, fps, sh in FORMATS:
        rate = w * h * fps / 1e6 * 2.0          # 4:2:2 => 2x luma samples
        eng = int(-(-rate // 500.0))
        print("   %-17s%12.0f%10d%12.0f"
              % (name, rate, eng, eng * PER_SAMPLE * LUT_PER_OP))
    print("""
   Slices remain independent, so parallelism is structural — the same property
   the codec and the upconverter already rely on.""")

    print("\n3. MEMORY  (the filter's entire cost is memory, not delay)\n")
    print("   %-17s%14s%14s%14s" % ("format", "window", "tail", "total"))
    for name, w, h, fps, sh in FORMATS:
        rows_win = sh + 2 * PAD
        # 4:2:2: luma width + two half-width chroma planes = 2x luma width
        kb = lambda r: r * w * 2 * 2 / 1024.0
        print("   %-17s%12.0f KB%12.0f KB%12.0f KB"
              % (name, kb(rows_win), kb(PAD), kb(rows_win + PAD)))
    print("""
   The window is the previous frame around the slice being reconstructed; the
   tail is the %d rows above it, copied before reconstruction overwrote them.
   The lower %d rows of the window are still unwritten in the reference store,
   so a hardware implementation can read them in place and carry only
   %d + %d = %d rows instead of %d + %d.  The software keeps the full window for
   clarity; the budget above states the software figure, which is the larger.

   For scale: docs/HARDWARE.md sizes the decoder at ~297 KB on-chip plus slice
   buffers, and the upconverter adds ~360 KB at its top format.""" %
          (PAD, PAD, 16, PAD, 16 + PAD, 16 + 2 * PAD, PAD))

    print("\n4. LATENCY:  ZERO ADDED  (A2)\n")
    print("""   The filter consumes (a) the slice that has just been reconstructed and
   (b) the previous frame, which is already resident as the temporal
   reference.  It never reads a later slice and never waits for the frame to
   complete, so it adds no delay to the sub-1 ms budget at any format.  This
   is verified structurally by the poisoned-row gate in tests/test_tf.c, which
   fails if the filter ever indexes outside [-pad, h+pad) of the previous
   frame around the current slice.

   It does NOT change the upconverter's one-slice-period cost, and it does not
   interact with it: the filter runs in the coding loop at coded resolution,
   the upconverter runs after it as an output stage.""")

    print("\n5. BANDWIDTH\n")
    print("""   Unchanged in the decode loop.  The filter reads the reference the decoder
   already reads for prediction and writes the reconstruction it already
   writes.  The encoder pays the same cost a second time, because it must run
   the identical filter to keep rt = 0 — that is the price of an in-loop tool
   and it is paid in logic, not in bits: the bitstream is byte-identical in
   size whether the filter is on or off.""")


if __name__ == "__main__":
    report()
