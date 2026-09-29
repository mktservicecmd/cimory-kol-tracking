import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import tracker  # noqa: E402
from platforms import PLATFORMS  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))[0]


def test_tiktok_normalize_and_match():
    item = load("tiktok_post.json")
    tt = PLATFORMS["tiktok"]
    m = tt.normalize(item)
    assert m["views"] == item["playCount"]
    assert m["likes"] == item["diggCount"]
    assert m["saves"] == item["collectCount"]
    assert m["followers"] == item["authorMeta"]["fans"]
    url = f"https://www.tiktok.com/@someone/video/{item['id']}?is_from_webapp=1"
    assert tt.post_key(url) in tt.item_keys(item)


def test_instagram_normalize_and_match():
    item = load("instagram_post.json")
    ig = PLATFORMS["instagram"]
    m = ig.normalize(item)
    assert m["views"] == item["videoPlayCount"]
    assert m["likes"] == item["likesCount"]
    assert m["shares"] is None
    for url in (f"https://www.instagram.com/reel/{item['shortCode']}/?igsh=abc",
                f"https://instagram.com/p/{item['shortCode']}"):
        assert ig.post_key(url) in ig.item_keys(item)


def test_instagram_hidden_likes():
    m = PLATFORMS["instagram"].normalize({"likesCount": -1, "commentsCount": 10, "videoPlayCount": 1000})
    assert m["likes"] is None


def test_compute_metrics():
    post = {"campaign": "C", "kol_name": "K", "platform": "tiktok", "post_url": "u",
            "fee_idr": "Rp 1.000.000", "followers": ""}
    m = {"views": 10000, "likes": 800, "comments": 100, "shares": 50, "saves": 50, "followers": 20000}
    r = tracker.compute_metrics(post, m)
    assert r["engagements"] == 1000
    assert r["er_views_pct"] == 10.0
    assert r["er_followers_pct"] == 5.0
    assert r["cpv_idr"] == 100.0
    assert r["cpe_idr"] == 1000.0
    assert r["status"] == "ok"


def test_compute_metrics_not_found():
    r = tracker.compute_metrics({"platform": "instagram", "post_url": "u"}, None)
    assert r["status"] == "not_found"
    assert r["views"] is None and r["er_views_pct"] is None


def test_snapshots_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "SNAPSHOTS_CSV", tmp_path / "s.csv")
    monkeypatch.setattr(tracker, "LATEST_CSV", tmp_path / "l.csv")
    base = {"campaign": "C", "kol_name": "K", "post_url": "u", "status": "ok"}
    tracker.save_snapshots([{**base, "snapshot_date": "2026-09-01", "views": 1}])
    tracker.save_snapshots([{**base, "snapshot_date": "2026-09-02", "views": 2}])
    tracker.save_snapshots([{**base, "snapshot_date": "2026-09-02", "views": 3}])
    tracker.save_snapshots([{**base, "snapshot_date": "2026-09-03", "status": "not_found"}])
    hist = tracker._read_csv(tmp_path / "s.csv")
    assert [(r["snapshot_date"], r["views"]) for r in hist] == [("2026-09-01", "1"), ("2026-09-02", "3"), ("2026-09-03", "")]
    latest = tracker._read_csv(tmp_path / "l.csv")
    assert latest[0]["views"] == "3"  # snapshot gagal tidak menimpa angka terakhir yang valid
