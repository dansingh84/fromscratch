#!/usr/bin/env python3
"""linelib.py -- FIFTEEN independent detectors for a STRAIGHT HORIZONTAL LINE
the decode has and the source does not.

Owner's instruction, 2026-08-26: "compares the source full frame against OMC's
full frames and highlights whenever OMC's detail shows a straight, horizontal
line where one is not present in the source.  Ensure your analyses are not
limited to luma, but also covers color, and any other visual element."

WHAT COUNTS AS A LINE.  Two conditions, and a detector that drops either one is
not measuring a line:

  (1) a ROW-TO-ROW anomaly -- something changes between row r-1 and row r that
      does not change there in the source.  A defect confined to one row's
      CONTENT is a texture defect, not a line;
  (2) HORIZONTAL EXTENT -- the anomaly is consistent along the row.  A row whose
      error is large but random along its length is noise; the eye reads a line
      only when the same thing happens all the way across.

Every detector below therefore returns a per-(row, column-block) score built
from a row-difference of some quantity, MINUS the same quantity's row-difference
in the source, and the driver requires horizontal runs before drawing anything.

NEVER LUMA-ONLY.  Five of the fifteen are chroma or colour-difference measures
and two more are joint.  The recurring failure this guards against is finding a
luma line, fixing it, and shipping a chroma line that was always the stronger of
the two: on the arm that opened this investigation the row-replication defect is
0.53 in luma and 0.67 in Cb, and a luma-only search would have under-read it by
a quarter and mis-ranked the planes.

Scores are "excess over source", in 10-bit code units unless stated, so 0 means
the decode's vertical structure at that row is exactly the source's and larger
is worse.  One renderer draws them all.
"""
import numpy as np

def _rowdiff(p):
    """Row-to-row difference, same shape as p, first row zero."""
    d = np.zeros_like(p)
    d[1:] = p[1:] - p[:-1]
    return d

def _colblocks(a, cb):
    """Average |a| over column blocks of width cb -> (H, W//cb)."""
    H, W = a.shape
    nw = W // cb
    return a[:, :nw * cb].reshape(H, nw, cb).mean(axis=2)

def _excess(sd, dd, cb):
    """|decode row-difference| minus |source row-difference|, per column block.
    Positive = the decode has vertical structure here that the source lacks."""
    return _colblocks(np.abs(dd), cb) - _colblocks(np.abs(sd), cb)

# ------------------------------------------------------------ the fifteen
def L01_luma_step(s, d, cb, k):
    """L01 LUMA ROW-STEP EXCESS.  The plainest form: |dec[r]-dec[r-1]| minus the
    same in the source, luma.  Catches any row boundary the decode sharpens."""
    return _excess(_rowdiff(s['y']), _rowdiff(d['y']), cb)

def L02_cb_step(s, d, cb, k):
    """L02 Cb ROW-STEP EXCESS.  The same on Cb.  Present because on this codec
    the chroma line is the stronger of the two and a luma-only search
    under-reads it."""
    return _excess(_rowdiff(s['cbf']), _rowdiff(d['cbf']), cb)

def L03_cr_step(s, d, cb, k):
    """L03 Cr ROW-STEP EXCESS."""
    return _excess(_rowdiff(s['crf']), _rowdiff(d['crf']), cb)

def L04_level(s, d, cb, k):
    """L04 ROW-MEAN LEVEL STEP.  The row's MEAN luma, differenced against the
    row above, excess over source.  A pure DC line: a row whose brightness is
    wrong as a whole, which a per-sample measure dilutes because the error is
    small everywhere rather than large somewhere."""
    sm = s['y'].mean(1, keepdims=True); dm = d['y'].mean(1, keepdims=True)
    e = np.abs(_rowdiff(dm)) - np.abs(_rowdiff(sm))
    return np.repeat(e, s['y'].shape[1] // cb, axis=1)

def L05_texture(s, d, cb, k):
    """L05 ROW-TEXTURE STEP.  The row's local sd, differenced row to row.  A
    line where the amount of TEXTURE changes abruptly -- one row soft, the next
    sharp -- which carries no level error at all and is invisible to L01/L04."""
    def rs(p):
        m = p.mean(1, keepdims=True)
        return np.sqrt(((p - m) ** 2).mean(1, keepdims=True))
    e = np.abs(_rowdiff(rs(d['y']))) - np.abs(_rowdiff(rs(s['y'])))
    return np.repeat(e, s['y'].shape[1] // cb, axis=1)

def L06_sat(s, d, cb, k):
    """L06 SATURATION ROW-STEP EXCESS.  sqrt((Cb-mid)^2+(Cr-mid)^2) differenced
    row to row.  A line where the COLOURFULNESS jumps, which can be invisible in
    Cb and Cr separately when they move in compensating directions."""
    def sat(p):
        m = p['mid']
        return np.sqrt((p['cbf'] - m) ** 2 + (p['crf'] - m) ** 2)
    return _excess(_rowdiff(sat(s)), _rowdiff(sat(d)), cb)

def L07_hue(s, d, cb, k):
    """L07 HUE ROW-STEP EXCESS.  atan2(Cr-mid, Cb-mid) differenced row to row,
    unwrapped, scaled to code units.  A line where the HUE turns, at constant
    saturation and constant luma -- which L01, L04 and L06 all score as clean."""
    def hue(p):
        m = p['mid']
        return np.arctan2(p['crf'] - m, p['cbf'] - m)
    def wrapdiff(h):
        d_ = _rowdiff(h)
        return np.arctan2(np.sin(d_), np.cos(d_)) * (512.0 / np.pi)
    return _excess(wrapdiff(hue(s)), wrapdiff(hue(d)), cb)

def L08_de76(s, d, cb, k):
    """L08 COLOUR-DIFFERENCE ROW-STEP.  A cheap DeltaE-like distance in the
    opponent-RGB space, differenced row to row.  The joint measure: it fires on
    a line the eye sees as a colour edge whatever combination of the three
    planes carries it."""
    def de(p):
        return np.sqrt(p['r'] ** 2 + p['g'] ** 2 + p['b'] ** 2)
    return _excess(_rowdiff(de(s)), _rowdiff(de(d)), cb)

def L09_dup(s, d, cb, k):
    """L09 ROW REPLICATION EXCESS.  The fraction of samples exactly equal to the
    sample above, decode minus source, over all three planes.  An EXACT copy is
    not a step at all, so every difference-based detector above scores it as
    perfect -- yet a replicated row bounds the whole vertical change into the
    next boundary, which is where the line then appears.  This is the detector
    that found the slice-bottom collapse (sect.55)."""
    out = None
    for kk in ('y', 'cbf', 'crf'):
        e = np.zeros_like(s[kk])
        e[1:] = (d[kk][1:] == d[kk][:-1]).astype(np.float64) - \
                (s[kk][1:] == s[kk][:-1]).astype(np.float64)
        b = _colblocks(e, cb) * 100.0     # per cent, to sit on the same scale
        out = b if out is None else out + b
    return out / 3.0

def L10_newedge(s, d, cb, k):
    """L10 EDGE CREATED FROM NOTHING.  |dec row-difference| where the SOURCE's
    row-difference is below a small threshold.  The strictest reading of the
    owner's words -- a line "where one is not present in the source" -- because
    it scores only rows the source holds smooth and ignores every real edge the
    codec merely sharpened."""
    sd = np.abs(_rowdiff(s['y'])) + np.abs(_rowdiff(s['cbf'])) + np.abs(_rowdiff(s['crf']))
    dd = np.abs(_rowdiff(d['y'])) + np.abs(_rowdiff(d['cbf'])) + np.abs(_rowdiff(d['crf']))
    q = np.where(sd < 6.0, dd, 0.0)
    return _colblocks(q, cb) / 3.0

def L11_lost_edge(s, d, cb, k):
    """L11 EDGE DESTROYED.  The signed opposite of L10: rows where the SOURCE
    has a strong horizontal edge and the decode flattened it.  A line is as
    often a MISSING boundary as an invented one, and every detector that takes
    an absolute excess is blind to this half by construction."""
    sd = np.abs(_rowdiff(s['y']))
    dd = np.abs(_rowdiff(d['y']))
    q = np.where(sd > 24.0, sd - dd, 0.0)
    return _colblocks(np.maximum(q, 0), cb)

def L12_runlen(s, d, cb, k):
    """L12 HORIZONTAL COHERENCE OF THE ROW ERROR.  The row's step-excess is
    multiplied by how CONSISTENTLY SIGNED it is along the row (the absolute mean
    of the sign over each column block).  A row whose excess is large but
    randomly signed is noise; the eye reads a line only when the excess points
    the same way all the way across.  This is condition (2) made a measure
    rather than a filter."""
    e = _rowdiff(d['y']) - _rowdiff(s['y'])
    mag = _colblocks(np.abs(e), cb)
    coh = np.abs(_colblocks(np.sign(e), cb))
    return mag * coh

def L13_phase_lock(s, d, cb, k):
    """L13 SLICE-PITCH LOCK.  L12's score with each row REPLACED by how much its
    row-phase (row mod slice_h) exceeds the frame's median phase.  A defect
    locked to the coding grid is a different object from one that happens to be
    horizontal, and only this one can tell them apart: content lines land on
    arbitrary rows, coding lines land on the same phase everywhere."""
    e = np.abs(_rowdiff(d['y']) - _rowdiff(s['y']))
    prof = np.zeros(k); cnt = np.zeros(k)
    rm = _colblocks(e, cb).mean(1)
    for r in range(len(rm)):
        prof[r % k] += rm[r]; cnt[r % k] += 1
    prof /= np.maximum(cnt, 1)
    med = np.median(prof)
    out = np.zeros_like(_colblocks(e, cb))
    for r in range(out.shape[0]):
        out[r] = max(prof[r % k] - med, 0.0)
    return out

def L14_persist(s, d, cb, k, sp=None, dp=None):
    """L14 TEMPORAL PERSISTENCE OF THE LINE.  L12's score on this frame,
    multiplied by the same score on the previous frame, normalised.  A line that
    stands still frame after frame is a structural defect and is far more
    visible than one that moves; a line that moves is read as flicker and
    belongs to a different fix.  Returns L12 unchanged on frame 0."""
    cur = L12_runlen(s, d, cb, k)
    if sp is None:
        return cur
    prev = L12_runlen(sp, dp, cb, k)
    return np.sqrt(np.maximum(cur, 0) * np.maximum(prev, 0))

def L15_ringing(s, d, cb, k):
    """L15 VERTICAL RINGING.  The second row-difference (curvature) excess: a
    line accompanied by an overshoot above and below it -- the signature of a
    transform boundary rather than of content -- shows here and is diluted in
    every first-difference measure, because ringing's first differences cancel."""
    def d2(p):
        q = np.zeros_like(p)
        q[1:-1] = p[2:] - 2 * p[1:-1] + p[:-2]
        return q
    e = np.abs(d2(d['y'])) + np.abs(d2(d['cbf'])) + np.abs(d2(d['crf']))
    a = np.abs(d2(s['y'])) + np.abs(d2(s['cbf'])) + np.abs(d2(s['crf']))
    return (_colblocks(e, cb) - _colblocks(a, cb)) / 3.0

MEASURES = [
    ('L01_luma_step',  L01_luma_step,  'luma row-step excess'),
    ('L02_cb_step',    L02_cb_step,    'Cb row-step excess'),
    ('L03_cr_step',    L03_cr_step,    'Cr row-step excess'),
    ('L04_level',      L04_level,      'row-mean LEVEL step (DC line)'),
    ('L05_texture',    L05_texture,    'row TEXTURE step'),
    ('L06_sat',        L06_sat,        'saturation row-step'),
    ('L07_hue',        L07_hue,        'HUE row-step'),
    ('L08_de76',       L08_de76,       'colour-difference row-step'),
    ('L09_dup',        L09_dup,        'row REPLICATION excess (%)'),
    ('L10_newedge',    L10_newedge,    'edge created where source is smooth'),
    ('L11_lost_edge',  L11_lost_edge,  'edge DESTROYED that source has'),
    ('L12_runlen',     L12_runlen,     'excess weighted by horizontal coherence'),
    ('L13_phase_lock', L13_phase_lock, 'locked to the SLICE PITCH'),
    ('L14_persist',    L14_persist,    'the line STANDS STILL across frames'),
    ('L15_ringing',    L15_ringing,    'vertical RINGING (2nd difference)'),
]

def render(score, path, cb, sat=None):
    """Full-frame PNG.  BLACK = the decode's vertical structure matches the
    source at this row.  Cyan -> white = a horizontal line the source does not
    have.  Cyan rather than red so these maps can never be confused with the
    sect.50.7 error maps or the sect.54 flatness maps at a glance."""
    from PIL import Image
    H, nw = score.shape
    if sat is None:
        sat = max(float(np.percentile(score, 99.9)), 1e-6)
    t = np.clip(score / sat, 0.0, 1.0)
    img = np.zeros((H, nw, 3), np.float64)
    img[..., 1] = t
    img[..., 2] = t
    img[..., 0] = np.clip((t - 0.6) / 0.4, 0, 1)
    big = np.repeat((img * 255).astype(np.uint8), cb, axis=1)
    Image.fromarray(big).save(path)
    return sat
