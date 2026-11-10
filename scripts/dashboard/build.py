import json,re,pandas as pd
from match import *
s,m,d=emb(); E=decode(d); df=sheet()
df['m']=df['Month'].astype(str).str.strip().str.lower().map(MON)
P,un=pairs(E,df)
STAT=['total','org','ads','likes','comments','shares','saves']
TIERS=set(d['dict']['tier'])
log={'stats':[],'camp':0,'tier':[],'date':[],'link':[],'eng':[],'new':[]}
def sdate(r):
    ad=pd.to_datetime(r['Airing Date'],errors='coerce'); return '' if pd.isna(ad) else ad.strftime('%Y-%m-%d')
for idx,i in P:
    r=df.loc[idx]; e=E[i]
    ch=[f for f in STAT if num(r[F[f]]) is not None and abs(num(r[F[f]])-e[f])>1]
    for f in ch: e[f]=int(round(num(r[F[f]])))  # Sheet1 is the source of truth for these rows
    if num(r[F['fee']]) is not None and abs(num(r[F['fee']])-e['fee'])>1: ch.append('fee'); e['fee']=int(round(num(r[F['fee']])))
    if ch: log['stats'].append((e['kol'],e['m'],ch))
    eng=e['likes']+e['comments']+e['shares']+e['saves']
    te=num(r[F['eng']])
    if te is not None and abs(te-eng)>1: log['eng'].append((e['kol'],e['m'],e['plat'],int(te),eng))
    e['eng']=eng
    c=str(r['Campaign Name']).strip()
    if c and c!='nan' and c!=e['camp']: e['camp']=c; log['camp']+=1
    t=str(r['KOL Tier']).strip()
    if t in TIERS and t!=e['tier']: log['tier'].append((e['kol'],e['m'],e['tier'],t)); e['tier']=t
    sd=sdate(r)
    if sd and sd!=e['date']: log['date'].append((e['kol'],e['m'],e['date'],sd)); e['date']=sd
    h=re.search(r'@([^/]+)/video',e['link'])
    if h and h.group(1).lower()!=e['kol'].lower(): log['link'].append((e['kol'],e['link'],r['Link Post']))
CATS=d['dict']['cat']
for idx in un:
    r=df.loc[idx]
    vw=[num(r[c]) for c in df.columns if str(c).startswith('Views ') and 'Day' not in str(c) and '100%' not in str(c)]
    vw=[int(v) for v in vw if v is not None]
    qr=str(r['Q Result']).strip(); pos=int(qr[1]) if re.fullmatch(r'Q[1-4]',qr) else 0
    q=[num(r['Q1']),num(r['Q2']),num(r['Q3']),num(r['Q4']),pos,vw] if vw else 0
    cat=str(r['Category Product']).strip(); cat=cat if cat in CATS else 'Unmapped'
    t=str(r['KOL Tier']).strip(); t=t if t in TIERS else 'nan'
    e={'y':2026,'m':int(r['m']),'cat':cat,'camp':str(r['Campaign Name']).strip(),'plat':str(r['Platform']).strip(),'kol':str(r['KOL Name']).strip(),
       'tier':t,'int':str(r['Interest']).strip() if str(r['Interest'])!='nan' else 'Not specified','prod':cat if cat in d['dict']['prod'] else 'Other',
       'link':str(r['Link Post']).strip(),'date':sdate(r),'fee':int(num(r[F['fee']]) or 0)}
    for f in STAT: e[f]=int(round(num(r[F[f]]) or 0))
    e['eng']=e['likes']+e['comments']+e['shares']+e['saves']; e['q']=q
    E.append(e); log['new'].append((e['kol'],e['m'],e['plat'],e['total']))

# ---- manual fixes agreed with the user (10 Nov 2026) ----
LINKFIX={  # Aug "Product Launch BBCC": Sheet1 links point at another KOL's video
 'azzsyr':'https://www.tiktok.com/@azzsyr/video/7679479808136334600',
 'gedehidayah27':'https://www.tiktok.com/@gedehidayah27/video/7679415078533221639',
 'salmaaristiana':'https://www.tiktok.com/@salmaristiana/video/7679360069154163989',
 'willenlen':'https://www.tiktok.com/@willenlen/video/7679319673015373076',
 'shinta_rona':'https://www.tiktok.com/@shinta_rona/video/7679437743520255249',
 'emakdankriwil17':'https://www.tiktok.com/@emakdankriwil17/video/7678628326642339093',
 'marmyutt':'https://www.tiktok.com/@marmyutt/video/7679768287068163336',
 'aryyobin':'',  # his own video link is not in Sheet1; the given link is @sakhansaaa's
}
DROP={('aurel',4),('nikita willy',4)}  # May, Es Krim Yogurt: no fee, removed on request
log['fix']=[]
for e in E:
    if e['m']==7 and e['camp'].startswith('Product Launch') and e['kol'].lower() in LINKFIX and e['link']!=LINKFIX[e['kol'].lower()]:
        log['fix'].append((e['kol'],'link',e['link'],LINKFIX[e['kol'].lower()])); e['link']=LINKFIX[e['kol'].lower()]
    if e['kol'].lower()=='gedehidayah27' and e['m']==6 and e['saves']<10:  # Sheet1 "3.971" = 3,971
        log['fix'].append((e['kol'],'saves',e['saves'],3971)); e['saves']=3971; e['eng']=e['likes']+e['comments']+e['shares']+e['saves']
n=len(E); E=[e for e in E if (e['kol'].lower(),e['m']) not in DROP]; log['fix'].append(('dropped',n-len(E)))
# re-encode
C=d['cols']; D={k:[] for k in d['dict']}
for k in D: D[k]=list(d['dict'][k])
rows=[]
for e in E:
    row=[]
    for c in C:
        v=e[c]
        if c in D:
            if v not in D[c]: D[c].append(v)
            v=D[c].index(v)
        row.append(v)
    rows.append(row)
nd={'cols':C,'dict':D,'rows':rows,'source':'YTD 2026 KOL Recap.xlsx · sheet "2026" (Jan–Jul) + Sheet1 (Apr–Aug rows refreshed from Sheet1)','generated':'2026-11-10'}
js=json.dumps(nd,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
out=s[:m.start(1)]+js+s[m.end(1):]
open('index.html','w').write(out)
json.dump(log,open('log.json','w'),indent=0,ensure_ascii=False,default=str)
print({k:(v if isinstance(v,int) else len(v)) for k,v in log.items()}, len(E))
for k in ['stats','tier','date','link','eng','new']: print(k,log[k][:12])
