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
data/inbox_pdfs/
data/parsed_json/
data/validated_json/
data/review_queue/
data/discovery/
```

## Instalasi

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Untuk mode browser opsional pada scraper discovery:

```bash
pip install -e '.[browser]'
playwright install chromium
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

Proses hanya PDF baru dari folder inbox:

```bash
python -m src.cli ingest-inbox
python -m src.cli ingest-inbox data/inbox_pdfs --with-manual-truth
```

Buat report ringkas pipeline:

```bash
python -m src.cli report
python -m src.cli report --output data/pipeline_reports/latest.json
```

Sinkronkan perkara baru dari web MKRI tracking:

```bash
python -m src.cli sync-new --case-type PUU --year 2025
python -m src.cli sync-new --case-type PUU --year 2025 --download-decisions
python -m src.cli sync-new --case-type PUU --year 2025 --browser
```

Jalankan discovery + download + parse + validate dalam satu command:

```bash
python -m src.cli sync-and-ingest --case-type PUU --year 2025
python -m src.cli sync-and-ingest --case-type PUU --year 2025 --browser
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

## Discovery Scraper

Scraper discovery memakai `tracking.mkri.id` untuk menemukan perkara baru dan link dokumen pendukung.

Output utamanya:

- snapshot HTML tracking ke `data/discovery/raw_html/`
- metadata tracking ke `data/discovery/tracking_cases/`
- checkpoint scan ke `data/discovery/checkpoints/`
- opsional unduhan `File Putusan` ke `data/raw_pdfs/`

Command utama:

```bash
python -m src.cli sync-new --case-type PUU --year 2025
```

Untuk pipeline otomatis sampai masuk ke viewer:

```bash
python -m src.cli sync-and-ingest --case-type PUU --year 2025
```

Command tersebut akan:

1. scan perkara baru dari `tracking.mkri.id`
2. unduh `File Putusan` bila tersedia
3. parse PDF ke `data/parsed_json/`
4. validate ke `data/validated_json/` atau `data/review_queue/`
5. membuat hasil baru langsung terbaca oleh viewer web

Jika endpoint MKRI memunculkan Cloudflare challenge, gunakan mode browser:

```bash
python -m src.cli sync-and-ingest --case-type PUU --year 2025 --browser
```

Untuk sesi interaktif pertama kali, mode headful bisa membantu:

```bash
python -m src.cli sync-and-ingest --case-type PUU --year 2025 --browser --browser-headful
```

Flag yang berguna:

- `--download-decisions` untuk mengunduh `File Putusan` bila tersedia
- `--max-candidates` untuk membatasi jumlah nomor perkara yang discan per run
- `--max-misses` untuk berhenti setelah sekian nomor kosong berturut-turut
- `--force` untuk refresh snapshot HTML dan metadata walau file lokal sudah ada

## Batasan Parser V1

- Format heading yang sangat tidak konsisten masih bisa lolos dari splitter.
- Ekstraksi `kuasa hukum`, `alat bukti`, dan `proses persidangan` masih berbasis regex/heuristik.
- Tanggal angka dan ejaan Indonesia didukung pada blok pengucapan putusan; layout/OCR yang tidak dikenal tetap perlu review.
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
python -m src.cli ingest-inbox
```

Output command tersebut berisi:

- jumlah file baru yang diproses
- jumlah file yang di-skip karena sudah pernah diproses
- jumlah file yang masuk `processed`, `review`, dan `failed`
- daftar kegagalan bila ada

Workflow yang disarankan:

1. taruh PDF baru ke `data/inbox_pdfs/`
2. jalankan `python -m src.cli ingest-inbox`
3. file yang sudah diproses dipindah ke `data/raw_pdfs/processed/`
4. file yang gagal parse dipindah ke `data/raw_pdfs/failed/`
5. website otomatis membaca JSON baru dari `data/parsed_json/`, `data/validated_json/`, dan `data/review_queue`

## MKRI — Case Explorer

Viewer kini mengutamakan topik dan isi perkara: judul deskriptif, ringkasan bahasa
Indonesia, hasil perkara, serta undang-undang yang diuji. Koleksi awal berisi 13
perkara dalam 9 topik. Ini koleksi pilihan, bukan arsip lengkap MKRI.

- Cari nomor perkara, nama pihak, undang-undang, atau kata dalam teks dokumen.
- Gabungkan filter `topic`, `year` (tahun **putusan**, bukan tahun pendaftaran),
  dan `outcome`; urutan awal adalah putusan terbaru.
- Filter operasional lama tetap tersedia di **Filter & catatan data**.
- Halaman detail memisahkan ringkasan editorial, amar asli hasil ekstraksi,
  dan teks dokumen yang dapat dibuka. Tautan MKRI tetap tersedia.
- API daftar mendukung filter yang sama; `stats` menghitung hasil pencarian,
  sedangkan `facets` menyediakan pilihan filter dari seluruh koleksi.

### Mengubah judul, ringkasan, atau topik

Edit [`data/editorial/cases.json`](data/editorial/cases.json), dengan nomor perkara
sebagai kunci. Field yang tersedia: `title`, `summary`, `topics`, `law`, dan
`source_sections` (bagian dokumen yang menjadi dasar ringkasan). Viewer membaca
perubahan pada request berikutnya. Catatan ini terpisah dari hasil parser sehingga
tidak tertimpa saat PDF diimpor ulang. Perkara baru tanpa catatan tetap tampil
dengan judul/amar hasil ekstraksi dan dapat dicari.

Ringkasan koleksi awal disusun dari pembuka, konklusi, dan amar dokumen lokal;
bukan penjelasan tentang status hukum terkini. Label `Tervalidasi` berarti lolos
pemeriksaan otomatis, bukan seluruh field telah diverifikasi manual. Kuasa hukum,
relasi, dan peserta lain masih memakai heuristik.

### Menjalankan viewer

Jalankan `python3 -m src.webapp`, lalu buka `http://localhost:8000/admin` atau
klik **Kelola**. Server lokal kini mengikat ke `127.0.0.1`; pengelolaan tanpa
kata sandi hanya tersedia dari mesin yang sama. Untuk bind nonlokal, gunakan
`HOST=0.0.0.0` dan konfigurasi pemilik di bawah.

### Upload, preview, dan koreksi

1. Pilih/jatuhkan satu PDF (maksimal 25 MB dan 500 halaman).
2. Periksa hasilnya sambil membuka PDF asli. Koreksi nomor, jenis, tanggal,
   pemohon, hakim, panitera, amar, judul, ringkasan, topik, dan undang-undang.
3. Klik **Simpan ke koleksi**. Draf belum masuk koleksi sebelum langkah ini.
4. Untuk perkara lama, buka detail lalu **Ubah data perkara** atau **Ganti PDF**.

PDF yang sama, atau dokumen dengan nomor/jenis perkara yang sama, memperbarui
perkara yang ada. Koreksi pemilik disimpan terpisah dari ekstraksi dan dipakai
kembali saat re-import. Bila ada dua tab yang mengubah perkara, penyimpanan
kedua ditolak agar koreksi terbaru tidak tertimpa. PDF scan tanpa teks perlu
OCR terlebih dahulu; PDF berkata sandi perlu dibuka kuncinya.

### Penyimpanan dan backup

PDF, draf, dan koreksi disimpan secara transaksional dalam
`data/library/library.sqlite3` (tidak masuk Git). Snapshot awal tetap dibaca
dari folder JSON; koreksi browser diprioritaskan atas snapshot/editorial file.
Set `MKRI_STORAGE_DIR` untuk memindahkan database ke direktori lain.

Klik **Unduh cadangan** pada halaman Kelola untuk mendapatkan salinan database
yang konsisten. Untuk restore, hentikan server, simpan salinan database lama,
letakkan file cadangan sebagai `library.sqlite3` di direktori penyimpanan,
lalu jalankan server kembali. Backup ini meliputi seluruh unggahan dan koreksi;
13 snapshot bawaan tetap berasal dari repo.

### Mengaktifkan pemilik di hosting

Situs hosted tetap hanya-baca sampai **kedua** environment variable tersedia:

- `MKRI_STORAGE_DIR`: direktori pada disk permanen, misalnya `/var/data/mkri`.
- `MKRI_ADMIN_PASSWORD`: kata sandi pemilik yang panjang dan unik; set melalui
  pengaturan hosting, jangan masukkan ke Git. Login melalui `/admin`.

Pada Render, pasang persistent disk dengan mount `/var/data` terlebih dahulu.
Disk permanen memerlukan layanan berbayar; filesystem bawaan hilang saat
restart/redeploy. Lihat [panduan resmi Render](https://render.com/docs/disks).
Mengatur nama direktori saja **tidak** membuat disk menjadi permanen.
`render.yaml` tetap untuk viewer yang ada dan tidak otomatis membeli disk.
Gunakan satu instance aplikasi untuk database lokal ini. Sesi login berakhir
setelah 8 jam atau restart; data koleksi tetap tersimpan pada disk.

Jalankan verifikasi dengan `python3 -m unittest discover -s tests`.

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

Repo sudah memiliki [`render.yaml`](/Users/adhni/Desktop/MK/render.yaml) untuk jalur deploy awal di Render. File ini tidak lagi mengunci plan berbayar.

Start command:

```text
python -m src.webapp
```

Jika `Blueprint` di Render tetap mengarah ke plan berbayar, deploy manual saja:

1. `New +` -> `Web Service`
2. pilih repo GitHub `mkri-scraper`
3. isi:
   - Environment: `Python`
   - Build Command: `pip install -e .`
   - Start Command: `python -m src.webapp`
   - Plan: `Free`

Catatan:

- deploy free cocok untuk viewer demo
- filesystem Render free bersifat ephemeral, jadi jangan mengandalkan server Render untuk menyimpan PDF atau hasil ingest lokal jangka panjang

## Tempat Meletakkan PDF Contoh

Untuk contoh sensitif, taruh PDF di:

```text
tests/fixtures/pdfs/
```

Kalau ingin diproses sebagai korpus kerja, taruh di:

```text
data/raw_pdfs/
```

Untuk workflow harian yang lebih stabil, taruh PDF baru di:

```text
data/inbox_pdfs/
```

## Fallback LLM

Direktori `src/llm_fallback/` disediakan untuk pengembangan berikutnya:

- klien Responses API
- prompt untuk bagian ambigu
- structured output schema

Modul ini tidak dipakai oleh pipeline default dan tidak membutuhkan API key untuk menjalankan parser utama.
