/* OMC-1 (Open Mezzanine Codec, bitstream v1.0) - public API and normative constants.
 *
 * A royalty-free, intra-only, slice-based contribution codec:
 *   - slices of 16 (or 8) luma lines, fully independent (latency / error unit)
 *   - CDF 5/3 integer lifting wavelet, 2 vertical x 5 horizontal levels
 *   - power-of-two shift quantizer (round-half-away, recon = q<<s): idempotent
 *   - static-table tANS entropy coding, 2-way causal context (left significance)
 *   - exact-CBR rate control: every slice exactly `bits_per_slice` bits
 *
 * Per-pixel datapath uses shifts/adds/table-lookups only (FPGA-native, C3).
 */
#ifndef OMC1_H
#define OMC1_H

#include <stddef.h>
#include <stdint.h>

/* ===================================================================
 * OMC v5.0 -- RELEASE IDENTITY
 * ===================================================================
 * This is OMC version 5.  The major version is carried in the stream at
 * header byte 4 (offset 4, immediately after the 4-byte magic) and a decoder
 * REFUSES any stream whose major does not match its own -- omc_read_stream_header
 * returns -2.  A v4 decoder therefore rejects a v5 stream outright rather than
 * mis-decoding it, and so does the reverse.  That is the intended hard gate:
 * v5 changed normative reconstruction rules and there is no safe partial
 * interoperability.
 *
 * VERSIONING NOTE: the MAJOR is 5 (this product).  The stream MINOR stays 12
 * and is NOT reset, because the minor names a set of normative RECONSTRUCTION
 * RULES defined in docs/TEMPORAL_T5.md 12.23, and renumbering it would break
 * the only link between this build and the document that specifies it.
 * Major 5 supplies the compatibility gate; the minor supplies traceability.
 *
 * Full account of what v5 is, every default and every measurement:
 * docs/OMC_V5.md. */
#define OMC_PRODUCT_VERSION "5.3.6"   /* 2026-09-08: the five agents' and the outside review's findings on v5.3.5, merged and applied (docs/CHANGES_v5_3_6.md) */
#define OMC_VERSION_MAJOR 5

#define OMC_RELEASE_MINOR 12
#define OMC_VERSION_MINOR 13 /* sect.65: the grain-fill parameters are NORMATIVE --
                              * fill_value_p() runs at DECODE time, so the ants gate, the
                              * fill threshold, the amplitude divisor and the intra latch
                              * all change the decoded picture.  Proof: one stream decoded
                              * with and without them differs by 8 016 330 luma samples and
                              * rt goes from 0 to NONZERO.  They were briefly treated as
                              * encoder-only levers and that was wrong.  v5.2 compiles them
                              * into BOTH ends, so encoder and decoder agree by
                              * construction; a minor-12 decoder would silently produce the
                              * wrong picture from a minor-13 stream, so the minor bumps and
                              * the two refuse each other rather than disagreeing quietly. */ /* T5: rebuilt temporal layer + always-on reversible XSL.
                              * NOT bumped by v5.1: v5.1 changes only ENCODER policy
                              * (the in-gamut repair, docs/OMC_V5_1.md), so the
                              * bitstream syntax and every normative reconstruction
                              * rule are identical to v5.0 and a v5.0 decoder decodes
                              * a v5.1 stream byte-exactly.  The minor names a set of
                              * RECONSTRUCTION rules; those did not change. */
/* sect.80: BUMPED 12 -> 13.  v5.2 made the grain-fill parameters NORMATIVE
 * (omc_filldiv 2, omc_filldiv_c 1, omc_fillthr 1) and OMC_VERSION_MINOR was
 * raised to 13 to say so -- but that constant is library metadata and never
 * reaches the wire.  The stream header writes OMC_MINOR_T5 (codec.c:297) and
 * the decoder gates on it (codec.c:349), so a v5.2 stream carried minor 12,
 * identical to v5.0/v5.1, and a v5.1 decoder ACCEPTED it and silently
 * mis-reconstructed it.  Measured: 47.06% of luma samples differ, peak 165
 * codes, mean 27.35.  That is precisely the C8 failure the version gate
 * exists to prevent, and three documents claimed it could not happen. */
#define OMC_MINOR_T5 16      /* v5.3.6 (2026-09-08) keeps minor 16: no normative change shipped (the level-2 boundary predictor is a candidate, dwt.c sect.55, BITSTREAM 4.2a.1); 16 = Agent 1 block motion field + half-pel (NORMATIVE, sect. S5.84); was 15 = v5.3.5 rate-rung fill divisor
                                 + Task C slice-header state hash (3-bit table-group ids, 16-bit hash, 14 reserved)
                                 + zero-mean lifting rounding [S5-DC] + level-1 chroma fill halving at 4:4:4 [S5.31].
                                 One bump for the whole integration (IP review: ship normative changes once). */
#define OMC_MINOR_T5_PREHASH 14
                              /* (minor 14, v5.3.5 rate-rung note:) the decoder derives the same rung from the
                                 header and computes a louder fill above 0.375
                                 bits per coded sample, so minor 13 and 14
                                 reconstruct differently and must refuse each
                                 other.  Bumped per the sect.11.6 rule: any
                                 change to a rule the DECODER executes moves
                                 OMC_MINOR_T5, the only version byte on the
                                 wire. */
/* 13 in v5.3: */      /* 11 adds pad neutralization (baseband-exact rasters);
                                12 adds the flattest-tier grain-fill gate and the
                                static fill tile (docs/TEMPORAL_T5.md 12.23) */

/* T5 pixel domain: every omc_frame_t (encoder input, decoder output, recon)
 * carries samples as u16 = true_value + OMC_PIX_BIAS, UNCLIPPED to the legal
 * range: values live in [0, (2^depth - 1) + 2*OMC_PIX_BIAS].  The bias keeps
 * reconstruction overshoot (quantization ringing past black/white) exactly
 * representable, which is one of the three pillars of the generation-exact
 * guarantee (the others: the reversible boundary edit + mandatory un-blend,
 * and the invariant temporal prediction).  Display/legal-range output is a
 * non-normative projection: clip(v - OMC_PIX_BIAS, 0, 2^depth - 1). */
#define OMC_PIX_BIAS 2048
/* Decoder output-stage contract (A2).  The vertical rescaler needs a few source
 * rows beyond the row it is producing.  HOW the decoder hands rows to it decides
 * what that costs:
 *   OMC_OUT_RASTER  (0, the product's design and the default) -- rows are handed
 *      over as they become final and the output is clocked at the destination
 *      raster rate, so the wait is `reach` LINES.  Requires a `reach`-row output
 *      buffer (<= 68 lines at the steepest supported ratio) and a free-running
 *      output clock, which a genlocked facility already has.
 *   OMC_OUT_SLICE_BATCHED (1) -- rows are handed over one whole slice at a time,
 *      so the wait rounds up to ceil(reach/slice_h) whole SLICE PERIODS.  This is
 *      what the model charged before 2026-08-12; declare it if an integration
 *      cannot meet the raster contract, and take the higher figure. */
#define OMC_OUT_RASTER 0
#define OMC_OUT_SLICE_BATCHED 1

#define OMC_XSL_LIM_MINOR9 8 /* normative boundary-blend cap below 0.75 bpp,
                                 * in codes at 10-bit scale (minor 9).  See
                                 * src/codec.c xsl_lim_for(). */
#define OMC_MINOR_UC 8
#define OMC_MINOR_XSL 9     /* 9: cross-slice boundary reconstruction (XSL level 3 +
                               refresh barriers) is NORMATIVE-ON for the whole stream.
                               No per-slice bits; the minor IS the signal. */      /* 8: stream byte 26 carries uc_ratio (OMC-UC upconversion).
                             * Written ONLY when uc_ratio != 0, so every stream an
                             * encoder produced before this feature -- and every
                             * conformance hash -- is byte-identical. */

/* ---- normative constants ---- */
#define OMC_SYNC 0x4F4D5331u      /* "OMS1" slice sync word */
#define OMC_MAGIC 0x4F4D4331u    /* "OMC1" stream header magic */
#define OMC_NBANDS 10             /* per plane: LL5 HL5 HL4 HL3 LH2 HL2 HH2 LH1 HL1 HH1 */
#define OMC_NPLANES 3
#define OMC_CHUNK 256             /* refinement chunk, in coefficients */
#define OMC_MAX_SHIFT 15
#define OMC_LL_CAP 2              /* absolute max shift for the LL band (anti-banding G2) */

typedef enum { OMC_CF_422 = 0, OMC_CF_444 = 1 } omc_chroma_t;

/* colorimetry signaling (transparent carriage, B3) */
typedef struct {
    uint8_t primaries;  /* 1=BT.709, 9=BT.2020 (ISO 23001-8 code points) */
    uint8_t transfer;   /* 1=BT.709, 18=HLG (16=PQ is refused by the validator since v5.3.6: not carried) */
    uint8_t matrix;     /* 1=BT.709, 9=BT.2020ncl */
    uint8_t full_range; /* 0=limited (video), 1=full */
} omc_colorimetry_t;

typedef struct {
    uint16_t width;          /* luma width, multiple of 32 */
    uint16_t height;         /* luma height, multiple of slice height */
    uint8_t bitdepth;        /* 8, 10 or 12 */
    omc_chroma_t chroma;
    uint8_t slice_h;         /* 8 or 16 luma lines */
    uint16_t fps_num, fps_den;
    omc_colorimetry_t color;
    uint32_t bits_per_slice; /* exact CBR budget per slice, multiple of 8 */
    uint8_t tune_vmaf;       /* encoder-only: 0 = plane-fair allocation (default),
                                1 = luma-weighted (VMAF-oriented) allocation */
    uint8_t refresh_r;       /* rolling intra-refresh period in frames (A5 recovery
                                bound); 0 -> default 8. Encoders MUST intra-code each
                                slice at least once every refresh_r frames.
                                [S3-REFRESH] OMC_REFRESH_NONE (255): no scheduled
                                wave — recovery is on demand through
                                omc_enc_request_refresh() (a return path is
                                required; multicast/join deployments keep a
                                period).  The value is carried in the stream
                                header so both ends derive the same barriers. */
    uint8_t mv_regions;      /* REMOVED (T5): motion is DERIVED from committed
                                reconstruction history, never searched against
                                the source, so there is nothing to configure.
                                Must be 0. */
    /* v4.2 extension fields (all zero = 4.1-identical behavior) */
    uint16_t display_width;  /* true width before padding; 0 = coded width */
    uint16_t display_height; /* true height before padding; 0 = coded height */
    uint8_t rct;             /* 1 = reversible color transform applied (RGB input,
                                requires 4:4:4 and depth <= 10; BITSTREAM.md section 8) */
    uint8_t ver_minor;       /* decode side: stream's minor version as read from the
                                stream header (0 = v4.0 slice-header layout, 1 = v4.1
                                wide-MV + fill-gain layout). Encoders always write
                                OMC_VERSION_MINOR. Set by omc_read_stream_header. */
    uint8_t no_block_mv;     /* REMOVED (T5): the per-block motion field is
                                gone from the bitstream.  Must be 0. */
    uint8_t lossless_pref;   /* encoder-only: 1 = lossless-preferred. Each slice
                                starts from the minimum-quantization plan (all
                                shifts 0, no fill); if it fits the CBR budget the
                                slice is bit-exact, else the normal overflow
                                backoff coarsens it (stream stays exact-CBR).
                                Requires fill_grain == 0. Per-frame lossless status is
                                reported by the CLI via rt=0 recon compare. */
    uint8_t no_deadzone;     /* encoder-only: 1 = disable the 9/16 detail-band
                                deadzone (v4.4 default ON; auto-disabled under
                                tune_vmaf whose 0.375 bias cancels it).
                                Reconstruction points never move either way. */
    uint8_t reserved_was_fill_static; /* minor 11 carried the fill tile
                                phase here; minor 12 makes the
                                frame-independent tile the only
                                behaviour, so this field is inert and
                                option-word bit 2 is reserved zero. */
    uint8_t grain_corr;      /* 1 = fill signs from the CORRELATED tile
                                (organic film grain; measured lag-1 ~ -0.33);
                                0 = white tile (electronic noise; default).
                                Carried in stream-header pixel_flags bit 1 -
                                decoders honor the stream. */
    uint8_t grain_replace;   /* encoder-only: 1 = OMC_GR classifier (inter-scale
                                parent-support test) widens the finest-band zero
                                zone to a full step ONLY where energy has no
                                coarser-scale support AND the fill regenerates
                                it. Default 0 pending blind-viewing signoff. */
    uint8_t tf_mode;         /* REMOVED (T5): the in-loop temporal filter was
                                part of the old temporal engine and is gone.
                                Must be 0; streams with the bits set are
                                rejected (a temporal filter re-applied at each
                                generation compounds and can never be
                                generation-exact). */
    uint8_t uc_ratio;        /* OMC-UC output conversion, stream byte 27 bits 3-4:
                                0 = none (decode at coded resolution, the default and
                                the only value <= minor 7), 1 = 2x, 2 = 4x in both
                                dimensions. This is the encoder's RECOMMENDATION; a
                                decoder may override it from its own output-port
                                configuration. Conformance is defined on the pair
                                (stream, ratio): the upconverted output is bit-exact.
                                Setting it makes the encoder write minor 8. */
    uint8_t uc_out_batched;  /* how the DECODER hands rows to the rescaler.
                                0 = OMC_OUT_RASTER (default, the product's
                                design): rows go downstream as they become final
                                and the wait is `reach` LINES.  1 =
                                OMC_OUT_SLICE_BATCHED: a whole slice at a time,
                                so the wait rounds up to whole slice periods.
                                Affects the LATENCY FIGURE only -- never the
                                bitstream, never a pixel. */
    uint8_t a2_strict;       /* 1 = REFUSE any (format, uc_ratio) pair whose total
                                latency reaches 1 ms; 0 (default) = permit it and
                                let the caller declare the figure, which
                                omc_config_latency() reports.  A2 binds the
                                contribution PRODUCT; it is not a reason to make
                                a correct conversion unavailable on a leg that
                                can afford it.  A facility that needs the bar
                                enforced rather than declared sets this. */
uint8_t fill_grain;      /* encoder-only: 1 = regenerate the grain the
                                quantizer removed (the amplitude-matched fill).
                                DEFAULT 0 -- OFF.  Measured on the whole corpus
                                (docs/TEMPORAL_T5.md 12.23.8), running with the
                                fill off is at least as good on BOTH metrics at
                                once: lower ants tail on all three planes and
                                higher VMAF-NEG.  Lossless coding requires it
                                off (it cannot regenerate grain and stay
                                lossless).  CLI: --fill / --no-fill. */
    uint8_t fill_grain_explicit; /* encoder-only, [G-NOFILL] 2026-09-06: 1 = the caller SET
                                fill_grain deliberately (tool --fill/--no-fill), so the
                                library's fill-on default must not override it.  Before
                                this the library forced fill_grain = 1 whenever OMC_FILL
                                was unset and --no-fill was silently inert. */
} omc_config_t;

/* One frame of planar pixels, uint16 little-endian, T5 BIASED DOMAIN:
 * sample = true_value + OMC_PIX_BIAS, range [0, 2^bitdepth - 1 + 2*OMC_PIX_BIAS].
 * Encoder input, decoder output and recon all use this domain; it is the
 * generation-chain interchange format (CDR: coded-domain raw). */
typedef struct {
    uint16_t *p[OMC_NPLANES];
    int stride[OMC_NPLANES]; /* in samples */
} omc_frame_t;

typedef struct omc_enc omc_enc_t;
typedef struct omc_dec omc_dec_t;

/* ---- encoder ---- */
/* T5: undo the (always-on, exactly reversible) cross-slice boundary edit on a
 * whole picture, recovering the exact committed reconstruction that produced
 * it.  omc_enc_frame() calls this on (a copy of) its input automatically —
 * the mandatory un-blend that makes generation chains byte-exact.  Exposed
 * for tests and for callers driving omc_enc_slice() directly (who must apply
 * it themselves before slicing; it reads 2 rows below each slice boundary).
 * Frame values are in the T5 biased domain. */
void omc_xsl_unblend(omc_frame_t *f, const omc_config_t *cfg, int frame_idx);

omc_enc_t *omc_enc_create(const omc_config_t *cfg);
void omc_enc_destroy(omc_enc_t *e);
/* Encode one slice (rows [slice_idx*slice_h, +slice_h)). Strictly causal: touches
 * only those input rows (plus the encoder's own previous reconstructed frame,
 * the single permitted temporal reference). Frames must be fed in order.
 * If recon is non-NULL, the encoder-side reconstruction of the slice rows is
 * written there (for rt=0 verification). Returns bytes written or <0 on error. */
int omc_enc_slice(omc_enc_t *e, const omc_frame_t *in, int frame_idx, int slice_idx,
                  uint8_t *dst, omc_frame_t *recon);
/* Convenience: whole frame = all slices concatenated. */
int64_t omc_enc_frame(omc_enc_t *e, const omc_frame_t *in, int frame_idx,
                      uint8_t *dst, size_t cap, omc_frame_t *recon);
/* [S3-REFRESH] REFRESH ON DEMAND (control plane, not bitstream).  Ask the
 * encoder to intra-code slices [first_slice, first_slice + count) the next
 * time each of them is encoded (the current frame if that slice has not been
 * encoded yet, else the next frame).  Requests accumulate and are consumed
 * one slice at a time.  Nothing in the stream marks a requested refresh: the
 * decoder sees ordinary all-intra slices, the transform keeps its cross-slice
 * boundary term (only the SCHEDULED wave suppresses it, rule d), and every
 * re-encode generation is unaffected (an intra-coded lattice picture is
 * re-emitted exactly whether the next encoder codes it intra or inter).
 * Recovery of a lost slice therefore heals top-down: a run of contaminated
 * slices is requested as one contiguous block so each slice's boundary term
 * reads an already-healed predecessor.  Returns the number of slices newly
 * marked, or -1 on a bad range. */
int omc_enc_request_refresh(omc_enc_t *e, int first_slice, int count);
/* Number of slices with a pending (not yet consumed) refresh request. */
int omc_enc_refresh_pending(const omc_enc_t *e);
/* Gamut report: committed samples so far outside the legal range [0, 2^depth).
 * Nonzero means a legal-range baseband hop would alter the committed picture,
 * so this stream is NOT safe for baseband-interchange generation chains (the
 * CDR interchange is always safe).  Instrumentation only; never changes
 * coding.  The reference encoder CLI prints the verdict at end of encode.
 * Returns -1, "not measured", if any slice was encoded with recon == NULL:
 * the report is taken on the EMITTED picture, so it needs one to exist.  A
 * caller must therefore test for 0 exactly, never for "not positive". */
int64_t omc_enc_oob(const omc_enc_t *e);
/* Strict in-gamut mode (encoder-side policy; default OFF).
 * `passes` is the per-slice repair budget (0 disables it, 16 is the cap; the
 * reference CLI defaults to 12).  A slice whose committed reconstruction
 * leaves the legal range is re-coded with its offending SOURCE coefficients
 * shrunk toward the slice's own local mean, before quantization -- so what is
 * emitted is still an ordinary lattice point and the committed picture is
 * still the unclamped inverse transform of it, and the bitstream, the
 * decoder, the reconstruction rule and the generation lock are all unchanged.
 * The mode is what makes a legal-range BASEBAND interchange chain exact on
 * content that would otherwise clip; it costs first-generation quality on
 * that content and nothing on any other, and it is inert from generation 2
 * (the committed picture it produces is already in range, so the repair never
 * fires again).  It MUST NOT be used on CDR input -- see
 * omc_enc_set_cdr_input() -- and it is a best effort with a bounded budget,
 * never a promise: when the budget runs out omc_enc_oob() reports the truth.
 * docs/TEMPORAL_T5.md 12.22. */
/* [LEGACY-REPAIR] */ int  omc_enc_gamut_default(void);   /* [V537-BUDGET] the library's per-slice repair budget (OMC_GAMUT_DEFPASS) */
void omc_enc_set_gamut_strict(omc_enc_t *e, int passes);
/* Declare that the frames fed to this encoder are COMMITTED pictures (the CDR
 * interchange written by omc_dec --cdr), not ordinary baseband video.  Strict
 * in-gamut mode then stands down: a committed picture may legitimately sit
 * outside the legal range and must be reproduced verbatim, and the CDR chain
 * is already exact unconditionally with no help from the mode. */
void omc_enc_set_cdr_input(omc_enc_t *e, int on);
/* Diagnostics for the mode: slices re-coded, and slices still out of gamut
 * when the per-slice budget ran out. */
/* [LEGACY-REPAIR] */ int64_t omc_enc_gamut_repairs(const omc_enc_t *e);   /* repair PASSES executed */
/* [LEGACY-REPAIR] */ int64_t omc_enc_gamut_slices(const omc_enc_t *e);    /* distinct slices repaired */
/* [LEGACY-REPAIR] */ int64_t omc_enc_gamut_fallbacks(const omc_enc_t *e); /* slices the gentle rule
                                                      * could not finish, redone
                                                      * with the harsh rule */
/* DIAGNOSTIC (OMC_GM_STAT=1): print what the repair did -- candidates, vetoes,
 * reductions, and how many of those reductions actually moved a coefficient
 * across a quantizer boundary.  Process-wide, not per context. */
/* [LEGACY-REPAIR] */ void omc_enc_gamut_stat_report(void);
int64_t omc_enc_gamut_unfixed(const omc_enc_t *e);
/* [V15] enforced per-slice total-pass bound: the worst total seen, the cap in
 * force, how many slices the cap stopped, and integer percentiles over the
 * repaired slices. */
int omc_enc_gamut_total_max(const omc_enc_t *e);
int omc_enc_gamut_total_cap(const omc_enc_t *e);
int64_t omc_enc_gamut_capstops(const omc_enc_t *e);
int omc_enc_gamut_total_pct(const omc_enc_t *e, int pct);
int64_t omc_enc_gamut_total_n(const omc_enc_t *e);
/* 1 when this raster's geometry is recoverable from a cropped baseband
 * picture (minor 11 pad neutralization applies), 0 when it is not -- a
 * horizontally padded raster, or a visible run the rule cannot express.
 * A stream is baseband-safe only when this is 1 AND omc_enc_oob() is 0. */
int omc_enc_geom_baseband_safe(const omc_enc_t *e);
/* TEST ONLY: reintroduce the pre-minor-11 pad behaviour on this context, so a
 * gate can prove it is non-vacuous.  Never an environment variable: a lever
 * that changes normative reconstruction from the environment is an
 * encoder/decoder disagreement channel. */
void omc_enc_debug_oldpads(omc_enc_t *e, int on);
void omc_dec_debug_oldpads(omc_dec_t *d, int on);

/* ---- decoder ---- */
omc_dec_t *omc_dec_create(const omc_config_t *cfg);
void omc_dec_destroy(omc_dec_t *d);
/* Decode one slice from src (up to 2*bits_per_slice/8 bytes are examined; the
 * true size comes from the header). Returns slice_idx decoded (>=0), or <0 on
 * corruption (caller may conceal). Fills the slice's rows of out. */
int omc_dec_slice(omc_dec_t *d, const uint8_t *src, omc_frame_t *out);
int omc_dec_slice_ex(omc_dec_t *d, const uint8_t *src, size_t avail,
                     size_t *consumed, omc_frame_t *out);
/* Decode one frame (n >= nslices*bits_per_slice/8 wire bytes). Damaged slices
 * are skipped via sync-scan resync; their rows keep out's previous content
 * (concealment). Returns the number of slices successfully decoded. */
int64_t omc_dec_frame(omc_dec_t *d, const uint8_t *src, size_t n, omc_frame_t *out);
/* Select how omc_dec_frame conceals a lost slice: 0 = freeze (hold the
 * previous frame, the v4.1 behavior), 1 = motion-compensated + spatial
 * (default). Never changes a clean decode - concealment fires only when a
 * slice fails to decode, so the golden byte-compare is identical either way. */
void omc_dec_set_conceal(omc_dec_t *d, int mode);
/* [S3-HASH] STATE VERIFICATION.  After a frame is decoded, the slices whose
 * committed state (as of the previous frame) did not match the encoder's are
 * flagged: lost slices, the slices below them damaged through the boundary
 * term, motion spread, or a mid-stream join.  A control plane forwards the
 * flagged slices to omc_enc_request_refresh() on the encoder.  Returns the
 * number of flagged slices; `out` (nslices bytes, may be NULL) receives 1 per
 * flagged slice.  Loss detected in THIS frame (a slice that failed to decode)
 * is flagged too, immediately. */
int omc_dec_state_report(const omc_dec_t *d, uint8_t *out, int n);

/* ---- stream header (C8: versioned, self-describing) ---- */
#define OMC_STREAM_HDR_BYTES 32
/* [S3-REFRESH] refresh_r value meaning "no scheduled intra-refresh wave" */
#define OMC_REFRESH_NONE 255
/* Total end-to-end latency of a configuration, docs/LATENCY.md verbatim, with
 * the upconverter's extra slice periods included.  Writes the total in
 * milliseconds and the extra slice periods.  Returns 0 if it holds sub-1 ms,
 * +1 if the configuration is VALID AND AVAILABLE but exceeds it -- in which
 * case the caller is obliged to declare the number it was just handed.  This
 * exists so "not sub-1 ms" is a fact a caller can read, rather than an error it
 * has to work around. */
int omc_config_latency(const omc_config_t *cfg, double *total_ms, int *periods);

int omc_write_stream_header(const omc_config_t *cfg, uint8_t *dst);
int omc_read_stream_header(const uint8_t *src, omc_config_t *cfg);

/* One-time global initialization (idempotent): builds the constant lookup
 * tables (tANS decode tables, grain-sign tile, CRC table). Called
 * automatically by omc_enc_create/omc_dec_create; single-threaded programs
 * never need it. Multi-threaded programs MUST call it once before creating
 * codec instances from more than one thread - table construction itself is
 * not thread-safe, but all tables are read-only afterwards, and encoder and
 * decoder instances share no mutable state (verified by the interleaved
 * two-instance unit test). */
void omc_global_init(void);


/* Validate a configuration against every normative constraint and measured
 * operating floor, writing a human-readable reason into err on failure.
 * Returns 0 if valid, -1 otherwise. This is the single shared validation
 * authority: control-plane software and hardware firmware should call this
 * (or a bit-exact port) so that all layers accept exactly the same configs.
 * slice_h = 0 is accepted and means "auto" (16 if height allows, else 8). */
/* The ONE place the automatic slice height is resolved.  Three sites used to
 * spell this rule out separately and they did not agree, and the library entry
 * point took the raw value, so a caller passing "auto" reached the encoder with
 * a literal zero.  Adversarial review F4/7.1.  Every consumer calls this. */
int omc_resolve_slice_h(const omc_config_t *cfg);

int omc_validate_config(const omc_config_t *cfg, char *err, size_t errlen);

/* helpers */
int omc_num_slices(const omc_config_t *cfg);
int omc_chroma_width(const omc_config_t *cfg);

#endif
