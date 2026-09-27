"""Curated reading journeys, separate from extracted case facts."""
import json
from pathlib import Path
from urllib.parse import quote

from .experience import safe, case_href


def load_stories(path, summaries):
    path = Path(path)
    if not path.is_file():
        return []
    numbers = {item['case_number'] for item in summaries}
    # A partial/custom collection must not advertise journeys with broken links.
    return [story for story in json.loads(path.read_text(encoding='utf-8'))
            if story['entries'] and all(entry['case_number'] in numbers for entry in story['entries'])]


def story_href(story):
    return '/stories/' + quote(story['slug'], safe='')


def story_cards(stories):
    if not stories:
        return ''
    cards = ''.join(f'''<a class="story-card" href="{story_href(story)}">
        <span class="eyebrow">Cerita {index:02d} · {len(story['entries'])} perkara</span>
        <h3>{safe(story['title'])}</h3><p>{safe(story['description'])}</p>
        <span class="story-card-foot">Ikuti ceritanya <span aria-hidden="true">↗</span></span></a>'''
        for index, story in enumerate(stories, 1))
    return f'''<section id="stories" class="stories-section"><div class="section-heading">
        <div><span class="eyebrow">Mulai dari sebuah pertanyaan</span><h2>Cerita di balik putusan</h2></div>
        <a class="inline-link" href="#results">Semua perkara ↓</a></div>
        <div class="story-card-grid">{cards}</div></section>'''


def story_navigation(number, stories, summaries, back='/cases#results'):
    by_number = {item['case_number']: item for item in summaries}
    sections = []
    for story in stories:
        numbers = [entry['case_number'] for entry in story['entries']]
        if number not in numbers:
            continue
        index = numbers.index(number)
        entry = story['entries'][index]
        group = next((g for g in story.get('chapters', []) if g['id'] == entry.get('chapter')), None)
        context = f'<span class="story-context-chapter">{safe(group["title"])} · {safe(entry.get("office"))}</span>' if group else ''
        links = []
        for neighbor, label in [(index - 1, '← Perkara sebelumnya'), (index + 1, 'Perkara berikutnya →')]:
            if 0 <= neighbor < len(numbers):
                item = by_number[numbers[neighbor]]
                links.append(f'<a href="{safe(case_href(item["case_id"], back))}"><span>{label}</span><strong>{safe(item["title"])}</strong></a>')
        sections.append(f'''<aside class="story-context" aria-label="Navigasi cerita">
            <div><span class="eyebrow">Bagian {index + 1} dari {len(numbers)}</span>
            <a class="story-context-title" href="{story_href(story)}#chapter-{index + 1}">{safe(story['title'])} ↗</a>{context}</div>
            <nav class="story-neighbors" aria-label="Perkara dalam cerita">{''.join(links)}</nav></aside>''')
    return ''.join(sections)


def render_story(story, summaries):
    by_number = {item['case_number']: item for item in summaries}
    groups = story.get('chapters', [])
    rendered, links = {}, {}
    for index, entry in enumerate(story['entries'], 1):
        item = by_number[entry['case_number']]
        date = item['decision_date']
        pdf = '/cases/' + quote(item['case_id'], safe='') + '/pdf'
        sources = ' '.join(f'<a class="inline-link" href="{pdf}#page={int(page)}" target="_blank" rel="noopener">PDF hlm. {int(page)} ↗</a>' for page in entry['source_pages'])
        heading_tag, label_tag = ('h3', 'h4') if groups else ('h2', 'h3')
        paragraphs = ''.join(f'<div class="story-explanation"><{label_tag}>{label}</{label_tag}><p>{safe(entry[key])}</p></div>'
                             for key, label in [('what', 'Apa putusannya?'), ('why', 'Alasan & dampak' if groups else 'Mengapa berarti?'), ('connection', 'Benang merah')])
        office = f'<span class="office-label">{safe(entry["office"])}</span>' if entry.get('office') else ''
        background = f'<p class="story-background">{safe(entry["background"])}</p>' if entry.get('background') else ''
        change = ''
        if entry.get('before') and entry.get('after'):
            change = f'<div class="story-change"><div><span class="eyebrow">Sebelum</span><p>{safe(entry["before"])}</p></div><div><span class="eyebrow">Setelah putusan</span><p>{safe(entry["after"])}</p></div></div>'
        supporting = ''
        if groups:
            debate = f'<h4>Yang diperdebatkan</h4><p>{safe(entry["debate"])}</p>' if entry.get('debate') else ''
            opinion = f'<h4>Pendapat di dalam putusan</h4><p>{safe(entry["opinion"])}</p>' if entry.get('opinion') else ''
            supporting = f'<details class="story-evidence"><summary>Perdebatan & sumber putusan</summary>{debate}{opinion}<div class="story-sources" aria-label="Sumber putusan">{sources}</div></details>'
        links[index] = f'<li><a href="#chapter-{index}"><span>{index:02d}</span>{safe(entry["heading"])}</a></li>'
        rendered[index] = f'''<li id="chapter-{index}" class="story-chapter">
            <div class="story-year"><span>{safe(date[:4])}</span><time datetime="{safe(date)}">{safe(date[8:10] + '.' + date[5:7] + '.' + date[:4])}</time></div>
            <article><div class="story-entry-meta">{office}<span class="eyebrow">{safe(entry['case_number'])}</span></div><{heading_tag}>{safe(entry['heading'])}</{heading_tag}>
            <span class="badge outcome-{safe(item['outcome_key'])}">{safe(item['outcome_label'])}</span>
            {background}{paragraphs}{change}{supporting}<div class="story-chapter-actions"><a class="button-link" href="{safe(case_href(item['case_id']))}">Baca perkara →</a>
            {'' if groups else f'<div class="story-sources" aria-label="Sumber putusan">{sources}</div>'}</div></article></li>'''
    contents, sections = [], []
    if groups:
        for position, group in enumerate(groups, 1):
            indices = [index for index, entry in enumerate(story['entries'], 1) if entry['chapter'] == group['id']]
            anchor = 'part-' + group['id']
            contents.append(f'<li class="story-part-link"><a href="#{safe(anchor)}"><span>{position:02d}</span><strong>{safe(group["title"])}</strong></a><ol>{"".join(links[i] for i in indices)}</ol></li>')
            sections.append(f'<section id="{safe(anchor)}" class="story-part"><header><span class="eyebrow">Bab {position} · {len(indices)} perkara</span><h2>{safe(group["title"])}</h2><p>{safe(group["intro"])}</p></header><ol class="story-timeline">{"".join(rendered[i] for i in indices)}</ol></section>')
    else:
        contents = list(links.values())
        sections = ['<ol class="story-timeline">' + ''.join(rendered.values()) + '</ol>']
    comparison = ''
    if story.get('comparison'):
        rows = ''.join('<tr>' + ''.join(f'<td>{safe(value)}</td>' for value in row) + '</tr>' for row in story['comparison']['rows'])
        comparison = f'<section class="story-comparison"><h2>{safe(story["comparison"]["title"])}</h2><p>{safe(story["comparison"]["note"])}</p><div class="story-table-scroll"><table><caption>Ringkasan jalur dalam delapan putusan yang dibahas</caption><thead><tr><th scope="col">Jabatan</th><th scope="col">Jalur pencalonan</th><th scope="col">Yang perlu dibedakan</th></tr></thead><tbody>{rows}</tbody></table></div></section>'
    history = 'Urutan waktu di dalam setiap bab; antar-bab mengikuti pertanyaan.' if groups else 'Dibaca menurut tanggal putusan.'
    return f'''<a class="back-link" href="/cases#stories">← Semua cerita & perkara</a>
        <header class="story-hero"><span class="eyebrow">Satu pertanyaan · {len(story['entries'])} putusan{' · 3 bab' if len(groups) == 3 else ''}</span>
        <h1>{safe(story['title'])}</h1><p class="story-deck">{safe(story['description'])}</p>
        <p>{safe(story['intro'])}</p><p class="historical-note">{history} Cerita ini bukan keterangan status hukum terkini.</p></header>
        <div class="story-layout"><aside class="story-contents{' story-contents-grouped' if groups else ''}"><span class="eyebrow">Dalam cerita ini</span>
        <nav aria-label="Bab cerita"><ol>{''.join(contents)}</ol></nav><a class="inline-link" href="/cases#results">Jelajahi {len(summaries)} perkara →</a></aside>
        <div>{''.join(sections)}{comparison}<section class="story-ending"><span class="eyebrow">Setelah membaca</span>
        <h2>{safe(story['closing_title'])}</h2><p>{safe(story['conclusion'])}</p>
        <a class="inline-link" href="/cases#stories">Pilih cerita berikutnya →</a></section></div></div>'''
