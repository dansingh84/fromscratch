import os; os.environ['TABLES']='../out/tables_B.pkl'
import cProfile, pstats, seq2
A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv'
c=seq2.Codec(1280,720,S=4,tabs=seq2.Tables())
c.encode(seq2.read(A,1280,720,0),0.5*1280*4)
cProfile.run('c.encode(seq2.read(A,1280,720,1),0.5*1280*4)','/tmp/claude-1000/-home-dan-Documents-Apps-Codec/349df860-b2b7-4717-bcf8-5bdc1c07368a/scratchpad/p.out')
p=pstats.Stats('/tmp/claude-1000/-home-dan-Documents-Apps-Codec/349df860-b2b7-4717-bcf8-5bdc1c07368a/scratchpad/p.out'); p.sort_stats('cumulative').print_stats(14)
