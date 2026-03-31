# MKRI Scraper Project Summary

## Ringkasan

`mkri-scraper` adalah proyek parser dokumen Mahkamah Konstitusi Republik Indonesia untuk mengekstrak struktur perkara dari PDF putusan dan ketetapan, lalu menghasilkan JSON tervalidasi yang bisa dibaca pipeline dan viewer web.

Fokus implementasi saat ini:

- parser inti berbasis pure Python
- tanpa OpenAI API di pipeline default
- viewer web untuk review internal
- workflow ingest berbasis folder inbox
- deploy viewer ke Render

## Status Saat Ini

Yang sudah jadi:

- CLI parse, validate, batch parse, report, dan pipeline
- parser PDF v1 dengan output JSON terstruktur
- schema validation + business rules + review flags
- folder `review_queue` untuk kasus yang masih perlu review
- viewer web untuk daftar perkara dan halaman detail
- workflow `ingest-inbox` untuk file PDF baru
- deploy codebase ke GitHub private
- deploy viewer ke Render free

Yang belum dijadikan fondasi utama:

- auto-scraping penuh dari website MKRI
- ingest otomatis yang stabil dari tracking MKRI

Alasannya:

- endpoint MKRI sering dilindungi Cloudflare
- flow browser fallback sudah dicoba, tapi belum cukup andal untuk dijadikan jalur operasional utama

## Workflow Operasional yang Dipakai

Workflow yang disarankan sekarang:

1. Taruh PDF baru ke `data/inbox_pdfs/`
2. Jalankan:

```bash
python3 -B -m src.cli ingest-inbox
```

3. Pipeline akan:
   - memproses hanya PDF baru
   - membuat JSON di `data/parsed_json/`
   - memvalidasi ke `data/validated_json/` atau `data/review_queue/`
   - memindahkan PDF ke `data/raw_pdfs/processed/` atau `data/raw_pdfs/failed/`
   - mencatat hash file di `data/pipeline_state/inbox_manifest.json`

4. Viewer web otomatis membaca output itu

## Command Penting

Jalankan viewer lokal:

```bash
python3 -m src.webapp
```

Ingest PDF baru dari inbox:

```bash
python3 -B -m src.cli ingest-inbox
```

Parse satu PDF:

```bash
python3 -B -m src.cli ingest-pdf path/to/file.pdf
```

Buat report pipeline:

```bash
python3 -B -m src.cli report
```

## Struktur Data Penting

- `data/inbox_pdfs/`
  - folder masuk untuk PDF baru
- `data/raw_pdfs/processed/`
  - arsip PDF yang sudah diproses
- `data/raw_pdfs/failed/`
  - arsip PDF yang gagal diproses
- `data/parsed_json/`
  - hasil parse awal
- `data/validated_json/`
  - hasil yang lolos validasi tanpa review
- `data/review_queue/`
  - hasil yang perlu review manual
- `data/pipeline_state/inbox_manifest.json`
  - state file untuk mencegah PDF yang sama diproses dua kali

## Deploy

GitHub:

- repo private: `https://github.com/adhni/mkri-scraper`

Render:

- deploy sebagai `Web Service`
- build command:

```text
pip install -e .
```

- start command:

```text
python -m src.webapp
```

Catatan:

- app sudah bind ke `0.0.0.0`
- deploy free cocok untuk viewer demo
- filesystem Render free bersifat ephemeral
- data operasional jangka panjang jangan mengandalkan disk Render free

## Dataset di Repo

Saat ini repo membawa snapshot JSON viewer agar deploy Render tidak kosong:

- `data/parsed_json/*.json`
- `data/review_queue/*.json`

Yang tidak ikut repo:

- PDF asli
- fixture PDF sensitif
- browser state
- snapshot discovery HTML/JSON
- hasil operasional yang tidak dibutuhkan viewer

## Known Limits

- parser masih heuristik untuk banyak blok naratif
- field yang masih rentan:
  - `decision_date`
  - `judges`
  - `clerks`
  - `relations`
  - `proceedings`
  - `legal_counsels`
  - `amicus_curiae`
- banyak perkara nyata masih masuk `review_queue`
- discovery dari MKRI belum bisa dianggap full otomatis dan stabil

## Arah Lanjut yang Masuk Akal

Prioritas berikutnya yang paling bernilai:

1. memperkuat kualitas extractor
2. memperbaiki review workflow di UI
3. menambah admin/upload flow langsung dari web
4. merapikan strategi data untuk deploy hosted

## Commit Penting

- `e92691a` Add inbox-based ingestion workflow
- `bd5470e` Adjust Render config for free deploy
- `13d4d74` Bind webapp to 0.0.0.0 by default
- `948cf55` Include viewer dataset snapshot
