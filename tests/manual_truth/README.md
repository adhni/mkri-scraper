# Manual Truth

Folder ini dipakai untuk anotasi manual field inti per perkara.

Buat template dari hasil parse:

```bash
python -m src.cli scaffold-manual-truth data/parsed_json
```

Tujuan anotasi:

- memverifikasi `document_type`
- memverifikasi `case_number`
- memverifikasi tanggal putusan/ketetapan
- memverifikasi daftar pemohon dan kuasa hukum
- memverifikasi pasal batu uji/prosedural
- memverifikasi amar

File anotasi di folder ini perlu direview dulu sebelum di-commit, karena tetap bisa mengandung nama pihak atau detail sensitif yang diturunkan dari dokumen.
