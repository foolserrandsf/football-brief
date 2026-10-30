# Tidies the football brief for fast, low-effort reading (safe to run on every edition, any number of times).
# Usage: python3 tools/tidy_brief.py brief.html [out.html]   (edits in place when no out file is given)
#
# What it does:
#  - header stamp "a · b · c" -> a short "Start here" card, one line per item
#  - long paragraphs and bullets -> one sentence per line; very long ones show 3 lines + a "More" drawer
#  - game lines ("Game line: x · y · z") and summary lines -> one item per line
#  - "Sources:" notes -> a small Sources drawer
#  - bet cards: the long "vs. the pregame read" notes go in a "Full read" drawer
#  - finished / older groups (finals, past weeks, recaps) -> closed drawers; live and upcoming stay open
#  - reference sections (method, picks, wraps, old recaps, archive) -> one closed drawer each
import re, sys
from bs4 import BeautifulSoup, NavigableString, Tag

SRC = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else SRC
raw = open(SRC, encoding='utf-8').read()
soup = BeautifulSoup(raw, 'html.parser')

SKIP_ANCESTORS = {'script', 'style', 'svg', 'table', 'nav', 'summary', 'header'}
SKIP_CLASSES = {'quiz', 'q', 'opts', 'why', 'diagram', 'tidy-skip'}
BLOCK_CHILDREN = {'ul', 'ol', 'div', 'table', 'details', 'p', 'section', 'svg', 'h3', 'h4'}
VOID = {'br', 'img', 'input', 'hr', 'meta', 'link', 'wbr', 'source'}
ABBR = re.compile(r'^(?:a\.m|p\.m|vs|Jr|Sr|St|Mr|Mrs|Ms|Dr|No|Nos|e\.g|i\.e|U\.S|approx|Lt|Mt|Ft|Jan|Feb|Mar|Apr|Aug|Sept|Sep|Oct|Nov|Dec|etc|Inc|Co|Ave|Gen|Rep|Sen|Gov|Mon|Tue|Tues|Wed|Thu|Thur|Thurs|Fri|Sat|Sun|pts|yds|min|approx|est|ca)\.$|^(?:[A-Z]\.)+$', re.I)

def cls(t):
    return set(t.get('class') or [])

def skipped(t):
    for a in t.parents:
        if not isinstance(a, Tag):
            continue
        if a.name in SKIP_ANCESTORS or cls(a) & SKIP_CLASSES:
            return True
    return False

def tokens(html):
    return [x for x in re.split(r'(<[^>]+>)', html) if x != '']

def split_html(html, sep_re):
    """Split an inline-HTML string at depth-0 matches of sep_re (a function deciding each whitespace/separator).
    Returns list of html pieces with balanced tags."""
    toks = tokens(html)
    plain = ''.join(t for t in toks if not t.startswith('<'))
    pieces, cur, depth, ppos = [], '', 0, 0
    for t in toks:
        if t.startswith('<'):
            m = re.match(r'<\s*(/?)\s*([a-zA-Z0-9]+)', t)
            if m:
                name = m.group(2).lower()
                if m.group(1):
                    depth -= 1
                elif name not in VOID and not t.rstrip().endswith('/>'):
                    depth += 1
            cur += t
            continue
        if depth != 0:
            cur += t; ppos += len(t); continue
        i = 0
        for m in sep_re(t):
            a, b = m.span()
            before = plain[:ppos + a]
            after = plain[ppos + b:]
            if decide(m, before, after):
                cur += t[i:a]
                pieces.append(cur); cur = ''
                i = b
        cur += t[i:]
        ppos += len(t)
    pieces.append(cur)
    return [p.strip() for p in pieces if re.sub(r'<[^>]+>|\s|&nbsp;', '', p)]

def sentence_iter(text):
    m_list = []
    for m in re.finditer(r'\s+', text):
        m.kind = 'sent'
        m_list.append(m)
    return m_list

class Sep:
    def __init__(self, m, kind):
        self.m, self.kind = m, kind
    def span(self):
        return self.m.span()

def sent_seps(text):
    return [Sep(m, 'sent') for m in re.finditer(r'\s+', text)]

def dot_seps(text):
    return [Sep(m, 'dot') for m in re.finditer(r'\s+·\s+|\s*&nbsp;·&nbsp;\s*', text)]

def decide(sep, before, after):
    if sep.kind == 'dot':
        return True
    b = before.rstrip()
    if not re.search(r'[.!?][”"’)\]]?$', b):
        return False
    if b.endswith(':'):
        return False
    w = re.search(r'(\S+)$', b)
    word = re.sub(r'[”"’)\]]+$', '', w.group(1)) if w else ''
    word = word.lstrip('(“"')
    if ABBR.match(word) or re.match(r'^\d+\.$', word) and len(word) <= 3 and not b.endswith(').'):
        return False
    a = after.lstrip()
    if not a:
        return False
    return bool(re.match(r'[A-Z0-9“"(\'$¡]', a))

def frag(html):
    return BeautifulSoup(html, 'html.parser')

def to_lines(el, pieces):
    el.clear()
    for p in pieces:
        span = soup.new_tag('span', attrs={'class': 'ln'})
        for c in list(frag(p).contents):
            span.append(c)
        el.append(span)

def visible_len(el):
    return len(el.get_text(' ', strip=True))

def inner(el):
    return el.decode_contents()

# ---------------------------------------------------------------- start-here card from the stamp
stamp = soup.select_one('header .stamp')
if stamp is not None:
    parts = split_html(inner(stamp), dot_seps)
    if len(parts) > 1:
        old = soup.select_one('#starthere')
        if old: old.decompose()
        first = parts[0]
        rest = parts[1:]
        if not re.match(r'(?i)\s*(<[^>]+>)*\s*updated', re.sub(r'<[^>]+>', '', first)):
            rest = parts; first = ''
        stamp.clear()
        if first:
            for c in list(frag(first).contents): stamp.append(c)
        else:
            stamp.decompose()
        card = soup.new_tag('div', attrs={'id': 'starthere', 'class': 'starthere'})
        h = soup.new_tag('p', attrs={'class': 'sh-k'}); h.string = 'Start here'
        card.append(h)
        ul = soup.new_tag('ul')
        for r in rest:
            r = re.sub(r'^((?:\s|<[^>]+>)*)([a-z])', lambda m: m.group(1) + m.group(2).upper(), r, count=1)
            li = soup.new_tag('li')
            for c in list(frag(r).contents): li.append(c)
            ul.append(li)
        card.append(ul)
        nav = soup.select_one('main nav.toc')
        if nav: nav.insert_after(card)
        else: soup.select_one('main .wrap').insert(0, card)

# ---------------------------------------------------------------- sources -> drawer
for p in soup.select('main p.note'):
    t = p.get_text(' ', strip=True)
    if re.match(r'^Sources?\s*:', t) and not skipped(p):
        d = soup.new_tag('details', attrs={'class': 'src'})
        s = soup.new_tag('summary'); s.string = 'Sources'
        d.append(s)
        body = soup.new_tag('p', attrs={'class': 'note'})
        h = inner(p)
        h = re.sub(r'^\s*(<(strong|b)>)?\s*Sources?\s*:\s*(</(strong|b)>)?\s*', '', h)
        for c in list(frag(h).contents): body.append(c)
        d.append(body)
        p.replace_with(d)

# ---------------------------------------------------------------- bet cards: long notes -> "Full read" drawer
for card in soup.select('.lbc'):
    notes = [c for c in card.find_all('p', recursive=False) if 'note' in cls(c)]
    if not notes:
        continue
    d = soup.new_tag('details', attrs={'class': 'more full'})
    s = soup.new_tag('summary'); s.string = 'Full read'
    d.append(s)
    notes[0].insert_before(d)
    for n in notes:
        d.append(n.extract())

# ---------------------------------------------------------------- " · " lists -> one item per line
for el in soup.select('main .gl, main .record, main .tile .s, main .lbc p.note:not(.x)'):
    if skipped(el) or el.select_one('.ln'):
        continue
    if '·' not in el.get_text():
        continue
    if el.name == 'p' and 'note' in cls(el) and 'gl' not in cls(el):
        continue
    pieces = split_html(inner(el), dot_seps)
    if len(pieces) > 1:
        to_lines(el, pieces)

for sl in soup.select('main .sumline'):
    for sp in sl.find_all('span', recursive=False):
        if 'sl' not in cls(sp):
            sp['class'] = (sp.get('class') or []) + ['sl']
        if sp.select_one('.ln') or '·' not in sp.get_text():
            continue
        pieces = split_html(inner(sp), dot_seps)
        if len(pieces) > 1:
            to_lines(sp, pieces)

# ---------------------------------------------------------------- sentences -> lines (+ "More" drawer)
MORE_AT, SHOW = 5, 3

def no_block_children(el):
    return not any(isinstance(c, Tag) and c.name in BLOCK_CHILDREN for c in el.descendants)

targets = [e for e in soup.select('main p, main li, main .sumline > span') if not skipped(e)]
for el in targets:
    if el.parent is None or el.select_one('.ln') or el.find_parent(class_='ln'):
        continue
    if not no_block_children(el):
        continue
    if visible_len(el) < 160:
        continue
    pieces = split_html(inner(el), sent_seps)
    if len(pieces) < 2:
        continue
    in_lesson = el.find_parent(class_='lesson') is not None or el.find_parent(id='archive') is not None
    in_more = el.find_parent('details', class_='more') is not None
    if len(pieces) >= MORE_AT and not in_lesson and not in_more and el.name in ('p', 'li'):
        to_lines(el, pieces[:SHOW])
        d = soup.new_tag('details', attrs={'class': 'more'})
        s = soup.new_tag('summary'); s.string = 'More (%d lines)' % (len(pieces) - SHOW)
        d.append(s)
        box = soup.new_tag('div', attrs={'class': 'morebody'})
        for p in pieces[SHOW:]:
            span = soup.new_tag('span', attrs={'class': 'ln'})
            for c in list(frag(p).contents): span.append(c)
            box.append(span)
        d.append(box)
        if el.name == 'p':
            el.name = 'div'
            el['class'] = (el.get('class') or []) + ['para']
        el.append(d)
    else:
        to_lines(el, pieces)

# ---------------------------------------------------------------- long section titles -> short title + subtitle
for h2 in soup.select('main section > h2'):
    if h2.find(True):
        continue
    t = h2.get_text().strip()
    if len(t) <= 24:
        continue
    i = t.find(':')
    j = t.find(' (')
    cut = i if i > 0 else j
    if cut <= 0:
        continue
    head, rest = t[:cut].strip(), t[cut:].lstrip(': ').strip()
    if rest.startswith('(') and rest.endswith(')'):
        rest = rest[1:-1]
    if not rest:
        continue
    h2.string = head
    sub = soup.new_tag('p', attrs={'class': 'h2sub'})
    sub.string = rest[0].upper() + rest[1:]
    h2.insert_after(sub)

# ---------------------------------------------------------------- finished groups -> closed drawers
CLOSED = re.compile(r'\bfinals?\b|\(won|\(lost|\bwon\)|\blost\)|passed|\bpasses\b|what happened|kept for the record|\bnotes\b|results|recap|last week|two weeks|weeks ago|previous|finished|last weekend|last (mon|tues|wednes|thurs|fri|satur|sun)day', re.I)

def group_title(h):
    return h.get_text(' ', strip=True)

def wrap_groups(container, open_rule):
    kids = [c for c in container.children if isinstance(c, Tag)]
    groups, cur = [], None
    for k in kids:
        if k.name == 'h2':
            cur = None; continue
        if k.name == 'h3':
            cur = [k]; groups.append(cur); continue
        if cur is not None:
            cur.append(k)
    for g in groups:
        h = g[0]
        d = soup.new_tag('details', attrs={'class': 'grp'})
        s = soup.new_tag('summary')
        h.insert_before(d)
        s.append(h.extract())
        d.append(s)
        for k in g[1:]:
            d.append(k.extract())

def card_to_drawer(card):
    first = next((c for c in card.children if isinstance(c, Tag)), None)
    if first is None or first.name != 'h3':
        return
    card.name = 'details'
    card['class'] = [c for c in (card.get('class') or []) if c != 'card'] + ['grp', 'cardd']
    s = soup.new_tag('summary')
    first.insert_before(s)
    s.append(first.extract())

def has_action(d):
    return d.select_one('.pill.o') is not None or d.select_one('.lbc.wait .pill.o') is not None

for sid in ('mybets', 'bets', 'ahead', 'psu', 'uh', 'wrap', 'now'):
    sec = soup.find('section', id=sid)
    if sec: wrap_groups(sec, None)

today = soup.find('section', id='today')
if today:
    for c in today.find_all('div', class_='card', recursive=False):
        card_to_drawer(c)
    wrap_groups(today, None)

# open/closed state (re-evaluated every run)
for sid in ('mybets', 'bets', 'ahead', 'psu', 'uh', 'now'):
    sec = soup.find('section', id=sid)
    if not sec: continue
    for d in sec.find_all('details', class_='grp', recursive=False):
        title = group_title(d.summary)
        is_open = not CLOSED.search(title)
        if is_open: d['open'] = ''
        elif d.has_attr('open'): del d['open']
    # live / upcoming drawers first, finished ones after
    ds = sec.find_all('details', class_='grp', recursive=False)
    if ds:
        anchor = soup.new_tag('i'); ds[0].insert_before(anchor)
        for d in [d for d in ds if d.has_attr('open')] + [d for d in ds if not d.has_attr('open')]:
            anchor.insert_before(d.extract())
        anchor.decompose()
if today:
    ds = today.find_all('details', class_='grp', recursive=False)
    for i, d in enumerate(ds):
        if i == 0: d['open'] = ''
        elif d.has_attr('open'): del d['open']

# ---------------------------------------------------------------- reference sections -> one drawer each
for sid in ('picks', 'method', 'live', 'saturday', 'wrap', 'college', 'archive'):
    sec = soup.find('section', id=sid)
    if not sec or sec.find('details', class_='secd', recursive=False):
        continue
    h2 = sec.find('h2', recursive=False)
    if not h2: continue
    d = soup.new_tag('details', attrs={'class': 'secd'})
    s = soup.new_tag('summary')
    rest = [c for c in list(sec.children) if c is not h2]
    h2.insert_before(d)
    s.append(h2.extract())
    hint = soup.new_tag('span', attrs={'class': 'hint'})
    hint.string = ('Old recap · tap to open' if sid in ('live', 'saturday') else 'Tap to open')
    s.append(hint)
    d.append(s)
    for c in rest:
        d.append(c.extract())

# ---------------------------------------------------------------- tables -> stacked rows on phones
for tb in soup.select('main table'):
    if tb.find_parent('svg'):
        continue
    ths = tb.select('thead th')
    if not ths:
        continue
    labels = [th.get_text(' ', strip=True) for th in ths]
    for tr in tb.select('tbody tr'):
        for i, td in enumerate(tr.find_all('td', recursive=False)):
            if i < len(labels):
                td['data-label'] = labels[i]
    if 'stack' not in cls(tb):
        tb['class'] = (tb.get('class') or []) + ['stack']

# ---------------------------------------------------------------- css + js (replaced each run)
for old in soup.select('#tidy-css, #tidy-js, #tidy-font'):
    old.decompose()
font = soup.new_tag('link', attrs={'id': 'tidy-font', 'rel': 'stylesheet', 'href': 'https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400&display=swap'})
soup.head.append(font)
style = soup.new_tag('style', attrs={'id': 'tidy-css'})
style.string = r'''
/* ---- easy-read layer (tools/tidy_brief.py) ---- */
body{font-family:"Atkinson Hyperlegible",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:17px;line-height:1.5}
p,li{max-width:62ch}
.ln{display:block;margin:0 0 .5em}
.ln:last-child{margin-bottom:0}
li{margin-bottom:14px}
li .ln{margin-bottom:.35em}
section{margin-top:30px}
h2{font-size:32px;margin-bottom:14px}
h3{font-size:22px;line-height:1.2}
header .wrap{padding-bottom:30px}
header .stamp{font-family:"Atkinson Hyperlegible",sans-serif;font-size:13px;line-height:1.4;border-radius:8px;padding:4px 10px}
/* sticky section chips */
nav.toc{position:sticky;top:0;z-index:5;flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;
  background:var(--paper);margin:0 -20px;padding:10px 20px;border-bottom:1px solid var(--line);scrollbar-width:none}
nav.toc::-webkit-scrollbar{display:none}
nav.toc a{white-space:nowrap;flex:0 0 auto}
/* start-here card */
.starthere{background:var(--card);border:1px solid var(--line);border-left:6px solid var(--flag);border-radius:10px;padding:14px 16px 6px;margin:16px 0 0}
.starthere .sh-k{font-family:"Barlow Condensed",Arial,sans-serif;font-size:22px;font-weight:700;margin:0 0 6px}
.starthere ul{list-style:none;padding:0;margin:0}
.starthere li{position:relative;padding:8px 0 8px 22px;border-top:1px solid var(--line);margin:0;font-size:16px;line-height:1.45}
.starthere li:first-child{border-top:0}
.starthere li::before{content:"";position:absolute;left:4px;top:15px;width:8px;height:8px;border-radius:50%;background:var(--field)}
/* summary lines */
.sumline{flex-direction:column;gap:8px;font-family:inherit;font-size:16px;line-height:1.45}
.sumline span.sl{display:block;border-left:3px solid var(--field);padding:2px 0 2px 10px}
.sumline span b{font-size:inherit}
/* drawers */
details.grp,details.secd{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:0;margin:10px 0;overflow:hidden}
details.grp>summary,details.secd>summary{list-style:none;cursor:pointer;padding:12px 44px 12px 14px;position:relative;font-family:inherit;font-size:inherit}
details.grp>summary::-webkit-details-marker,details.secd>summary::-webkit-details-marker{display:none}
details.grp>summary::after,details.secd>summary::after{content:"";position:absolute;right:16px;top:50%;width:9px;height:9px;margin-top:-7px;
  border-right:2.5px solid var(--muted);border-bottom:2.5px solid var(--muted);transform:rotate(45deg);transition:transform .15s}
details.grp[open]>summary::after,details.secd[open]>summary::after{transform:rotate(-135deg);margin-top:-2px}
details.grp>summary h3{margin:0;font-size:18px;line-height:1.25}
details.grp[open]>summary{border-bottom:1px solid var(--line);margin:0}
details.grp>*:not(summary){margin-left:14px;margin-right:14px}
details.grp>*:not(summary):first-of-type{margin-top:12px}
details.grp>:last-child{margin-bottom:14px}
details.grp .lb,details.grp .bets{margin-top:10px}
details.secd>summary h2{margin:0;font-size:24px;border-left:0;padding-left:0}
.h2sub{color:var(--muted);font-size:15px;margin:-8px 0 14px}
details.secd>summary .hint{display:block;font-size:13px;color:var(--muted);margin:2px 0 0}
details.secd[open]>summary .hint{display:none}
details.secd>*:not(summary){margin-left:14px;margin-right:14px}
details.secd>:last-child{margin-bottom:14px}
details.cardd{background:var(--card)}
details.more{background:none;border:0;padding:0;margin:4px 0 0}
details.more>summary{display:inline-block;font-family:inherit;font-size:14px;font-weight:700;color:var(--field);cursor:pointer;
  list-style:none;padding:3px 10px;border:1px solid var(--line);border-radius:999px;margin:2px 0 0}
details.more>summary::-webkit-details-marker{display:none}
details.more>summary::after{content:" ▾"}
details.more[open]>summary::after{content:" ▴"}
details.more[open]>summary{margin-bottom:8px}
.morebody{border-left:3px solid var(--line);padding-left:10px;margin-top:4px}
details.full>summary{margin-top:8px}
details.src{background:none;border:0;padding:0;margin:6px 0 0}
details.src>summary{font-family:inherit;font-size:13px;font-weight:400;color:var(--muted);list-style:none;cursor:pointer}
details.src>summary::-webkit-details-marker{display:none}
details.src>summary::after{content:" ▾"}
details.src p{font-size:13px}
/* cards and bet cards */
.lbc{border-radius:10px;padding:14px 16px}
.lbc .gl{font-family:inherit;font-size:14px;line-height:1.4;background:var(--paper);border-radius:6px;padding:8px 10px;margin:8px 0}
.lbc .gl .ln{margin:0 0 2px}
.lbc p{font-size:16px;line-height:1.5}
.lbc .pill{font-size:15px;padding:1px 8px;margin-bottom:4px}
.bet{border-radius:10px;padding:14px 16px}
.bet p{margin:0 0 10px}
.record .ln{margin:0}
.tile{border-radius:10px}
.tile .s .ln{margin:0 0 2px}
.card{border-radius:10px}
div.para{margin:0 0 14px;max-width:62ch}
/* tables wrap instead of running off the screen */
th,td{white-space:normal;vertical-align:top}
table{font-size:14px;min-width:620px}
@media (max-width:700px){
  table.stack{min-width:0;background:none;font-size:15px}
  table.stack thead{display:none}
  table.stack,table.stack tbody,table.stack tr,table.stack td{display:block;width:100%}
  table.stack tr{background:var(--card);border:1px solid var(--line);border-radius:8px;margin:0 0 10px;padding:8px 12px}
  table.stack td{border:0;padding:3px 0;text-align:left!important}
  table.stack td[data-label]:not([data-label=""])::before{content:attr(data-label);display:block;font-size:12px;color:var(--muted);
    font-weight:700;margin-top:4px}
  table.stack td:first-child{font-weight:700}
  table.stack td:first-child::before{display:none!important}
  table.stack td:empty{display:none}
}
'''
soup.head.append(style)
js = soup.new_tag('script', attrs={'id': 'tidy-js'})
js.string = r'''
(function(){
  function openTo(id){ if(!id) return; var el=document.getElementById(id); if(!el) return;
    for(var p=el; p; p=p.parentElement){ if(p.tagName==='DETAILS') p.open=true; }
    if(el.tagName==='DETAILS') el.open=true; }
  window.addEventListener('hashchange', function(){ openTo(location.hash.slice(1)); });
  document.addEventListener('click', function(e){ var a=e.target.closest && e.target.closest('a[href^="#"]');
    if(a) openTo(a.getAttribute('href').slice(1)); });
  if(location.hash) openTo(location.hash.slice(1));
})();
'''
soup.body.append(js)

out = str(soup)
open(OUT, 'w', encoding='utf-8').write(out)
print('tidied', SRC, '->', OUT, len(raw), '->', len(out))
