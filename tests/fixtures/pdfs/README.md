# PDF Fixtures

Taruh contoh PDF sensitif di folder ini.

Rekomendasi isi:

- `putusan_simple.pdf`
- `ketetapan_simple.pdf`
- `multi_pemohon.pdf`
- `dpr_presiden_pemerintah.pdf`
- `ahli_saksi.pdf`
- `amicus_curiae.pdf`
- `sidang_gabungan.pdf`
- `heading_variatif.pdf`
- `ocr_buruk.pdf`
- `amar_bervariasi.pdf`

Kalau Anda punya 12 kasus, idealnya:

- 8 kasus sudah cukup untuk parser v1 yang berguna
- 10-12 kasus lebih baik untuk menutup variasi format

Prioritas pemilihan:

1. 1 putusan biasa
2. 1 ketetapan
3. 1 kasus dengan banyak pemohon
4. 1 kasus dengan DPR / Presiden / Pemerintah
5. 1 kasus dengan ahli atau saksi
6. 1 kasus dengan amicus curiae
7. 1 sidang gabungan
8. 1 dokumen dengan heading yang tidak konsisten
9. 1 dokumen dengan OCR/scan yang lebih buruk
10. 1 dokumen dengan amar yang tidak standar

Kalau ada 12 kasus, pakai semuanya. Kalau harus disaring, ambil minimal 8 yang paling berbeda format.

