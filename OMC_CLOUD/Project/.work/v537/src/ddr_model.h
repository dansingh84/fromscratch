/* ddr_model.h — OMC-1 external-DDR service model, slice-ahead prefetch
 * scheduler and BRAM window cache.  MEASUREMENT INSTRUMENT ONLY.
 *
 * Task D (Agent 4, 2026-09-04).  Nothing in this file may change a decoded
 * byte: with the model enabled the codec reads the SAME sample values, taken
 * from a cached copy of the reference rows instead of from the frame store
 * directly.  If the window geometry is wrong the cached copy will not hold a
 * row the predictor asks for and the model aborts loudly — which is exactly
 * how the window bound is proven rather than asserted.
 *
 * Everything here is off unless OMC_DDR=1 is set in the environment (H.0
 * item 5: env levers are for probes; this is an instrument, not a product
 * feature, and it has no effect on the product path when off).
 */
#ifndef OMC_DDR_MODEL_H
#define OMC_DDR_MODEL_H

#include <stdint.h>
#include <stddef.h>

/* traffic classes, kept apart so the report can separate them */
enum {
    OMC_DDR_REF_READ = 0,   /* previous-frame reference window reads   */
    OMC_DDR_MV_READ  = 1,   /* motion-derivation reads (encoder, N-2)  */
    OMC_DDR_RECON_WR = 2,   /* committed-frame writes                  */
    OMC_DDR_CAP_WR   = 3,   /* capture DMA writes (pixel path in)      */
    OMC_DDR_OUT_RD   = 4,   /* output DMA reads (pixel path out)       */
    OMC_DDR_NKIND    = 5
};

/* traffic models for the deadline study */
enum { OMC_DDR_NOMINAL = 0, OMC_DDR_ADVERSARIAL = 1, OMC_DDR_CONTENDED = 2 };

typedef struct {
    int      enabled;
    int      burst_bytes;     /* 64 / 128 / 256                                 */
    int      bus_bytes;       /* 4 = x32, 8 = x64                               */
    double   mt_per_s;        /* transfers per second (DDR4-2400 -> 2.4e9)      */
    double   t_rfc_ns;        /* refresh recovery, 260 (4Gb) .. 350 (8/16Gb)    */
    double   t_refi_ns;       /* refresh interval, 7812.5 at normal temperature */
    double   t_base_ns;       /* controller+PHY read latency, cmd -> first data */
    double   t_pagemiss_ns;   /* tRP + tRCD on a row change                     */
    double   t_turn_ns;       /* read/write bus turnaround                      */
    double   t_faw_ns;        /* four-activate window (bank-interleave limit)   */
    double   contend_frac;    /* share of bus time taken by other masters       */
    int      model;           /* OMC_DDR_NOMINAL / ADVERSARIAL / CONTENDED      */
    int      lead_slices;     /* prefetch lead, in slices (1 or 2)              */
    int      tile_rows;       /* frame-store layout: rows per tile (0 = linear) */
    int      qos;             /* 1 = reference reads preempt writes             */
    int      mvcap;           /* 0 = none; else |mvy| cap in whole pixels       */
    double   slice_period_ns; /* one slice time; 0 = derived from fps           */
    double   fps;
    unsigned seed;
} omc_ddr_cfg_t;

/* --- lifecycle ------------------------------------------------------- */
int  omc_ddr_active(void);                 /* 1 when OMC_DDR=1 */
void omc_ddr_init(int W, int H, int Wc, int chroma444, int bitdepth,
                  int slice_h, int nslices, double fps, const char *side);
void omc_ddr_finish(void);                 /* prints the report to stderr / OMC_DDR_LOG */

/* --- per-frame / per-slice hooks ------------------------------------- */
void omc_ddr_frame_begin(int frame_idx);
/* bind the frame stores the model must copy rows out of */
void omc_ddr_bind(int which, int plane, const uint16_t *base, int pw, int H);
/* traffic-only binding for the sweep tool: rows are charged, nothing is copied */
void omc_ddr_bind_synth(int which, int plane, int pw, int H);
#define OMC_DDR_BIND_PREV  0   /* refprev  (prediction source)   */
#define OMC_DDR_BIND_PREV2 1   /* refprev2 (motion derivation)   */
/* slice k's header has been parsed: issue the prefetch for slice k+lead */
void omc_ddr_slice_header(int slice_idx);
/* admit slice k into the prediction pipeline; returns the wait in ns */
double omc_ddr_admit(int slice_idx);
/* residency-checked row accessor; `fallback` is the direct frame-store row */
const uint16_t *omc_ddr_ref_row(int plane, int y, const uint16_t *fallback);
/* the encoder's motion derivation sweeps the N-2 store over the same band */
void omc_ddr_mv_band(int slice_idx);
/* the committed slice is written back to the frame store */
void omc_ddr_commit(int slice_idx);
/* the capture / output DMA the pixel paths generate, one slice's worth */
void omc_ddr_pixel_dma(int slice_idx);

/* --- for the sweep tool ---------------------------------------------- */
const omc_ddr_cfg_t *omc_ddr_get_cfg(void);
void omc_ddr_set_cfg(const omc_ddr_cfg_t *c);
/* window geometry, in rows, for a given slice height / lead / vector cap */
int  omc_ddr_window_rows(int slice_h, int lead, int mvcap);

#endif
