# Cimory KOL Tracking

Tracker performa post KOL (**views & engagement**) untuk TikTok dan Instagram,
memakai [Apify](https://apify.com) sebagai scraper. Data diambil otomatis setiap hari
lewat GitHub Actions, disimpan sebagai histori CSV, dan ditampilkan di dashboard HTML.

```
data/kol_posts.csv  ──►  src/tracker.py  ──►  Apify actors  ──►  data/snapshots.csv  ──►  docs/index.html
 (daftar post KOL)        (tiap hari)          (TikTok / IG)        (histori harian)         (dashboard)
```

## 1. Setup (sekali saja)

1. **Tambahkan token Apify sebagai GitHub secret**
   Repo → *Settings* → *Secrets and variables* → *Actions* → *New repository secret*
   - Name: `APIFY_TOKEN`
   - Secret: token dari <https://console.apify.com/settings/integrations>
2. **Aktifkan dashboard (GitHub Pages)**
   Repo → *Settings* → *Pages* → *Source: Deploy from a branch* → branch `main`, folder `/docs`.
   Dashboard akan tersedia di `https://<org>.github.io/cimory-kol-tracking/`.
   > Catatan: GitHub Pages di repo private butuh plan GitHub Team/Enterprise. Alternatifnya,
   > download `docs/index.html` dan buka langsung di browser.

## 2. Input daftar post KOL

Edit `data/kol_posts.csv` (bisa langsung di GitHub web, atau di Excel/Google Sheets lalu export CSV):

| kolom       | wajib | keterangan |
|-------------|:-----:|------------|
| `campaign`  |   ✓   | nama campaign, dipakai untuk filter dashboard |
| `kol_name`  |   ✓   | nama KOL |
| `platform`  |   ✓   | `tiktok` atau `instagram` |
| `post_url`  |   ✓   | link post, mis. `https://www.tiktok.com/@user/video/123…` atau `https://www.instagram.com/reel/ABC…/` |
| `post_date` |       | tanggal posting (`YYYY-MM-DD`); kosong = diambil dari hasil scrape |
| `fee_idr`   |       | fee KOL (boleh `5000000` atau `Rp 5.000.000`) → untuk hitung CPV & CPE |
| `followers` |       | jumlah followers. TikTok terisi otomatis; **Instagram perlu diisi manual** untuk ER by followers |

Hapus 2 baris contoh sebelum dipakai.

## 3. Menjalankan

- **Otomatis**: setiap hari jam 08:47 WIB (`.github/workflows/track.yml`).
- **Manual**: tab *Actions* → *Track KOL performance* → *Run workflow* (opsional isi nama campaign).
- **Lokal**:
  ```bash
  pip install -r requirements.txt
  cp .env.example .env        # lalu isi APIFY_TOKEN
  python src/tracker.py --dry-run            # cek CSV tanpa memanggil Apify
  python src/tracker.py                      # scrape semua post + update dashboard
  python src/tracker.py --campaign "Nama"    # hanya satu campaign
  ```

Menjalankan ulang di hari yang sama akan menimpa snapshot hari itu (tidak dobel).

## 4. Metrik

| metrik | rumus |
|---|---|
| Engagement | likes + comments + shares + saves (yang tersedia) |
| ER views | engagement ÷ views × 100% |
| ER followers | engagement ÷ followers × 100% |
| CPV | fee ÷ views |
| CPE | fee ÷ engagement |
| Δ views | selisih views terhadap snapshot sukses sebelumnya |

Sumber data per platform:

| | views | likes | comments | shares | saves | followers |
|---|---|---|---|---|---|---|
| TikTok (`clockworks~tiktok-scraper`) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Instagram (`apify~instagram-scraper`) | ✓ (Reels/video) | ✓* | ✓ | – | – | manual |

\* Jika KOL menyembunyikan jumlah like, likes kosong. Share & save Instagram tidak tersedia secara
publik — untuk angka itu minta insight screenshot dari KOL.

## 5. Output

- `data/snapshots.csv` — histori: 1 baris per post per tanggal (bisa di-import ke Looker Studio / Sheets).
- `data/latest.csv` — angka terbaru per post.
- `docs/index.html` — dashboard: KPI, views per KOL, tren views, tabel detail (bisa di-sort & difilter).

Post yang gagal di-scrape (private/terhapus/URL salah) ditandai `not_found`; dashboard tetap
menampilkan angka terakhir yang valid dengan label *stale*.

## 6. Biaya Apify

Kedua actor memakai harga *pay per result* (per post per sekali scrape). Tarif plan FREE saat
repo ini dibuat (cek halaman actor untuk tarif terbaru):

| actor | per post | contoh: 50 post × 30 hari |
|---|---|---|
| TikTok | ~USD 0,0037 | ~USD 5,5 |
| Instagram | ~USD 0,0027 | ~USD 4 |

Kredit gratis Apify ~USD 5/bulan, jadi untuk scrape harian puluhan post kemungkinan perlu
upgrade plan atau mengurangi frekuensi. Cara berhemat:
- ubah `cron` di `.github/workflows/track.yml` jadi 2–3× seminggu, mis. `"47 1 * * 1,3,5"`;
- hapus post dari `kol_posts.csv` setelah campaign selesai (views biasanya sudah stabil ±14 hari
  setelah posting) — histori tetap tersimpan di `snapshots.csv`.

## Struktur

```
src/apify.py                 client Apify (start run, tunggu, ambil dataset)
src/platforms.py             konfigurasi actor & normalisasi metrik per platform
src/tracker.py               CLI utama
src/dashboard.py             generate docs/index.html dari snapshots.csv
src/dashboard_template.html  template dashboard
tests/                       unit test (python -m pytest)
```

Menambah platform lain (mis. YouTube): tambahkan entri baru di `PLATFORMS` pada `src/platforms.py`.
