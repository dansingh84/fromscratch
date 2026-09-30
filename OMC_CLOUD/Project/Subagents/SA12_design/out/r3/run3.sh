export HF_FAST=1
for c in "spot /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/spotrobotL_1920x1080_422_10.yuv 1920 1080 5 16" "floor /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/floorballgameL_1920x1080_422_10.yuv 1920 1080 5 16" "dng1080 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1920x1080_422_10.yuv 1920 1080 5 16"; do
 set -- $c
 nice -n 19 python3 ../../notes/hf.py $2 $3 $4 $5 $6 422 10 0 1023 $1 '{"B6_s6a_4v":[4,"s10","s6a",true]}' '[2,3,4,5,6,7,8,9,10]' '[-1]' > $1.log 2>&1 &
 HF_EDGE=12 nice -n 19 python3 ../../notes/hf.py $2 $3 $4 $5 $6 422 10 0 1023 e_$1 '{"B5e12":[3,"s10","s6a",true]}' '[2,3,4,5,6,7,8,9,10]' '[-1]' > e_$1.log 2>&1 &
done
for c in "dng720 /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv 1280 720 5 8" "gfx /home/user/fromscratch/OMC_CLOUD/Project/.work/arms/cf_gfx_448x256_422_10.yuv 448 256 0 8"; do
 set -- $c
 HF_EDGE=12 nice -n 19 python3 ../../notes/hf.py $2 $3 $4 $5 $6 422 10 0 1023 e_$1 '{"B5e12":[3,"s10","s6a",true]}' '[2,3,4,5,6,7,8,9,10]' '[-1]' > e_$1.log 2>&1 &
done
wait
for f in e_*.json; do c=${f#e_}; c=${c%.json}; cp $c.base.json e_$c.base.json; done
