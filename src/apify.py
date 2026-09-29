"""Client minimal untuk Apify API (run actor -> tunggu selesai -> ambil dataset)."""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

API_BASE = "https://api.apify.com/v2"


class ApifyError(RuntimeError):
    pass


def get_token() -> str:
    token = os.environ.get("APIFY_TOKEN", "").strip()
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not token and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "APIFY_TOKEN":
                token = value.strip().strip('"').strip("'")
    if not token:
        raise ApifyError(
            "APIFY_TOKEN belum di-set. Tambahkan sebagai environment variable "
            "atau GitHub Actions secret."
        )
    return token


def run_actor(actor_id: str, run_input: dict, *, max_wait_s: int = 900) -> list[dict]:
    """Jalankan actor Apify dan kembalikan item dari default dataset-nya.

    actor_id memakai format "username~actor-name", mis. "clockworks~tiktok-scraper".
    """
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.post(
        f"{API_BASE}/acts/{actor_id}/runs", json=run_input, headers=headers, timeout=60
    )
    if resp.status_code >= 400:
        raise ApifyError(f"Gagal start actor {actor_id}: {resp.status_code} {resp.text[:300]}")
    run = resp.json()["data"]

    deadline = time.monotonic() + max_wait_s
    while run["status"] in ("READY", "RUNNING"):
        if time.monotonic() > deadline:
            raise ApifyError(f"Actor {actor_id} belum selesai setelah {max_wait_s} detik (run {run['id']})")
        resp = requests.get(
            f"{API_BASE}/actor-runs/{run['id']}",
            params={"waitForFinish": 60},
            headers=headers,
            timeout=90,
        )
        resp.raise_for_status()
        run = resp.json()["data"]

    if run["status"] != "SUCCEEDED":
        raise ApifyError(f"Actor {actor_id} berakhir dengan status {run['status']} (run {run['id']})")

    resp = requests.get(
        f"{API_BASE}/datasets/{run['defaultDatasetId']}/items",
        params={"clean": "true", "format": "json"},
        headers=headers,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()
