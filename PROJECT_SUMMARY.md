# MKRI Scraper Project Summary

## Ringkasan

`mkri-scraper` adalah proyek parser dokumen Mahkamah Konstitusi Republik Indonesia untuk mengekstrak struktur perkara dari PDF putusan dan ketetapan, lalu menghasilkan JSON tervalidasi yang bisa dibaca pipeline dan viewer web.

Fokus implementasi saat ini:

- parser inti berbasis pure Python
- tanpa OpenAI API di pipeline default
- MKRI: explorer perkara dengan ringkasan, topik, dan pencarian teks dokumen
- workflow ingest berbasis folder inbox
- deploy viewer ke Render

## Status Saat Ini

Yang sudah jadi:

- halaman pemilik `/admin`: upload PDF, preview, koreksi, simpan, buang draf
- edit perkara yang ada; koreksi bertahan saat re-import PDF
- SQLite terpisah untuk PDF/draf/koreksi, unduh backup, dan deteksi perubahan dari tab lain
- mode lokal di loopback; hosting memerlukan password pemilik dan direktori disk permanen

- CLI parse, validate, batch parse, report, dan pipeline
- parser PDF v1 dengan output JSON terstruktur
- schema validation + business rules + review flags
- folder `review_queue` untuk kasus yang masih perlu review
- viewer dengan judul/ringkasan editorial, topik, filter tahun putusan dan hasil perkara, serta tampilan mobile
- ekstraksi tanggal pengucapan (angka/ejaan), amar final, panel hakim bertanda tangan, dan pemohon ketetapan
- 13 snapshot perkara diperbarui; catatan editorial terpisah agar aman dari re-import
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
- `data/validated_json/*.json`
- `data/editorial/cases.json`

Yang tidak ikut repo:

- PDF asli
- fixture PDF sensitif
- browser state
- snapshot discovery HTML/JSON
- hasil operasional yang tidak dibutuhkan viewer

## Known Limits

- parser masih heuristik untuk banyak blok naratif
- field yang masih rentan:
  - `relations`
  - `proceedings`
  - `legal_counsels`
  - `amicus_curiae`
- 13 perkara contoh kini lolos pemeriksaan otomatis; ini bukan jaminan seluruh field telah diverifikasi manual
- format PDF baru atau OCR yang buruk masih dapat masuk `review_queue`
- discovery dari MKRI belum bisa dianggap full otomatis dan stabil

## Arah Lanjut yang Masuk Akal

Prioritas berikutnya yang paling bernilai:

1. mencoba alur upload/koreksi lokal dengan koleksi nyata
2. memasang disk permanen dan password sebelum mengaktifkan upload hosted
3. perbandingan dua perkara dan bookmark
4. menambah koleksi tematik; memperkuat extractor saat format baru ditemukan

## Commit Penting

- `e92691a` Add inbox-based ingestion workflow
- `bd5470e` Adjust Render config for free deploy
- `13d4d74` Bind webapp to 0.0.0.0 by default
- `948cf55` Include viewer dataset snapshot

## Tambahan koleksi perkara besar

- Koleksi kini 16 perkara: ditambah putusan 60/PUU-XXII/2024, 91/PUU-XVIII/2020, dan 35/PUU-X/2012.
- Tiga PDF resmi (728 halaman) diunduh lokal; snapshot dan ringkasan masuk repo.
- Nomor, tanggal pengucapan, pemohon, hasil pokok, dan panel pengucapan diperiksa terhadap PDF. Catatan sumber: `data/editorial/landmark_sources.json`.

## Pembaruan pengalaman desktop

- Beranda perkara pilihan, pencarian relevan dengan cuplikan, filter aktif, dan navigasi kembali yang mempertahankan pencarian.
- Detail mengutamakan keputusan, perubahan, hakim, pendapat terpisah, dan sumber PDF per halaman; amar panjang dapat dibuka.
- Panel pengambil putusan dibedakan dari panel pengucapan untuk catatan terkurasi. Posisi tersedia pada tiga perkara; data yang belum diverifikasi tidak ditebak.
- Perkara terkait berdasarkan topik, pencarian teks dokumen, dan tabel ambang Pilkada.
