# Operating note: quality monitoring for Perception mode

OMC v4's default (Perception) mode deliberately trades PSNR/VMAF for
appearance: erased grain is regenerated with the right energy and the wrong
(unverifiable) realization, so full-reference metrics score it 0.05-0.8 dB /
up to ~0.1 VMAF below Fidelity mode on identical streams while looking
better. Automated QoE probes must account for this or they will false-alarm:

1. **Do not gate Perception-mode links on full-reference PSNR/VMAF deltas**
   against source. Use them for trend/regression monitoring only (a sudden
   *change* still means something; the absolute level does not).
2. **Structural checks remain valid:** sync/CRC rates, slice loss and
   concealment counters, exact-CBR conformance (stream size = 32 + n*F),
   decoder final-state errors - none of these are affected by fill.
3. **For absolute quality audits** (acceptance, disputes), either switch the
   encoder to Fidelity mode (`--no-fill`) for the audit window - decoders
   need no change - or use blind viewing per the rev. 6 blind-viewing
   protocol (see REPORT.md 18.x).
4. A stream's mode is observable: Perception-mode slices carry nonzero
   grain-fill bits in their headers (bits [328, 346) in the current,
   minor >= 1, slice-header layout; see BITSTREAM.md 9.3-9.5); a
   monitoring probe can label streams accordingly.

**v4.7 observability.** The v4.5-v4.7 fill variants are directly
monitorable from the stream header: byte 27 (pixel_flags) bit 1 signals
the correlated fill tile (`--grain-corr`, bitstream minor >= 5) and bit 2
the STATIC fill tile (`--fill-static`, minor >= 7); bits 3-7 are reserved
zero. By contrast, grain-hold v3 and perceptual slice-budget allocation
are encoder-only decisions made at existing pipeline points - they change
what the encoder emits, not the stream syntax, and are invisible in-stream
by design (see ENHANCEMENTS_LEDGER E-9/E-10/E-11). None of the v4.5-v4.7
changes adds buffering, so the LATENCY.md table stands unchanged.
