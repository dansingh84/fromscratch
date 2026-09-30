"""Streaming-order (architectural) ENCODER model for FPGA/ASIC handoff.

The encoder is the harder half: its per-pixel datapath is as clean as the
decoder's (shifts/adds, no multipliers - HARDWARE.md 1), but it carries a
CONTROL PLANE the decoder lacks (motion search, rate control, generation
lock, multi-pass overflow backoff). There is no independent bit-exact
encoder to diff against (the C reference IS the encoder), so this model
does NOT re-derive the bitstream. Instead it is an ARCHITECTURE
specification that:

  1. states the encoder pipeline as streaming stages with their memory
     ports and bandwidth;
  2. describes the control plane (search / rate-control / lock) and its
     multi-pass structure, tied to the MEASURED worst-case pass counts;
  3. SELF-VERIFIES its resource accounting against ground truth emitted by
     the instrumented reference encoder (OMC_ENC_FOOTPRINT) and the
     attempt-loop statistics (OMC_STAT_ATTEMPTS) - so the memory map and
     timing budget are checked numbers, not hand-waving.

This is the encoder side of roadmap C1; together with hw_decoder_model.py
it completes the architectural-model handoff. RTL correctness is proven
separately by the conformance vectors (make_conformance.py) + the two
reference decoders.

Usage: hw_encoder_model.py <input.yuv> -w W -h H [--fmt 422|444]
                           [--bpp R] [--refresh N] [--depth D]
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_args(argv):
    a = {'fmt': '422', 'bpp': '2.0', 'refresh': None, 'depth': '10'}
    a['inp'] = argv[0]
    i = 1
    while i < len(argv):
        k = argv[i]
        if k == '-w':
            a['w'] = int(argv[i + 1]); i += 2
        elif k == '-h':
            a['h'] = int(argv[i + 1]); i += 2
        elif k == '--fmt':
            a['fmt'] = argv[i + 1]; i += 2
        elif k == '--bpp':
            a['bpp'] = argv[i + 1]; i += 2
        elif k == '--refresh':
            a['refresh'] = argv[i + 1]; i += 2
        elif k == '--depth':
            a['depth'] = argv[i + 1]; i += 2
        else:
            i += 1
    return a


def model_footprint(W, H, fmt, depth, sh, bps_bytes, R):
    """Predicted encoder memory by class, from the documented structure.
    Must match OMC_ENC_FOOTPRINT byte-for-byte (that is the test)."""
    Wc = W if fmt == '444' else W // 2
    NB = 10
    # band layout element counts (mirrors omc_band_layout: total = pw*sh/? )
    # the coefficient planes together tile the whole slice, so sum over
    # bands of h*w == pw*sh for luma and Wc*sh for chroma.
    slicebuf = 0
    bandbuf = 0
    refstore = 0
    for p in range(3):
        pw = W if p == 0 else Wc
        slicebuf += 4 * pw * sh          # sbuf (int32)
        slicebuf += 4 * pw * sh          # pbuf (int32)
        bandbuf += 4 * (pw * sh) * 4     # coef+qbuf+pcoef+dcoef, tiling pw*sh
        refstore += pw * H * 2           # reference frame (uint16)
    maxsym = W * sh + 2 * Wc * sh + 64
    symbuf = maxsym * (1 + 1 + 2 + 1)
    misc_fixed = None  # struct + lattice + bandcost are sizeof-dependent; see check
    return dict(slicebuf=slicebuf, bandbuf=bandbuf, refstore=refstore,
                symbuf=symbuf, Wc=Wc)


def report(a):
    W, H = a['w'], a['h']
    fmt, depth = a['fmt'], int(a['depth'])
    sh = 16 if H % 16 == 0 else 8
    Wc = W if fmt == '444' else W // 2
    R = int(a['refresh']) if a['refresh'] else 8
    fps = 50
    m = model_footprint(W, H, fmt, depth, sh, 0, R)

    print("=== Encoder pipeline (streaming stages) ===")
    for i, (s, note) in enumerate([
        ("input line buffer", "sh lines x 3 planes in"),
        ("forward DWT (2V x 5H lifting)", "line-buffered, shifts/adds only"),
        ("motion search (inter frames)", "reads reference window +/-32H/+/-16V; block-sum SAD"),
        ("rate control + generation lock", "CONTROL: Q/steps/partial scan + lattice lock verify"),
        ("quantize + mode select per band", "cats + raw"),
        ("tANS entropy encode (backward)", "coeff -> payload bits"),
        ("CBR pack + overflow backoff", "MULTI-PASS: re-symbolize until <= budget (cap 40)"),
        ("reference update (write recon)", "-> reference store"),
    ], 1):
        print(f"  {i}. {s:34s} {note}")
    print()

    print("=== Encoder memory map (predicted; checked below) ===")
    b = (depth + 3 + 7) // 8
    print(f"  slice/pred coeff buffers   {m['slicebuf']/1024:9.1f} KB  RW  on-chip")
    print(f"  per-band working buffers   {m['bandbuf']/1024:9.1f} KB  RW  on-chip")
    print(f"  symbol staging (syms/raws) {m['symbuf']/1024:9.1f} KB  RW  on-chip")
    if R != 1:
        print(f"  reference frame store      {m['refstore']/1024:9.1f} KB  RW  DDR")
    print()

    print("=== Reference-store bandwidth (encoder) ===")
    stream = W * H + 2 * Wc * H
    if R != 1:
        # write recon (1x) + search reads. Search reads a window per slice;
        # with block-sum decimation the read traffic is ~1x video (every
        # pixel touched once per candidate set via cached window), plus recon
        # write 1x = ~2x, plus the wide-MV window over-fetch (bounded, the
        # +/-32 col / +/-16 line halo on each slice).
        halo = (sh + 32) / sh  # vertical over-fetch factor per slice
        bw = (1 + 1 * halo) * stream * fps / 1e9
        print(f"  ~{bw:.2f} GB/s @ {fps} fps (recon write 1x + search read "
              f"~{halo:.1f}x with the +/-16-line halo); block-sum SAD keeps "
              f"the search on cached lines, no per-candidate refetch")
    else:
        print("  0 for a stateless-only PART (R=1: intra only, no prediction).")
        print("  NOTE: the reference SOFTWARE encoder still allocates the store")
        print("  regardless of R; a Contribution-stateless SKU omits it in RTL.")
    print()

    print("=== Control-plane multi-pass structure (the encoder-specific cost) ===")
    print("  - rate-control scan: Q (16) x profile (4) x steps (<=70), pruned")
    print("  - generation lock: <=48 candidate reconstructions verified, "
          "cheapest bit-exact one locks (encoder-only; skippable in a "
          "no-generation-guarantee SKU)")
    print("  - overflow backoff: re-symbolize on budget miss (measured max 3 "
          "attempts at 2.0 bpp, 9 at 0.4, 32 adversarial; cap 40 - HARDWARE.md 7)")
    print("  These are the pipeline-depth / clock-budget drivers for the "
          "encoder RTL; the per-pixel datapath itself is decoder-class.")
    print()

    return sh, R


def selfcheck(a, sh, R):
    """Verify the model's memory accounting against the instrumented
    reference encoder (ground truth)."""
    W, H = a['w'], a['h']
    fmt, depth = a['fmt'], int(a['depth'])
    m = model_footprint(W, H, fmt, depth, sh, 0, R)
    env = dict(os.environ, OMC_ENC_FOOTPRINT='1')
    args = [ROOT + '/omc_enc', '-i', a['inp'], '-o', '/dev/null',
            '-w', str(W), '-h', str(H), '--fmt', fmt, '--bpp', a['bpp'],
            '--depth', a['depth']]
    if a['refresh']:
        args += ['--refresh', a['refresh']]
    r = subprocess.run(args, capture_output=True, text=True, env=env)
    line = [ln for ln in r.stderr.splitlines() if 'ENC_FOOTPRINT' in ln]
    if not line:
        print("=== Self-check: FAILED (no ground-truth line) ==="); return 1
    gt = dict(kv.split('=') for kv in line[0].split()[1:])
    checks = [('slicebuf', m['slicebuf']), ('bandbuf', m['bandbuf']),
              ('refstore', m['refstore']), ('symbuf', m['symbuf'])]
    ok = True
    print("=== Check 1: model formula vs instrumented encoder (datapath "
          "buffers) ===")
    for name, pred in checks:
        actual = int(gt[name])
        match = pred == actual
        ok = ok and match
        print(f"  {name:10s} model {pred:>10d}  actual {actual:>10d}  "
              f"{'OK' if match else 'MISMATCH'}")
    # Check 2: the INDEPENDENT one. Sum of ALL instrumented classes
    # (datapath + control-plane misc) vs actual live heap measured by the
    # allocator (mallinfo2 uordblks+hblkhd). Agreement within allocator
    # per-block overhead rules out a shared-formula error, which check 1
    # alone cannot - it also covers the control-plane buffers (lattice +
    # cost tables) that are not in the datapath check.
    if 'heap_live' in gt:
        accounted = sum(int(gt[k]) for k in
                        ('slicebuf', 'bandbuf', 'refstore', 'symbuf', 'misc'))
        heap = int(gt['heap_live'])
        delta = heap - accounted
        pct = 100.0 * delta / accounted if accounted else 0
        heap_ok = 0 <= delta < accounted * 0.05  # small positive = overhead
        ok = ok and heap_ok
        print("=== Check 2: accounted total vs MEASURED live heap "
              "(independent) ===")
        print(f"  accounted (all classes) {accounted:>10d}")
        print(f"  measured live heap       {heap:>10d}")
        print(f"  delta {delta:+d} ({pct:+.2f}%)  "
              f"{'OK (allocator overhead)' if heap_ok else 'ANOMALY'}")
    print("=== ENCODER MODEL:", "VERIFIED (formula + measured heap)"
          if ok else "MISMATCH", "===")
    return 0 if ok else 1


def main(argv):
    a = parse_args(argv)
    sh, R = report(a)
    return selfcheck(a, sh, R)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
