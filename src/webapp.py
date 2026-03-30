from __future__ import annotations

import json
import os
from html import escape
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode
from wsgiref.simple_server import make_server

from .webdata import build_case_catalog, build_dashboard_stats, filter_case_summaries, get_case_record, summarize_case


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
  grid-template-columns: 2fr 1fr 1fr 1fr 1.3fr auto auto;
  gap: 12px;
  padding: 18px;
  margin-bottom: 18px;
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
.toolbar .toggle {
  display: flex;
  align-items: center;
  gap: 10px;
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
        f'<a class="flag flag-link" href="{_safe(_query_href(query, review_flag=name))}">{_safe(name)} ({count})</a>'
        for name, count in list(stats["review_flag_counts"].items())[:6]
    ) or '<span class="flag">tidak ada review flag</span>'
    review_checked = ' checked' if query.get("review_only") == "1" else ""
    body = f"""
    <section class="hero">
      <div class="hero-card">
        <span class="hero-kicker">MKRI Visual Prototype</span>
        <h1>Case Viewer</h1>
        <p>Prototype visualisasi untuk menelusuri hasil parse putusan dan ketetapan MKRI, dengan fokus pada status pipeline dan review semantik.</p>
      </div>
      <div class="stats">
        <div class="stat"><div class="stat-label">Total Perkara</div><div class="stat-value">{stats['total_cases']}</div></div>
        <div class="stat"><div class="stat-label">Perlu Review</div><div class="stat-value">{stats['needs_review']}</div></div>
        <div class="stat"><div class="stat-label">Putusan</div><div class="stat-value">{stats['document_type_counts'].get('putusan', 0)}</div></div>
        <div class="stat"><div class="stat-label">Ketetapan</div><div class="stat-value">{stats['document_type_counts'].get('ketetapan', 0)}</div></div>
      </div>
    </section>
    <form method="get" action="/cases" class="panel toolbar">
      <input type="text" name="q" value="{_safe(query.get('q', ''))}" placeholder="Cari nomor perkara, title, outcome">
      {_select('status', query.get('status', ''), ['', 'ok', 'partial', 'failed'])}
      {_select('document_type', query.get('document_type', ''), ['', 'putusan', 'ketetapan'])}
      {_select('source', query.get('source', ''), ['', 'review_queue', 'validated_json', 'parsed_json'])}
      {_select('review_flag', query.get('review_flag', ''), [''] + list(stats['review_flag_counts'].keys())[:12])}
      <label class="toggle"><input type="checkbox" name="review_only" value="1"{review_checked}>hanya review</label>
      <button type="submit">Apply</button>
    </form>
    <section class="panel">
      <h2>Review Signals</h2>
      <div class="flag-list">{top_flags}</div>
    </section>
    <section class="grid">{cards}</section>
    """
    return _render_layout("MKRI Case Viewer", body)


def _select(name: str, current: str, options: list[str]) -> str:
    opts = []
    for option in options:
        label = option or f"all {name.replace('_', ' ')}"
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


def _render_case_card(item: dict[str, Any]) -> str:
    status = item.get("status") or "unknown"
    review_badge = '<span class="badge review">needs review</span>' if item.get("needs_manual_review") else ""
    flags = "".join(
        f'<a class="flag flag-link" href="{_safe(_query_href({}, review_flag=flag))}">{_safe(flag)}</a>'
        for flag in item.get("review_flags", [])
    )
    return f"""
    <article class="case-card">
      <div class="case-top">
        <div>
          <a href="/cases/{_safe(item['case_id'])}"><h3 class="case-number">{_safe(item.get('case_number') or item['case_id'])}</h3></a>
          <div class="case-meta">
            <span class="badge {status}">{_safe(status)}</span>
            <span class="badge">{_safe(item.get('document_type') or 'unknown')}</span>
            <span class="badge">{_safe(item.get('source') or 'unknown')}</span>
            {review_badge}
          </div>
        </div>
        <div class="mono">{_safe(item.get('file_name'))}</div>
      </div>
      <p class="summary">{_safe(item.get('outcome_summary') or 'Outcome belum tersedia')}</p>
      <div class="case-meta">
        <span class="badge">pemohon {item.get('applicant_count', 0)}</span>
        <span class="badge">termohon {item.get('respondent_count', 0)}</span>
        <span class="badge">{_safe(item.get('decision_date') or 'tanggal belum terbaca')}</span>
      </div>
      <div class="flag-list">{flags}</div>
    </article>
    """


def _render_detail(record_summary: dict[str, Any], payload: dict[str, Any]) -> str:
    parties = payload.get("parties", {})
    document = payload.get("document", {})
    legal_basis = payload.get("legal_basis", {})
    outcome = payload.get("outcome", {})
    adjudicators = payload.get("adjudicators", {})
    proceedings = payload.get("proceedings", {})
    relations = payload.get("case_relations", {})
    sections = payload.get("sections", [])
    source_links = "".join(
        f'<div class="source-item"><div class="source-name">{_safe(source)}</div><div class="source-path mono">{_safe(path)}</div></div>'
        for source, path in sorted(record_summary.get("available_sources", {}).items())
    ) or '<div class="empty">Tidak ada sumber tambahan.</div>'
    section_chips = "".join(
        f'<span class="chip">{_safe(section.get("heading") or "section")}</span>'
        for section in sections[:10]
    ) or '<span class="chip">section belum tersedia</span>'
    review_flags = "".join(
        f'<a class="flag flag-link" href="{_safe(_query_href({}, review_flag=flag))}">{_safe(flag)}</a>'
        for flag in record_summary.get("review_flags", [])
    ) or '<span class="flag">tidak ada</span>'
    body = f"""
    <section class="hero">
      <div class="hero-card">
        <div class="topbar">
          <a href="/cases" class="hero-kicker">Kembali ke daftar</a>
          <a href="/api/cases/{_safe(record_summary['case_id'])}" class="inline-link mono">/api/cases/{_safe(record_summary['case_id'])}</a>
        </div>
        <h1>{_safe(document.get('case_number') or record_summary['case_id'])}</h1>
        <p>{_safe(document.get('title') or outcome.get('summary') or 'Outcome belum tersedia')}</p>
        <div class="case-meta">
          <span class="badge {record_summary.get('status')}">{_safe(record_summary.get('status'))}</span>
          <span class="badge">{_safe(document.get('document_type') or 'unknown')}</span>
          <span class="badge">{_safe(record_summary.get('source'))}</span>
        </div>
        <div class="hero-stats">
          <div class="mini-stat"><div class="label">Pemohon</div><div class="value">{record_summary.get('applicant_count', 0)}</div></div>
          <div class="mini-stat"><div class="label">Termohon</div><div class="value">{record_summary.get('respondent_count', 0)}</div></div>
          <div class="mini-stat"><div class="label">Tanggal</div><div class="value">{_safe(document.get('decision_date') or document.get('decision_date_raw') or '-')}</div></div>
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
            ('Tanggal', document.get('decision_date') or document.get('decision_date_raw')),
            ('Sumber', record_summary.get('source')),
        ]))}
        {_panel('Pihak', _party_group('Pemohon', parties.get('applicants', [])) + _party_group('Kuasa Hukum', parties.get('legal_counsels', [])) + _party_group('Termohon / Pihak', parties.get('respondents', [])))}
        {_panel('Sumber JSON', f'<div class="source-list">{source_links}</div>')}
        {_panel('Hakim & Panitera', _kv_rows([
            ('Hakim', ', '.join(adjudicators.get('judges', []))),
            ('Panitera', ', '.join(adjudicators.get('clerks', []))),
        ]))}
      </div>
      <div class="stack">
        {_panel('Amar', _list_block(outcome.get('dictum', [])))}
        {_panel('Dasar Hukum', _kv_rows([
            ('Objek Uji', '; '.join(legal_basis.get('object_of_review', []))),
            ('Batu Uji UUD', '; '.join(legal_basis.get('constitutional_articles', []))),
            ('Pasal Prosedural', '; '.join(legal_basis.get('procedural_articles', []))),
            ('Alat Bukti', '; '.join(legal_basis.get('evidence', []))),
        ]))}
        {_panel('Proses & Relasi', _kv_rows([
            ('Proses Persidangan', '; '.join(proceedings.get('hearing_events', []))),
            ('Ahli', ', '.join(proceedings.get('experts', []))),
            ('Saksi', ', '.join(proceedings.get('witnesses', []))),
            ('Amicus Curiae', ', '.join(proceedings.get('amicus_curiae', []))),
            ('Perkara Terkait', '; '.join(relations.get('related_cases', []))),
            ('Sidang Gabungan', '; '.join(relations.get('joint_hearing_cases', []))),
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


def _list_block(items: list[str]) -> str:
    if not items:
        return '<div class="empty">Tidak ada item.</div>'
    rendered = "".join(f'<div class="kv-row"><div class="kv-key">Item</div><div>{_safe(item)}</div></div>' for item in items)
    return f'<div class="kv">{rendered}</div>'


def _sections_block(sections: list[dict[str, Any]]) -> str:
    if not sections:
        return '<div class="empty">Section belum tersedia.</div>'
    blocks = []
    for section in sections[:18]:
        excerpt = (section.get("text") or "")[:280]
        blocks.append(
            f'<div class="kv-row"><div class="kv-key">{_safe(section.get("heading"))}</div><div>{_safe(excerpt)}{"..." if len(section.get("text") or "") > 280 else ""}</div></div>'
        )
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
