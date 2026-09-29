"""Konfigurasi actor Apify & normalisasi metrik per platform.

Setiap platform punya:
  - actor_id      : actor Apify yang dipakai
  - build_input() : membuat input actor dari daftar URL post
  - post_key()    : ID unik post yang diambil dari URL (untuk mencocokkan hasil)
  - item_keys()   : ID unik post yang diambil dari item hasil scrape
  - normalize()   : mengubah item hasil scrape jadi metrik standar
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

METRIC_FIELDS = ["views", "likes", "comments", "shares", "saves", "followers"]


def _int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- TikTok ----
_TT_ID = re.compile(r"/(?:video|photo)/(\d+)")


def _tt_post_key(url: str) -> str:
    m = _TT_ID.search(url)
    return m.group(1) if m else url.strip().rstrip("/")


def _tt_item_keys(item: dict) -> list[str]:
    keys = [str(item.get("id", ""))]
    for field in ("submittedVideoUrl", "webVideoUrl", "input"):
        if item.get(field):
            keys.append(item[field].strip().rstrip("/"))
    return [k for k in keys if k]


def _tt_build_input(urls: list[str]) -> dict:
    return {
        "postURLs": urls,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False,
        "shouldDownloadSlideshowImages": False,
    }


def _tt_normalize(item: dict) -> dict:
    author = item.get("authorMeta") or {}
    return {
        "username": author.get("name"),
        "posted_at": item.get("createTimeISO"),
        "caption": item.get("text"),
        "views": _int(item.get("playCount")),
        "likes": _int(item.get("diggCount")),
        "comments": _int(item.get("commentCount")),
        "shares": _int(item.get("shareCount")),
        "saves": _int(item.get("collectCount")),
        "followers": _int(author.get("fans")),
    }


# ------------------------------------------------------------- Instagram ----
_IG_CODE = re.compile(r"instagram\.com/(?:[\w.]+/)?(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")


def _ig_post_key(url: str) -> str:
    m = _IG_CODE.search(url)
    return m.group(1) if m else url.strip().rstrip("/")


def _ig_item_keys(item: dict) -> list[str]:
    keys = [str(item.get("shortCode", ""))]
    for field in ("inputUrl", "url"):
        if item.get(field):
            keys.append(_ig_post_key(item[field]))
    return [k for k in keys if k]


def _ig_build_input(urls: list[str]) -> dict:
    return {"directUrls": urls, "resultsType": "posts", "resultsLimit": 1}


def _ig_normalize(item: dict) -> dict:
    # Reels: videoPlayCount = jumlah play (angka yang tampil di app).
    views = item.get("videoPlayCount") or item.get("videoViewCount")
    likes = item.get("likesCount")
    return {
        "username": item.get("ownerUsername"),
        "posted_at": item.get("timestamp"),
        "caption": item.get("caption"),
        "views": _int(views),
        # IG mengembalikan -1 bila like disembunyikan oleh pemilik akun.
        "likes": _int(likes) if likes is not None and likes >= 0 else None,
        "comments": _int(item.get("commentsCount")),
        "shares": None,  # tidak tersedia secara publik di Instagram
        "saves": None,
        "followers": None,  # isi manual di kolom `followers` pada kol_posts.csv
    }


@dataclass(frozen=True)
class Platform:
    name: str
    actor_id: str
    build_input: Callable[[list[str]], dict]
    post_key: Callable[[str], str]
    item_keys: Callable[[dict], list[str]]
    normalize: Callable[[dict], dict]


PLATFORMS: dict[str, Platform] = {
    "tiktok": Platform("tiktok", "clockworks~tiktok-scraper", _tt_build_input, _tt_post_key, _tt_item_keys, _tt_normalize),
    "instagram": Platform("instagram", "apify~instagram-scraper", _ig_build_input, _ig_post_key, _ig_item_keys, _ig_normalize),
}
