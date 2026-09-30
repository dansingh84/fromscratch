import seq2
A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/'
def make(a):
    f=[seq2.read(A+'floorballgameL_1920x1080_422_10.yuv',1920,1080,t) for t in range(6)]
    return f+[seq2.read(A+'volleyballgameL_1920x1080_422_10.yuv',1920,1080,t) for t in range(6,a.N)]
