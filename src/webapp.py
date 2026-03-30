from __future__ import annotations

import json
import os
import re
from html import escape
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, quote, urlencode
from wsgiref.simple_server import make_server

from .webdata import build_case_catalog, build_dashboard_stats, filter_case_summaries, get_case_record, summarize_case


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
    "judges_missing": "Daftar hakim belum terbaca",
    "constitutional_articles_missing": "Batu uji UUD belum terbaca",
}
_SORT_LABELS = {
    "review_priority": "Paling perlu review",
    "case_number": "Nomor perkara",
    "document_type": "Jenis dokumen",
    "status": "Status parse",
}


STYLES_CSS = """
:root {
  --bg: #f4efe6;
  --paper: #fffaf1;
  --ink: #1c221b;
  --muted: #5f6a5f;
  --line: #d8d0c1;
  --accent: #1d6b4f;
  --accent-soft: #dcefe6;
  --warn: #9d4d00;
  --warn-soft: #fde9d7;
  --shadow: 0 18px 60px rgba(28, 34, 27, 0.08);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
  background:
    radial-gradient(circle at top left, rgba(29,107,79,0.09), transparent 30%),
    linear-gradient(180deg, #f7f1e8 0%, var(--bg) 100%);
  color: var(--ink);
}
a { color: inherit; text-decoration: none; }
.shell { max-width: 1280px; margin: 0 auto; padding: 28px; }
.hero {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 24px;
  align-items: start;
  margin-bottom: 24px;
}
.hero-card, .panel, .case-card {
  background: rgba(255, 250, 241, 0.92);
  border: 1px solid var(--line);
  border-radius: 22px;
  box-shadow: var(--shadow);
}
.hero-card { padding: 28px; }
.hero-kicker {
  display: inline-block;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font: 600 12px/1.2 "Avenir Next", "Segoe UI", sans-serif;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.hero h1 {
  margin: 14px 0 10px;
  font-size: clamp(36px, 5vw, 58px);
  line-height: 0.95;
}
.hero p {
  margin: 0;
  color: var(--muted);
  font-size: 18px;
}
.stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.stat {
  padding: 18px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 18px;
}
.stat-label {
  font: 600 12px/1.2 "Avenir Next", "Segoe UI", sans-serif;
  color: var(--muted);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.stat-value {
  margin-top: 8px;
  font-size: 34px;
  font-weight: 700;
}
.toolbar {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 18px;
  margin-bottom: 18px;
  align-items: end;
}
.toolbar input, .toolbar select, .toolbar button {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 12px 14px;
  background: #fffdf8;
  color: var(--ink);
  font: 500 14px/1.3 "Avenir Next", "Segoe UI", sans-serif;
}
.toolbar button {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
  cursor: pointer;
}
.field {
  display: grid;
  gap: 6px;
}
.field.search {
  grid-column: span 2;
}
.field-label {
  color: var(--muted);
  font: 600 12px/1.2 "Avenir Next", "Segoe UI", sans-serif;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.toolbar .toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 46px;
  padding: 0 14px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #fffdf8;
  font: 500 14px/1.3 "Avenir Next", "Segoe UI", sans-serif;
}
.toolbar .toggle input {
  width: auto;
  margin: 0;
}
.grid {
  display: grid;
  gap: 16px;
}
.case-card { padding: 18px; }
.case-top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: start;
}
.case-number {
  margin: 0;
  font-size: 22px;
}
.case-meta {
  margin-top: 10px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.badge {
  display: inline-flex;
  padding: 6px 10px;
  border-radius: 999px;
  background: #f0ece3;
  font: 600 12px/1.2 "Avenir Next", "Segoe UI", sans-serif;
}
.badge.partial { background: var(--warn-soft); color: var(--warn); }
.badge.ok { background: var(--accent-soft); color: var(--accent); }
.badge.review { background: #efe4ff; color: #6b46a8; }
.badge.source { background: #ebe6da; color: #5a6257; }
.summary {
  margin-top: 14px;
  color: var(--muted);
}
.flag-list {
  margin-top: 14px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.flag {
  padding: 6px 10px;
  border-radius: 999px;
  background: #f5eee0;
  color: #71431b;
  font: 600 12px/1.2 "Avenir Next", "Segoe UI", sans-serif;
}
.flag-link {
  display: inline-flex;
  align-items: center;
}
.topbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  flex-wrap: wrap;
}
.hero-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}
.mini-stat {
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--paper);
}
.mini-stat .label {
  color: var(--muted);
  font: 600 12px/1.2 "Avenir Next", "Segoe UI", sans-serif;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.mini-stat .value {
  margin-top: 6px;
  font-size: 20px;
  font-weight: 700;
}
.section-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  display: inline-flex;
  padding: 7px 12px;
  border-radius: 999px;
  background: #efe9db;
  color: #4c5248;
  font: 600 12px/1.2 "Avenir Next", "Segoe UI", sans-serif;
}
.subtle {
  color: var(--muted);
}
.source-list {
  display: grid;
  gap: 10px;
}
.source-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
}
.source-item:first-child {
  padding-top: 0;
  border-top: 0;
}
.source-name {
  font: 600 12px/1.2 "Avenir Next", "Segoe UI", sans-serif;
  color: var(--muted);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.source-path {
  text-align: right;
  word-break: break-all;
}
.inline-link {
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.detail-layout {
  display: grid;
  grid-template-columns: 0.95fr 1.35fr;
  gap: 18px;
}
.panel { padding: 20px; }
.panel h2 {
  margin: 0 0 14px;
  font-size: 22px;
}
.kv { display: grid; gap: 10px; }
.kv-row {
  display: grid;
  grid-template-columns: 150px 1fr;
  gap: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
}
.kv-key {
  color: var(--muted);
  font: 600 12px/1.2 "Avenir Next", "Segoe UI", sans-serif;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.stack {
  display: grid;
  gap: 14px;
}
.mono {
  font-family: "SFMono-Regular", "JetBrains Mono", ui-monospace, monospace;
  font-size: 13px;
}
.empty {
  padding: 24px;
  text-align: center;
  color: var(--muted);
}
@media (max-width: 980px) {
  .hero, .detail-layout { grid-template-columns: 1fr; }
  .toolbar { grid-template-columns: 1fr; }
}
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
</head>
<body>
  <div class="shell">
    {body}
  </div>
</body>
</html>"""


def _render_dashboard(summaries: list[dict[str, Any]], stats: dict[str, Any], query: dict[str, str]) -> str:
    cards = "".join(_render_case_card(item) for item in summaries) or '<div class="case-card empty">Belum ada perkara yang cocok dengan filter.</div>'
    top_flags = "".join(
        f'<a class="flag flag-link" href="{_safe(_query_href(query, review_flag=name))}">{_safe(_label_review_flag(name))} ({count})</a>'
        for name, count in list(stats["review_flag_counts"].items())[:6]
    ) or '<span class="flag">tidak ada review flag</span>'
    review_checked = ' checked' if query.get("review_only") == "1" else ""
    body = f"""
    <section class="hero">
      <div class="hero-card">
        <span class="hero-kicker">MKRI Visual Prototype</span>
        <h1>Daftar Perkara MKRI</h1>
        <p>Telaah hasil parse putusan dan ketetapan Mahkamah Konstitusi, lalu fokuskan review ke perkara yang masih paling bermasalah.</p>
      </div>
      <div class="stats">
        <div class="stat"><div class="stat-label">Total Perkara</div><div class="stat-value">{stats['total_cases']}</div></div>
        <div class="stat"><div class="stat-label">Perlu Review</div><div class="stat-value">{stats['needs_review']}</div></div>
        <div class="stat"><div class="stat-label">Putusan</div><div class="stat-value">{stats['document_type_counts'].get('putusan', 0)}</div></div>
        <div class="stat"><div class="stat-label">Ketetapan</div><div class="stat-value">{stats['document_type_counts'].get('ketetapan', 0)}</div></div>
      </div>
    </section>
    <form method="get" action="/cases" class="panel toolbar">
      <label class="field search"><span class="field-label">Cari</span><input type="text" name="q" value="{_safe(query.get('q', ''))}" placeholder="Cari nomor perkara, judul, atau amar singkat"></label>
      <label class="field"><span class="field-label">Status Parse</span>{_select('status', query.get('status', ''), ['', 'ok', 'partial', 'failed'], labels=_STATUS_LABELS, empty_label='Semua status')}</label>
      <label class="field"><span class="field-label">Jenis Dokumen</span>{_select('document_type', query.get('document_type', ''), ['', 'putusan', 'ketetapan'], labels=_DOCUMENT_TYPE_LABELS, empty_label='Semua jenis')}</label>
      <label class="field"><span class="field-label">Sumber Data</span>{_select('source', query.get('source', ''), ['', 'review_queue', 'validated_json', 'parsed_json'], labels=_SOURCE_LABELS, empty_label='Semua sumber')}</label>
      <label class="field"><span class="field-label">Sinyal Review</span>{_select('review_flag', query.get('review_flag', ''), [''] + list(stats['review_flag_counts'].keys())[:12], labels=_REVIEW_FLAG_LABELS, empty_label='Semua sinyal')}</label>
      <label class="field"><span class="field-label">Urutkan</span>{_select('sort', query.get('sort', 'review_priority'), list(_SORT_LABELS.keys()), labels=_SORT_LABELS)}</label>
      <label class="toggle"><input type="checkbox" name="review_only" value="1"{review_checked}>Hanya yang perlu review</label>
      <button type="submit">Terapkan</button>
    </form>
    <section class="panel">
      <h2>Sinyal Review</h2>
      <div class="flag-list">{top_flags}</div>
    </section>
    <section class="grid">{cards}</section>
    """
    return _render_layout("Daftar Perkara MKRI", body)


def _select(
    name: str,
    current: str,
    options: list[str],
    *,
    labels: dict[str, str] | None = None,
    empty_label: str | None = None,
) -> str:
    opts = []
    for option in options:
        if option == "":
            label = empty_label or f"Semua {name.replace('_', ' ')}"
        else:
            label = labels.get(option, option) if labels else option
        selected = " selected" if option == current else ""
        opts.append(f'<option value="{_safe(option)}"{selected}>{_safe(label)}</option>')
    return f'<select name="{_safe(name)}">{"".join(opts)}</select>'


def _query_href(current_query: dict[str, str], **updates: str | None) -> str:
    merged = dict(current_query)
    for key, value in updates.items():
        if value in (None, "", False):
            merged.pop(key, None)
        else:
            merged[key] = str(value)
    return "/cases" + (f"?{urlencode(merged)}" if merged else "")


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
    return 1 < len(words) <= 8


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


def _render_case_card(item: dict[str, Any]) -> str:
    status = item.get("status") or "unknown"
    review_badge = '<span class="badge review">Perlu review</span>' if item.get("needs_manual_review") else ""
    date_display = "perlu review" if "decision_date_missing" in item.get("review_flags", []) else (item.get("decision_date") or "tanggal belum terbaca")
    flags = "".join(
        f'<a class="flag flag-link" href="{_safe(_query_href({}, review_flag=flag))}">{_safe(_label_review_flag(flag))}</a>'
        for flag in item.get("review_flags", [])[:3]
    )
    hidden_flags = max(len(item.get("review_flags", [])) - 3, 0)
    extra_flags = f'<span class="flag">+{hidden_flags} sinyal lain</span>' if hidden_flags else ""
    return f"""
    <article class="case-card">
      <div class="case-top">
        <div>
          <a href="/cases/{_safe(item['case_id'])}"><h3 class="case-number">{_safe(item.get('case_number') or item['case_id'])}</h3></a>
          <div class="case-meta">
            <span class="badge {status}">{_safe(_label_status(status))}</span>
            <span class="badge">{_safe(_label_document_type(item.get('document_type')))}</span>
            {review_badge}
          </div>
        </div>
        <div class="mono">{_safe(item.get('file_name'))}</div>
      </div>
      <p class="summary">{_safe(item.get('outcome_summary') or 'Outcome belum tersedia')}</p>
      <div class="case-meta">
        <span class="badge">pemohon {item.get('applicant_count', 0)}</span>
        <span class="badge">termohon {item.get('respondent_count', 0)}</span>
        <span class="badge">{_safe(date_display)}</span>
        <span class="badge source">{_safe(_label_source(item.get('source')))}</span>
      </div>
      <div class="flag-list">{flags}{extra_flags}</div>
    </article>
    """


def _render_detail(record_summary: dict[str, Any], payload: dict[str, Any]) -> str:
    parties = payload.get("parties", {})
    document = payload.get("document", {})
    legal_basis = payload.get("legal_basis", {})
    outcome = payload.get("outcome", {})
    adjudicators = payload.get("adjudicators", {})
    proceedings = payload.get("proceedings", [])
    relations = payload.get("relations", {})
    sections = payload.get("sections", [])
    review_flag_set = set(record_summary.get("review_flags", []))
    proceeding_items = proceedings if isinstance(proceedings, list) else list(proceedings.get("hearing_events", []))
    relation_joined = relations.get("joined_cases", []) if isinstance(relations, dict) else []
    relation_referenced = relations.get("referenced_cases", []) if isinstance(relations, dict) else []
    display_date = _display_date(document, review_flag_set)
    applicant_names, hidden_applicants = _clean_people(parties.get("applicants", []))
    counsel_names, hidden_counsels = _clean_people(parties.get("legal_counsels", []))
    respondent_names, hidden_respondents = _clean_people(parties.get("respondents", []))
    expert_names, hidden_experts = _clean_people(parties.get("experts", []), max_items=6)
    witness_names, hidden_witnesses = _clean_people(parties.get("witnesses", []), max_items=6)
    amicus_names, hidden_amicus = _clean_people(parties.get("amicus_curiae", []), max_items=6)
    judge_names, hidden_judges = _clean_names(adjudicators.get("judges", []))
    clerk_names, hidden_clerks = _clean_names(adjudicators.get("clerks", []), max_items=4)
    proceeding_items, hidden_proceedings = _clean_proceedings(proceeding_items)
    relation_joined, hidden_joined = _clean_case_refs(relation_joined)
    relation_referenced, hidden_referenced = _clean_case_refs(relation_referenced)
    object_of_review, hidden_object = _compact_items(legal_basis.get("object_of_review", []), max_items=4, max_length=80, max_words=12)
    constitutional_articles, hidden_constitutional = _clean_article_refs(legal_basis.get("constitutional_articles", []))
    procedural_articles, hidden_procedural = _clean_article_refs(legal_basis.get("procedural_articles", []))
    evidence_items, hidden_evidence = _clean_evidence(legal_basis.get("evidence", []))
    section_heading_items, hidden_headings = _clean_section_headings(sections)
    viewer_notes: list[str] = []
    if "decision_date_missing" in review_flag_set:
        viewer_notes.append("Tanggal putusan disembunyikan dari tampilan utama karena masih ditandai perlu review.")
    if hidden_judges or hidden_clerks:
        viewer_notes.append("Blok hakim dan panitera diringkas karena ekstraksi nama masih tercemar narasi.")
    if hidden_joined or hidden_referenced:
        viewer_notes.append("Relasi perkara dibatasi ke nomor perkara yang tampak valid agar tidak menampilkan referensi liar.")
    if hidden_proceedings:
        viewer_notes.append("Proses persidangan hanya menampilkan item singkat yang paling terbaca.")
    if hidden_evidence:
        viewer_notes.append("Daftar alat bukti dipotong ke bukti inti agar panel tetap terbaca.")
    if hidden_headings:
        viewer_notes.append("Heading dokumen diringkas agar chip hanya menampilkan section yang paling informatif.")
    section_chips = "".join(
        f'<span class="chip">{_safe(heading)}</span>'
        for heading in section_heading_items
    ) or '<span class="chip">section belum tersedia</span>'
    mkri_url = _mkri_case_url(document)
    mkri_tracking_url = _mkri_tracking_url(document)
    mkri_link = (
        f'<a href="{_safe(mkri_url)}" class="inline-link mono" target="_blank" rel="noopener noreferrer">Lihat di mkri.id</a>'
        if mkri_url
        else ""
    )
    mkri_tracking_link = (
        f'<a href="{_safe(mkri_tracking_url)}" class="inline-link mono" target="_blank" rel="noopener noreferrer">Tracking MKRI</a>'
        if mkri_tracking_url
        else ""
    )
    review_flags = "".join(
        f'<a class="flag flag-link" href="{_safe(_query_href({}, review_flag=flag))}">{_safe(_label_review_flag(flag))}</a>'
        for flag in record_summary.get("review_flags", [])
    ) or '<span class="flag">tidak ada</span>'
    viewer_notes_block = _list_block(viewer_notes, label="Catatan") if viewer_notes else '<div class="empty">Tidak ada catatan tambahan.</div>'
    body = f"""
    <section class="hero">
      <div class="hero-card">
        <div class="topbar">
          <a href="/cases" class="hero-kicker">Kembali ke daftar</a>
          <div class="stack">
            {mkri_link}
            {mkri_tracking_link}
            <a href="/api/cases/{_safe(record_summary['case_id'])}" class="inline-link mono">/api/cases/{_safe(record_summary['case_id'])}</a>
          </div>
        </div>
        <h1>{_safe(document.get('case_number') or record_summary['case_id'])}</h1>
        <p>{_safe(document.get('title') or outcome.get('summary') or 'Outcome belum tersedia')}</p>
        <div class="case-meta">
          <span class="badge {record_summary.get('status')}">{_safe(_label_status(record_summary.get('status')))}</span>
          <span class="badge">{_safe(_label_document_type(document.get('document_type')))}</span>
          <span class="badge source">{_safe(_label_source(record_summary.get('source')))}</span>
        </div>
        <div class="hero-stats">
          <div class="mini-stat"><div class="label">Pemohon</div><div class="value">{record_summary.get('applicant_count', 0)}</div></div>
          <div class="mini-stat"><div class="label">Termohon</div><div class="value">{record_summary.get('respondent_count', 0)}</div></div>
          <div class="mini-stat"><div class="label">Tanggal</div><div class="value">{_safe(display_date)}</div></div>
        </div>
      </div>
      <div class="panel">
        <h2>Review Flags</h2>
        <div class="flag-list">{review_flags}</div>
      </div>
    </section>
    <section class="detail-layout">
      <div class="stack">
        {_panel('Metadata', _kv_rows([
            ('Nomor Perkara', document.get('case_number')),
            ('Jenis Dokumen', document.get('document_type')),
            ('Jenis Perkara', document.get('case_type')),
            ('Tanggal', display_date),
            ('mkri.id', mkri_url or '-'),
            ('tracking.mkri.id', mkri_tracking_url or '-'),
        ]))}
        {_panel('Pihak', _kv_rows([
            ('Pemohon', _format_display_list(applicant_names, hidden_applicants)),
            ('Kuasa Hukum', _format_display_list(counsel_names, hidden_counsels)),
            ('Termohon / Pihak', _format_display_list(respondent_names, hidden_respondents)),
        ]))}
        {_panel('Hakim & Panitera', _kv_rows([
            ('Hakim', _format_display_list(judge_names, hidden_judges)),
            ('Panitera', _format_display_list(clerk_names, hidden_clerks)),
        ]))}
        {_panel('Catatan Viewer', viewer_notes_block)}
      </div>
      <div class="stack">
        {_panel('Amar', _list_block(outcome.get('dictum', [])))}
        {_panel('Dasar Hukum', _kv_rows([
            ('Objek Uji', _format_display_list(object_of_review, hidden_object)),
            ('Batu Uji UUD', _format_display_list(constitutional_articles, hidden_constitutional)),
            ('Pasal Prosedural', _format_display_list(procedural_articles, hidden_procedural)),
            ('Alat Bukti', _format_display_list(evidence_items, hidden_evidence)),
        ]))}
        {_panel('Proses & Relasi', _kv_rows([
            ('Proses Persidangan', _format_display_list(proceeding_items, hidden_proceedings)),
            ('Ahli', _format_display_list(expert_names, hidden_experts)),
            ('Saksi', _format_display_list(witness_names, hidden_witnesses)),
            ('Amicus Curiae', _format_display_list(amicus_names, hidden_amicus)),
            ('Perkara Gabungan', _format_display_list(relation_joined, hidden_joined)),
            ('Perkara Dirujuk', _format_display_list(relation_referenced, hidden_referenced)),
        ]))}
        {_panel('Struktur Ringkas', f'<div class="section-chips">{section_chips}</div>')}
        {_panel('Struktur Dokumen', _sections_block(sections))}
      </div>
    </section>
    """
    return _render_layout(f"MKRI Case {document.get('case_number') or record_summary['case_id']}", body)


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
):
    parsed_dir = Path(parsed_dir)
    validated_dir = Path(validated_dir)
    review_dir = Path(review_dir)

    def app(environ: dict[str, Any], start_response: Callable[..., Any]) -> list[bytes]:
        path = environ.get("PATH_INFO", "/")
        query = {key: values[-1] for key, values in parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True).items()}

        if path == "/static/styles.css":
            return _text_response(start_response, STYLES_CSS, content_type="text/css; charset=utf-8")

        catalog = build_case_catalog(parsed_dir=parsed_dir, validated_dir=validated_dir, review_dir=review_dir)
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
            )
            filtered = _sort_case_summaries(filtered, query.get("sort", "review_priority"))
            return _json_response(start_response, {"items": filtered, "stats": build_dashboard_stats(filtered)})

        if path.startswith("/api/cases/"):
            case_id = path.rsplit("/", 1)[-1]
            record = get_case_record(case_id, parsed_dir=parsed_dir, validated_dir=validated_dir, review_dir=review_dir)
            if not record:
                return _json_response(start_response, {"error": "case not found"}, status="404 Not Found")
            return _json_response(start_response, {"summary": summarize_case(record), "payload": record.payload})

        if path.startswith("/cases/"):
            case_id = path.rsplit("/", 1)[-1]
            record = get_case_record(case_id, parsed_dir=parsed_dir, validated_dir=validated_dir, review_dir=review_dir)
            if not record:
                return _text_response(start_response, _render_layout("Not Found", '<div class="panel empty">Case tidak ditemukan.</div>'), status="404 Not Found")
            return _text_response(start_response, _render_detail(summarize_case(record), record.payload))

        if path in {"/", "/cases"}:
            filtered = filter_case_summaries(
                summaries,
                query=query.get("q", ""),
                status=query.get("status", ""),
                document_type=query.get("document_type", ""),
                source=query.get("source", ""),
                review_flag=query.get("review_flag", ""),
                review_only=query.get("review_only") == "1",
            )
            filtered = _sort_case_summaries(filtered, query.get("sort", "review_priority"))
            return _text_response(start_response, _render_dashboard(filtered, build_dashboard_stats(filtered), query))

        return _text_response(start_response, _render_layout("Not Found", '<div class="panel empty">Route tidak ditemukan.</div>'), status="404 Not Found")

    return app


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    app = create_app()
    with make_server(host, port, app) as server:
        print(f"MKRI viewer running on http://{host}:{port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
