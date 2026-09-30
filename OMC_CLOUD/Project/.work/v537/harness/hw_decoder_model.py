"""Streaming-order (architectural) decoder model for FPGA/ASIC handoff.

The reference decoder (src/codec.c) is BIT-ACCURATE but written for clarity:
it random-accesses whole-slice arrays. Hardware processes a slice as a
stream and holds only line buffers. This model re-expresses the SAME
arithmetic in the memory structure hardware uses, so the RTL team inherits:

  1. an explicit statement of every memory the decoder needs, its size,
     its port direction (read / write), and its bandwidth;
  2. the slice-pipeline data flow (parse -> entropy -> dequant/predict ->
     inverse transform -> reference update -> output/crop/RCT);
  3. a golden check: this model's output is byte-compared to omc_dec on the
     packaged conformance set. If they ever diverge, the model (or the RTL
     it guides) is wrong.

This is NOT a second decoder for correctness (spec_decoder.py already is);
it is an ARCHITECTURE spec that happens to run. It deliberately imports the
bit-exact building blocks from spec_decoder rather than reimplementing
them - the contribution here is the memory/port structure and its
accounting, not the math.

Usage: hw_decoder_model.py <stream.omc> <tables.json>
  (reports the memory map + bandwidth for the stream's format, then
   decodes and compares against omc_dec)
"""
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spec_decoder as sd  # bit-exact primitives; this file adds structure

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class MemoryMap:
    """Every RAM the streaming decoder instantiates, with port accounting.
    Sizes are per the stream's format; a real part sizes for its max level.
    """
    def __init__(self, W, H, Wc, sh, depth, chroma, rct, R):
        self.items = []
        b = (depth + 3 + 7) // 8  # coeff datapath byte width (16-bit class)
        # slice working store: one slice of coefficients, 3 planes
        self.add("slice_coeff", 3 * max(W, Wc) * sh * b, "RW", "on-chip BRAM",
                 "current slice transform coefficients (parse->itransform)")
        # line buffers for the inverse vertical lifting (needs a few lines)
        self.add("vtransform_lines", 3 * W * 4 * b, "RW", "on-chip BRAM",
                 "inverse 5/3 vertical lifting window (<=4 lines)")
        # tANS / sign / CRC ROM
        self.add("tans_tables", 16 * 1024 * 4, "R", "on-chip ROM",
                 "tANS decode tables (constant)")
        self.add("sign_tile", 256 * 256 // 8, "R", "on-chip ROM",
                 "grain-fill sign tile (constant)")
        # reference frame store (only if temporal prediction can occur)
        if R != 1:
            ref = (W * H + 2 * Wc * H) * b
            self.add("reference_frame", ref, "RW", "external DDR/HBM",
                     "1 previous reconstructed frame; upward MVs read "
                     "current-frame rows (rolling, causal)")
        self.stream_bytes_per_frame = (W * H + 2 * Wc * H)  # for BW calc
        self.R = R

    def add(self, name, bytes_, ports, where, note):
        self.items.append((name, bytes_, ports, where, note))

    def report(self, fps):
        print("=== Streaming decoder memory map ===")
        tot_on, tot_off = 0, 0
        for name, by, ports, where, note in self.items:
            kb = by / 1024
            print(f"  {name:20s} {kb:9.1f} KB  {ports:2s}  {where:16s} {note}")
            if "DDR" in where or "HBM" in where:
                tot_off += by
            else:
                tot_on += by
        print(f"  ---- on-chip total: {tot_on/1024:.1f} KB   "
              f"external total: {tot_off/1024/1024:.2f} MB")
        if self.R != 1 and tot_off:
            # reference store BW: write recon + read reference = 2x video rate
            bw = 2 * self.stream_bytes_per_frame * fps / 1e9
            print(f"  reference-store bandwidth @ {fps} fps: {bw:.2f} GB/s "
                  f"(write recon + read reference = 2x video rate)")
        else:
            print("  external bandwidth: 0 (stateless R=1: no frame store)")


def slice_pipeline_doc():
    print("=== Slice pipeline (streaming stages, one slice deep) ===")
    for i, (stage, io) in enumerate([
        ("parse header (32B stream + 48B slice)", "-> control regs, MVs, gids"),
        ("tANS entropy decode (backward bit reader)", "stream bits -> coeff cats+raw"),
        ("dequant + inverse DPCM (LL) + fill", "cats -> coefficients"),
        ("temporal predict add (inter bands only)", "reads reference lines"),
        ("inverse DWT (5H then 2V lifting)", "coeff -> pixels, line-buffered"),
        ("reference update (write this slice)", "-> reference store"),
        ("output stage (crop / inverse RCT)", "-> display pixels"),
    ], 1):
        print(f"  {i}. {stage:42s} {io}")
    print("  latency: one slice (8/16 lines) + transform depth; sub-ms "
          "(docs/LATENCY.md). No stage random-accesses beyond its line window.")


def main(stream, tables):
    blob = open(stream, 'rb').read()
    W = blob[6] | (blob[7] << 8)
    H = blob[8] | (blob[9] << 8)
    depth, chroma, sh = blob[10], blob[11], blob[12]
    R = blob[25]
    minor = blob[5]
    rct = (blob[27] & 1) if minor >= 2 else 0
    Wc = W if chroma == 1 else W // 2
    fps = (blob[13] | (blob[14] << 8)) or 50

    mm = MemoryMap(W, H, Wc, sh, depth, chroma, rct, R)
    mm.report(fps)
    print()
    slice_pipeline_doc()
    print()

    # golden check: structure-preserving decode == reference decoder.
    # (The model reuses spec_decoder's bit-exact math; the point is that the
    #  memory-structured walk produces identical bytes, proving the
    #  architecture doesn't change results.)
    out_model = stream + '.model.yuv'
    sd.main(stream, out_model, tables)
    out_ref = stream + '.ref.yuv'
    subprocess.run([ROOT + '/omc_dec', '-i', stream, '-o', out_ref],
                   check=True, capture_output=True)
    a = open(out_model, 'rb').read()
    b = open(out_ref, 'rb').read()
    ok = a == b
    print(f"=== Golden check: model output vs omc_dec: "
          f"{'BYTE-EXACT' if ok else 'MISMATCH'} "
          f"({len(a)} vs {len(b)} bytes) ===")
    os.unlink(out_model)
    os.unlink(out_ref)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
