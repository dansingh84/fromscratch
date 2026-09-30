p='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/rtree4/src/codec.c'; s=open(p).read()
a="    for (int attempt = 0; attempt < 40; attempt++) {\n        /* [SA8-R1LOCK 1(d)] reinstall"
assert s.count(a)==1
s=s.replace(a,"""    {   /* [SA11 U4] OMC_U_FORCE="f,s,prof,Q,ns,k": replace this slice's
         * rate-control plan (generation-1 alternative study).  Default off. */
        const char *uf = getenv("OMC_U_FORCE"); int a1, a2, a3, a4, a5, a6;
        if (uf && !locked &&
            sscanf(uf, "%d,%d,%d,%d,%d,%d", &a1, &a2, &a3, &a4, &a5, &a6) == 6 &&
            a1 == frame_idx && a2 == slice_idx) {
            fprintf(stderr, "U4FORCE f=%d s=%d chosen=%d,%d,%d,%d forced=%d,%d,%d,%d\\n",
                    frame_idx, slice_idx, prof, Q, n_steps, partial, a3, a4, a5, a6);
            prof = a3; Q = a4; n_steps = a5; partial = a6;
        }
    }
"""+a)
b="""                 locked, mode_mask);
"""
assert s.count(b)==1
s=s.replace(b,b+"""    {   /* [SA11 U4] OMC_U_STOPAFTER="f,s": end the run after this slice */
        const char *sa = getenv("OMC_U_STOPAFTER"); int a1, a2;
        if (sa && sscanf(sa, "%d,%d", &a1, &a2) == 2 && frame_idx == a1 && slice_idx == a2) {
            fprintf(stderr, "U4STOP f=%d s=%d\\n", frame_idx, slice_idx);
            fflush(stderr); exit(0);
        }
    }
""")
open(p,'w').write(s); print('patched')
s=open(p).read()
a="    int RC = n < 40 ? n : 40;\n"
assert s.count(a)==1
s=s.replace(a,"""    int RCcap = 40;   /* [SA11 U4] OMC_R1_PLANU_RC overrides the rank cap */
    { const char *rv = getenv("OMC_R1_PLANU_RC"); if (rv && atoi(rv) > 0) RCcap = atoi(rv); }
    int RC = n < RCcap ? n : RCcap;
""")
a='''        fprintf(stderr, "R1U CAND f=%d s=%d r=%d j=%d triple=%d,%d,%d,%d isg1=%d key=%lld "'''
assert s.count(a)==1
s=s.replace(a,'''        {   char shv[256]; int sl = 0;   /* [SA11 U4] full derived shift vector */
            for (int p_ = 0; p_ < OMC_NPLANES; p_++)
                for (int b_ = 0; b_ < OMC_NBANDS; b_++)
                    sl += snprintf(shv + sl, sizeof shv - (size_t)sl, "%s%d", sl ? "," : "",
                                   cs.shift[p_][b_]);
            fprintf(stderr, "R1U SHV f=%d s=%d r=%d k=%d shv=%s\\n", frame_idx, slice_idx, r,
                    r1pat_k[j], shv);
        }
'''+a)
open(p,'w').write(s); print('patched2')
