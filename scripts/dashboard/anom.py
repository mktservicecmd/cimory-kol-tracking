from load import *
import pandas as pd, re, collections
df=sheet(); df['m']=df['Month'].astype(str).str.strip().str.lower().map(MON)
F={'total':'Total Views (Ads + Organic)','org':'Organic Views','ads':'Ads Views','likes':'Likes','comments':'Comment','shares':'Share','saves':'Save','te':'Total Engagement','fee':'Total KOL Rate (Rate + Pph + Product Fee)'}
for k,c in F.items(): df[k]=df[c].map(num)
out=[]
def add(r,msg): out.append((int(r.m)+1,r['Platform'],r['KOL Name'],r['Campaign Name'],msg))
for _,r in df.iterrows():
    t,o,a=r.total,r.org,r.ads
    if t is not None and o is not None:
        if o>t+1: add(r,f"organic {o:,.0f} > total {t:,.0f}")
        elif a is not None and abs(t-o-a)>max(2,0.01*t): add(r,f"total {t:,.0f} != organic {o:,.0f} + ads {a:,.0f}")
    parts=[r[x] for x in ['likes','comments','shares','saves']]
    if r.te is not None and all(p is not None for p in parts) and abs(sum(parts)-r.te)>1: add(r,f"total engagement {r.te:,.0f} != sum {sum(parts):,.0f}")
    base=o if o else t
    if base and r.likes and r.likes>base: add(r,f"likes {r.likes:,.0f} > views {base:,.0f}")
    elif base and r.te and r.te/base>0.5 and base>1000: add(r,f"ER {r.te/base:.0%}")
    if o and r.fee and r.fee/o>2000: add(r,f"CPV Rp {r.fee/o:,.0f}")
    if o is not None and o==0 and t: add(r,"organic 0")
    ad=pd.to_datetime(r['Airing Date'],errors='coerce')
    if not pd.isna(ad) and (ad.month-1-r.m) not in (0,1): add(r,f"airing {ad.date()} vs month {r['Month']}")
    if str(r['Link Post'])=='nan': add(r,"no link")
    if (r.fee is None or r.fee==0) and str(r['KOL Tier']).strip()!='Buzzer': add(r,"no fee")
    l=str(r['Link Post']); h=re.search(r'@([^/?]+)/video',l)
    nm=re.sub(r'[^a-z0-9]','',str(r['KOL Name']).lower()); hh=re.sub(r'[^a-z0-9]','',h.group(1).lower()) if h else ''
    if h and nm[:5] not in hh and hh[:5] not in nm: add(r,f"link is @{h.group(1)}")
df['_l']=df['Link Post'].astype(str).str.strip()
for l,rs in df[df['_l']!='nan'].groupby('_l'):
    if len(rs)<2: continue
    out.append((int(rs.m.iloc[0])+1,rs['Platform'].iloc[0],' & '.join(rs['KOL Name']),rs['Campaign Name'].iloc[0],f"same link"))
