#!/bin/bash
# cell_measure.sh TAG SRC DEC W H FMT DEPTH NF OMCFILE  — the standard sandbox cell line, ALL instruments:
# NEG (full clip), BLOTCH three planes + contiguity (sect.51.30), FLAT per plane (frame 2), and the
# owner-verified artifact map (sect.50.7) summarised on three planes at frame 2 (AM column).
tag=$1; src=$2; dec=$3; W=$4; Hh=$5; fmt=$6; dep=$7; nf=$8; omc=$9
H=/home/user/fromscratch/OMC_CLOUD/Project/.work/sandbox/harness
esh=$(python3 -c "print(open('$omc','rb').read(32)[12])")
neg=$(bash $H/negscore.sh $src $dec $W $Hh $fmt $dep $nf 2>/dev/null | tail -1)
bl=$(python3 $H/blotch.py $src $dec $W $Hh $nf --sh $esh --fmt $fmt --depth $dep 2>/dev/null | tail -1)
f2=$(python3 $H/flatplane.py $src $dec $W $Hh 2 --fmt $fmt --depth $dep 2>/dev/null | tail -1 | sed 's/textured blocks//g; s/  */ /g')
am=$(bash $H/amsum.sh $src $dec $W $Hh 2 --fmt $fmt --depth $dep --slice-h $esh 2>/dev/null)
# OWNER METHOD (2026-09-02): level-map groupings = smudges (thr 6 codes, density 0.4, >= 8 blocks), frame 2 and frame 0
sg2=$(python3 $H/smudgegroups.py $src $dec $W $Hh 2 ${TMPDIR:-/tmp}/sg_$$ --sh $esh --fmt $fmt --thr 6 --dens 0.4 2>/dev/null | grep -E "^(Y|Cb|Cr):" | sed -E 's/^([A-Za-z]+): ([0-9]+) groups, ([0-9]+) blocks, largest ([0-9]+).*/\1 \2g\/\3b\/\4/' | tr '\n' ' ')
sg0=$(python3 $H/smudgegroups.py $src $dec $W $Hh 0 ${TMPDIR:-/tmp}/sg0_$$ --sh $esh --fmt $fmt --thr 6 --dens 0.4 2>/dev/null | grep -E "^(Y|Cb|Cr):" | sed -E 's/^([A-Za-z]+): ([0-9]+) groups, ([0-9]+) blocks, largest ([0-9]+).*/\1 \2g\/\3b\/\4/' | tr '\n' ' ')
rm -f ${TMPDIR:-/tmp}/sg_$$* ${TMPDIR:-/tmp}/sg0_$$*
# THE LEDGER'S OWN INSTRUMENTS (v5.3 sect.51/58, v5.4 sect.B3): level error per plane (levelplane), texture
# loss per plane (smudgeplane), and strong red/blue regions by class (strongmap: WASH / SMUDGE / BOTH / RATE)
lv=$(python3 $H/levelplane.py $src $dec $W $Hh $nf --sh $esh --fmt $fmt --depth $dep 2>/dev/null | grep -E "^\s+(Y|Cb|Cr)\s" | sed -E 's/^\s+(\S+)\s+worst\s+(\S+)\s+p99.9\s+(\S+)\s+blocks>20:\s+(\S+).*/\1 w\2 n\4/' | tr '\n' ' ')
sp=$(python3 $H/smudgeplane.py $src $dec $W $Hh 2 --sh $esh --fmt $fmt --depth $dep 2>/dev/null | tail -1 | sed -E 's/textured blocks//g; s/\(mean sd ratio [0-9.]+\)//g; s/  */ /g')
st=$(python3 $H/strongmap.py $src $dec $W $Hh 2 ${TMPDIR:-/tmp}/strong_$$.png --sh $esh --fmt $fmt --depth $dep 2>/dev/null | grep -m1 "STRONG regions" | sed -E "s/.*: ([0-9]+) STRONG regions +\(classes: \{(.*)\}\)/\1 regions: \2/; s/'//g"); rm -f ${TMPDIR:-/tmp}/strong_$$.png
sc2=$(python3 $H/strongcov.py $src $dec $W $Hh 2 --fmt $fmt --depth $dep --sh $esh 2>/dev/null); sc0=$(python3 $H/strongcov.py $src $dec $W $Hh 0 --fmt $fmt --depth $dep --sh $esh 2>/dev/null)
dk=$(python3 $H/darkblocks.py $src $dec $W $Hh $nf --fmt $fmt --depth $dep 2>/dev/null)
echo "SCELL $tag sh=$esh bytes=$(stat -c %s $omc) NEG=$neg BLOTCH[$bl] FLATF2[$f2] $am LEVEL[$lv] TEXLOSS_F2[$sp] STRONG_F2[$st] F2:$sc2 F0:$sc0 $dk LVLGRP_F2[$sg2] LVLGRP_F0[$sg0]"
