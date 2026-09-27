"""Reader-facing presentation and search helpers; court positions are curated, never guessed."""
from html import escape
from urllib.parse import urlencode, urlsplit
import re


def safe(value):
    return escape(str(value or ''))


def browse_return(value):
    try:
        parts = urlsplit(value or '/cases#results')
    except ValueError:
        return '/cases#results'
    if parts.scheme or parts.netloc or parts.path != '/cases':
        return '/cases#results'
    return '/cases' + ('?' + parts.query if parts.query else '') + '#results'


def case_href(case_id, back='/cases#results'):
    return '/cases/' + case_id + '?' + urlencode({'return': browse_return(back)})


def pdf_source(payload):
    if payload.get('has_pdf'):
        return True
    url = payload.get('source', {}).get('download_url', '')
    parts = urlsplit(url)
    if parts.scheme == 'https' and parts.hostname in {'www.mkri.id', 's.mkri.id'} and parts.path.endswith('.pdf'):
        return url
    filename = payload.get('source', {}).get('file_name', '')
    if re.fullmatch(r'putusan_mkri_\d+(?:_\d+)?\.pdf', filename):
        return 'https://s.mkri.id/public/content/persidangan/putusan/' + filename
    return None


def search_matches(items, query):
    terms = query.casefold().split()
    if not terms:
        return items
    result = []
    for item in items:
        groups = [
            ('Nomor perkara', str(item.get('case_number') or ''), 120),
            ('Judul', str(item.get('title') or ''), 50),
            ('Topik', ' '.join(item.get('topics', [])), 35),
            ('Ringkasan', str(item.get('description') or ''), 20),
            ('Undang-undang', str(item.get('law') or ''), 15),
            ('Teks dokumen', item.get('_excerpt_text', ''), 1),
        ]
        score = 0
        candidates = []
        for label, text, weight in groups:
            hits = sum(term in text.casefold() for term in terms)
            score += hits * weight + (weight if hits == len(terms) else 0)
            if hits:
                candidates.append((hits == len(terms), weight, label, text))
        copy = dict(item, _relevance=score)
        if candidates:
            _, _, label, text = max(candidates)
            text = ' '.join(text.split())
            found = [text.casefold().find(term) for term in terms if term in text.casefold()]
            start = max(0, min(found) - 75)
            copy['match_excerpt'] = ('…' if start else '') + text[start:start+240] + ('…' if len(text) > start+240 else '')
            copy['match_label'] = label
        result.append(copy)
    return result


def highlighted(text, query):
    terms = sorted(set(query.split()), key=len, reverse=True)
    if not terms:
        return safe(text)
    pattern = re.compile('(' + '|'.join(re.escape(t) for t in terms) + ')', re.I)
    return ''.join('<mark>' + safe(part) + '</mark>' if i % 2 else safe(part)
                   for i, part in enumerate(pattern.split(text or '')))


def citation(page, label=None):
    if not page:
        return ''
    return f'<a class="inline-link citation" href="#dokumen" data-pdf-page="{int(page)}">{safe(label or f"PDF hlm. {page}")} ↗</a>'


def related_cases(current, summaries):
    matches = []
    for other in summaries:
        if current['case_id'] == other['case_id']:
            continue
        common = set(current.get('topics', [])) & set(other.get('topics', []))
        if common:
            matches.append(dict(other, connection='Sama-sama membahas ' + ', '.join(sorted(common))))
    return sorted(matches, key=lambda c: c.get('decision_date') or '', reverse=True)[:3]


POSITION_LABELS = {
    'majority': 'Mengikuti putusan', 'concurring': 'Alasan berbeda',
    'dissenting': 'Pendapat berbeda', 'unverified': 'Belum diverifikasi',
}


def judges_html(names, insights):
    court = insights.get('court', {})
    positions = {p['name']: p for p in court.get('positions', [])}
    if not positions:
        names_html = ''.join(f'<span class="judge-name">{safe(n)}</span>' for n in names)
        note = court.get('note') or 'Panel pengucapan. Posisi individual belum diverifikasi; tidak diasumsikan dari tanda tangan.'
        return f'<section id="hakim" class="judges-section reader-section"><div class="section-heading"><h2>Hakim dalam perkara</h2><span>{len(names)} hakim</span></div><div class="judge-name-list">{names_html or "Daftar hakim belum tersedia."}</div><p class="court-note">{safe(note)} {citation(court.get("page"))}</p></section>'
    counts = {key: 0 for key in POSITION_LABELS}
    cards = []
    for name in names:
        position = positions.get(name, {})
        kind = position.get('position', 'unverified')
        if kind not in counts:
            kind = 'unverified'
        counts[kind] += 1
        explanation = position.get('explanation') or 'Nama tercantum pada panel perkara. Posisi individual belum diverifikasi dari dokumen.'
        initials = ''.join(part[0] for part in name.split() if len(part) > 2)[:2]
        cards.append(f'''<article class="judge-card position-{kind}">
        <div class="judge-identity"><span class="judge-avatar" aria-hidden="true">{safe(initials)}</span><h3>{safe(name)}</h3></div>
        <span class="position-label">{safe(POSITION_LABELS[kind])}</span>
        <details><summary>Alasan & sumber</summary><p>{safe(explanation)}</p>{citation(position.get('page'))}</details></article>''')
    tally = ''.join(f'<span class="tally position-{key}"><strong>{n}</strong> {safe(POSITION_LABELS[key])}</span>' for key, n in counts.items() if n)
    note = court.get('note') or 'Daftar panel pengucapan, bukan catatan voting. Posisi yang belum diverifikasi tidak dihitung sebagai dukungan atau penolakan.'
    return f'''<section id="hakim" class="judges-section reader-section"><div class="section-heading"><div><span class="eyebrow">Orang di balik putusan</span><h2>Hakim & posisi mereka</h2></div><span>{len(names)} hakim</span></div>
    <div class="vote-tally">{tally}</div><p class="court-note">{safe(note)} {citation(court.get('page'))}</p>
    <div class="judge-grid">{''.join(cards) or '<p>Daftar hakim belum tersedia.</p>'}</div></section>'''


def change_html(insights):
    change = insights.get('change')
    if not change:
        return ''
    sources = ' '.join(citation(page) for page in change.get('pages', [change.get('page')]))
    return f'''<section id="perubahan" class="reader-section"><div class="section-heading"><h2>Apa yang berubah?</h2><span class="story-sources">{sources}</span></div>
    <div class="change-grid"><div><span class="eyebrow">Sebelum putusan</span><p>{safe(change.get('before'))}</p></div><div><span class="eyebrow">Setelah putusan</span><p>{safe(change.get('after'))}</p></div></div>
    <p class="historical-note">Perubahan pada tanggal putusan; bukan keterangan status hukum terkini.</p></section>'''


def reasoning_html(insights):
    points = insights.get('reasoning', [])
    if not points:
        return ''
    cards = ''.join(f'<article><span class="eyebrow">{safe(p["label"])}</span><h3>{safe(p["title"])}</h3><p>{safe(p["text"])}</p>{citation(p.get("page"))}</article>' for p in points)
    return f'<section id="alasan" class="reader-section"><div class="section-heading"><h2>Di balik keputusan</h2></div><div class="reasoning-grid">{cards}</div></section>'


def thresholds_html(insights):
    table = insights.get('thresholds')
    if not table:
        return ''
    rows = ''.join('<tr>' + ''.join('<td>' + safe(v) + '</td>' for v in row) + '</tr>' for row in table['rows'])
    return f'''<section class="reader-section threshold-section"><div class="section-heading"><h2>Ambang pencalonan, lebih mudah dibaca</h2>{citation(table['page'])}</div>
    <p>Persentase minimum suara sah partai atau gabungan partai. Kelompok daerah ditentukan oleh jumlah penduduk dalam daftar pemilih tetap (DPT).</p>
    <table><caption>Pencalonan gubernur dan bupati/wali kota</caption><thead><tr><th scope="col">Suara sah minimum</th><th scope="col">DPT provinsi</th><th scope="col">DPT kabupaten/kota</th></tr></thead><tbody>{rows}</tbody></table></section>'''
