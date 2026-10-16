"""Saved English presentation, leaving case identities and source documents intact.

Content keys are exact Indonesian source strings: an edit cannot reuse an old
translation. HTML localization changes text and reader links, never form values.
"""
from functools import lru_cache
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRANSLATION_PATH = Path(__file__).resolve().parent.parent / 'data/translations/en.json'


@lru_cache(maxsize=1)
def translations():
    return json.loads(TRANSLATION_PATH.read_text(encoding='utf-8'))


def english(value):
    return translations().get(value, value) if isinstance(value, str) else value


def content(value):
    """Mark editorial prose, including future edits, for visible fallback handling."""
    if value is None or value == '':
        return ''
    return '<span data-en-content>' + escape(str(value)) + '</span>'


def language_url(url, language):
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if parts.scheme or parts.netloc:
        return url
    if not (parts.path in {'/', '/cases'} or parts.path.startswith(('/cases/', '/stories/'))):
        return url
    if parts.path.endswith('/pdf'):
        return url
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.pop('lang', None)
    if language == 'en':
        query['lang'] = 'en'
    if 'return' in query:
        # Return URLs are separately constrained to /cases by browse_return.
        query['return'] = language_url(query['return'], language)
    return urlunsplit(('', '', parts.path, urlencode(query), parts.fragment))


UI_EN = {
    'MKRI — beranda': 'MKRI — home', 'Navigasi utama': 'Main navigation',
    'Jelajahi perkara': 'Browse cases', 'Jelajahi Perkara': 'Browse cases',
    'Topik': 'Topics', 'Tentang': 'About', 'Kelola': 'Manage',
    'Koleksi perkara konstitusi dengan sumber resmi.': 'Constitutional cases with official sources.',
    'Proyek independen, bukan situs resmi Mahkamah Konstitusi.': 'An independent project, not the official Constitutional Court website.',
    'Situs resmi MKRI ↗': 'Official MKRI website ↗',
    'Mahkamah Konstitusi · koleksi perkara': 'Constitutional Court · case collection',
    'Temukan perkara konstitusi.': 'Find constitutional cases.',
    'Cari topik, nomor perkara, undang-undang, atau nama pemohon.': 'Search by topic, case number, law, or petitioner.',
    'Koleksi pilihan, bukan arsip lengkap.': 'A selected collection, not a complete archive.',
    'Cari perkara': 'Search cases', 'Coba: 35/2012, UU ITE, hutan adat…': 'Try: 35/2012, UU ITE, customary forests…',
    'Tahun putusan': 'Decision year', 'Urutkan': 'Sort by', 'Semua topik': 'All topics',
    'Semua tahun': 'All years', 'Filter lainnya': 'More filters', 'Hasil perkara': 'Outcome',
    'Jenis Dokumen': 'Document type', 'Semua hasil': 'All outcomes', 'Semua jenis': 'All types',
    'Judul, topik, dan isi dokumen tercakup dalam pencarian.': 'Search covers titles, topics, and document text in Indonesian, plus English overviews.',
    'Terapkan filter': 'Apply filters', 'Hasil pencarian': 'Search results',
    'Daftar Perkara MKRI': 'MKRI cases', 'Hapus semua': 'Clear all',
    'Belum menemukan yang cocok.': 'No matching cases.',
    'Coba kata lain atau hapus salah satu filter di atas.': 'Try another search or remove a filter above.',
    'Lihat semua perkara': 'View all cases', '← Sebelumnya': '← Previous',
    'Berikutnya →': 'Next →', 'Halaman hasil': 'Results pages',
    'Relevansi': 'Relevance', 'Terbaru': 'Newest', 'Terlama': 'Oldest',
    'Nomor perkara': 'Case number', 'Sesuai pencarian': 'Automatic',
    'Putusan': 'Judgment', 'Ketetapan': 'Order', 'Tidak diketahui': 'Unknown',
    'Dikabulkan sebagian': 'Partly granted', 'Dikabulkan': 'Granted',
    'Ditolak': 'Rejected', 'Tidak dapat diterima': 'Inadmissible',
    'Sebagian tidak diterima; sisanya ditolak': 'Partly inadmissible; remainder rejected',
    'Ditarik kembali': 'Withdrawn', 'Gugur': 'Dismissed', 'Belum teridentifikasi': 'Not identified',
    'Belum dikelompokkan': 'Not yet categorized', 'Baca perkara': 'Read case',
    'Baca perkara →': 'Read case →', 'Sebagian data perlu review': 'Some extracted data needs review',
    'Ringkasan belum tersedia. Buka perkara untuk membaca dokumen.': 'No summary yet. Open the case to read the document.',
    'Ringkasan belum tersedia.': 'No summary available.', 'Tanggal belum tersedia': 'Date unavailable',
    'Tanggal perlu review': 'Date needs review', 'Judul': 'Title', 'Ringkasan': 'Summary',
    'Undang-undang': 'Law', 'Teks dokumen': 'Document text (original Indonesian)',
    'Pengelolaan data': 'Data management', 'Status Parse': 'Parsing status',
    'Sumber Data': 'Data source', 'Sinyal Review': 'Review flags', 'Semua status': 'All statuses',
    'Semua sumber': 'All sources', 'Semua sinyal': 'All flags',
    'Hanya yang perlu review': 'Only cases needing review', 'Pencarian': 'Search',
    'Tahun': 'Year', 'Hasil': 'Outcome', 'Jenis': 'Type', 'Sumber': 'Source',
    'Perlu review': 'Needs review', 'Lengkap': 'Complete', 'Sebagian': 'Partial',
    'Gagal': 'Failed', 'Perlu ditinjau': 'Needs review',
    'Koleksi pemilik': 'Owner collection', 'Antrian review': 'Review queue',
    'Tervalidasi': 'Validated', 'Hasil parse': 'Parsed data',
    'Nomor perkara belum ditemukan': 'Case number not found',
    'Tanggal putusan belum ditemukan': 'Decision date not found',
    'Nama hakim belum ditemukan': 'Judge names not found',
    'Nama pemohon perlu diperiksa': 'Petitioner names need review',
    'Ringkasan amar belum rapi': 'Ruling summary needs review',
    'Keputusan': 'Decision', 'Perubahan': 'Changes', 'Hakim & posisi': 'Judges & positions',
    'Alasan': 'Reasoning', 'Dokumen': 'Documents', 'Perkara terkait': 'Related cases',
    'Baca amar ↓': 'Read original ruling ↓', 'Buka PDF asli ↗': 'Open original PDF ↗',
    'Ubah data perkara': 'Edit case data', 'Ringkasan editorial': 'Editorial summary',
    'Ringkasan dokumen': 'Document summary', 'Perkara ini tentang apa?': 'What is this case about?',
    'Undang-undang yang diuji': 'Law under review', 'Pemohon': 'Petitioners',
    'Kuasa hukum': 'Legal counsel', 'Pihak lain terdeteksi': 'Other detected parties',
    'Panitera': 'Clerks', 'Panel pengucapan': 'Pronouncement panel',
    'Diambil dari hasil ekstraksi dokumen.': 'From the extracted document.',
    'Sebagian data hasil ekstraksi masih perlu review. Lihat catatan data di bawah.': 'Some extracted data still needs review. See the data notes below.',
    'Data inti telah diperiksa dan disimpan oleh pemilik koleksi.': 'Core data has been checked and saved by the collection owner.',
    'Periksa sumbernya': 'Check the source', 'Dokumen & amar putusan': 'Documents & operative ruling',
    'Ringkasan membantu membaca perkara. Amar lengkap dan PDF tetap menjadi rujukan.': 'Summaries help explain the case. The full operative ruling and PDF are the source references, in Indonesian.',
    'Baca PDF di samping penjelasan': 'Read the PDF alongside the explanation',
    'Lihat di mkri.id': 'View on mkri.id', 'Lihat di mkri.id ↗': 'View on mkri.id ↗',
    'Tracking MKRI ↗': 'MKRI case tracking ↗', 'PDF langsung belum tersedia.': 'A direct PDF is not available yet.',
    'Amar putusan / ketetapan — baca lengkap': 'Full operative ruling / order — original Indonesian',
    'Dalam provisi': 'Provisional matters', 'Dalam pokok permohonan': 'Merits of the petition',
    'Pemohon, pihak & panitera': 'Petitioners, parties & clerks',
    'Lanjutkan penelusuran': 'Continue exploring', 'Kembali ke koleksi →': 'Back to the collection →',
    'Belum ada perkara lain dengan topik yang sama dalam koleksi ini.': 'There are no other cases on the same topic in this collection yet.',
    'Jelajahi semua perkara →': 'Browse all cases →', 'Catatan data & rincian tambahan': 'Data notes & additional details',
    'Catatan Viewer': 'Viewer notes', 'Status parse': 'Parsing status', 'Sumber data': 'Data source',
    'Ekstraksi otomatis dapat melewatkan atau memotong informasi. Periksa dokumen sumber untuk detail lengkap.': 'Automatic extraction may omit or truncate information. Check the source document for full details.',
    'Daftar hakim dan panitera menyembunyikan teks yang tidak menyerupai nama.': 'Judge and clerk lists omit text that does not appear to be a name.',
    'Batu uji UUD': 'Constitutional provisions', 'Alat bukti': 'Evidence',
    'Proses persidangan': 'Proceedings', 'Perkara gabungan': 'Joined cases', 'Perkara dirujuk': 'Referenced cases',
    'Hasil ekstraksi otomatis; pemenggalan kata dan judul dapat berbeda dari PDF.': 'Original Indonesian text, automatically extracted; word breaks and headings may differ from the PDF.',
    'Cari dalam dokumen': 'Search original document', 'Temukan': 'Find', 'Teks belum tersedia.': 'Text unavailable.',
    'Dokumen sumber': 'Source document (Indonesian)', 'Tutup dokumen': 'Close document', 'Tutup ×': 'Close ×',
    'Halaman PDF': 'PDF page', 'Buka halaman': 'Go to page', 'Buka di tab baru ↗': 'Open in a new tab ↗',
    'Bagian perkara': 'Case sections', 'Kembali ke hasil pencarian': 'Back to search results',
    '← Kembali ke hasil pencarian': '← Back to search results',
    'Hakim dalam perkara': 'Judges in this case', 'Daftar hakim belum tersedia.': 'Judge list unavailable.',
    'Panel pengucapan. Posisi individual belum diverifikasi; tidak diasumsikan dari tanda tangan.': 'Pronouncement panel. Individual positions have not been verified and are not inferred from signatures.',
    'Nama tercantum pada panel perkara. Posisi individual belum diverifikasi dari dokumen.': 'Listed on the case panel. The individual position has not been verified from the document.',
    'Daftar panel pengucapan, bukan catatan voting. Posisi yang belum diverifikasi tidak dihitung sebagai dukungan atau penolakan.': 'Pronouncement panel list, not a voting record. Unverified positions are not counted as support or opposition.',
    'Orang di balik putusan': 'The people behind the decision', 'Hakim & posisi mereka': 'Judges & their positions',
    'Mengikuti putusan': 'Following the ruling', 'Alasan berbeda': 'Concurring reasons',
    'Pendapat berbeda': 'Dissenting opinion', 'Belum diverifikasi': 'Unverified', 'Alasan & sumber': 'Reasons & source',
    'Apa yang berubah?': 'What changed?', 'Sebelum putusan': 'Before the decision',
    'Setelah putusan': 'After the decision', 'Di balik keputusan': 'Behind the decision',
    'Perubahan pada tanggal putusan; bukan keterangan status hukum terkini.': 'Changes as of the decision date, not a statement of current law.',
    'Ambang pencalonan, lebih mudah dibaca': 'Nomination thresholds at a glance',
    'Persentase minimum suara sah partai atau gabungan partai. Kelompok daerah ditentukan oleh jumlah penduduk dalam daftar pemilih tetap (DPT).': 'Minimum percentage of valid votes for a party or coalition. Regional groups are determined by the population on the final electoral roll (DPT).',
    'Pencalonan gubernur dan bupati/wali kota': 'Nominations for governor and regent/mayor',
    'Suara sah minimum': 'Minimum valid votes', 'DPT provinsi': 'Provincial electoral roll',
    'DPT kabupaten/kota': 'Regency/city electoral roll',
    'Mulai dari sebuah pertanyaan': 'Start with a question', 'Cerita di balik putusan': 'Stories behind the decisions',
    'Ikuti ceritanya': 'Follow the story', 'Semua perkara ↓': 'All cases ↓',
    '← Perkara sebelumnya': '← Previous case', 'Perkara berikutnya →': 'Next case →',
    'Navigasi cerita': 'Story navigation', 'Perkara dalam cerita': 'Cases in this story',
    'Apa putusannya?': 'What did the Court decide?', 'Alasan & dampak': 'Reasons & effects',
    'Mengapa berarti?': 'Why does it matter?', 'Benang merah': 'The connection', 'Sebelum': 'Before',
    'Yang diperdebatkan': 'The debate', 'Pendapat di dalam putusan': 'Opinions in the decision',
    'Perdebatan & sumber putusan': 'Debate & decision sources', 'Sumber putusan': 'Decision sources',
    'Ringkasan jalur dalam delapan putusan yang dibahas': 'Routes summarized from the eight decisions discussed',
    'Jabatan': 'Office', 'Jalur pencalonan': 'Nomination route', 'Yang perlu dibedakan': 'What to distinguish',
    'Urutan waktu di dalam setiap bab; antar-bab mengikuti pertanyaan.': 'Chronological within each chapter; chapters follow the questions.',
    'Dibaca menurut tanggal putusan.': 'Read in order of decision date.',
    'Cerita ini bukan keterangan status hukum terkini.': 'This story is not a statement of current law.',
    '← Semua cerita & perkara': '← All stories & cases', 'Dalam cerita ini': 'In this story',
    'Bab cerita': 'Story chapters', 'Setelah membaca': 'After reading', 'Pilih cerita berikutnya →': 'Choose another story →',
    'Cerita tidak ditemukan': 'Story not found', 'Kembali ke cerita & perkara →': 'Back to stories & cases →',
    'Case tidak ditemukan.': 'Case not found.', 'Route tidak ditemukan.': 'Page not found.',
}

UI_EN.update({
    'Siap': 'Ready', 'Parsial': 'Partial', 'Disimpan pemilik': 'Saved by owner',
    'Tanggal putusan belum terbaca': 'Decision date not extracted',
    'Jumlah pihak termohon terlalu tinggi': 'Unusually high respondent count',
    'Daftar hakim belum terbaca': 'Judge list not extracted',
    'Batu uji UUD belum terbaca': 'Constitutional provisions not extracted',
    'Otomatis': 'Automatic', 'Paling relevan': 'Most relevant',
    'Putusan terbaru': 'Newest decisions', 'Putusan terlama': 'Oldest decisions',
    'Paling perlu review': 'Review priority', 'Jenis dokumen': 'Document type',
    'Buka': 'Go', 'PDF putusan resmi': 'Official judgment PDF (Indonesian)',
    'Yang sedang Anda baca': 'What you are reading',
    'Jika pratinjau tidak tampil, gunakan tautan tab baru.': 'If the preview does not load, use the new-tab link.',
    '← Kembali ke daftar perkara': '← Back to case results',
    'dokumen sumber': 'the source document', 'Disusun dari:': 'Prepared from:',
    'Batu uji UUD (teks asli)': 'Constitutional provisions (original Indonesian)',
    'Alat bukti (teks asli)': 'Evidence (original Indonesian)',
    'Proses persidangan (teks asli)': 'Proceedings (original Indonesian)',
})
for history in ['Urutan waktu di dalam setiap bab; antar-bab mengikuti pertanyaan.', 'Dibaca menurut tanggal putusan.']:
    UI_EN[history + ' Cerita ini bukan keterangan status hukum terkini.'] = UI_EN[history] + ' ' + UI_EN['Cerita ini bukan keterangan status hukum terkini.']

# Only presentation-generated fragments use patterns; editorial content requires
# an exact source match above, avoiding partial translations of changed prose.
_PATTERNS = [
    (r'Halaman (\d+)', r'Page \1'), (r'PDF hlm\. (\d+)', r'PDF p. \1'),
    (r'(\d+) hakim', r'\1 judges'), (r'Jelajahi (\d+) topik', r'Browse \1 topics'),
    (r'Jelajahi (\d+) perkara →', r'Browse \1 cases →'),
    (r'Bagian (\d+) dari (\d+)', r'Part \1 of \2'),
    (r'Cerita (\d+) · (\d+) perkara', r'Story \1 · \2 cases'),
    (r'Bab (\d+) · (\d+) perkara', r'Chapter \1 · \2 cases'),
    (r'Satu pertanyaan · (\d+) putusan( · 3 bab)?', lambda m: f'One question · {m[1]} decisions' + (' · 3 chapters' if m[2] else '')),
    (r'([\d–]+) dari (\d+) perkara', r'\1 of \2 cases'),
    (r'(\d+) perkara', r'\1 cases'), (r'(\d+) topik', r'\1 topics'),
]
_MONTHS = dict(zip('Januari Februari Maret April Mei Juni Juli Agustus September Oktober November Desember'.split(),
                   'January February March April May June July August September October November December'.split()))


def text(value):
    """Translate UI text or an exact editorial source, preserving surrounding space."""
    value = str(value)
    core = value.strip()
    if not core:
        return value
    result = translations().get(core, UI_EN.get(core))
    if result is None:
        for pattern, replacement in _PATTERNS:
            if re.fullmatch(pattern, core):
                result = re.sub(pattern, replacement, core)
                break
    if result is None and core.endswith(' · teks asli'):
        result = text(core[:-12]) + ' · Indonesian match'
    if result is None and core.endswith(' · MKRI'):
        result = text(core[:-7]) + ' · MKRI'
    if result is None and core.startswith('Disusun dari: '):
        source = core[len('Disusun dari: '):].removesuffix('.')
        result = 'Prepared from: ' + text(source) + '.'
    if result is None and core.startswith('Sama-sama membahas '):
        result = 'Also about ' + ', '.join(text(t) for t in core[len('Sama-sama membahas '):].split(', '))
    if result is None and ': ' in core and core.split(': ', 1)[0] in UI_EN:
        label, rest = core.split(': ', 1)
        result = UI_EN[label] + ': ' + text(rest)
    if result is None and core.startswith('Hapus '):
        label, sep, rest = core[6:].partition(': ')
        result = 'Remove ' + text(label) + sep + text(rest)
    if result is None:
        # Counts are also split across <strong>, <span>, and <br> elements.
        result = re.sub(r'\btopik\b', 'topics', re.sub(r'\bperkara\b', 'cases', core)) if re.fullmatch(r'perkara(?: · \d+ topik)?', core) else core
        if core.startswith('· ') or core.endswith(' ↗') or core.endswith(' →'):
            match = re.fullmatch(r'(· )?(.*?)( [↗→])?', core)
            result = (match[1] or '') + text(match[2]) + (match[3] or '')
        result = re.sub(r' · (Putusan|Ketetapan)$', lambda m: ' · ' + UI_EN[m[1]], result)
        result = re.sub(r'\(\+(\d+) item lain disembunyikan\)', r'(+\1 more items hidden)', result)
        result = re.sub(r'\b(\d{1,2}) (' + '|'.join(_MONTHS) + r') (\d{4})\b',
                        lambda m: f'{m[1]} {_MONTHS[m[2]]} {m[3]}', result)
    return value[:len(value)-len(value.lstrip())] + result + value[len(value.rstrip()):]


_VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


class _EnglishHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.stack = []

    def handle_decl(self, decl):
        self.output.append('<!' + decl + '>')

    def handle_comment(self, data):
        self.output.append('<!--' + data + '-->')

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        skip = bool(self.stack and self.stack[-1][1]) or attributes.get('translate') == 'no' or tag in {'script', 'style'}
        scope = 'data-en-content' in attributes
        if not skip:
            for i, (key, value) in enumerate(attrs):
                if key in {'aria-label', 'title', 'placeholder', 'alt'} and value:
                    attrs[i] = (key, text(value))
                elif key == 'href' and value and 'data-language' not in attributes:
                    attrs[i] = (key, language_url(value, 'en'))
                elif tag == 'html' and key == 'lang':
                    attrs[i] = (key, 'en')
        self.output.append('<' + tag + ''.join(' ' + key + (('="' + escape(value, quote=True) + '"') if value is not None else '') for key, value in attrs) + '>')
        if tag not in _VOID:
            self.stack.append((tag, skip, scope))
        if tag == 'form' and not skip and attributes.get('method', 'get').lower() == 'get':
            self.output.append('<input type="hidden" name="lang" value="en">')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.stack.pop()
        self.output[-1] = self.output[-1][:-1] + ' />'

    def handle_endtag(self, tag):
        self.output.append('</' + tag + '>')
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_data(self, data):
        if self.stack and self.stack[-1][0] in {'script', 'style'}:
            self.output.append(data)
        elif self.stack and self.stack[-1][1]:
            self.output.append(escape(data))
        elif self.stack and self.stack[-1][2] and data.strip():
            translated = translations().get(data)
            if translated is None:
                translated = UI_EN.get(data)
            if translated is None and re.search(r'[A-Za-z]', data):
                if self.stack[-1][0] == 'option':
                    self.output.append(escape(data + ' — English translation not available'))
                else:
                    self.output.append('<span lang="id">' + escape(data) + '</span><small class="translation-missing">English translation not available</small>')
            else:
                self.output.append(escape(translated if translated is not None else data))
        else:
            self.output.append(escape(text(data)))


def render_page(html, url, language):
    language = 'en' if language == 'en' else 'id'
    links = []
    for lang, label in [('id', 'Bahasa Indonesia'), ('en', 'English')]:
        links.append('<a data-language="' + lang + '" lang="' + lang + '" hreflang="' + lang + '" href="' + escape(language_url(url, lang), quote=True) + '"' + (' aria-current="true"' if lang == language else '') + '>' + label + '</a>')
    switch = '<div class="language-switch" aria-label="' + ('Language' if language == 'en' else 'Bahasa') + '">' + '<span aria-hidden="true">|</span>'.join(links) + '</div>'
    html = html.replace('<!--language-switch-->', switch)
    if language == 'id':
        return html
    parser = _EnglishHTML()
    parser.feed(html)
    parser.close()
    return ''.join(parser.output)
