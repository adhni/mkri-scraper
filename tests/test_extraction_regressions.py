from __future__ import annotations

import unittest

from src.extractors.document import detect_document_info
from src.extractors.adjudicators import extract_adjudicators
from src.extractors.outcome import extract_outcome
from src.extractors.parties import extract_parties
from src.extractors.legal_basis import extract_legal_basis
from src.normalizers import normalize_indonesian_date


class ExtractionRegressionTests(unittest.TestCase):
    def test_pronouncement_date_not_law_date_or_deliberation(self):
        text = """PUTUSAN
Nomor 135/PUU-XXIII/2025
Pengujian Undang-Undang Nomor 27 Tahun 2022.
Putusan lain diucapkan pada tanggal 12 Maret 2020.
Demikian diputus dalam Rapat Permusyawaratan Hakim pada hari Rabu,
tanggal sembilan belas, bulan November, tahun dua ribu dua puluh lima,
yang diucapkan dalam Sidang Pleno Mahkamah Konstitusi terbuka untuk
umum pada hari Senin, tanggal sembilan belas, bulan Januari,
tahun dua ribu dua puluh enam, selesai diucapkan pukul 11.05 WIB.
"""
        self.assertEqual(detect_document_info(text)['decision_date'], '2026-01-19')
        self.assertIsNone(detect_document_info(text.split('Demikian')[0])['decision_date'])

    def test_word_dates_and_invalid_dates(self):
        for text, expected in [
            ('tanggal, tiga puluh bulan Januari, tahun dua ribu dua puluh enam', '2026-01-30'),
            ('enam belas, Oktober, tahun dua ribu dua puluh tiga', '2023-10-16'),
            ('dua, bulan Maret, tahun dua ribu dua puluh enam', '2026-03-02'),
            ('31 Februari 2026', None), ('27 Tahun 2022', None),
        ]:
            with self.subTest(text=text):
                self.assertEqual(normalize_indonesian_date(text), expected)

    def test_signed_judges_and_multiple_clerks_only(self):
        text = """Hakim Konstitusi disebut dalam keterangan Pemohon.
Nama Orang Dalam Narasi
KETUA,
ttd.
Suhartoyo
ANGGOTA-ANGGOTA,
190
ttd.
Saldi Isra
PANITERA PENGGANTI,
ttd.
Rahmadiani Putri Nilasari
ttd.
Aqmarina Rasika
"""
        people = extract_adjudicators([], text)
        self.assertEqual(people.judges, ['Suhartoyo', 'Saldi Isra'])
        self.assertEqual(people.clerks, ['Rahmadiani Putri Nilasari', 'Aqmarina Rasika'])
        self.assertEqual(extract_adjudicators([], 'Hakim Konstitusi Nama Seseorang').judges, [])

    def test_operative_section_ignores_requests_and_stops_before_dissent(self):
        text = """Pemohon meminta:
Mengabulkan permohonan seluruhnya.
5. AMAR PUTUSAN
Mengadili:
1. Mengabulkan permohonan untuk sebagian;
2. Menyatakan ketentuan tetap berlaku sampai
165
undang-undang baru dibentuk;
3. Menolak permohonan untuk selain dan selebihnya.
6. ALASAN BERBEDA (CONCURRING OPINION) DAN
PENDAPAT BERBEDA
Saya berpendapat permohonan harus ditolak.
Demikian diputus dalam Rapat Permusyawaratan Hakim.
"""
        outcome = extract_outcome([], text, 'putusan')
        self.assertEqual(outcome.summary, 'Mengabulkan permohonan untuk sebagian;')
        self.assertEqual(outcome.dictum, [
            'Mengabulkan permohonan untuk sebagian;',
            'Menyatakan ketentuan tetap berlaku sampai undang-undang baru dibentuk;',
            'Menolak permohonan untuk selain dan selebihnya.',
        ])
        missing = extract_outcome([], 'Pemohon meminta: Mengabulkan permohonan.', 'putusan')
        self.assertIn('tidak terdeteksi', missing.summary)

    def test_ketetapan_applicants_are_not_registration_numbers(self):
        for intro, expected in [
            ('atas nama Hertika Sihotang (selanjutnya disebut Pemohon)', ['Hertika Sihotang']),
            ('bernama Saiful Salim, S.H., yang memberikan kuasa', ['Saiful Salim, S.H']),
            ('permohonan bertanggal 12 Januari 2026 dari Bernita Matondang dan Ariyanto Zalukhu, yang memberikan kuasa', ['Bernita Matondang', 'Ariyanto Zalukhu']),
        ]:
            text = 'KETETAPAN\nMenimbang: ' + intro + '\nAkta Pengajuan Permohonan Pemohon Nomor 19/PUU/PAN.MK/AP3/01/2026'
            self.assertEqual([p.name for p in extract_parties([], text).applicants], expected)
        self.assertEqual(extract_parties([], 'Akta Pengajuan Permohonan Pemohon Nomor 19').applicants, [])

    def test_challenged_law_comes_from_opening(self):
        text = 'Permohonan Pengujian Undang -Undang Nomor 27 Tahun 2022\ntentang Pelindungan Data Pribadi terhadap Undang-Undang Dasar Negara Republik Indonesia Tahun 1945.'
        self.assertEqual(extract_legal_basis([], text).object_of_review, ['Undang-Undang Nomor 27 Tahun 2022 tentang Pelindungan Data Pribadi'])


if __name__ == '__main__':
    unittest.main()
