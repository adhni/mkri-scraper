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

## Alur Pipeline

1. `src.pdf_text` mengekstrak teks mentah PDF memakai `pypdf`.
2. `src.section_splitter` mengidentifikasi heading dan membentuk blok section.
3. `src.extractors.*` mengambil metadata, pihak, dasar hukum, proses, amar, panel hakim, dan relasi perkara.
4. `src.normalizers` menormalkan nomor perkara, tanggal Indonesia, referensi pasal, dan nama pihak.
5. `src.validators` menjalankan validasi schema dan business rules.
6. JSON valid disalin ke `data/validated_json`; JSON yang perlu review masuk `data/review_queue`.

## Batasan Parser V1

- Format heading yang sangat tidak konsisten masih bisa lolos dari splitter.
- Ekstraksi `kuasa hukum`, `alat bukti`, dan `proses persidangan` masih berbasis regex/heuristik.
- Tanggal yang sepenuhnya ditulis dengan kata, bukan angka, belum dinormalisasi penuh.
- Relasi antar-perkara sidang gabungan masih mengandalkan pola nomor perkara yang eksplisit.

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
