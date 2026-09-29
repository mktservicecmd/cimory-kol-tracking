"""Generate dashboard statis (docs/index.html) dari data/snapshots.csv.

Dashboard bisa dibuka langsung di browser, atau dipublish via GitHub Pages
(Settings -> Pages -> Deploy from branch -> folder /docs).
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS_CSV = ROOT / "data" / "snapshots.csv"
TEMPLATE = Path(__file__).resolve().parent / "dashboard_template.html"
OUTPUT = ROOT / "docs" / "index.html"

NUMERIC = {"views", "likes", "comments", "shares", "saves", "engagements", "followers",
           "er_views_pct", "er_followers_pct", "fee_idr", "cpv_idr", "cpe_idr"}


def _parse(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if k in NUMERIC:
            out[k] = float(v) if v not in ("", None) else None
        else:
            out[k] = v
    return out


def build(snapshots: Path = SNAPSHOTS_CSV, output: Path = OUTPUT) -> Path:
    rows = []
    if snapshots.exists():
        with snapshots.open(newline="", encoding="utf-8") as f:
            rows = [_parse(r) for r in csv.DictReader(f)]
    payload = {
        "generated_at": datetime.now(timezone(timedelta(hours=7))).strftime("%d %b %Y %H:%M WIB"),
        "snapshots": rows,
    }
    # "</" di-escape supaya caption yang mengandung "</script>" tidak merusak HTML.
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", data)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    print(f"Dashboard ditulis ke {output.relative_to(ROOT)}")
    return output


if __name__ == "__main__":
    build()
