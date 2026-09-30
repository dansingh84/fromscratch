#!/bin/bash
# xsrun.sh ARM.yuv OUT.yuv W H FMT DEPTH NFRAMES BPP [STREAM.jxs]
#
# JPEG XS reference arm: SVT-JPEG-XS 0.10.0, 1st-edition toolset, main-profile
# feature set, run AT ITS BEST (--coding-signs 2 --coding-vpred 2
# --quantization 1) -- the project-established setting, worth +1.75..+2.46 dB
# to the incumbent over SVT's own defaults.  Do not drop those three flags:
# doing so silently weakens the baseline the mandate is measured against.
#
# sect.84: two MORE axes the incumbent has and this runner never varied.
# Owner, 2026-08-30: "JPEG XS users too can change the slice size."
#   XS_SH  -> --slice-height   (SVT default 16)
#   XS_RC  -> --rc             (SVT default 0)
# sect.21's xsfair.sh swept --quantization and --rc and already concluded "we
# are not running the incumbent at its best"; --slice-height had never appeared
# in the ledger at all.  Measured over 3 arms x 6 rates, `--quantization 1
# --rc 2 --slice-height 32` is the best cell EVERY TIME at 0.3..1.0 bpp, worth
# +0.33..+0.60 VMAF-NEG to XS over the flags this board has always used.  Every
# A1 figure computed before this was optimistic in OMC's favour.
# Unset = the historical behaviour, so old boards stay reproducible.
#
# Consumes and produces ARM-SHAPED single concatenated planar YUV.  8-bit is
# transparently packed/unpacked (SVT wants u8 there, the arms are <u2).
set -e
# The incumbent's binaries are NOT shipped in this zip (they are a third-party
# build).  Point XS at your own SVT-JPEG-XS Bin/Release, or put it on PATH.
XS=${XS:-}
if [ -z "$XS" ]; then
  if command -v SvtJpegxsEncApp >/dev/null 2>&1; then
    XS=$(dirname "$(command -v SvtJpegxsEncApp)")
  else
    echo "xsrun.sh: set XS to your SVT-JPEG-XS Bin/Release directory (it holds" >&2
    echo "          SvtJpegxsEncApp and SvtJpegxsDecApp), or put them on PATH." >&2
    exit 2
  fi
fi
A=$1; O=$2; W=$3; H=$4; FMT=$5; DEP=$6; NF=$7; BPP=$8
STREAM=${9:-$(mktemp -u ${TMPDIR:-/tmp}/xs_XXXXXX).jxs}
HD=$(dirname "$(readlink -f "$0")")
CF=$([ "$FMT" = 444 ] && echo yuv444 || echo yuv422)

IN=$A
if [ "$DEP" = 8 ]; then
  IN=$(mktemp -u ${TMPDIR:-/tmp}/xsin_XXXXXX).u8
  python3 "$HD/xsdepth8.py" pack "$A" "$IN" "$W" "$H" "$FMT" "$NF"
fi

nice -n 19 "$XS/SvtJpegxsEncApp" -i "$IN" -w "$W" -h "$H" --colour-format "$CF" \
  --input-depth "$DEP" --bpp "$BPP" \
  --coding-signs 2 --coding-vpred 2 --quantization ${XS_Q:-1} \
  ${XS_RC:+--rc $XS_RC} ${XS_SH:+--slice-height $XS_SH} \
  -n "$NF" -b "$STREAM" --no-progress 1 >/dev/null 2>&1

if [ "$DEP" = 8 ]; then
  RAW=$(mktemp -u ${TMPDIR:-/tmp}/xsout_XXXXXX).u8
  nice -n 19 "$XS/SvtJpegxsDecApp" -i "$STREAM" -o "$RAW" >/dev/null 2>&1
  python3 "$HD/xsdepth8.py" unpack "$RAW" "$O" "$W" "$H" "$FMT" "$NF"
  rm -f "$IN" "$RAW"
else
  nice -n 19 "$XS/SvtJpegxsDecApp" -i "$STREAM" -o "$O" >/dev/null 2>&1
fi

B=$(stat -c%s "$STREAM")
python3 -c "
b=$B; nf=$NF; w=$W; h=$H; req=$BPP
ach=b*8.0/(w*h*nf)
print('xs  req_bpp=%.5f  ach_bpp=%.5f  ratio=%.5f  bytes=%d  bytes/frame=%s'
      % (req, ach, ach/req, b, (b//nf if b%nf==0 else '%.1f NOT CONSTANT'%(b/nf))))"
[ -z "$9" ] && rm -f "$STREAM"
exit 0
