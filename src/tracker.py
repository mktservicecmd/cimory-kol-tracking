"""KOL performance tracker: ambil views & engagement post KOL via Apify.

Pemakaian:
    python src/tracker.py                 # scrape semua post di data/kol_posts.csv
    python src/tracker.py --campaign "X"  # hanya campaign tertentu
    python src/tracker.py --dry-run       # validasi CSV tanpa memanggil Apify

Hasil:
    data/snapshots.csv  histori harian (1 baris per post per tanggal)
    data/latest.csv     snapshot terbaru per post
    docs/index.html     dashboard (via dashboard.py)
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apify import ApifyError, run_actor  # noqa: E402
from platforms import PLATFORMS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
POSTS_CSV = ROOT / "data" / "kol_posts.csv"
SNAPSHOTS_CSV = ROOT / "data" / "snapshots.csv"
LATEST_CSV = ROOT / "data" / "latest.csv"
WIB = timezone(timedelta(hours=7))
BATCH_SIZE = 50

SNAPSHOT_FIELDS = [
    "snapshot_date", "scraped_at", "campaign", "kol_name", "platform", "username", "post_url",
    "post_date", "views", "likes", "comments", "shares", "saves", "engagements",
    "followers", "er_views_pct", "er_followers_pct", "fee_idr", "cpv_idr", "cpe_idr", "status",
]


def _num(value: str | None) -> float | None:
    """Parse angka bulat dari CSV; toleran terhadap "Rp 5.000.000" atau "12,500"."""
    digits = re.sub(r"\D", "", str(value or ""))
    return float(digits) if digits else None


def load_posts(path: Path | None = None) -> list[dict]:
    with (path or POSTS_CSV).open(newline="", encoding="utf-8-sig") as f:
        rows = [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(f)]
    posts, errors = [], []
    for i, r in enumerate(rows, start=2):
        if not r.get("post_url"):
            continue
        platform = r.get("platform", "").lower()
        if platform not in PLATFORMS:
            errors.append(f"baris {i}: platform '{r.get('platform')}' tidak dikenal (pilih: {', '.join(PLATFORMS)})")
            continue
        r["platform"] = platform
        posts.append(r)
    if errors:
        raise SystemExit("Error di kol_posts.csv:\n  " + "\n  ".join(errors))
    return posts


def compute_metrics(post: dict, m: dict | None) -> dict:
    """Gabungkan data post (dari CSV) dengan metrik hasil scrape."""
    m = m or {}
    eng_parts = [m.get(k) for k in ("likes", "comments", "shares", "saves")]
    engagements = sum(v for v in eng_parts if v is not None) if any(v is not None for v in eng_parts) else None
    views = m.get("views")
    followers = m.get("followers") or _num(post.get("followers"))
    fee = _num(post.get("fee_idr"))

    def ratio(a, b, scale=1.0, digits=2):
        return round(a / b * scale, digits) if a is not None and b else None

    return {
        "campaign": post.get("campaign", ""),
        "kol_name": post.get("kol_name", ""),
        "platform": post["platform"],
        "username": m.get("username") or "",
        "post_url": post["post_url"],
        "post_date": post.get("post_date") or (m.get("posted_at") or "")[:10],
        "views": views,
        "likes": m.get("likes"),
        "comments": m.get("comments"),
        "shares": m.get("shares"),
        "saves": m.get("saves"),
        "engagements": engagements,
        "followers": int(followers) if followers else None,
        "er_views_pct": ratio(engagements, views, 100),
        "er_followers_pct": ratio(engagements, followers, 100),
        "fee_idr": int(fee) if fee else None,
        "cpv_idr": ratio(fee, views),
        "cpe_idr": ratio(fee, engagements),
        "status": "ok" if m else "not_found",
    }


def scrape(posts: list[dict]) -> dict[str, dict]:
    """Kembalikan {post_url: metrik ter-normalisasi} untuk semua post."""
    results: dict[str, dict] = {}
    for name, platform in PLATFORMS.items():
        urls = sorted({p["post_url"] for p in posts if p["platform"] == name})
        for start in range(0, len(urls), BATCH_SIZE):
            batch = urls[start:start + BATCH_SIZE]
            print(f"[{name}] scraping {len(batch)} post via {platform.actor_id} ...", flush=True)
            try:
                items = run_actor(platform.actor_id, platform.build_input(batch))
            except ApifyError as e:
                print(f"[{name}] ERROR: {e}", file=sys.stderr)
                continue
            by_key: dict[str, dict] = {}
            for item in items:
                if item.get("error") or item.get("errorDescription"):
                    continue
                for key in platform.item_keys(item):
                    by_key.setdefault(key, item)
            for url in batch:
                item = by_key.get(platform.post_key(url)) or by_key.get(url.strip().rstrip("/"))
                if item:
                    results[url] = platform.normalize(item)
                else:
                    print(f"[{name}] tidak ditemukan / private / terhapus: {url}", file=sys.stderr)
    return results


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SNAPSHOT_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def save_snapshots(rows: list[dict]) -> None:
    """Tambah snapshot hari ini; jika dijalankan ulang di hari yang sama, baris lama diganti."""
    new_keys = {(r["snapshot_date"], r["post_url"]) for r in rows}
    history = [r for r in _read_csv(SNAPSHOTS_CSV) if (r["snapshot_date"], r["post_url"]) not in new_keys]
    history.extend(rows)
    history.sort(key=lambda r: (r["snapshot_date"], r["campaign"], r["kol_name"], r["post_url"]))
    _write_csv(SNAPSHOTS_CSV, history)

    latest: dict[str, dict] = {}
    for r in history:
        # Post yang gagal di-scrape hari ini tetap menampilkan angka terakhir yang valid.
        if r["status"] == "ok" or r["post_url"] not in latest:
            latest[r["post_url"]] = r
    _write_csv(LATEST_CSV, list(latest.values()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--posts", type=Path, help=f"file CSV daftar post (default: {POSTS_CSV.relative_to(ROOT)})")
    ap.add_argument("--campaign", help="hanya scrape campaign ini")
    ap.add_argument("--dry-run", action="store_true", help="validasi CSV saja, tanpa memanggil Apify")
    ap.add_argument("--no-dashboard", action="store_true", help="jangan generate docs/index.html")
    args = ap.parse_args(argv)

    posts = load_posts(args.posts)
    if args.campaign:
        posts = [p for p in posts if p.get("campaign") == args.campaign]
    counts = {name: sum(p["platform"] == name for p in posts) for name in PLATFORMS}
    print(f"{len(posts)} post ditemukan: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    if args.dry_run or not posts:
        return 0

    now = datetime.now(WIB)
    scraped = scrape(posts)
    rows = []
    for p in posts:
        row = compute_metrics(p, scraped.get(p["post_url"]))
        row["snapshot_date"] = now.date().isoformat()
        row["scraped_at"] = now.isoformat(timespec="seconds")
        rows.append(row)
    save_snapshots(rows)

    ok = sum(r["status"] == "ok" for r in rows)
    print(f"Selesai: {ok}/{len(rows)} post berhasil di-scrape. Disimpan ke {SNAPSHOTS_CSV}")

    if not args.no_dashboard:
        from dashboard import build
        build()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
