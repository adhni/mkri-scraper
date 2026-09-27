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
        links = []
        for neighbor, label in [(index - 1, '← Perkara sebelumnya'), (index + 1, 'Perkara berikutnya →')]:
            if 0 <= neighbor < len(numbers):
                item = by_number[numbers[neighbor]]
                links.append(f'<a href="{safe(case_href(item["case_id"], back))}"><span>{label}</span><strong>{safe(item["title"])}</strong></a>')
        sections.append(f'''<aside class="story-context" aria-label="Navigasi cerita">
            <div><span class="eyebrow">Bagian {index + 1} dari {len(numbers)}</span>
            <a class="story-context-title" href="{story_href(story)}#chapter-{index + 1}">{safe(story['title'])} ↗</a></div>
            <nav class="story-neighbors" aria-label="Perkara dalam cerita">{''.join(links)}</nav></aside>''')
    return ''.join(sections)


def render_story(story, summaries):
    by_number = {item['case_number']: item for item in summaries}
    chapters, contents = [], []
    for index, entry in enumerate(story['entries'], 1):
        item = by_number[entry['case_number']]
        date = item['decision_date']
        pdf = '/cases/' + quote(item['case_id'], safe='') + '/pdf'
        sources = ' '.join(f'<a class="inline-link" href="{pdf}#page={int(page)}" target="_blank" rel="noopener">PDF hlm. {int(page)} ↗</a>' for page in entry['source_pages'])
        paragraphs = ''.join(f'<div class="story-explanation"><h3>{label}</h3><p>{safe(entry[key])}</p></div>'
                             for key, label in [('what', 'Apa putusannya?'), ('why', 'Mengapa berarti?'), ('connection', 'Benang merah')])
        contents.append(f'<li><a href="#chapter-{index}"><span>{index:02d}</span>{safe(entry["heading"])}</a></li>')
        chapters.append(f'''<li id="chapter-{index}" class="story-chapter">
            <div class="story-year"><span>{safe(date[:4])}</span><time datetime="{safe(date)}">{safe(date[8:10] + '.' + date[5:7] + '.' + date[:4])}</time></div>
            <article><span class="eyebrow">{safe(entry['case_number'])}</span><h2>{safe(entry['heading'])}</h2>
            <span class="badge outcome-{safe(item['outcome_key'])}">{safe(item['outcome_label'])}</span>
            {paragraphs}<div class="story-chapter-actions"><a class="button-link" href="{safe(case_href(item['case_id']))}">Baca perkara →</a>
            <div class="story-sources" aria-label="Sumber putusan">{sources}</div></div></article></li>''')
    return f'''<a class="back-link" href="/cases#stories">← Semua cerita & perkara</a>
        <header class="story-hero"><span class="eyebrow">Satu pertanyaan · {len(chapters)} putusan</span>
        <h1>{safe(story['title'])}</h1><p class="story-deck">{safe(story['description'])}</p>
        <p>{safe(story['intro'])}</p><p class="historical-note">Dibaca menurut tanggal putusan. Cerita ini bukan keterangan status hukum terkini.</p></header>
        <div class="story-layout"><aside class="story-contents"><span class="eyebrow">Dalam cerita ini</span>
        <nav aria-label="Bab cerita"><ol>{''.join(contents)}</ol></nav><a class="inline-link" href="/cases#results">Jelajahi {len(summaries)} perkara →</a></aside>
        <div><ol class="story-timeline">{''.join(chapters)}</ol><section class="story-ending"><span class="eyebrow">Setelah membaca</span>
        <h2>{safe(story['closing_title'])}</h2><p>{safe(story['conclusion'])}</p>
        <a class="inline-link" href="/cases#stories">Pilih cerita berikutnya →</a></section></div></div>'''
