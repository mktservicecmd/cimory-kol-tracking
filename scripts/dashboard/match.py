from load import *
import pandas as pd
F={'total':'Total Views (Ads + Organic)','org':'Organic Views','ads':'Ads Views','likes':'Likes','comments':'Comment','shares':'Share','saves':'Save','eng':'Total Engagement','fee':'Total KOL Rate (Rate + Pph + Product Fee)'}
kk=lambda kol,mo,p:(str(kol).strip().lower(),int(mo),str(p).strip().lower())
def pairs(E,df):
    EK={};KK={}
    for i,r in enumerate(E): EK.setdefault(key(r['link']),[]).append(i); KK.setdefault(kk(r['kol'],r['m'],r['plat']),[]).append(i)
    used=set();out=[];un=[]
    for idx,r in df[df.m<=7].iterrows():
        k=key(r['Link Post']); c=[i for i in EK.get(k,[]) if i not in used] if k else []
        if not c:
            c=[i for i in KK.get(kk(r['KOL Name'],r['m'],r['Platform']),[]) if i not in used]
            tv=num(r[F['total']])
            c.sort(key=lambda i:abs((E[i]['total'] or 0)-(tv or 0)))
        if not c: un.append(idx); continue
        used.add(c[0]); out.append((idx,c[0]))
    return out,un
