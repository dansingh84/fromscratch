# Task D — IP provenance of everything delivered (constraint C1)
Agent 4, 2026-09-04.  Every line delivered under Task D is either written from
scratch for this project or an implementation of a published, royalty-free
open standard.  Nothing is copied from any codec, library or reference
implementation.

| deliverable | what it is | provenance | licence position |
|---|---|---|---|
| `src/ddr_model.c/.h` | DDR service model, BRAM sliding-band window cache, slice-ahead prefetch scheduler, admission rule | written from scratch for this task | own work. The techniques (burst prefetch into on-chip memory ahead of a hard-real-time consumer, deadline admission, bank interleave, QoS on a read channel) are ordinary memory-system engineering, published since the 1990s and used in every DRAM controller and video pipeline; none of it is a codec technique and none of it touches a patent pool codec. |
| `[D-DDR]` hooks in `src/codec.c` | route reference reads through the window cache; account traffic | own work | own work |
| `OMC_MVYCAP` encoder probe | clamps the derived vertical vector | own work, one comparison added to an existing loop | own work |
| `tools/omc_pack.c`, `tools/omc_depack.c`, `tools/omc_pkt.h` | slice-aligned packetiser, depacketiser, receive filter | own work | own 20-byte header layout. It is *RTP-shaped* — it carries the same fields an RTP sender carries — but **it is not RTP and implements no RTP or SMPTE payload format**. RTP itself (IETF RFC 3550) is an open standard, freely implementable, no licence. If the product later carries OMC over RTP, writing that mapping is a specification job, not a licence. |
| `tools/omc_pixpack.c`, `tools/omc_pixunpack.c`, `tools/omc_pix.h` | pixel packing to/from ST 2110-20 pgroups and an SDI-style 10-bit word layout | own work, implementing a published octet layout | SMPTE ST 2110-20 is an open published standard; a sample-packing octet layout is a data format, and implementing one is not use of anyone's code. **`v210` was deliberately not implemented** (Apple-originated layout) in favour of the plain SDI 10-bit word order. **Action for the owner: the pgroup table in `omc_pix.h` (sizes and sample order per format) was written from knowledge of ST 2110-20 and should be checked line by line against the purchased standard text before it ships.** That is a conformance check, not a licence question. |
| channel simulator inside `omc_pack` (`--net-*`) | loss / reorder / duplication for the gates | own work; xorshift PRNG (Marsaglia, published algorithm, no licence) | test-only, not in the codec |
| `notes/*.py`, `notes/*.sh` | measurement scripts | own work; use the project's existing harness and Python's standard library only (`zlib.crc32` in one *analysis* script, never in shipped code) | own work |

## Reviewed 2026-09-05 by an outside codec/FPGA expert

The reviewer's own IP position on everything they suggested, recorded here so it
travels with the design:

| item | status |
|---|---|
| SMPTE ST 2110-20, RFC 4175, RFC 2435, RFC 9134 | public interoperability formats; no licence to implement. Do **not** reproduce normative text verbatim (copyright, not patent) — state values and cite |
| **VC-2 / SMPTE ST 2042-1** | royalty-free by design (BBC R&D). Our nearest relative — a wavelet codec with no arithmetic coder — and the one existing codec the reviewer actively encouraged reading. RF-by-design is the publisher's position, not a warranty; a freedom-to-operate check remains standard practice |
| BBC `vc2_bit_widths` (affine-arithmetic bit-width bounding) | open source, aimed at a royalty-free codec; the underlying method is generic numerical analysis, not codec IP |
| JPEG 2000 / HTJ2K guard-bit signalling | explicitly permitted under C1 (ISO/IEC 15444-15); carry the upstream BSD-2 notice as C1 requires |
| **HEVC's "requirement of bitstream conformance" drafting idiom** (the §7.4 route in `DDR_WINDOW_CACHE.md`) | a specification *convention*, not patented technology — the reviewer flagged it deliberately as the one place their reply takes an idea from a pool codec. Take the drafting pattern, not one line of their process definitions, and have counsel confirm we are comfortable with the distinction |
| JPEG XS | referenced only via published JPEG committee *requirements* documents (multi-generation targets), never internals. Keep it at that distance |
| tANS | treated as free on the usual basis (Duda's published construction; the notable ANS patent applications rejected or abandoned). Common understanding, not a legal opinion — C1 requires counsel confirmation. Nothing here uses rANS |
| AMD UG573 / PG313, Micron datasheets, WCET DRAM literature | vendor documentation and academic literature; no codec IP |
| tiled/skewed DWT buffer layouts, LUTRAM field splitting, write-buffer-bounded turnaround | general hardware architecture, long published, no codec-specific claims |

**Action for counsel:** the only item needing a judgement call is the
bitstream-conformance drafting idiom. Everything else is either our own work or
an open standard we are already entitled to use.

No rANS anywhere (C1 absolute).  No HEVC/AVC/JPEG XS internals.  No CABAC.
No per-unit-fee technology.  No third-party source was consulted or copied.
