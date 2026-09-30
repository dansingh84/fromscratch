"""Burst-loss robustness harness (ST 2110-style network failures).

Applies loss patterns to OMC streams and verifies, per pattern:
  1. the decoder never crashes and always emits full frames;
  2. after the last lost slice, the picture returns to byte-equality with
     the clean decode within R frames (the normative recovery bound);
  3. all output samples are in range.

Patterns: single slice, contiguous burst (N slices), Gilbert-Elliott
random bursts at several loss rates, full frame loss, and stream-header
survivability is NOT tested here (the header repeats per the transport
note; a lost header is a session-layer event, not a codec event).

Loss model: a lost packet = the affected slice bytes are zeroed (CRC then
fails and the decoder conceals), which is how a depacketizer presents a
gap to the decoder per TRANSPORT_NOTE.md.

Usage: loss_harness.py <stream.omc> [seed]
"""
import subprocess
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_header(b):
    W = b[6] | (b[7] << 8)
    H = b[8] | (b[9] << 8)
    depth, chroma, sh = b[10], b[11], b[12]
    bps = int.from_bytes(b[21:25], 'little')
    R = b[25]
    return W, H, depth, chroma, sh, bps, R


def decode(path, out):
    r = subprocess.run([ROOT + '/omc_dec', '-i', path, '-o', out],
                       capture_output=True)
    return r.returncode


def main(stream, seed=7):
    blob = bytearray(open(stream, 'rb').read())
    W, H, depth, chroma, sh, bps, R = parse_header(blob)
    nsl = H // sh
    sb = bps // 8
    F = sb * nsl
    nframes = (len(blob) - 32) // F
    wc = W if chroma == 1 else W // 2
    words = W * H + 2 * wc * H
    maxv = (1 << depth) - 1
    tmp = os.path.dirname(os.path.abspath(stream))
    clean_out = os.path.join(tmp, '_clean.yuv')
    assert decode(stream, clean_out) == 0
    clean = np.fromfile(clean_out, dtype='<u2')

    def slice_span(f, s):
        return 32 + f * F + s * sb, 32 + f * F + (s + 1) * sb

    def run_pattern(name, losses):
        """losses = list of (frame, slice) pairs to zero."""
        dmg = bytearray(blob)
        for (f, s) in losses:
            a, b = slice_span(f, s)
            dmg[a:b] = b'\0' * (b - a)
        p = os.path.join(tmp, '_dmg.omc')
        open(p, 'wb').write(bytes(dmg))
        out = os.path.join(tmp, '_dmg.yuv')
        rc = decode(p, out)
        if rc != 0:
            return f"{name}: CRASH/refuse (rc={rc})"
        got = np.fromfile(out, dtype='<u2')
        if got.size != clean.size:
            return f"{name}: SHORT OUTPUT"
        if got.max() > maxv:
            return f"{name}: OUT-OF-RANGE sample {got.max()}"
        last_f = max(f for (f, s) in losses)
        rec = None
        for f in range(last_f + 1, nframes):
            if np.array_equal(got[f * words:(f + 1) * words],
                              clean[f * words:(f + 1) * words]):
                rec = f - last_f
                break
        if rec is None and last_f + 1 < nframes:
            return f"{name}: NO RECOVERY within {nframes - 1 - last_f} frames"
        if rec is not None and rec > R:
            return f"{name}: recovery {rec} frames EXCEEDS bound R={R}"
        return f"{name}: OK (recovered in {rec} frames, bound {R})" if rec \
            else f"{name}: OK (loss at stream end)"

    results = []
    results.append(run_pattern("single slice", [(1, nsl // 2)]))
    results.append(run_pattern("burst 8 slices", [(1, s) for s in range(4, 12)]))
    results.append(run_pattern("full frame", [(1, s) for s in range(nsl)]))
    results.append(run_pattern("two frames back-to-back",
                               [(1, s) for s in range(nsl)] +
                               [(2, s) for s in range(nsl)]))
    rng = np.random.RandomState(seed)
    for rate, burst in ((0.01, 4), (0.05, 8), (0.20, 16)):
        losses, in_burst, left = [], False, 0
        for f in range(1, nframes - R):
            for s in range(nsl):
                if in_burst:
                    losses.append((f, s))
                    left -= 1
                    in_burst = left > 0
                elif rng.rand() < rate / burst:
                    in_burst, left = True, burst - 1
                    losses.append((f, s))
        if losses:
            results.append(run_pattern(
                f"Gilbert-Elliott {int(rate*100)}% burst={burst} "
                f"({len(losses)} slices lost)", losses))
    ok = all(': OK' in r for r in results)
    for r in results:
        print(r)
    print("LOSS-HARNESS:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 7))
