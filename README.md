# mkri-scraper

`mkri-scraper` adalah parser dokumen Mahkamah Konstitusi Republik Indonesia yang mengekstrak metadata dan struktur perkara dari PDF putusan maupun ketetapan, lalu menghasilkan JSON tervalidasi.

Fokus versi ini:

- parser inti tetap `pure Python`
- tidak memakai OpenAI API di pipeline default
- struktur sudah menyiapkan fallback LLM opsional untuk kasus ambigu
- parse yang gagal penuh tetap menghasilkan JSON parsial beserta `warnings`

## Struktur Repo

```text
src/
tests/
tests/fixtures/pdfs/
schemas/
scripts/
data/raw_pdfs/
data/parsed_json/
data/validated_json/
data/review_queue/
```

## Instalasi

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## CLI

Parse satu file PDF:

```bash
python -m src.cli parse path/to/file.pdf
```

Batch parse seluruh PDF dalam direktori:

```bash
python -m src.cli batch-parse data/raw_pdfs
```

Validasi seluruh JSON hasil parse:

```bash
python -m src.cli validate data/parsed_json
```

Buat template anotasi manual dari JSON hasil parse:

```bash
python -m src.cli scaffold-manual-truth data/parsed_json
```

Jalankan pipeline end-to-end:

```bash
python -m src.cli run-pipeline data/raw_pdfs --with-manual-truth
```

Buat report ringkas pipeline:

```bash
python -m src.cli report
python -m src.cli report --output data/pipeline_reports/latest.json
```

## Alur Pipeline

1. `src.pdf_text` mengekstrak teks mentah PDF memakai `pypdf`.
2. `src.section_splitter` mengidentifikasi heading dan membentuk blok section.
3. `src.extractors.*` mengambil metadata, pihak, dasar hukum, proses, amar, panel hakim, dan relasi perkara.
4. `src.normalizers` menormalkan nomor perkara, tanggal Indonesia, referensi pasal, dan nama pihak.
5. `src.validators` menjalankan validasi schema dan business rules.
6. JSON valid disalin ke `data/validated_json`; JSON yang perlu review masuk `data/review_queue`.
7. Template anotasi manual bisa dihasilkan ke `tests/manual_truth/` untuk membuat ground truth bertahap.
8. Report operasional bisa dihasilkan dari `parsed_json`, `validated_json`, dan `review_queue`.
9. Viewer web membaca hasil JSON yang sama untuk prototype visualisasi dan demo internal.

## Batasan Parser V1

- Format heading yang sangat tidak konsisten masih bisa lolos dari splitter.
- Ekstraksi `kuasa hukum`, `alat bukti`, dan `proses persidangan` masih berbasis regex/heuristik.
- Tanggal yang sepenuhnya ditulis dengan kata, bukan angka, belum dinormalisasi penuh.
- Relasi antar-perkara sidang gabungan masih mengandalkan pola nomor perkara yang eksplisit.

## Review Queue

`review_queue` dipakai untuk file yang lolos schema tetapi masih tampak meragukan secara semantik.

Contoh sinyal review:

- tanggal putusan tidak terbaca
- amar tidak berbentuk gaya amar
- jumlah pihak terlalu tinggi dan diduga tercemar narasi
- hakim tidak berhasil diekstrak
- batu uji konstitusional tidak muncul pada putusan

## Operasional Pipeline

Command yang paling praktis untuk kerja harian:

```bash
python -m src.cli run-pipeline data/raw_pdfs
```

Output command tersebut berisi:

- daftar file hasil parse
- daftar file hasil validate
- daftar kegagalan bila ada
- summary jumlah status `ok/partial/failed`
- summary `review_flags` yang paling sering muncul

## Visual Prototype

Viewer web tersedia di:

```text
python -m src.webapp
```

Jika environment Anda tidak punya alias `python`, gunakan `python3 -m src.webapp`.

Route utama:

- `/` atau `/cases` untuk daftar perkara
- `/cases/<case_id>` untuk detail perkara
- `/api/cases` untuk daftar perkara dalam JSON
- `/api/cases/<case_id>` untuk detail perkara dalam JSON

Viewer ini membaca sumber yang diprioritaskan sebagai berikut:

1. `data/review_queue`
2. `data/validated_json`
3. `data/parsed_json`

Jadi bila satu perkara ada di `review_queue`, viewer akan menampilkan versi itu sebagai sumber utama.
Filter dashboard mendukung `status`, `document_type`, `source`, `review_flag`, dan opsi `hanya review`.

## Render

Repo sudah memiliki [`render.yaml`](/Users/adhni/Desktop/MK/render.yaml) untuk jalur deploy awal di Render.

Start command:

```text
python -m src.webapp
```

## Tempat Meletakkan PDF Contoh

Untuk contoh sensitif, taruh PDF di:

```text
tests/fixtures/pdfs/
```

Kalau ingin diproses sebagai korpus kerja, taruh di:

```text
data/raw_pdfs/
```

## Fallback LLM

Direktori `src/llm_fallback/` disediakan untuk pengembangan berikutnya:

- klien Responses API
- prompt untuk bagian ambigu
- structured output schema

Modul ini tidak dipakai oleh pipeline default dan tidak membutuhkan API key untuk menjalankan parser utama.
