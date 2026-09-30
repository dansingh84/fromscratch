"""OMC-1 acceptance gates (pytest). Requires prepared masters
(harness/prep_masters.py) and built CLI tools (make).

Covers: rt=0 (C4), exact CBR (A1), generation stability (A4), loss containment
and one-frame recovery (A5), corruption fuzz (A5), 12-bit (B1), colorimetry
signaling (B3), and a smooth-gradient banding tripwire (G2 - final verdict is
human review, this is the automated floor).
"""

import os
import random
import struct
import subprocess
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "harness"))
from common import MASTERS_DIR, SCRATCH, read_yuv, write_yuv, psnr_all  # noqa: E402

ENC = os.path.join(REPO, "omc_enc")
DEC = os.path.join(REPO, "omc_dec")
OUT = os.path.join(SCRATCH, "test_out")

pytestmark = pytest.mark.skipif(
    not (os.path.exists(ENC) and os.path.exists(MASTERS_DIR)),
    reason="needs built tools + prepared masters")


def setup_module():
    os.makedirs(OUT, exist_ok=True)


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True)


def enc(src, bs, w, h, fmt="422", bpp=2.0, depth=10, recon=None, extra=()):
    cmd = [ENC, "-i", src, "-o", bs, "-w", str(w), "-h", str(h),
           "--fmt", fmt, "--bpp", str(bpp), "--depth", str(depth)] + list(extra)
    if recon:
        cmd += ["--recon", recon]
    run(cmd)


def dec(bs, out):
    run([DEC, "-i", bs, "-o", out])


def stream_info(bs):
    hdr = open(bs, "rb").read(32)
    w, h = struct.unpack("<HH", hdr[6:10])
    depth, chroma, slice_h = hdr[10], hdr[11], hdr[12]
    color = tuple(hdr[17:21])
    bits_per_slice = struct.unpack("<I", hdr[21:25])[0]
    return dict(w=w, h=h, depth=depth, chroma=chroma, slice_h=slice_h,
                color=color, bits_per_slice=bits_per_slice)


def slice_table(bs):
    """Parse per-slice (offset, size, slice_idx) from a stream file."""
    info = stream_info(bs)
    F = info["bits_per_slice"] // 8 * (info["h"] // info["slice_h"])
    data = open(bs, "rb").read()[32:]
    nsl = info["h"] // info["slice_h"]
    frames = []
    fo = 0
    while fo + F <= len(data):
        fr = data[fo:fo + F]
        offs = []
        off = 0
        for _ in range(nsl):
            def bits(buf, pos, n):
                v = 0
                for i in range(n):
                    p = pos + i
                    v |= ((buf[p >> 3] >> (p & 7)) & 1) << i
                return v
            sl = fr[off:]
            sidx = bits(sl, 40, 16)
            used = bits(sl, 86, 24)
            size = 48 + (used + 7) // 8  # v4.0 slice header
            offs.append((fo + off, size, sidx))
            off += size
        frames.append(offs)
        fo += F
    return info, F, frames


# --------------------------------------------------------------- gates

def test_rt0_and_cbr_422():
    src = os.path.join(MASTERS_DIR, "couch12_422_10.yuv")
    bs = os.path.join(OUT, "c.omc")
    rec = os.path.join(OUT, "c_rec.yuv")
    dc = os.path.join(OUT, "c_dec.yuv")
    enc(src, bs, 1920, 1056, recon=rec)
    dec(bs, dc)
    assert open(rec, "rb").read() == open(dc, "rb").read(), "rt=0 all planes"
    info = stream_info(bs)
    F = info["bits_per_slice"] // 8 * (1056 // 16)
    assert (os.path.getsize(bs) - 32) % F == 0, "every frame exactly F bytes"
    assert (os.path.getsize(bs) - 32) // F == 3


def test_rt0_444():
    src = os.path.join(MASTERS_DIR, "couch12_444_10.yuv")
    bs = os.path.join(OUT, "c4.omc")
    rec = os.path.join(OUT, "c4_rec.yuv")
    dc = os.path.join(OUT, "c4_dec.yuv")
    enc(src, bs, 1920, 1056, fmt="444", recon=rec)
    dec(bs, dc)
    assert open(rec, "rb").read() == open(dc, "rb").read()


def test_generations_byte_stable():
    """A4: repeated encode/decode must not accumulate loss. Gen2..Gen5 outputs
    must be byte-identical to Gen1 (idempotence by construction)."""
    src = os.path.join(MASTERS_DIR, "alpine_422_10.yuv")
    w, h = 2048, 1152
    cur = src
    outs = []
    for g in range(1, 6):
        bs = os.path.join(OUT, f"g{g}.omc")
        dc = os.path.join(OUT, f"g{g}.yuv")
        enc(cur, bs, w, h)
        dec(bs, dc)
        outs.append(dc)
        cur = dc
    g1 = open(outs[0], "rb").read()
    for g in range(2, 6):
        assert open(outs[g - 1], "rb").read() == g1, f"generation {g} != generation 1"


def test_loss_containment_and_recovery():
    """A5 (rev.3, temporal): zap slices in frame 0. Damage must stay within
    those slices' rows on every frame (prediction is co-located, so drift
    never crosses slice boundaries), and with refresh R=2 every slice is
    re-intra-coded within 2 frames: frame 2 must decode bit-identically."""
    src = os.path.join(MASTERS_DIR, "beach_422_10.yuv")
    w, h, sh = 2048, 1152, 16
    bs = os.path.join(OUT, "l.omc")
    enc(src, bs, w, h, extra=["--refresh", "2"])
    clean = os.path.join(OUT, "l_clean.yuv")
    dec(bs, clean)
    info, F, frames = slice_table(bs)
    nsl = h // sh
    rng = random.Random(7)
    kill = sorted(rng.sample(range(nsl), 5))
    data = bytearray(open(bs, "rb").read())
    for k in kill:
        off, size, sidx = frames[0][k]
        assert sidx == k
        for i in range(off + 32, off + 32 + size):
            data[i] = 0xAA  # obliterate the slice (header offset +32 stream hdr)
    corr = os.path.join(OUT, "l_corr.omc")
    open(corr, "wb").write(bytes(data))
    dcor = os.path.join(OUT, "l_corr.yuv")
    dec(corr, dcor)
    cw = w // 2
    fr_clean = read_yuv(clean, w, h, cw)
    fr_corr = read_yuv(dcor, w, h, cw)
    allowed = set()
    for k in kill:
        allowed.update(range(k * sh, (k + 1) * sh))
    # spatial containment on every frame: drift stays in the lost slices' rows
    for fi in (0, 1):
        for p in range(3):
            diff_rows = np.where((fr_clean[fi][p] != fr_corr[fi][p]).any(axis=1))[0]
            assert set(diff_rows.tolist()) <= allowed, \
                f"frame {fi} plane {p}: damage escaped the lost slices"
    # bounded recovery: with R=2 every slice refreshed by frame 2 -> identical
    for p in range(3):
        assert np.array_equal(fr_clean[2][p], fr_corr[2][p]), \
            f"frame 2 plane {p} not recovered within refresh bound"


def test_concealment_clean_identical_and_helps():
    """Decoder-side MC + spatial concealment (A5): (1) it must NEVER change a
    clean decode - default (MC) and --no-conceal must be byte-identical when
    no slice is lost (the golden invariant); (2) on a coherent global pan, a
    lost burst must conceal decisively better than freeze; (3) it must not
    regress below freeze on static content."""
    # synthesize a small coherent pan and a static clip from a master window
    src = read_yuv(os.path.join(MASTERS_DIR, "alpine_422_10.yuv"),
                   2048, 1152, 1024)[0]
    w, h, sh, nfr = 1024, 512, 16, 8

    def window(x0, y0):
        return (src[0][y0:y0 + h, x0:x0 + w].copy(),
                src[1][y0:y0 + h, x0 // 2:(x0 + w) // 2].copy(),
                src[2][y0:y0 + h, x0 // 2:(x0 + w) // 2].copy())

    for tag, frames in (("pan", [window(8 * i, 80) for i in range(nfr)]),
                        ("still", [window(40, 80) for _ in range(nfr)])):
        y = os.path.join(OUT, f"cz_{tag}.yuv")
        write_yuv(y, frames)
        bs = os.path.join(OUT, f"cz_{tag}.omc")
        enc(y, bs, w, h, extra=["--refresh", "8"])
        clean = os.path.join(OUT, f"cz_{tag}_clean.yuv")
        dec(bs, clean)
        # (1) clean decode identical with concealment on (default) and off
        noc = os.path.join(OUT, f"cz_{tag}_noc.yuv")
        run([DEC, "-i", bs, "-o", noc, "--no-conceal"])
        assert open(clean, "rb").read() == open(noc, "rb").read(), \
            f"{tag}: concealment altered a CLEAN decode"
        # damage a 6-slice burst on frame 4 (an inter frame)
        info, F, _ = slice_table(bs)
        nsl = h // sh
        data = bytearray(open(bs, "rb").read())
        s0, k, fdmg = 12, 6, 4
        sb = info["bits_per_slice"] // 8
        for s in range(s0, s0 + k):
            a = 32 + fdmg * F + s * sb
            data[a:a + sb] = b"\0" * sb
        dp = os.path.join(OUT, f"cz_{tag}_dmg.omc")
        open(dp, "wb").write(bytes(data))
        mc = os.path.join(OUT, f"cz_{tag}_mc.yuv")
        frz = os.path.join(OUT, f"cz_{tag}_frz.yuv")
        dec(dp, mc)
        run([DEC, "-i", dp, "-o", frz, "--no-conceal"])
        cw = w // 2
        fc = read_yuv(clean, w, h, cw)
        fm = read_yuv(mc, w, h, cw)
        ff = read_yuv(frz, w, h, cw)
        r0, r1 = s0 * sh, (s0 + k) * sh

        def rpsnr(a, b):
            mse = np.mean((a[r0:r1].astype(np.float64) -
                           b[r0:r1].astype(np.float64)) ** 2)
            return 99.0 if mse == 0 else 10 * np.log10(1023.0 ** 2 / mse)

        pm = rpsnr(fm[fdmg][0], fc[fdmg][0])
        pf = rpsnr(ff[fdmg][0], fc[fdmg][0])
        assert pm >= pf - 0.5, f"{tag}: MC regressed below freeze ({pm:.2f} < {pf:.2f})"
        if tag == "pan":
            assert pm >= pf + 5.0, \
                f"pan: MC concealment not decisively better ({pm:.2f} vs {pf:.2f})"


def test_corruption_fuzz_no_crash():
    src = os.path.join(MASTERS_DIR, "city_422_10.yuv")
    bs = os.path.join(OUT, "f.omc")
    enc(src, bs, 2048, 1152)
    blob = open(bs, "rb").read()
    rng = random.Random(11)
    for trial in range(30):
        data = bytearray(blob)
        mode = trial % 3
        if mode == 0:  # bit flips
            for _ in range(rng.randrange(1, 200)):
                i = rng.randrange(32, len(data))
                data[i] ^= 1 << rng.randrange(8)
        elif mode == 1:  # truncation
            data = data[:rng.randrange(40, len(data))]
        else:  # random garbage block
            i = rng.randrange(32, len(data) - 1000)
            for j in range(i, i + 900):
                data[j] = rng.randrange(256)
        p = os.path.join(OUT, "fz.omc")
        open(p, "wb").write(bytes(data))
        r = subprocess.run([DEC, "-i", p, "-o", os.path.join(OUT, "fz.yuv")],
                           capture_output=True, timeout=120)
        assert r.returncode == 0, f"decoder crashed on fuzz trial {trial}"


def test_12bit_roundtrip():
    """B1: 12-bit path. Promote a master by <<2 and run the full chain."""
    w, h = 1920, 1056
    src = read_yuv(os.path.join(MASTERS_DIR, "couch12_422_10.yuv"), w, h, w // 2)
    src12 = [(np.left_shift(Y.astype(np.uint16), 2),
              np.left_shift(Cb.astype(np.uint16), 2),
              np.left_shift(Cr.astype(np.uint16), 2)) for (Y, Cb, Cr) in src]
    p12 = os.path.join(OUT, "c12.yuv")
    write_yuv(p12, src12)
    bs = os.path.join(OUT, "c12.omc")
    rec = os.path.join(OUT, "c12_rec.yuv")
    dc = os.path.join(OUT, "c12_dec.yuv")
    enc(p12, bs, w, h, depth=12, recon=rec)
    dec(bs, dc)
    assert open(rec, "rb").read() == open(dc, "rb").read(), "12-bit rt=0"
    out = read_yuv(dc, w, h, w // 2)
    p = psnr_all(src12[0], out[0], bits=12)
    assert p["Y"] > 44 and p["Cb"] > 44 and p["Cr"] > 44, p


def test_colorimetry_signaling():
    """B3: BT.2020/HLG signaling carried transparently in the stream header (v5.3.6: PQ, code 16, is refused -- not carried)."""
    src = os.path.join(MASTERS_DIR, "alpine_422_10.yuv")
    bs = os.path.join(OUT, "hdr.omc")
    enc(src, bs, 2048, 1152, extra=["--primaries", "9", "--transfer", "18",
                                    "--matrix", "9"])
    info = stream_info(bs)
    assert info["color"][:3] == (9, 18, 9)


def test_gradient_banding_tripwire():
    """G2 floor: a slow smooth 10-bit ramp must reconstruct without steps
    larger than 2 code values (human review of rendered ramps is the final
    verdict; this catches gross banding)."""
    w, h = 1920, 512
    x = np.linspace(0, 1, w)
    y = np.linspace(0, 1, h)[:, None]
    Y = (256 + 300 * (0.6 * x[None, :] + 0.4 * y)).astype(np.uint16)
    Cb = (512 + 60 * x[None, :] * np.ones((h, 1))).astype(np.uint16)
    Cr = (512 - 40 * y * np.ones((1, w))).astype(np.uint16)
    Cb2 = Cb[:, ::2].copy()
    Cr2 = Cr[:, ::2].copy()
    p = os.path.join(OUT, "grad.yuv")
    write_yuv(p, [(Y, Cb2, Cr2)])
    bs = os.path.join(OUT, "grad.omc")
    dc = os.path.join(OUT, "grad_dec.yuv")
    enc(p, bs, w, h)
    dec(bs, dc)
    out = read_yuv(dc, w, h, w // 2)[0]
    for pl, ref, name in ((out[0], Y, "Y"), (out[1], Cb2, "Cb"), (out[2], Cr2, "Cr")):
        d = np.abs(pl.astype(int) - ref.astype(int))
        assert d.max() <= 2, f"{name}: gradient error {d.max()} > 2"
        steps = np.abs(np.diff(pl.astype(int), axis=1))
        assert steps.max() <= 2, f"{name}: step {steps.max()} > 2 (banding)"
