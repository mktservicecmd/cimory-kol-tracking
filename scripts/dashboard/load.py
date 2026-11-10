import json,base64,io,re,math,pandas as pd
SHEET='/root/.claude/projects/-home-user-cimory-kol-tracking/4267e443-ac8d-5bff-b60f-b06d84834b96/tool-results/mcp-Google_Drive-download_file_content-1794294722676.txt'
MON={m:i for i,m in enumerate(['january','february','march','april','may','june','july','august','september','october','november','december'])}
def emb():
    s=open('v15.html').read()
    m=re.search(r'<script id="data" type="application/json">(.*?)</script>',s,re.S)
    return s,m,json.loads(m.group(1))
def decode(d):
    C=d['cols'];D=d['dict'];out=[]
    for r in d['rows']:
        o=dict(zip(C,r))
        for k,vals in D.items(): o[k]=vals[o[k]] if isinstance(o[k],int) else o[k]
        out.append(o)
    return out
def sheet():
    j=json.load(open(SHEET))
    df=pd.read_excel(io.BytesIO(base64.b64decode(j['content'])),sheet_name='Sheet1',header=3)
    return df[df['KOL Name'].notna()].reset_index(drop=True)
TT=re.compile(r'/(?:video|photo)/(\d+)'); IG=re.compile(r'instagram\.com/(?:[\w.]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)')
SH=re.compile(r'(v[mt]\.tiktok\.com/[A-Za-z0-9_-]+)')
def key(link):
    l=str(link or "").strip(); l=l if "instagram" in l.lower() else l.lower()
    for rx,p in ((TT,'tt-'),(IG,'ig-')):
        m=rx.search(l)
        if m: return p+m.group(1)
    m=SH.search(l)
    if m: return 'sh-'+m.group(1)
    return None
def num(v):
    if v is None or (isinstance(v,float) and math.isnan(v)): return None
    if isinstance(v,(int,float)): return v
    s=str(v).strip().replace(',','')
    try: return float(s)
    except: return None
