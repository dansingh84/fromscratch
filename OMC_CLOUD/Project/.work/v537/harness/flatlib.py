#!/usr/bin/env python3
"""flatlib.py -- FIFTEEN independent measures of FLATTENING, plus the renderer.

FLATTENING (project vocabulary G4) is the loss of detail, colour or information
inside a region while the region's LEVEL stays approximately right.  It is the
artifact class that a mean-square metric REWARDS -- removing texture always
lowers MSE -- so it cannot be found with PSNR or with VMAF-NEG, and the §50-51
level instruments are blind to it by construction (they average over a block,
which is exactly the operation flattening survives).

Fifteen measures rather than one, because every single measure of "detail" has
content it is blind to:

  a variance measure     misses a region whose texture was REPLACED by
                         same-variance noise, and misses posterisation
  a gradient measure     misses low-contrast texture and is dominated by edges
  an entropy measure     misses geometric structure (a ramp and a random field
                         can carry the same entropy)
  a colour measure       misses achromatic flattening entirely
  a temporal measure     misses flattening that is stable frame to frame

Agreement between measures that fail differently is evidence; agreement between
fifteen variants of the same measure is not.  Each function below returns a
per-block ratio or score where **1.0 means "as much detail as the source" and
values below 1 mean FLATTER**, except where the docstring says otherwise, so
one renderer can draw all of them.

All measures are computed on a BLOCK grid.  The default block is 8x8 picture
samples, deliberately NOT the 4x32 LL support the level instruments use: a grid
aligned to the coding structure cannot tell a coding-structure artifact from a
measurement artifact.  Set --blk to change it; every conclusion in the ledger
was re-checked at 4, 8 and 16.
"""
import numpy as np

# ----------------------------------------------------------------- utilities
def _blocks(a, b):
    """View a 2-D array as (nh, nw, b, b) blocks, cropping the ragged edge."""
    H, W = a.shape
    nh, nw = H // b, W // b
    return a[:nh * b, :nw * b].reshape(nh, b, nw, b).transpose(0, 2, 1, 3)

def _bstat(a, b, fn):
    return fn(_blocks(a, b).reshape(a.shape[0] // b, a.shape[1] // b, b * b), axis=2)

def _ratio(num, den, floor):
    """num/den with a FLOOR on the denominator.

    The floor is the whole reason this helper exists.  A block that is flat in
    the SOURCE (sky, a graphics plate, a letterbox bar) has den ~ 0, and any
    ratio against it is noise amplified without limit -- three of the fifteen
    measures below produced spectacular false positives on letterbox bars
    before the floor went in.  Blocks under the floor are returned as 1.0,
    i.e. "nothing was lost here", which is the truth: there was nothing to
    lose.  The floor is quoted in every ledger table because it is a THRESHOLD
    and a threshold is a decision."""
    out = np.ones_like(den)
    m = den > floor
    out[m] = num[m] / den[m]
    return out

def _ent(vals, nbins=32):
    """Shannon entropy in bits of one block's histogram."""
    h = np.apply_along_axis(lambda v: np.histogram(v, bins=nbins)[0], -1, vals).astype(np.float64)
    p = h / np.maximum(h.sum(-1, keepdims=True), 1)
    return -(p * np.log2(np.maximum(p, 1e-12))).sum(-1)

# ------------------------------------------------------------- the fifteen
# Each takes (src planes, dec planes, geometry) and returns a 2-D block map.

def m01_variance(s, d, b, floor=4.0):
    """M01 LOCAL VARIANCE RATIO.  sd(dec)/sd(src) per block, luma.
    The plainest statement of "there is less variation here than there was".
    Blind to: texture REPLACED by same-variance noise; posterisation."""
    return _ratio(_bstat(d['y'], b, np.std), _bstat(s['y'], b, np.std), floor)

def m02_gradient(s, d, b, floor=2.0):
    """M02 GRADIENT ENERGY RATIO.  mean|grad| dec / src, luma.
    Sensitive to the loss of EDGES specifically, where variance is dominated by
    the level difference across the edge rather than by its sharpness."""
    def g(a):
        gy = np.abs(np.diff(a, axis=0, prepend=a[:1]))
        gx = np.abs(np.diff(a, axis=1, prepend=a[:, :1]))
        return gy + gx
    return _ratio(_bstat(g(d['y']), b, np.mean), _bstat(g(s['y']), b, np.mean), floor)

def m03_laplacian(s, d, b, floor=1.5):
    """M03 LAPLACIAN ENERGY RATIO.  Second derivative, luma.
    A ramp has gradient but no Laplacian, so this separates "the shading
    survived" from "the texture survived".  This is the measure that catches a
    block replaced by a smooth gradient."""
    def L(a):
        p = np.pad(a, 1, mode='edge')
        return np.abs(4 * a - p[:-2, 1:-1] - p[2:, 1:-1] - p[1:-1, :-2] - p[1:-1, 2:])
    return _ratio(_bstat(L(d['y']), b, np.mean), _bstat(L(s['y']), b, np.mean), floor)

def m04_hfband(s, d, b, floor=1.0):
    """M04 HIGH-FREQUENCY WAVELET BAND ENERGY RATIO.
    One level of the codec's OWN 5/3-class analysis (lifting, integer), HH
    subband energy.  This is the measure that speaks the encoder's language:
    if it says a block lost HH energy, some quantiser threw those coefficients
    away and the band index is recoverable."""
    def hh(a):
        # 5/3 lifting, one level, both directions -> HH
        x = a.astype(np.float64)
        lo_r = x[0::2, :]; hi_r = x[1::2, :]
        n = min(lo_r.shape[0], hi_r.shape[0])
        lo_r, hi_r = lo_r[:n], hi_r[:n]
        dr = hi_r - lo_r
        lo_c = dr[:, 0::2]; hi_c = dr[:, 1::2]
        m = min(lo_c.shape[1], hi_c.shape[1])
        return np.abs(hi_c[:, :m] - lo_c[:, :m])
    a, c = hh(s['y']), hh(d['y'])
    bb = max(b // 2, 1)
    return _ratio(_bstat(c, bb, np.mean), _bstat(a, bb, np.mean), floor)

def m05_entropy(s, d, b, floor=0.30):
    """M05 LOCAL ENTROPY RATIO.  Shannon entropy of the block histogram, luma,
    32 bins over the block's own range.  Measures INFORMATION rather than
    amplitude: catches a block whose values were merged into fewer states even
    when the variance is unchanged."""
    a = _ent(_blocks(s['y'], b).reshape(s['y'].shape[0] // b, s['y'].shape[1] // b, b * b))
    c = _ent(_blocks(d['y'], b).reshape(d['y'].shape[0] // b, d['y'].shape[1] // b, b * b))
    return _ratio(c, a, floor)

def m06_levels(s, d, b, floor=2.0):
    """M06 DISTINCT-CODE-COUNT RATIO (posterisation).
    How many distinct luma codes the block holds.  This is the direct measure
    of BANDING/POSTERISATION, which every energy measure above is blind to: a
    smooth ramp quantised to 3 steps keeps most of its variance and all of its
    gradient, and loses almost all of its distinct values."""
    def u(a):
        bl = _blocks(a, b).reshape(a.shape[0] // b, a.shape[1] // b, b * b)
        bl = np.sort(bl, axis=2)
        return 1 + (np.diff(bl, axis=2) != 0).sum(2)
    return _ratio(u(d['y']).astype(np.float64), u(s['y']).astype(np.float64), floor)

def m07_runs(s, d, b, floor=1.0):
    """M07 HORIZONTAL RUN-LENGTH RATIO, INVERTED.
    Mean length of a run of identical luma codes along a row.  Longer runs =
    flatter, so this returns src_runlen/dec_runlen to keep "below 1 is flatter"
    consistent with the rest.  Catches literal constant patches, which an
    entropy measure with 32 bins can miss."""
    def rl(a):
        eq = (np.diff(a, axis=1) == 0)
        eq = np.pad(eq, ((0, 0), (0, 1)))
        bl = _blocks(eq.astype(np.float64), b).reshape(a.shape[0] // b, a.shape[1] // b, b * b)
        f = bl.mean(2)
        return 1.0 / np.maximum(1.0 - f, 1e-3)
    return _ratio(rl(s['y']), rl(d['y']), floor)

def m08_range(s, d, b, floor=4.0):
    """M08 LOCAL DYNAMIC RANGE RATIO.  (max-min) per block, luma.
    An order statistic, so unlike variance it is not moved by the bulk of the
    block: it asks only whether the extremes survived.  Catches clipping and
    the loss of isolated specular detail."""
    return _ratio(_bstat(d['y'], b, np.ptp), _bstat(s['y'], b, np.ptp), floor)

def m09_chroma_sd(s, d, b, floor=2.0):
    """M09 CHROMA VARIATION RATIO.  sd over the (Cb,Cr) pair per block.
    The first of the colour measures.  Every measure above is achromatic and
    would score a block that lost ALL of its colour detail as perfect."""
    def cs(p):
        # on the LUMA raster (chroma replicated, no invented detail) so that all
        # fifteen maps share ONE block grid and the consensus map is well-defined
        return np.sqrt(_bstat(p['cbf'], b, np.var) + _bstat(p['crf'], b, np.var))
    return _ratio(cs(d), cs(s), floor)

def m10_sat(s, d, b, floor=2.0):
    """M10 SATURATION RATIO.  mean sqrt((Cb-mid)^2+(Cr-mid)^2) per block.
    A LEVEL measure of colour, not a detail measure: catches a block that went
    grey without losing chroma texture -- desaturation, which M09 scores as
    perfect because the variation is intact around a moved centre."""
    def sat(p):
        m = p['mid']
        a = np.sqrt((p['cbf'] - m) ** 2 + (p['crf'] - m) ** 2)
        return _bstat(a, b, np.mean)
    return _ratio(sat(d), sat(s), floor)

def m11_hue(s, d, b, floor=0.05):
    """M11 HUE DISPERSION RATIO.  Circular spread of atan2(Cr-mid, Cb-mid).
    Catches a block whose colours all collapsed onto ONE hue while keeping
    their saturation and their variation -- which M09 and M10 both score as
    perfect.  Circular statistics, so it is correct across the wrap."""
    def hd(p):
        m = p['mid']
        th = np.arctan2(p['crf'] - m, p['cbf'] - m)
        c = _bstat(np.cos(th), b, np.mean); si = _bstat(np.sin(th), b, np.mean)
        return 1.0 - np.sqrt(c * c + si * si)          # 0 = one hue, 1 = uniform
    return _ratio(hd(d), hd(s), floor)

def m12_rgb_grad(s, d, b, floor=2.0):
    """M12 OPPONENT-CHANNEL GRADIENT RATIO.  mean|grad| over R,G,B.
    Colour EDGES.  A chroma-plane measure can miss an edge that is carried
    jointly by luma and chroma; this one cannot, because it works after the
    (cheap, monotone) opponent-to-RGB rotation."""
    def g(a):
        return np.abs(np.diff(a, axis=1, prepend=a[:, :1])) + \
               np.abs(np.diff(a, axis=0, prepend=a[:1]))
    def e(p):
        return sum(_bstat(g(ch), b, np.mean) for ch in (p['r'], p['g'], p['b'])) / 3.0
    return _ratio(e(d), e(s), floor)

def m13_tensor(s, d, b, floor=0.02):
    """M13 STRUCTURE-TENSOR COHERENCE CHANGE.
    Anisotropy (l1-l2)/(l1+l2) of the local gradient tensor.  Measures whether
    the block's texture kept its DIRECTIONALITY.  Returns dec/src, so below 1
    means the structure became more isotropic -- the signature of a directional
    texture replaced by a blur or by noise, which every energy measure can miss
    because the energy is still there."""
    def coh(a):
        gy = np.diff(a, axis=0, prepend=a[:1]); gx = np.diff(a, axis=1, prepend=a[:, :1])
        jxx = _bstat(gx * gx, b, np.mean); jyy = _bstat(gy * gy, b, np.mean)
        jxy = _bstat(gx * gy, b, np.mean)
        tr = jxx + jyy
        dsc = np.sqrt(np.maximum((jxx - jyy) ** 2 + 4 * jxy * jxy, 0))
        return _ratio(dsc, tr, 1e-6)
    return _ratio(coh(d['y']), coh(s['y']), floor)

def m14_autocorr(s, d, b, floor=0.02):
    """M14 CORRELATION-LENGTH RATIO, INVERTED.
    Lag-1 autocorrelation of the block after mean removal.  A blurred block is
    MORE correlated with its own shift, so this returns (1-rho_src)/(1-rho_dec):
    below 1 means the decode got smoother.  It is the one measure here that is
    a pure SHAPE statistic -- scale-free, so it survives a level error, a gain
    error and a contrast change untouched."""
    def rho(a):
        m = _bstat(a, b, np.mean)
        mm = np.repeat(np.repeat(m, b, 0), b, 1)
        z = a[:mm.shape[0], :mm.shape[1]] - mm
        num = _bstat(np.pad(z[:, 1:] * z[:, :-1], ((0, 0), (0, 1))), b, np.mean)
        den = _bstat(z * z, b, np.mean)
        # clamp: a block-mean-removed lag-1 correlation is a ratio of two block
        # means, not a true correlation coefficient, and on near-constant blocks
        # it leaves [-1,1].  Unclamped it produced ratios of -11 in the first run.
        return np.clip(_ratio(num, den, 1e-6), -0.999, 0.999)
    return _ratio(1.0 - rho(s['y']), 1.0 - rho(d['y']), floor)

def m15_temporal(s, d, sp, dp, b, floor=1.0):
    """M15 TEMPORAL DETAIL RATIO (frozen texture).
    sd of the FRAME DIFFERENCE per block, dec vs src.  Everything above is a
    single-frame measure and would score a perfectly frozen decode -- previous
    frame repeated -- as flawless on every block whose content did not move.
    This is the only one of the fifteen that can see a block whose detail is
    present but STALE, which for an inter codec is the flattening that matters
    most.  Needs the previous frame of both; returns all-ones on frame 0."""
    if sp is None:
        return np.ones((s['y'].shape[0] // b, s['y'].shape[1] // b))
    return _ratio(_bstat(np.abs(d['y'] - dp['y']), b, np.std),
                  _bstat(np.abs(s['y'] - sp['y']), b, np.std), floor)

MEASURES = [
    ('M01_variance',  m01_variance,  'luma variance'),
    ('M02_gradient',  m02_gradient,  'luma gradient energy'),
    ('M03_laplacian', m03_laplacian, 'luma laplacian energy'),
    ('M04_hfband',    m04_hfband,    'HH wavelet band energy'),
    ('M05_entropy',   m05_entropy,   'local entropy (information)'),
    ('M06_levels',    m06_levels,    'distinct codes (posterisation)'),
    ('M07_runs',      m07_runs,      'constant-run length'),
    ('M08_range',     m08_range,     'local dynamic range'),
    ('M09_chroma_sd', m09_chroma_sd, 'chroma variation'),
    ('M10_sat',       m10_sat,       'saturation level'),
    ('M11_hue',       m11_hue,       'hue dispersion'),
    ('M12_rgb_grad',  m12_rgb_grad,  'opponent-channel colour gradient'),
    ('M13_tensor',    m13_tensor,    'structure-tensor coherence'),
    ('M14_autocorr',  m14_autocorr,  'correlation length'),
    ('M15_temporal',  m15_temporal,  'temporal detail (frozen texture)'),
]

# ------------------------------------------------------------------ renderer
def render(ratio, path, blk, title='', lo=0.55, hi=1.0):
    """Full-frame PNG.  BLACK = detail preserved (ratio >= hi).  Warm colours =
    flattened, saturating at `lo`.  A clean picture is BLACK, the same
    convention as h/levelmap.py, so the two families can be read side by side.
    Ratios ABOVE 1 (the decode has MORE variation -- ringing, added noise) are
    drawn BLUE, because 'more detail than the source' is also a defect and
    silently clipping it to black would hide it."""
    from PIL import Image
    nh, nw = ratio.shape
    t = np.clip((hi - ratio) / max(hi - lo, 1e-6), 0.0, 1.0)      # 0 clean .. 1 flat
    over = np.clip((ratio - 1.15) / 0.85, 0.0, 1.0)
    img = np.zeros((nh, nw, 3), np.float64)
    img[..., 0] = t                       # red   rises with flatness
    img[..., 1] = t * t * 0.85            # green lags -> black->red->orange->yellow
    img[..., 2] = over                    # blue  = MORE detail than source
    big = np.repeat(np.repeat((img * 255).astype(np.uint8), blk, 0), blk, 1)
    Image.fromarray(big).save(path)
    return dict(mean=float(ratio.mean()), p01=float(np.percentile(ratio, 1)),
                frac70=float((ratio < 0.70).mean()), frac50=float((ratio < 0.50).mean()),
                worst=float(ratio.min()))


# ------------------------------------------------- rate-normalised flattening
def detail_of(s, b):
    """The SOURCE's own detail level per block -- the covariate every ratio has
    to be read against.  Local sd of luma plus the colour gradient, so it is
    not blind to a block that is flat in luma and busy in colour."""
    g = np.abs(np.diff(s['r'], axis=1, prepend=s['r'][:, :1])) + \
        np.abs(np.diff(s['b'], axis=1, prepend=s['b'][:, :1]))
    return _bstat(s['y'], b, np.std) + 0.5 * _bstat(g, b, np.mean)

def normalise(ratio, detail, nbins=12):
    """Divide each block's ratio by the MEDIAN ratio of blocks with a similar
    source detail level.

    This is the step that makes a flatness map readable, and it is here because
    the first run of the raw measures called 69.6% of the frame flattened -- a
    true statement about 0.5 bpp and a useless one about a defect.  At 0.5 bpp
    EVERY busy block loses detail; the question a map has to answer is which
    blocks lost MORE THAN THE RATE EXPLAINS.  After this, 1.0 means "exactly as
    much detail as this codec kept on other blocks of the same difficulty" and
    below 1 means an OUTLIER -- which is the definition of an artifact rather
    than of compression.

    Deciles are taken on the SOURCE, never on the decode, so a codec cannot
    move its own baseline by flattening everything."""
    out = np.ones_like(ratio)
    q = np.quantile(detail, np.linspace(0, 1, nbins + 1))
    q[0] -= 1e-9; q[-1] += 1e-9
    for i in range(nbins):
        m = (detail >= q[i]) & (detail < q[i + 1])
        if m.sum() < 8:
            continue
        med = np.median(ratio[m])
        if abs(med) < 1e-6:
            continue
        out[m] = ratio[m] / med
    return out
