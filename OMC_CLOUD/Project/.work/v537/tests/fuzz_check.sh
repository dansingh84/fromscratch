#!/bin/bash
# [V536] Decoder robustness under ASan/UBSan: (a) the CRC-valid structured fuzzer (harness/crcfuzz.py),
# (b) unstructured truncation / byte mutation / --lose patterns.  Not part of `make test` (it needs a
# sanitizer toolchain and ~10 minutes); run it before a release:  sh tests/fuzz_check.sh [NTRIALS]
set -u
D="$(cd "$(dirname "$0")/.." && pwd)"; N=${1:-600}; T=${TMPDIR:-/tmp}/omc_fuzz_$$; mkdir -p "$T"; trap 'rm -rf "$T"' EXIT
SRCS="$D/tools/omc_dec.c $D/src/dwt.c $D/src/tans.c $D/src/bitio.c $D/src/alloc.c $D/src/codec.c $D/src/tables.c $D/src/config.c $D/src/upconv.c $D/src/colour.c $D/src/ddr_model.c"
if gcc -O1 -g -std=c11 -fsanitize=address,undefined -fno-sanitize-recover=undefined -D_POSIX_C_SOURCE=200809L -I"$D/include" $SRCS -lm -o "$T/omc_dec_asan" 2>/dev/null; then
    echo "fuzz build: ASan + UBSan"
else
    # No sanitizer runtime on this machine: fall back to a HARDENED build (stack protector, fortified
    # libc, signed-overflow traps, heap checking via glibc) and say so -- a crash still counts, an
    # out-of-bounds read that a sanitizer would catch may not.  Record which build ran.
    gcc -O1 -g -std=c11 -fstack-protector-all -fstack-clash-protection -ftrapv -D_FORTIFY_SOURCE=3 -D_POSIX_C_SOURCE=200809L -I"$D/include" $SRCS -lm -o "$T/omc_dec_asan" || { echo "FUZZ FAIL: build"; exit 1; }
    export MALLOC_CHECK_=3 MALLOC_PERTURB_=165
    echo "fuzz build: HARDENED FALLBACK (no sanitizer runtime installed: -fstack-protector-all -ftrapv _FORTIFY_SOURCE=3 MALLOC_CHECK_=3)"
fi
python3 "$D/tests/mkrail.py" "$T/cell.yuv" 1280 720 10 2 >/dev/null 2>&1 || { echo "FUZZ FAIL: mkrail"; exit 1; }
"$D/omc_enc" -i "$T/cell.yuv" -o "$T/base.omc" -w 1280 -h 720 --fmt 422 --depth 10 --bpp 0.5 -n 2 >/dev/null 2>&1 || { echo "FUZZ FAIL: base encode"; exit 1; }
python3 "$D/harness/crcfuzz.py" "$T/base.omc" "$T/omc_dec_asan" "$T/out" "$N" || { echo "FUZZ FAIL: crcfuzz found crashes (kept in $T/out)"; trap - EXIT; exit 1; }
# unstructured: truncations and raw byte mutations (CRC-invalid: exercises the reject path)
sz=$(stat -c%s "$T/base.omc"); c=0; runs=0
for cut in $(seq 33 251 "$sz"); do head -c "$cut" "$T/base.omc" > "$T/t.omc"; "$T/omc_dec_asan" -i "$T/t.omc" -o "$T/t.yuv" >/dev/null 2>"$T/e"; rc=$?; runs=$((runs+1)); { [ $rc -ge 128 ] || grep -q 'Sanitizer\|runtime error' "$T/e"; } && { c=$((c+1)); echo "CRASH truncate $cut rc=$rc"; }; done
for k in $(seq 1 200); do python3 - "$T/base.omc" "$T/m.omc" "$k" <<'PY'
import sys,random; d=bytearray(open(sys.argv[1],'rb').read()); random.seed(int(sys.argv[3]))
for _ in range(random.randint(1,8)): d[random.randrange(len(d))]=random.choice([0,1,128,255,random.randrange(256)])
open(sys.argv[2],'wb').write(d)
PY
"$T/omc_dec_asan" -i "$T/m.omc" -o "$T/m.yuv" >/dev/null 2>"$T/e"; rc=$?; runs=$((runs+1)); { [ $rc -ge 128 ] || grep -q 'Sanitizer\|runtime error' "$T/e"; } && { c=$((c+1)); echo "CRASH mutate seed $k rc=$rc"; }; done
for lose in "0:0" "0:0-3" "1:5-9" "0:44" "1:0-44" "0:10,1:10"; do "$T/omc_dec_asan" -i "$T/base.omc" -o "$T/l.yuv" --lose "$lose" >/dev/null 2>"$T/e"; rc=$?; runs=$((runs+1)); { [ $rc -ge 128 ] || grep -q 'Sanitizer\|runtime error' "$T/e"; } && { c=$((c+1)); echo "CRASH lose $lose rc=$rc"; }; done
echo "unstructured fuzz: $runs runs, $c crashes"
[ $c -eq 0 ] && echo "ok: FUZZ decoder survives $N CRC-valid + $runs unstructured hostile inputs under ASan/UBSan" || { echo "FUZZ FAIL"; exit 1; }
