from __future__ import annotations

import json
import os
import re
from html import escape
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, quote, urlencode
from wsgiref.simple_server import make_server

from .webdata import build_case_catalog, build_dashboard_stats, filter_case_summaries, get_case_record, summarize_case, public_summary, OUTCOME_LABELS
from .admin import OwnerApp
from .library import Library
from .experience import (browse_return, case_href, pdf_source, search_matches, highlighted,
                         related_cases, judges_html, change_html, reasoning_html, thresholds_html, citation)


_NOISY_NAME_TOKENS = (
    "mahkamah konstitusi",
    "undang",
    "pasal",
    "permohonan",
    "tanggal",
    "bukti",
    "nomor",
    "dalam hal ini",
    "kepaniteraan",
)
_SECTION_KEYWORDS = (
    "putusan",
    "ketetapan",
    "duduk perkara",
    "pertimbangan",
    "amar",
    "konklusi",
    "petitum",
    "kewenangan",
    "kedudukan hukum",
    "pokok permohonan",
)
_STATUS_LABELS = {
    "ok": "Siap",
    "partial": "Parsial",
    "failed": "Gagal",
    "unknown": "Tidak diketahui",
}
_SOURCE_LABELS = {
    "library": "Disimpan pemilik",
    "review_queue": "Perlu review",
    "validated_json": "Tervalidasi",
    "parsed_json": "Hasil parse",
}
_DOCUMENT_TYPE_LABELS = {
    "putusan": "Putusan",
    "ketetapan": "Ketetapan",
    "unknown": "Tidak diketahui",
}
_REVIEW_FLAG_LABELS = {
    "decision_date_missing": "Tanggal putusan belum terbaca",
    "outcome_summary_not_in_amar_style": "Ringkasan amar belum rapi",
    "respondent_count_high": "Jumlah pihak termohon terlalu tinggi",
    "judges_not_extracted": "Daftar hakim belum terbaca",
    "constitutional_articles_missing_for_putusan": "Batu uji UUD belum terbaca",
}
_SORT_LABELS = {
    "auto": "Otomatis",
    "relevance": "Paling relevan",
    "newest": "Putusan terbaru",
    "oldest": "Putusan terlama",
    "review_priority": "Paling perlu review",
    "case_number": "Nomor perkara",
    "document_type": "Jenis dokumen",
    "status": "Status parse",
}


STYLES_CSS = """
:root{--bg:#f5f3ec;--paper:#fffdf8;--ink:#23392f;--muted:#65716a;--line:#dcded3;--accent:#235c44;--accent-soft:#e5ecd9;--warn:#89531d;--warn-soft:#f7edda}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
a{color:inherit;text-decoration:none}
a:hover{color:var(--accent)}
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid #aa742d;outline-offset:4px}
button,input,select{font:inherit}
button{cursor:pointer}
h1,h2,h3,p{margin-top:0}
h1,h2,h3{font-family:Georgia,"Iowan Old Style",serif;font-weight:400;line-height:1.2}
.shell{max-width:1200px;margin:auto;padding:0 36px}
.site-header{min-height:94px;display:flex;justify-content:space-between;align-items:center;gap:20px;border-bottom:1px solid var(--line)}
.wordmark{display:flex;align-items:center;gap:7px;font-size:16px;letter-spacing:.12em;white-space:nowrap}
.wordmark strong{font-weight:750}.brand-symbol{font-size:38px;line-height:1;margin-right:8px}
nav{display:flex;gap:28px;font-size:13px}nav a:hover,.read-link:hover{text-decoration:underline;text-underline-offset:5px}
.hero{display:grid;grid-template-columns:1.75fr 1fr;gap:80px;align-items:center;padding:62px 0 46px}
.eyebrow,.field-label{font-size:11px;font-weight:650;letter-spacing:.13em;text-transform:uppercase;color:var(--muted)}
.hero h1{font-size:clamp(38px,4.6vw,59px);letter-spacing:-.045em;margin:20px 0;line-height:1.08}
.hero h1 em{font-weight:400;color:var(--accent)}
.hero p{max-width:500px;font-size:16px;color:var(--muted);margin-bottom:0}
.collection-note{border-left:1px solid var(--line);padding:8px 0 8px 34px}
.collection-count{font:76px/1.15 Georgia,serif;letter-spacing:-.04em;margin:12px 0}.collection-count span{font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin-left:12px;letter-spacing:0;color:var(--muted)}
.collection-meta{display:flex;gap:25px;font-size:13px}.collection-note p{font-size:12px;line-height:1.6;margin-top:16px}
.browse-topics{padding:4px 0 30px}.topic-list{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.chip{display:inline-flex;align-items:center;gap:12px;padding:7px 13px;border:1px solid var(--line);border-radius:4px;font-size:12px;background:transparent}
.chip span{color:var(--muted);font-size:11px}.chip:hover,.chip.selected{background:var(--accent);color:white;border-color:var(--accent)}.chip.selected span,.chip:hover span{color:inherit}
.panel{padding:26px;background:var(--paper);border:1px solid var(--line);border-radius:8px;min-width:0}.panel h2{font-size:23px;margin:12px 0 18px}.panel h3{font-size:20px}.panel p:last-child{margin-bottom:0}
.search-panel{padding:24px;margin-bottom:30px;background:#eeeee5}
.search-line{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:end}
.field{display:grid;gap:8px;min-width:0}.field input,.field select{width:100%;min-width:0;padding:12px;border:1px solid #c9d0c2;border-radius:4px;background:var(--paper);color:var(--ink);font-size:13px;min-height:46px}
.search-line button,.small-button{background:var(--accent);color:#fff;border:1px solid var(--accent);border-radius:4px;padding:12px 22px;min-height:46px;font-size:13px}.search-line button:hover,.small-button:hover{background:#173f2d}.search-line button span{margin-left:20px}
.filter-line{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-top:20px}
.advanced{margin-top:20px;border-top:1px solid var(--line);padding-top:14px;font-size:12px}.advanced summary{color:var(--muted);cursor:pointer}.toggle{display:flex;gap:8px;align-items:center;margin-top:15px}
.filter-actions{display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin-top:18px;font-size:11px;color:var(--muted)}.filter-actions>span{margin-right:auto}.small-button{min-height:32px;padding:6px 12px;font-size:11px}
.results-heading{display:flex;justify-content:space-between;align-items:baseline;gap:16px;margin:34px 0 18px}.results-heading h2{font-size:25px;margin:0}.results-heading>span{font-size:12px;color:var(--muted)}
.grid{display:grid;gap:18px}.case-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.case-card{display:flex;flex-direction:column;min-width:0;padding:27px;background:var(--paper);border:1px solid var(--line);border-radius:8px;transition:border-color .15s,box-shadow .15s}.case-card:hover{border-color:#9dac97;box-shadow:0 5px 18px #263d2b08}
.card-topline{display:flex;justify-content:space-between;gap:15px;align-items:baseline;margin-bottom:20px;font-size:11px}.topic-link{font-weight:650;color:var(--accent)}.topic-link+.topic-link{margin-left:10px}.document-label{color:var(--muted)}
.case-title-link h3{font-size:26px;letter-spacing:-.02em;margin:0 0 12px;line-height:1.2}.case-title-link:hover h3{text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:4px}
.case-reference{font-size:11px;color:var(--muted);letter-spacing:.015em;overflow-wrap:anywhere}.case-reference span{margin:0 7px}
.summary{font-size:13px;line-height:1.8;color:#57665d;margin:18px 0 24px;flex:1}
.card-bottom{display:flex;justify-content:space-between;gap:12px;align-items:center;padding-top:18px;border-top:1px solid var(--line)}
.badge{display:inline-block;padding:5px 10px;border-radius:4px;background:#eeeee7;font:600 11px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#596359}
.outcome-granted,.outcome-granted_partly{background:#e3eddc;color:#3c6230}.outcome-rejected{background:#f2e7dc;color:#805538}.outcome-inadmissible{background:#e8edf0;color:#4b6675}.outcome-withdrawn,.outcome-dismissed{background:#ede7ef;color:#735f7a}
.read-link{font-size:12px;white-space:nowrap;font-weight:600}.read-link span{margin-left:8px}
.data-note{display:block;font-size:11px;color:var(--warn);margin-top:14px}
.back-link{display:inline-block;font-size:12px;color:var(--muted);margin-top:30px}.case-intro{padding:20px 0 32px;max-width:880px}.case-intro h1{font-size:clamp(32px,4.5vw,52px);letter-spacing:-.035em;margin:24px 0 18px;line-height:1.15}.case-intro .case-reference{font-size:13px}
.detail-layout{display:grid;grid-template-columns:minmax(0,1.65fr) minmax(0,1fr);gap:22px;align-items:start}.stack{display:grid;gap:18px;min-width:0}.detail-aside .panel{background:#efefe6}.story{font-size:17px;line-height:1.85}.story-panel h2{font-size:28px}.provenance{font-size:11px;color:var(--muted);border-top:1px solid var(--line);padding-top:14px}.provenance a{display:inline-block;margin-left:4px}.law-text{font-size:14px}.source-panel p{font-size:12px;color:var(--muted)}.source-panel .stack{gap:8px;font-size:12px}
.kv{display:grid;gap:12px}.kv-row{display:grid;grid-template-columns:100px minmax(0,1fr);gap:16px;padding-top:12px;border-top:1px solid var(--line);font-size:13px;overflow-wrap:anywhere}.kv-key{font-size:10px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
#amar .kv-row{grid-template-columns:42px minmax(0,1fr)}#amar{scroll-margin-top:24px}#amar .badge{font-size:13px}
.inline-link{color:var(--accent);text-decoration:underline;text-underline-offset:3px}.subtle{color:var(--muted)}.mono{font-family:ui-monospace,monospace;font-size:11px;overflow-wrap:anywhere}
.data-details{margin-top:20px;font-size:13px;background:transparent}.data-details>summary{cursor:pointer;font-size:13px;font-weight:600}.data-details[open]>summary{margin-bottom:20px}.document-text{max-height:650px;overflow:auto;padding:15px;background:var(--paper)}.document-text p{white-space:pre-wrap;font-size:13px;overflow-wrap:anywhere}.document-text h3{font-size:17px;overflow-wrap:anywhere}
.flag-list{display:flex;gap:8px;flex-wrap:wrap}.flag{font-size:11px;background:var(--warn-soft);color:var(--warn);padding:4px 8px;border-radius:4px}.empty{grid-column:1/-1;text-align:center;padding:50px 20px}.empty p{color:var(--muted)}
footer{margin-top:65px;padding:30px 0 40px;border-top:1px solid var(--line);display:flex;align-items:center;gap:35px}footer p{font-size:11px;color:var(--muted);margin:0;flex:1}footer>a{font-size:11px}
@media(max-width:850px){.hero{gap:30px;grid-template-columns:1.5fr 1fr}.hero h1{font-size:44px}.collection-note{padding-left:24px}.detail-layout{grid-template-columns:1fr}.detail-aside{grid-template-columns:1fr 1fr}.source-panel{grid-column:1/-1}.filter-line{grid-template-columns:1fr 1fr}.case-title-link h3{font-size:23px}.case-card{padding:22px}.card-bottom{align-items:start;flex-direction:column}}
@media(max-width:580px){.shell{padding:0 18px}.site-header{min-height:76px;gap:12px}.wordmark{font-size:13px;gap:5px}.brand-symbol{font-size:28px;margin-right:2px}nav{font-size:11px;gap:14px}nav a:last-child{display:none}.hero{grid-template-columns:1fr;padding:35px 0 24px;gap:24px}.hero h1{font-size:43px}.hero p{font-size:14px}.collection-note{border-left:0;border-top:1px solid var(--line);padding:18px 0 0}.collection-count{font-size:42px;margin:5px 0}.collection-note p{margin-top:8px}.collection-meta{font-size:12px}.browse-topics{padding-bottom:20px}.chip{padding:5px 9px;font-size:11px;gap:8px}.search-panel{padding:16px}.search-line{grid-template-columns:1fr}.search-line button{justify-self:start;padding:9px 14px;min-height:40px}.filter-line{gap:12px}.filter-actions{gap:12px}.filter-actions>span{flex-basis:100%}.case-grid{grid-template-columns:1fr}.results-heading h2{font-size:21px}.results-heading>span{font-size:11px}.case-card{padding:22px}.card-bottom{flex-direction:row;align-items:center}.case-intro h1{font-size:34px}.detail-aside{grid-template-columns:1fr}.panel{padding:20px}.kv-row{grid-template-columns:80px minmax(0,1fr);gap:10px}.story{font-size:15px}.data-details .detail-layout{gap:20px}footer{flex-wrap:wrap;gap:16px;margin-top:40px}footer p{flex-basis:100%}.field-label{font-size:10px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.case-card{transition:none}}
.owner-intro{padding:38px 0 24px;max-width:760px}.owner-intro h1{font-size:38px;margin:12px 0}.owner-form{display:grid;gap:18px}.owner-form input,.owner-form textarea,.owner-form select{font:inherit;max-width:100%;padding:10px;border:1px solid var(--line);border-radius:4px;background:var(--paper);color:var(--ink)}.owner-form textarea{resize:vertical;width:100%}.owner-form label{font-size:13px}.owner-form .small-button{justify-self:start}.drop-zone{padding:30px 20px;border:2px dashed #9aac9c;border-radius:8px;text-align:center;background:#edf2e8}.drop-zone input{width:100%;font-size:12px}.form-error:empty{display:none}.form-error{color:#943b2e;background:#f9e8df;padding:12px;border-radius:4px}.review-layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:24px;align-items:start}.pdf-preview{position:sticky;top:20px;display:grid;gap:18px;min-width:0}.pdf-preview iframe{width:100%;height:650px;border:1px solid var(--line)}.save-bar{display:flex;align-items:center;gap:20px;position:sticky;bottom:0;padding:16px 0;background:var(--paper);border-top:1px solid var(--line)}.upload-progress{color:var(--accent);font-size:13px}@media(max-width:850px){.review-layout{grid-template-columns:1fr}.pdf-preview{position:static}.pdf-preview iframe{height:400px}.owner-intro h1{font-size:32px}}

"""


def _json_response(start_response: Callable[..., Any], payload: dict[str, Any], status: str = "200 OK") -> list[bytes]:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    start_response(status, [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))])
    return [body]


def _text_response(start_response: Callable[..., Any], body: str, status: str = "200 OK", content_type: str = "text/html; charset=utf-8") -> list[bytes]:
    encoded = body.encode("utf-8")
    start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(encoded)))])
    return [encoded]


def _safe(value: Any) -> str:
    return escape("" if value is None else str(value))


def _label_status(value: str | None) -> str:
    return _STATUS_LABELS.get(value or "unknown", value or "Tidak diketahui")


def _label_source(value: str | None) -> str:
    return _SOURCE_LABELS.get(value or "unknown", value or "Tidak diketahui")


def _label_document_type(value: str | None) -> str:
    return _DOCUMENT_TYPE_LABELS.get(value or "unknown", value or "Tidak diketahui")


def _label_review_flag(value: str) -> str:
    return _REVIEW_FLAG_LABELS.get(value, value.replace("_", " "))


def _render_layout(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_safe(title)}</title>
  <link rel="stylesheet" href="/static/styles.css">
  <script src="/static/reader.js" defer></script>
</head>
<body>
  <div class="shell">
    <header class="site-header"><a class="wordmark" href="/cases" aria-label="MKRI — beranda"><span class="brand-symbol" aria-hidden="true">✳</span> <strong>MKRI</strong></a><nav aria-label="Navigasi utama"><a href="/cases">Jelajahi perkara</a><a href="/admin">Kelola</a><a href="#tentang">Tentang</a></nav></header>
    <main>{body}</main>
    <footer id="tentang"><div class="wordmark"><strong>MKRI</strong></div><p>Eksplorasi kecil untuk memahami perkara konstitusi.<br>Proyek independen, bukan situs resmi Mahkamah Konstitusi.</p><a class="inline-link" href="https://www.mkri.id" target="_blank" rel="noopener noreferrer">Situs resmi MKRI ↗</a></footer>
  </div>
</body>
</html>"""


def _render_dashboard(summaries: list[dict[str, Any]], stats: dict[str, Any], query: dict[str, str]) -> str:
    back = _query_href(query)
    cards = ''.join(_render_case_card(item, back=back, search=query.get('q', '')) for item in summaries) or '<div class="panel empty"><h2>Belum menemukan yang cocok.</h2><p>Coba kata lain atau hapus salah satu filter di atas.</p><a class="inline-link" href="/cases#results">Lihat semua perkara</a></div>'
    topics = ''.join(f'<a class="chip {"selected" if query.get("topic") == topic else ""}" href="{_safe(_query_href(query, topic=None if query.get("topic") == topic else topic))}">{_safe(topic)} <span>{count}</span></a>' for topic, count in stats['topic_counts'].items())
    flags = ''.join(f'<span class="flag">{_safe(_label_review_flag(name))} ({count})</span>' for name, count in stats['review_flag_counts'].items())
    filtered = any(query.get(k) for k in ('q', 'topic', 'year', 'outcome', 'status', 'source', 'review_flag', 'review_only', 'document_type'))
    featured = sorted([i for i in summaries if i.get('featured_rank') is not None], key=lambda i: i['featured_rank'])[:4] if not filtered else []
    feature_cards = ''.join(f'''<a class="featured-card" href="{_safe(case_href(i['case_id'], back))}" data-case-link><span class="eyebrow">{' / '.join(_safe(t) for t in i['topics'])}</span><h3>{_safe(i['title'])}</h3><p>{_safe(i.get('impact') or i.get('description'))}</p><span class="feature-foot">{_safe(i.get('year'))} <span aria-hidden="true">↗</span></span></a>''' for i in featured)
    feature_section = f'<section class="featured-section"><div class="section-heading"><h2>Mulai dari perkara besar</h2><a class="inline-link" href="#results">Semua perkara ↓</a></div><div class="featured-grid">{feature_cards}</div></section>' if featured else ''
    active = ''
    for key, label in [('q','Pencarian'),('topic','Topik'),('year','Tahun'),('outcome','Hasil'),('document_type','Jenis'),('status','Status'),('source','Sumber'),('review_flag','Review'),('review_only','Perlu review')]:
        if query.get(key):
            value = OUTCOME_LABELS.get(query[key], query[key]) if key == 'outcome' else query[key]
            active += f'<a class="chip selected" href="{_safe(_query_href(query, **{key: None}))}" aria-label="Hapus {_safe(label)}: {_safe(value)}">{_safe(label)}: {_safe(value)} <span aria-hidden="true">×</span></a>'
    advanced_open = ' open' if any(query.get(k) for k in ('status','source','review_flag','review_only','document_type')) else ''
    checked = ' checked' if query.get('review_only') == '1' else ''
    body = f'''
    <section class="browse-intro"><div><span class="eyebrow">Mahkamah Konstitusi · koleksi pilihan</span><h1>Putusan besar. Dampak nyata.</h1></div><p><strong>{stats['total_cases']}</strong> perkara · {len(stats['topic_counts'])} topik<br><span>Koleksi pilihan, bukan arsip lengkap.</span></p></section>
    <form method="get" action="/cases#results" class="search-panel panel compact-search">
      <div class="search-line"><label class="field"><span class="field-label">Cari perkara</span><input type="search" name="q" value="{_safe(query.get('q',''))}" placeholder="Coba: hutan adat, batas usia, Cipta Kerja…"></label><button type="submit">Cari perkara</button></div>
      <div class="filter-line">
        <label class="field"><span class="field-label">Topik</span>{_select('topic', query.get('topic',''), ['']+list(stats['topic_counts']), empty_label='Semua topik')}</label>
        <label class="field"><span class="field-label">Tahun putusan</span>{_select('year', query.get('year',''), ['']+stats['years'], empty_label='Semua tahun')}</label>
        <label class="field"><span class="field-label">Hasil perkara</span>{_select('outcome', query.get('outcome',''), ['']+list(OUTCOME_LABELS), labels=OUTCOME_LABELS, empty_label='Semua hasil')}</label>
        <label class="field"><span class="field-label">Urutkan</span>{_select('sort', query.get('sort') or 'auto', ['auto','relevance','newest','oldest','case_number'], labels=_SORT_LABELS)}</label>
      </div>
      <div class="filter-actions"><span>Judul dan topik diprioritaskan saat mencari. Teks dokumen juga tercakup.</span><button class="small-button" type="submit">Terapkan</button></div>
      <details class="advanced"{advanced_open}><summary>Filter & catatan data</summary><div class="filter-line">
        <label class="field"><span class="field-label">Status Parse</span>{_select('status',query.get('status',''),['','ok','partial','failed'],labels=_STATUS_LABELS,empty_label='Semua status')}</label>
        <label class="field"><span class="field-label">Jenis Dokumen</span>{_select('document_type',query.get('document_type',''),['','putusan','ketetapan'],labels=_DOCUMENT_TYPE_LABELS,empty_label='Semua jenis')}</label>
        <label class="field"><span class="field-label">Sumber Data</span>{_select('source',query.get('source',''),['','library','review_queue','validated_json','parsed_json'],labels=_SOURCE_LABELS,empty_label='Semua sumber')}</label>
        <label class="field"><span class="field-label">Sinyal Review</span>{_select('review_flag',query.get('review_flag',''),['']+list(stats['review_flag_counts']),labels=_REVIEW_FLAG_LABELS,empty_label='Semua sinyal')}</label>
      </div><label class="toggle"><input type="checkbox" name="review_only" value="1"{checked}> Hanya yang perlu review</label><div class="flag-list">{flags}</div><button class="small-button" type="submit">Terapkan filter data</button></details>
    </form>
    {feature_section}
    <section id="results" class="browse-results"><div class="results-heading"><h2>{'Hasil pencarian' if filtered else 'Daftar Perkara MKRI'}</h2><span>{len(summaries)} dari {stats['total_cases']} perkara</span></div>
    <div class="active-filters">{active}{'<a class="inline-link" href="/cases#results">Hapus semua</a>' if active else ''}</div>
    <details class="topic-disclosure"><summary>Jelajahi {len(stats['topic_counts'])} topik</summary><div class="topic-list">{topics}</div></details>
    <section class="grid case-grid" aria-label="Hasil pencarian">{cards}</section></section>'''
    return _render_layout('Jelajahi Perkara · MKRI', body)


def _select(
    name: str,
    current: str,
    options: list[str],
    *,
    labels: dict[str, str] | None = None,
    empty_label: str | None = None,
) -> str:
    opts = []
    if current and current not in options:
        options = options + [current]
    for option in options:
        if option == "":
            label = empty_label or f"Semua {name.replace('_', ' ')}"
        else:
            label = labels.get(option, option) if labels else option
        selected = " selected" if option == current else ""
        opts.append(f'<option value="{_safe(option)}"{selected}>{_safe(label)}</option>')
    field_labels = {
        "topic": "Topik", "year": "Tahun putusan", "outcome": "Hasil perkara",
        "sort": "Urutkan", "status": "Status Parse", "document_type": "Jenis Dokumen",
        "source": "Sumber Data", "review_flag": "Sinyal Review",
    }
    return f'<select name="{_safe(name)}" aria-label="{_safe(field_labels.get(name, name))}">{"".join(opts)}</select>'


def _query_href(current_query: dict[str, str], **updates: str | None) -> str:
    merged = dict(current_query)
    for key, value in updates.items():
        if value in (None, "", False):
            merged.pop(key, None)
        else:
            merged[key] = str(value)
    return "/cases" + (f"?{urlencode(merged)}" if merged else "") + "#results"


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        normalized = " ".join(str(item or "").split()).strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def _compact_items(
    items: list[str],
    *,
    max_items: int = 8,
    max_length: int = 80,
    max_words: int | None = None,
    predicate: Callable[[str], bool] | None = None,
) -> tuple[list[str], int]:
    cleaned = _dedupe_strings(items)
    kept: list[str] = []
    hidden = 0
    for item in cleaned:
        if len(item) > max_length:
            hidden += 1
            continue
        if max_words is not None and len(item.split()) > max_words:
            hidden += 1
            continue
        if predicate and not predicate(item):
            hidden += 1
            continue
        if len(kept) < max_items:
            kept.append(item)
        else:
            hidden += 1
    return kept, hidden


def _looks_like_person_name(value: str) -> bool:
    lowered = value.casefold()
    if any(token in lowered for token in _NOISY_NAME_TOKENS):
        return False
    if any(char.isdigit() for char in value):
        return False
    words = value.replace(",", " ").split()
    return 1 <= len(words) <= 8


def _looks_like_case_reference(value: str) -> bool:
    parts = value.split("/")
    if len(parts) not in {3, 4}:
        return False
    if not re.fullmatch(r"\d{4}", parts[-1]):
        return False
    return all(part and len(part) <= 20 and " " not in part for part in parts)


def _display_date(document: dict[str, Any], review_flags: set[str]) -> str:
    if "decision_date_missing" in review_flags:
        return "perlu review"
    return str(document.get("decision_date") or document.get("decision_date_raw") or "-")


def _infer_case_type(document: dict[str, Any]) -> str | None:
    explicit = str(document.get("case_type") or "").strip()
    if explicit:
        return explicit
    case_number = str(document.get("case_number") or "").strip()
    match = re.search(r"/([A-Z]+)(?:-[A-Z0-9]+)?/", case_number)
    return match.group(1) if match else None


def _mkri_case_url(document: dict[str, Any]) -> str | None:
    case_number = str(document.get("case_number") or "").strip()
    if not case_number:
        return None
    params = {"search": case_number}
    case_type = _infer_case_type(document)
    if case_type:
        params["jenis"] = case_type
    return f"https://www.mkri.id/perkara/persidangan/putusan?{urlencode(params)}"


def _mkri_tracking_url(document: dict[str, Any]) -> str | None:
    case_number = str(document.get("case_number") or "").strip()
    if not case_number:
        return None
    return f"https://tracking.mkri.id/index.php?id={quote(case_number, safe='')}&page=web.TrackPerkara"


def _sort_case_summaries(items: list[dict[str, Any]], sort_key: str) -> list[dict[str, Any]]:
    if sort_key == "relevance":
        return sorted(items, key=lambda i: (i.get("_relevance", 0), i.get("decision_date") or ""), reverse=True)
    if sort_key in {"newest", "oldest"}:
        dated = [item for item in items if item.get("decision_date")]
        undated = [item for item in items if not item.get("decision_date")]
        return sorted(dated, key=lambda item: (item["decision_date"], item.get("case_number") or ""), reverse=sort_key == "newest") + undated
    if sort_key == "case_number":
        return sorted(items, key=lambda item: ((item.get("case_number") or item.get("case_id") or "").casefold(), item.get("case_id") or ""))
    if sort_key == "document_type":
        return sorted(
            items,
            key=lambda item: (
                _label_document_type(item.get("document_type")).casefold(),
                (item.get("case_number") or item.get("case_id") or "").casefold(),
            ),
        )
    if sort_key == "status":
        status_rank = {"failed": 0, "partial": 1, "ok": 2, "unknown": 3}
        return sorted(
            items,
            key=lambda item: (
                status_rank.get(item.get("status") or "unknown", 9),
                (item.get("case_number") or item.get("case_id") or "").casefold(),
            ),
        )
    status_rank = {"failed": 0, "partial": 1, "ok": 2, "unknown": 3}
    return sorted(
        items,
        key=lambda item: (
            0 if item.get("needs_manual_review") else 1,
            -len(item.get("review_flags", [])),
            status_rank.get(item.get("status") or "unknown", 9),
            (item.get("case_number") or item.get("case_id") or "").casefold(),
        ),
    )


def _clean_people(items: list[dict[str, Any]], max_items: int = 8) -> tuple[list[str], int]:
    names = [item.get("name", "") for item in items if isinstance(item, dict)]
    return _compact_items(names, max_items=max_items, max_length=80, max_words=8)


def _clean_names(items: list[str], max_items: int = 9) -> tuple[list[str], int]:
    return _compact_items(items, max_items=max_items, max_length=60, max_words=8, predicate=_looks_like_person_name)


def _clean_proceedings(items: list[str], max_items: int = 6) -> tuple[list[str], int]:
    return _compact_items(items, max_items=max_items, max_length=64, max_words=8)


def _clean_case_refs(items: list[str], max_items: int = 8) -> tuple[list[str], int]:
    return _compact_items(items, max_items=max_items, max_length=32, predicate=_looks_like_case_reference)


def _clean_evidence(items: list[str], max_items: int = 12) -> tuple[list[str], int]:
    return _compact_items(
        items,
        max_items=max_items,
        max_length=20,
        predicate=lambda item: item.upper().startswith("BUKTI "),
    )


def _clean_article_refs(items: list[str], max_items: int = 8) -> tuple[list[str], int]:
    return _compact_items(items, max_items=max_items, max_length=40, max_words=6)


def _clean_section_headings(sections: list[dict[str, Any]], max_items: int = 8) -> tuple[list[str], int]:
    headings = [str(section.get("heading") or "").strip() for section in sections]
    kept: list[str] = []
    hidden = 0
    for heading in _dedupe_strings(headings):
        lowered = heading.casefold()
        is_keyword = any(keyword in lowered for keyword in _SECTION_KEYWORDS)
        is_short = len(heading) <= 48 and len(heading.split()) <= 6
        if not (is_keyword or is_short):
            hidden += 1
            continue
        if len(kept) < max_items:
            kept.append(heading)
        else:
            hidden += 1
    return kept, hidden


def _format_display_list(items: list[str], hidden_count: int = 0) -> str:
    if not items:
        return "-"
    text = "; ".join(items)
    if hidden_count:
        text += f" (+{hidden_count} item lain disembunyikan)"
    return text


def _display_short_date(value: str | None) -> str:
    if not value:
        return "Tanggal belum tersedia"
    from .normalizers import MONTHS
    try:
        year, month, day = value.split("-")
        return f"{int(day)} {list(MONTHS)[int(month) - 1].capitalize()} {year}"
    except (ValueError, IndexError):
        return value


def _render_case_card(item: dict[str, Any], back: str = '/cases#results', search: str = '') -> str:
    topics = ''.join(f'<a class="topic-link" href="{_safe(_query_href({}, topic=topic))}">{_safe(topic)}</a>' for topic in item.get('topics', []))
    href = _safe(case_href(item['case_id'], back))
    note = '<span class="data-note">Sebagian data perlu review</span>' if item.get('needs_manual_review') else ''
    match = f'<div class="search-match"><span>{_safe(item.get("match_label"))}</span><p>{highlighted(item.get("match_excerpt", ""), search)}</p></div>' if search and item.get('match_excerpt') else ''
    return f'''<article class="case-card">
      <div class="card-topline"><div>{topics or '<span class="subtle">Belum dikelompokkan</span>'}</div><span class="badge outcome-{_safe(item.get('outcome_key'))}">{_safe(item.get('outcome_label'))}</span></div>
      <a class="case-title-link" href="{href}" data-case-link><h3>{_safe(item.get('title'))}</h3></a>
      <div class="case-reference">{_safe(item.get('case_number') or item['case_id'])} · {_safe(_display_short_date(item.get('decision_date')))}</div>
      <p class="summary">{_safe(item.get('description') or 'Ringkasan belum tersedia. Buka perkara untuk membaca dokumen.')}</p>{match}
      <div class="card-bottom"><span class="document-label">{_safe(_label_document_type(item.get('document_type')))}</span><a class="read-link" href="{href}" data-case-link>Baca perkara <span aria-hidden="true">→</span></a></div>{note}</article>'''


def _render_detail(record_summary: dict[str, Any], payload: dict[str, Any], can_edit: bool = False, back: str = "/cases#results", related: list | None = None) -> str:
    document = payload.get("document", {})
    parties = payload.get("parties", {})
    outcome = payload.get("outcome", {})
    legal_basis = payload.get("legal_basis", {})
    adjudicators = payload.get("adjudicators", {})
    editorial = payload.get("editorial", {})
    sections = payload.get("sections", [])
    flags = record_summary.get("review_flags", [])
    date = _display_short_date(document.get("decision_date"))
    if "decision_date_missing" in flags:
        date = "Tanggal perlu review"
    topic_links = "".join(f'<a class="chip" href="{_safe(_query_href({}, topic=topic))}">{_safe(topic)}</a>' for topic in record_summary.get("topics", []))
    source_links = "".join(
        f'<a class="inline-link" href="{_safe(url)}" target="_blank" rel="noopener noreferrer">{label} ↗</a>'
        for label, url in [('Lihat di mkri.id', _mkri_case_url(document)), ('Tracking MKRI', _mkri_tracking_url(document))] if url
    )
    people = []
    for label, key in [('Pemohon', 'applicants'), ('Kuasa hukum', 'legal_counsels'), ('Pihak lain terdeteksi', 'respondents')]:
        names, hidden = _clean_people(parties.get(key, []), max_items=30)
        people.append((label, _format_display_list(names, hidden)))
    judges, hidden_judges = _clean_names(adjudicators.get('judges', []))
    clerks, hidden_clerks = _clean_names(adjudicators.get('clerks', []), max_items=4)
    relation_data = payload.get('relations', {})
    joined, _ = _clean_case_refs(relation_data.get('joined_cases', []))
    referenced, _ = _clean_case_refs(relation_data.get('referenced_cases', []))
    proceedings = payload.get('proceedings', [])
    proceedings = proceedings if isinstance(proceedings, list) else proceedings.get('hearing_events', [])
    proceedings, _ = _clean_proceedings(proceedings)
    evidence, _ = _clean_evidence(legal_basis.get('evidence', []))
    articles, _ = _clean_article_refs(legal_basis.get('constitutional_articles', []))
    review_flags = ''.join(f'<li>{_safe(_label_review_flag(flag))}</li>' for flag in flags)
    notes = '<p>Ekstraksi otomatis dapat melewatkan atau memotong informasi. Periksa dokumen sumber untuk detail lengkap.</p>'
    if hidden_judges or hidden_clerks:
        notes += '<p>Daftar hakim dan panitera menyembunyikan teks yang tidak menyerupai nama.</p>'
    summary_label = 'Ringkasan editorial' if editorial.get('summary') else 'Ringkasan dokumen'
    provenance = f"Disusun dari: {editorial.get('source_sections') or 'dokumen sumber'}." if editorial.get('summary') else 'Diambil dari hasil ekstraksi dokumen.'
    review_notice = '<p class="data-note">Sebagian data hasil ekstraksi masih perlu review. Lihat catatan data di bawah.</p>' if record_summary.get('needs_manual_review') else ''
    full_text = ''.join(f'<section><h3>{_safe(section.get("heading"))}</h3><p>{_safe(section.get("text"))}</p></section>' for section in sections)
    owner_link = f'<a class="inline-link" href="/admin/cases/{quote(record_summary["case_id"])}">Ubah data perkara</a>' if can_edit else ''
    pdf_link = f'<a class="inline-link" href="/cases/{quote(record_summary["case_id"])}/pdf" target="_blank" rel="noopener">Buka PDF asli ↗</a>' if payload.get('has_pdf') else ''
    correction_note = '<p class="data-note">Data inti telah diperiksa dan disimpan oleh pemilik koleksi.</p>' if payload.get('owner_review') else ''
    insights = payload.get('insights', {})
    deciding_judges = insights.get('court', {}).get('names') or judges
    has_source = bool(pdf_source(payload))
    pdf_url = f'/cases/{quote(record_summary["case_id"])}/pdf'
    pdf_link = f'<a class="button-link secondary" href="{pdf_url}" target="_blank" rel="noopener">Buka PDF asli ↗</a>' if has_source else ''
    court = judges_html(deciding_judges, insights)
    changes = change_html(insights)
    reasoning = reasoning_html(insights)
    thresholds = thresholds_html(insights)
    navigation = [('ringkasan','Keputusan')]
    if changes:
        navigation.append(('perubahan','Perubahan'))
    navigation.append(('hakim','Hakim & posisi'))
    if reasoning:
        navigation.append(('alasan','Alasan'))
    navigation += [('dokumen','Dokumen'),('terkait','Perkara terkait')]
    nav = ''.join(f'<a href="#{anchor}">{label}</a>' for anchor,label in navigation)
    related_markup = ''.join(f'<article class="related-card"><span class="eyebrow">{_safe(item["connection"])}</span><a href="{_safe(case_href(item["case_id"],back))}"><h3>{_safe(item["title"])}</h3></a><p>{_safe(item.get("impact") or item.get("description"))}</p></article>' for item in related or [])
    if not related_markup:
        related_markup = '<p>Belum ada perkara lain dengan topik yang sama dalam koleksi ini. <a class="inline-link" href="/cases#results">Jelajahi semua perkara →</a></p>'
    provisional = insights.get('provisional_items')
    dictum = outcome.get('dictum', [])
    if provisional is not None:
        original = ('<h3>Dalam provisi</h3>' + _list_block(dictum[:provisional],label='Provisi') if provisional else '')
        original += '<h3>Dalam pokok permohonan</h3>' + _list_block(dictum[provisional:],label='Amar')
    else:
        original = _list_block(dictum, label='Amar')
    drawer = f'''<dialog id="source-reader" aria-labelledby="source-title"><div class="reader-toolbar"><h2 id="source-title">Dokumen sumber</h2><button type="button" id="close-source" aria-label="Tutup dokumen">Tutup ×</button></div>
    <div class="source-reader-grid"><aside><span class="eyebrow">Yang sedang Anda baca</span><p id="source-context"></p><form id="pdf-page-form"><label for="pdf-page">Halaman PDF</label><div class="page-controls"><input id="pdf-page" type="number" min="1" max="{int(payload.get('source',{}).get('page_count') or 9999)}" value="1" required><button type="submit">Buka</button></div></form><a id="external-pdf" class="inline-link" href="{pdf_url}" target="_blank" rel="noopener">Buka di tab baru ↗</a><p class="subtle">Jika pratinjau tidak tampil, gunakan tautan tab baru.</p></aside><iframe id="source-frame" title="PDF putusan resmi" data-pdf-url="{pdf_url}"></iframe></div></dialog>''' if has_source else ''
    body = f'''
    <a class="back-link" href="{_safe(back)}" data-browse-back>← Kembali ke daftar perkara</a>
    <section id="ringkasan" class="decision-hero reader-section">
      <div class="decision-top"><span class="eyebrow">{_safe(' / '.join(record_summary.get('topics',[])))}</span><span class="badge outcome-{_safe(record_summary.get('outcome_key'))}">{_safe(record_summary.get('outcome_label'))}</span></div>
      <h1>{_safe(record_summary.get('title'))}</h1>
      <p class="decision-impact">{_safe(insights.get('impact') or record_summary.get('description') or outcome.get('summary') or 'Ringkasan belum tersedia.')}</p>
      <div class="case-reference">{_safe(document.get('case_number'))} · {_safe(date)} · {_safe(_label_document_type(document.get('document_type')))}</div>
      <div class="decision-actions"><a class="button-link" href="#hakim">Lihat hakim & posisi ↓</a>{pdf_link}{owner_link}</div>
    </section>
    <nav class="case-nav" aria-label="Bagian perkara">{nav}</nav>
    {review_notice}{correction_note}
    <section class="case-overview reader-section"><div><span class="eyebrow">{summary_label}</span><h2>Perkara ini tentang apa?</h2><p class="story">{_safe(record_summary.get('description') or 'Ringkasan belum tersedia.')}</p><p class="provenance">{_safe(provenance)} {citation(insights.get('amar_page'))}</p></div><aside><span class="eyebrow">Undang-undang yang diuji</span><p>{_safe(record_summary.get('law') or 'Belum teridentifikasi')}</p><span class="eyebrow">Pemohon</span><p>{_safe(people[0][1] if people else 'Belum teridentifikasi')}</p></aside></section>
    {changes}{thresholds}{court}{reasoning}
    <section id="dokumen" class="reader-section"><div class="section-heading"><div><span class="eyebrow">Periksa sumbernya</span><h2>Dokumen & amar putusan</h2></div>{pdf_link}</div>
    <p>Ringkasan membantu membaca perkara. Amar lengkap dan PDF tetap menjadi rujukan.</p>
    <div class="source-actions">{citation(insights.get('amar_page') or 1,'Baca PDF di samping penjelasan') if has_source else '<span>PDF langsung belum tersedia.</span>'}{source_links}</div>
    <details id="amar" class="panel original-ruling"><summary>Amar putusan / ketetapan — baca lengkap</summary>{original}</details>
    <details class="panel data-details"><summary>Pemohon, pihak & panitera</summary>{_kv_rows(people + [('Panitera',_format_display_list(clerks,hidden_clerks)),('Panel pengucapan',_format_display_list(judges,hidden_judges))])}</details>
    </section>
    <section id="terkait" class="reader-section"><div class="section-heading"><h2>Lanjutkan penelusuran</h2><a class="inline-link" href="{_safe(back)}">Kembali ke koleksi →</a></div><div class="related-grid">{related_markup}</div></section>
    <details class="panel data-details"><summary>Catatan data & rincian tambahan</summary>
      <div class="detail-layout">
        <div><h2>Catatan Viewer</h2>{notes}<ul>{review_flags}</ul>{_kv_rows([('Status parse', _label_status(record_summary.get('status'))), ('Sumber data', _label_source(record_summary.get('source')))])}<p><a class="inline-link mono" href="/api/cases/{_safe(record_summary['case_id'])}">/api/cases/{_safe(record_summary['case_id'])}</a></p></div>
        <div>{_kv_rows([('Batu uji UUD', _format_display_list(articles)), ('Alat bukti', _format_display_list(evidence)), ('Proses persidangan', _format_display_list(proceedings)), ('Perkara gabungan', _format_display_list(joined)), ('Perkara dirujuk', _format_display_list(referenced))])}</div>
      </div>
    </details>
    <details id="teks-dokumen" class="panel data-details"><summary>Teks dokumen</summary><p class="subtle">Hasil ekstraksi otomatis; pemenggalan kata dan judul dapat berbeda dari PDF.</p><form id="text-search-form" class="text-search"><label for="document-query">Cari dalam dokumen</label><input id="document-query" type="search"><button type="submit">Temukan</button><output id="text-search-status" aria-live="polite"></output></form><div class="document-text">{full_text or 'Teks belum tersedia.'}</div></details>
    {drawer}
    '''
    if has_source:
        body = re.sub(r'href="#dokumen" data-pdf-page="(\d+)"', lambda m: f'href="{pdf_url}#page={m[1]}" data-pdf-page="{m[1]}"', body)
    return _render_layout(f"{record_summary.get('title')} · MKRI", body)


def _panel(title: str, content: str) -> str:
    return f'<section class="panel"><h2>{_safe(title)}</h2>{content}</section>'


def _kv_rows(rows: list[tuple[str, Any]]) -> str:
    rendered = []
    for key, value in rows:
        rendered.append(
            f'<div class="kv-row"><div class="kv-key">{_safe(key)}</div><div>{_safe(value or "-")}</div></div>'
        )
    return f'<div class="kv">{"".join(rendered)}</div>'


def _party_group(title: str, items: list[dict[str, Any]]) -> str:
    values = ", ".join(item.get("name", "") for item in items) or "-"
    return _kv_rows([(title, values)])


def _list_block(items: list[str], label: str = "Item") -> str:
    if not items:
        return '<div class="empty">Tidak ada item.</div>'
    rendered = "".join(
        f'<div class="kv-row"><div class="kv-key">{_safe(label)}</div><div>{_safe(item)}</div></div>'
        for item in items
    )
    return f'<div class="kv">{rendered}</div>'


def _sections_block(sections: list[dict[str, Any]]) -> str:
    if not sections:
        return '<div class="empty">Section belum tersedia.</div>'
    allowed_headings, _ = _clean_section_headings(sections, max_items=18)
    allowed_lookup = {heading.casefold() for heading in allowed_headings}
    blocks = []
    for section in sections:
        heading = str(section.get("heading") or "").strip()
        if allowed_lookup and heading.casefold() not in allowed_lookup:
            continue
        excerpt = (section.get("text") or "")[:280]
        blocks.append(
            f'<div class="kv-row"><div class="kv-key">{_safe(heading)}</div><div>{_safe(excerpt)}{"..." if len(section.get("text") or "") > 280 else ""}</div></div>'
        )
        if len(blocks) >= 18:
            break
    if not blocks:
        return '<div class="empty">Section yang cukup informatif belum tersedia.</div>'
    return f'<div class="kv">{"".join(blocks)}</div>'


def create_app(
    parsed_dir: str | Path = "data/parsed_json",
    validated_dir: str | Path = "data/validated_json",
    review_dir: str | Path = "data/review_queue",
    *,
    library_dir: str | Path | None = None,
    admin_password: str | None = None,
    local_admin: bool = False,
):
    parsed_dir = Path(parsed_dir)
    validated_dir = Path(validated_dir)
    review_dir = Path(review_dir)
    storage = library_dir or os.environ.get('MKRI_STORAGE_DIR')
    library = Library(storage or parsed_dir.parent / 'library')
    password = admin_password if admin_password is not None else os.environ.get('MKRI_ADMIN_PASSWORD', '')
    owner = OwnerApp(library, _render_layout, password=password, local=local_admin,
                     enabled=bool(local_admin or (password and storage)))

    def app(environ: dict[str, Any], start_response: Callable[..., Any]) -> list[bytes]:
        path = environ.get("PATH_INFO", "/")
        query = {key: values[-1] for key, values in parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True).items()}

        if path == "/static/styles.css":
            return _text_response(start_response, STYLES_CSS + (Path(__file__).parent / 'reader.css').read_text(), content_type="text/css; charset=utf-8")
        if path == "/static/reader.js":
            return _text_response(start_response, (Path(__file__).parent / 'reader.js').read_text(), content_type="application/javascript; charset=utf-8")

        catalog = build_case_catalog(parsed_dir=parsed_dir, validated_dir=validated_dir, review_dir=review_dir, library_dir=library.directory)
        admin_response = owner(environ, start_response, catalog)
        if admin_response is not None:
            return admin_response
        pdf_match = re.fullmatch(r'/cases/([^/]+)/pdf', path)
        if pdf_match:
            content = library.pdf(case_id=pdf_match[1])
            if content is None:
                record = next((r for r in catalog if r.case_id == pdf_match[1]), None)
                if record:
                    filename = record.payload.get('source', {}).get('file_name', '')
                    # Only known catalog filenames, never URL-supplied filesystem paths.
                    if filename and Path(filename).name == filename:
                        roots = [parsed_dir.parent / 'raw_pdfs', parsed_dir.parent / 'raw_pdfs' / 'processed', parsed_dir.parent.parent / 'tests' / 'fixtures' / 'pdfs']
                        for root in roots:
                            candidate = root / filename
                            if candidate.is_file() and not candidate.is_symlink():
                                content = candidate.read_bytes()
                                break
                    if content is None:
                        remote = pdf_source(record.payload)
                        if isinstance(remote, str):
                            start_response('302 Found', [('Location', remote), ('Content-Length', '0')])
                            return [b'']
                if content is None:
                    return _text_response(start_response, 'PDF belum tersedia.', status='404 Not Found')
            return owner.binary(start_response, content, 'application/pdf', 'document.pdf')
        summaries = [summarize_case(record) for record in catalog]

        if path == "/api/cases":
            filtered = filter_case_summaries(
                summaries,
                query=query.get("q", ""),
                status=query.get("status", ""),
                document_type=query.get("document_type", ""),
                source=query.get("source", ""),
                review_flag=query.get("review_flag", ""),
                review_only=query.get("review_only") == "1",
                topic=query.get("topic", ""), year=query.get("year", ""), outcome=query.get("outcome", ""),
            )
            filtered = _sort_case_summaries(search_matches(filtered, query.get("q", "")), (query.get("sort") if query.get("sort") not in (None, "", "auto") else ("relevance" if query.get("q") else "newest")))
            return _json_response(start_response, {"items": [public_summary(item) for item in filtered], "stats": build_dashboard_stats(filtered), "facets": build_dashboard_stats(summaries)})

        if path.startswith("/api/cases/"):
            case_id = path.rsplit("/", 1)[-1]
            record = next((record for record in catalog if record.case_id == case_id), None)
            if not record:
                return _json_response(start_response, {"error": "case not found"}, status="404 Not Found")
            return _json_response(start_response, {"summary": public_summary(summarize_case(record)), "payload": record.payload})

        if path.startswith("/cases/"):
            case_id = path.rsplit("/", 1)[-1]
            record = next((record for record in catalog if record.case_id == case_id), None)
            if not record:
                return _text_response(start_response, _render_layout("Not Found", '<div class="panel empty">Case tidak ditemukan.</div>'), status="404 Not Found")
            return _text_response(start_response, _render_detail(summarize_case(record), record.payload, can_edit=owner.can_edit(environ), back=browse_return(query.get("return")), related=related_cases(summarize_case(record), summaries)))

        if path in {"/", "/cases"}:
            filtered = filter_case_summaries(
                summaries,
                query=query.get("q", ""),
                status=query.get("status", ""),
                document_type=query.get("document_type", ""),
                source=query.get("source", ""),
                review_flag=query.get("review_flag", ""),
                review_only=query.get("review_only") == "1",
                topic=query.get("topic", ""), year=query.get("year", ""), outcome=query.get("outcome", ""),
            )
            filtered = _sort_case_summaries(search_matches(filtered, query.get("q", "")), (query.get("sort") if query.get("sort") not in (None, "", "auto") else ("relevance" if query.get("q") else "newest")))
            return _text_response(start_response, _render_dashboard(filtered, build_dashboard_stats(summaries), query))

        return _text_response(start_response, _render_layout("Not Found", '<div class="panel empty">Route tidak ditemukan.</div>'), status="404 Not Found")

    return app


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0" if os.environ.get('RENDER') else "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    app = create_app(local_admin=host in {'127.0.0.1', 'localhost'} and not os.environ.get('RENDER') and not os.environ.get('MKRI_ADMIN_PASSWORD'))
    with make_server(host, port, app) as server:
        print(f"MKRI viewer running on http://{host}:{port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
