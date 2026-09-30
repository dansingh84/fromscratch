#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "omc1.h"
static void fill(uint16_t *p, size_t n, unsigned seed){
    unsigned x=seed; for(size_t i=0;i<n;i++){x=x*1103515245u+12345u;p[i]=(uint16_t)(64+((x>>16)%800));}
}
typedef struct { unsigned seed; uint8_t *out; size_t fbytes; } job_t;
static void *worker(void *arg){
    job_t *j=arg;
    omc_config_t cfg; memset(&cfg,0,sizeof cfg);
    cfg.width=64; cfg.height=32; cfg.bitdepth=10; cfg.chroma=OMC_CF_422;
    cfg.ver_minor=OMC_VERSION_MINOR; cfg.slice_h=16; cfg.fps_num=50; cfg.fps_den=1;
    cfg.bits_per_slice=32768;
    int W=64,H=32,Wc=32; size_t words=(size_t)W*H+2*(size_t)Wc*H;
    uint16_t *px=malloc(words*2);
    omc_enc_t *e=omc_enc_create(&cfg);
    for(int f=0; f<8; f++){
        fill(px,words,j->seed+(unsigned)f);
        omc_frame_t fr={{px,px+(size_t)W*H,px+(size_t)W*H+(size_t)Wc*H},{W,Wc,Wc}};
        omc_enc_frame(e,&fr,f,j->out+j->fbytes*f,j->fbytes,NULL);
    }
    omc_enc_destroy(e); free(px); return NULL;
}
int main(void){
    omc_global_init(); /* documented contract: once, before threads */
    size_t fbytes=32768/8*2;
    uint8_t *o1=malloc(fbytes*8),*o2=malloc(fbytes*8),*r1=malloc(fbytes*8),*r2=malloc(fbytes*8);
    job_t j1={0xA0000000u,o1,fbytes}, j2={0xB0000000u,o2,fbytes};
    pthread_t t1,t2;
    pthread_create(&t1,NULL,worker,&j1); pthread_create(&t2,NULL,worker,&j2);
    pthread_join(t1,NULL); pthread_join(t2,NULL);
    job_t s1={0xA0000000u,r1,fbytes}, s2={0xB0000000u,r2,fbytes};
    worker(&s1); worker(&s2);
    if(memcmp(o1,r1,fbytes*8)||memcmp(o2,r2,fbytes*8)){printf("MISMATCH\n");return 1;}
    printf("threads: byte-identical to sequential\n"); return 0;
}
