"""Daily IG update for the KOL dashboard Live tab.

Usage: python3 ig_daily.py <run_dir> <sheet_download_json>
Needs <run_dir>/live_posts/*.json (ArtifactData list out_dir) and
<run_dir>/data/versions.json ({doc_id: version}).
Writes /home/user/cimory-kol-tracking/.w/<id>.json, <run_dir>/data/writes.json
and <run_dir>/data/apify.json; prints a JSON summary.
"""
import base64, datetime as dt, glob, io, json, math, os, re, sys

import pandas as pd

REPO = '/home/user/cimory-kol-tracking'
sys.path.insert(0, REPO)
from src.apify import run_actor  # noqa: E402
from src.platforms import PLATFORMS  # noqa: E402

IG = PLATFORMS['instagram']
WIB = dt.timezone(dt.timedelta(hours=7))
CATS = {'UHT No Added Sugar', 'UHT 250', 'Eat Milk', 'Yogurt No Added Sugar',
        'Yogurt Stickpack', 'Yogurt Bites', 'Yogurt Squeeze'}
NOTE_A = 'Instagram stats from the report numbers in Sheet1.'
NOTE_B = 'Instagram stats via Apify (updated daily until H+35). Shares and saves are not public on Instagram.'
CODE = re.compile(r'instagram\.com/(?:[\w.]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)')


def num(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().replace(',', '').replace('.', '')
    return int(s) if s.isdigit() else None


def fix_cat(c):
    if c in CATS:
        return c
    lc = (c or '').lower()
    if 'yogurt drink' in lc or 'cyd' in lc:
        return 'Yogurt No Added Sugar'
    if 'uht' in lc:
        return 'UHT No Added Sugar'
    if 'eat' in lc and 'milk' in lc:
        return 'Eat Milk'
    return c


def main(run, sheet_json):
    now = dt.datetime.now(dt.timezone.utc)
    today = now.astimezone(WIB).date()
    versions = json.load(open(f'{run}/data/versions.json'))

    raw = json.load(open(sheet_json))
    df = pd.read_excel(io.BytesIO(base64.b64decode(raw['content'])), sheet_name='Sheet1', header=3)
    df = df[df['KOL Name'].notna()]
    rows = {}
    for _, r in df.iterrows():
        for col in ('Link Post', 'Link Post.1'):
            m = CODE.search(str(r.get(col, '')))
            if m:
                rows.setdefault(m.group(1), r)

    docs = {}
    for f in glob.glob(f'{run}/live_posts/ig-*.json'):
        d = json.load(open(f))
        i = os.path.basename(f)[:-5]
        if d.get('platform') == 'Instagram' and (d.get('month') or 0) >= 8 \
                and not d.get('final') and not d.get('replacedBy') and i in versions:
            docs[i] = d

    out = {'targets': len(docs), 'sheetA': [], 'apify': 0, 'fail': [], 'h35': [],
           'catfix': 0, 'newrows': [], 'top': [], 'gain': 0}
    upd, apify_ids = {}, []
    for i, d in docs.items():
        u = {}
        c = fix_cat(d.get('category'))
        if c != d.get('category'):
            u['category'] = c
            out['catfix'] += 1
        r = rows.get(i[3:])
        tot = num(r.get('Total Views (Ads + Organic)')) if r is not None else None
        org = num(r.get('Organic Views')) if r is not None else None
        if tot is not None or org is not None:
            ads = num(r.get('Ads Views')) or 0
            tot = tot if tot is not None else org + ads
            org = org if org is not None else tot - ads
            com, sav, sha = (num(r.get(k)) or 0 for k in ('Comment', 'Save', 'Share'))
            lik = num(r.get('Likes'))
            if lik is None:
                lik = (num(r.get('Total Engagement')) or 0) - com - sav - sha
            if not d.get('postedAt'):
                ad = pd.to_datetime(r.get('Airing Date'), errors='coerce')
                if not pd.isna(ad):
                    u['postedAt'] = (dt.datetime(ad.year, ad.month, ad.day, tzinfo=WIB)
                                     .astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
            snaps = list(d.get('snapshots') or [])
            snap = {'d': today.isoformat(), 'total': tot, 'ads': ads, 'organic': org,
                    'likes': lik, 'comments': com, 'saves': sav, 'shares': sha}
            last = snaps[-1] if snaps else {}
            if any(last.get(k) != snap[k] for k in ('total', 'ads', 'organic', 'likes', 'comments', 'saves', 'shares')):
                pa = u.get('postedAt') or d.get('postedAt')
                if pa:
                    snap['h'] = (today - dt.datetime.fromisoformat(pa.replace('Z', '+00:00')).astimezone(WIB).date()).days
                snaps = [s for s in snaps if s.get('d') != snap['d']] + [snap]
                u['snapshots'] = snaps
                u['note'] = NOTE_A
            out['sheetA'].append(i)
        else:
            apify_ids.append(i)
        if u:
            upd[i] = u

    items = []
    if apify_ids:
        urls = [docs[i]['link'] for i in apify_ids]
        for k in range(0, len(urls), 50):
            items += run_actor(IG.actor_id, IG.build_input(urls[k:k + 50]))
    json.dump(items, open(f'{run}/data/apify.json', 'w'))
    by = {}
    for it in items:
        if it.get('error'):
            continue
        for k in IG.item_keys(it):
            by.setdefault(k, it)
    gains = []
    for i in apify_ids:
        d = docs[i]
        it = by.get(i[3:])
        if not it:
            out['fail'].append(d.get('link'))
            continue
        n = IG.normalize(it)
        if n['views'] is None and it.get('type') in ('Image', 'Sidecar'):
            n['views'] = 0  # photo/carousel posts have no view count
        if n['views'] is None:
            out['fail'].append(d.get('link'))
            continue
        out['apify'] += 1
        u = upd.setdefault(i, {})
        pa = d.get('postedAt') or n['posted_at']
        if not d.get('postedAt') and pa:
            u['postedAt'] = pa
        h = (today - dt.datetime.fromisoformat(pa.replace('Z', '+00:00')).astimezone(WIB).date()).days if pa else None
        snaps = list(d.get('snapshots') or [])
        prev = snaps[-1]['total'] if snaps else 0
        snap = {'ads': 0, 'comments': n['comments'], 'd': today.isoformat(), 'h': h, 'likes': n['likes'],
                'organic': n['views'], 'saves': None, 'shares': None, 'total': n['views']}
        snaps = [s for s in snaps if s.get('d') != snap['d']] + [snap]
        snaps.sort(key=lambda s: (s.get('h') is None, s.get('h') or 0, s.get('d')))
        u['snapshots'] = snaps
        u['note'] = NOTE_B
        if h is not None and h >= 35:
            u['final'] = True
            out['h35'].append(i)
        gains.append((d.get('kol'), n['views'], n['views'] - (prev or 0)))
    out['gain'] = sum(g[2] for g in gains)
    out['top'] = [list(g) for g in sorted(gains, key=lambda g: -g[1])[:3]]

    # Sheet1 IG rows (Sept onwards) with no live doc yet
    have = {os.path.basename(f)[3:-5] for f in glob.glob(f'{run}/live_posts/ig-*.json')}
    for code, r in rows.items():
        mo = num(r.get('Month'))
        if code not in have and mo and mo >= 9 and num(r.get('Year')) == 2026:
            out['newrows'].append([str(r.get('KOL Name')), code])

    os.makedirs(f'{REPO}/.w', exist_ok=True)
    writes = []
    for i, u in upd.items():
        u['updatedAt'] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
        json.dump(u, open(f'{REPO}/.w/{i}.json', 'w'))
        writes.append({'op': 'update', 'collection': 'live_posts', 'doc_id': i,
                       'if_version': versions[i], 'file_path': f'.w/{i}.json'})
    json.dump(writes, open(f'{run}/data/writes.json', 'w'))
    out['writes'] = len(writes)
    print(json.dumps(out))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
