#!/usr/bin/env python3
"""[V536] CRC-valid structured decoder fuzz (adopted from the external adversarial review of
v5.3.5, section 4.2).  Random byte mutation almost never reaches the decode loop: it fails the
per-slice CRC-32 and the slice is dropped.  This fuzzer RECOMPUTES the slice CRC after mutating,
so the entropy / coefficient / fill / reconstruct path runs on hostile data.

Stream header (32 B): magic(4) major(1) minor(1) w(2) h(2) depth(1) chroma(1) slice_h(1)
fps(4) colour(4) bits_per_slice(4 @21) refresh(1) scan(1) flags(1) disp_h(2) disp_w(2).
Slice = 44-byte header + CRC-32 (LE at [44:48]) + payload of used_bytes; the CRC covers
header[0:44] then payload[0:used_bytes] (src/codec.c "CRC over header ... then payload").
used_bits is the 24-bit LSB-first field at bit offset 86 of the slice header.

usage: crcfuzz.py STREAM.omc DECODER OUTDIR NTRIALS [SEED]
prints one line per crash (rc >= 128 or sanitizer text) and a summary; exit 1 on any crash."""
import sys, os, random, struct, subprocess, zlib
st, dec, out, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
seed = int(sys.argv[5]) if len(sys.argv) > 5 else 1
random.seed(seed); os.makedirs(out, exist_ok=True)
data = bytearray(open(st, 'rb').read())
w, h = struct.unpack_from('<HH', data, 6); depth, chroma, sh = data[10], data[11], data[12]
bps = struct.unpack_from('<I', data, 21)[0]
ch = (h + 15) // 16 * 16 if sh == 16 else h
nsl = ch // sh; sbytes = bps // 8; fbytes = sbytes * nsl
nfr = (len(data) - 32) // fbytes
print(f"stream {w}x{h} {depth}b chroma{chroma} slice_h{sh} nsl{nsl} slice_bytes{sbytes} nframes{nfr}")
def getbits(buf, bitoff, nb):
    v = 0
    for k in range(nb):
        b = bitoff + k
        v |= ((buf[b >> 3] >> (b & 7)) & 1) << k
    return v
def setbits(buf, bitoff, nb, v):
    for k in range(nb):
        b = bitoff + k
        if (v >> k) & 1: buf[b >> 3] |= 1 << (b & 7)
        else: buf[b >> 3] &= ~(1 << (b & 7)) & 0xFF
# Slices are VARIABLE length on the wire and packed contiguously inside each fixed-size frame
# (exact CBR pads the frame's tail): walk used_bits slice by slice, as omc_dec's [G-LOSEWALK] does.
offs = []
for f in range(nfr):
    o = 32 + f * fbytes; fo = []
    for s in range(nsl):
        if o + 48 > 32 + (f + 1) * fbytes: break
        if data[o:o+4] != data[32:36]: break          # sync word must open every slice
        ub = getbits(data[o:o+44], 86, 24); nb = (ub + 7) // 8
        fo.append((o, nb)); o += 48 + nb
    offs.append(fo)
nsl_seen = sum(len(x) for x in offs)
# self-check: every stored CRC must equal our recomputation (the discriminator, both directions)
bad = 0
for fo in offs:
    for (o, nb) in fo:
        crc = zlib.crc32(bytes(data[o:o+44]) + bytes(data[o+48:o+48+nb])) & 0xFFFFFFFF
        if struct.unpack_from('<I', data, o+44)[0] != crc: bad += 1
if bad or nsl_seen != nfr * nsl: sys.exit(f"CRC recipe self-check FAILED ({bad} mismatches, {nsl_seen}/{nfr*nsl} slices walked) -- fuzzer would be vacuous")
print("CRC recipe self-check ok on every slice")
def fix(buf, o):
    ub = getbits(buf[o:o+44], 86, 24); nbytes = min((ub + 7) // 8, len(buf) - o - 48)
    crc = zlib.crc32(bytes(buf[o:o+44]) + bytes(buf[o+48:o+48+nbytes])) & 0xFFFFFFFF
    struct.pack_into('<I', buf, o+44, crc)
crashes = 0; modes = ['payload', 'header', 'shrink', 'bits']
for t in range(n):
    buf = bytearray(data); f = random.randrange(nfr); s = random.randrange(len(offs[f])); o, nbytes = offs[f][s]
    mode = modes[t % 4]
    ub = getbits(buf[o:o+44], 86, 24)
    if mode == 'payload':
        for _ in range(random.randint(1, 64)):
            if nbytes: buf[o + 48 + random.randrange(nbytes)] = random.randrange(256)
    elif mode == 'header':
        fld = random.choice([(56, 4), (60, 2), (62, 8), (70, 16), (86, 24), (110, 16), (126, 90), (216, 16), (232, 14), (246, 30), (276, 52), (328, 18), (346, 6)])
        setbits(buf, o * 8 + fld[0], fld[1], random.getrandbits(fld[1]))
    elif mode == 'shrink':
        setbits(buf, o * 8 + 86, 24, random.randrange(0, max(1, ub)))
    else:
        for _ in range(random.randint(1, 16)):
            b = random.randrange(48 * 8, (48 + max(nbytes, 1)) * 8); buf[o + (b >> 3)] ^= 1 << (b & 7)
    fix(buf, o)
    p = os.path.join(out, 'fz.omc'); open(p, 'wb').write(buf)
    r = subprocess.run([dec, '-i', p, '-o', os.path.join(out, 'fz.yuv')], capture_output=True, text=True, timeout=120)
    txt = r.stderr
    if r.returncode >= 128 or r.returncode < 0 or 'AddressSanitizer' in txt or 'runtime error' in txt or 'LeakSanitizer' in txt:
        crashes += 1; keep = os.path.join(out, f'crash_{t}_{mode}.omc'); os.replace(p, keep)
        print(f"CRASH trial {t} mode {mode} f{f} s{s} rc {r.returncode}: {txt.strip().splitlines()[-1][:160] if txt.strip() else ''} -> {keep}")
    if (t + 1) % 100 == 0: print(f"  {t+1} trials, {crashes} crashes", flush=True)
print(f"CRCFUZZ done: {n} trials, {crashes} crashes ({nfr} frames x {nsl} slices walked, modes {modes})")
sys.exit(1 if crashes else 0)
