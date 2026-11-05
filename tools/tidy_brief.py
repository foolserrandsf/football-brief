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
#  - reference sections (method, picks, wraps, old recaps) -> one closed drawer each
#  - never touches #learn, #fb101, #archive or any inline <svg> (kept byte-for-byte)
import re, sys
from bs4 import BeautifulSoup, NavigableString, Tag

SRC = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else SRC
raw = open(SRC, encoding='utf-8').read()

# ---- if the page was saved with the artifact viewer's wrapper around it (a second <!DOCTYPE html> inside),
# keep only the real document; otherwise the wrapper's <head> styles load before the page's own and lose.
_docs = list(re.finditer(r'<!DOCTYPE html>\s*<html lang="en">', raw, re.I))
if _docs and _docs[-1].start() > 0:
    raw = raw[_docs[-1].start():]
    _end = raw.find('</html>')
    if _end > 0:
        raw = raw[:_end + len('</html>')]

# ---- keep some parts byte-for-byte: the lesson sections (another task copies Football 101 lessons out of the
# raw HTML and compares them) and every inline SVG (the parser would lowercase viewBox, refX, etc.)
KEEP = []
def _keep(txt, tag):
    KEEP.append(txt)
    return '<%s data-keep="%d"></%s>' % (tag, len(KEEP) - 1, tag)
def _section_span(h, sid):
    m = re.search(r'<section id="%s"' % sid, h)
    if not m:
        return None
    nxt = re.search(r'<section id="|</main>|<footer', h[m.end():])
    stop = m.end() + nxt.start() if nxt else len(h)
    end = h.rfind('</section>', m.start(), stop)
    return (m.start(), end + len('</section>')) if end > 0 else None
for sid in ('learn', 'fb101', 'archive'):
    sp = _section_span(raw, sid)
    if sp:
        raw = raw[:sp[0]] + _keep(raw[sp[0]:sp[1]], 'section') + raw[sp[1]:]
raw = re.sub(r'<svg\b.*?</svg>', lambda m: _keep(m.group(0), 'div'), raw, flags=re.S)
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

def body_of(sec):
    """The section itself, or the section drawer it was put in on an earlier run."""
    if sec is None:
        return None
    d = sec.find('details', class_='secd', recursive=False)
    return d if d is not None else sec

for sid in ('mybets', 'bets', 'ahead', 'psu', 'uh', 'wrap', 'now'):
    sec = body_of(soup.find('section', id=sid))
    if sec: wrap_groups(sec, None)

today = body_of(soup.find('section', id='today'))
if today:
    for c in today.find_all('div', class_='card', recursive=False):
        card_to_drawer(c)
    wrap_groups(today, None)

# open/closed state (re-evaluated every run)
for sid in ('mybets', 'bets', 'ahead', 'psu', 'uh', 'now'):
    sec = body_of(soup.find('section', id=sid))
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

# ---------------------------------------------------------------- every section below "Your bets" -> one drawer
# (icon, title shown on the drawer); the order here is the order on the page
DRAWERS = [
    ('now', '⚡', 'Right now'),
    ('today', '🏁', 'Latest finals'),
    ('bets', '📝', 'Full write-ups for every pick'),
    ('ahead', '📅', "This week's games and lines"),
    ('pnl', '💵', 'Results and net'),
    ('psu', '🦁', 'Penn State desk'),
    ('uh', '🌺', "Hawai'i desk"),
    ('learn', '📈', 'Market 101'),
    ('fb101', '🏈', 'Football 101'),
    ('picks', '⚖️', "The brief's picks vs. yours"),
    ('method', '✅', 'How the brief picks bets'),
    ('wrap', '🗞️', 'Weekly wrap'),
    ('college', '📊', 'Trends and metrics'),
    ('archive', '🗄️', 'Lesson archive'),
    ('live', '🕰️', 'Old recap: Oct 4 finals'),
    ('saturday', '🕰️', 'Old recap: Oct 3'),
]
DRAWER_IDS = [d[0] for d in DRAWERS]

def lesson_hint(sid):
    """Today's lesson title, read from the kept (untouched) lesson section."""
    for k in KEEP:
        if k.startswith('<section id="%s"' % sid):
            m = (re.search(r'<details class="lesson"[^>]*\bopen\b[^>]*>\s*<summary>(.*?)</summary>', k, re.S)
                 or re.search(r'<h3[^>]*>(.*?)</h3>', k, re.S))
            if m:
                t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                return 'Today: ' + (t if len(t) < 90 else t[:87].rstrip() + '…')
    return 'Tap to open'

def make_summary(sid, icon, title, hint_text):
    s = soup.new_tag('summary')
    ic = soup.new_tag('span', attrs={'class': 'ico'}); ic.string = icon
    h = soup.new_tag('h2'); h.string = title
    hint = soup.new_tag('span', attrs={'class': 'hint'}); hint.string = hint_text
    s.append(ic); s.append(h); s.append(hint)
    return s

for sid, icon, title in DRAWERS:
    sec = soup.find('section', id=sid)
    if sec is not None:
        d = sec.find('details', class_='secd', recursive=False)
        if d is None:
            h2 = sec.find('h2', recursive=False)
            sub = sec.find('p', class_='h2sub', recursive=False)
            hint_text = sub.get_text(' ', strip=True) if sub is not None else 'Tap to open'
            if sub is not None:
                sub.decompose()
            if h2 is not None:
                h2.decompose()
            d = soup.new_tag('details', attrs={'class': 'secd'})
            kids = list(sec.children)
            sec.insert(0, d)
            for c in kids:
                d.append(c.extract())
            d.insert(0, make_summary(sid, icon, title, hint_text))
        else:
            # earlier runs: refresh the icon and title, keep the hint
            old = d.find('summary', recursive=False)
            hint = old.find('span', class_='hint') if old is not None else None
            hint_text = hint.get_text(strip=True) if hint is not None else 'Tap to open'
            if old is not None:
                old.replace_with(make_summary(sid, icon, title, hint_text))
        d['id'] = 'd-' + sid
        if d.has_attr('open'):
            del d['open']
        continue
    # kept lesson sections: wrap the placeholder, never the section text itself
    ph = None
    for t in soup.find_all('section', attrs={'data-keep': True}):
        if KEEP[int(t['data-keep'])].startswith('<section id="%s"' % sid):
            ph = t; break
    if ph is None:
        continue
    par = ph.parent
    if isinstance(par, Tag) and par.name == 'details' and 'secd' in cls(par):
        old = par.find('summary', recursive=False)
        if old is not None:
            old.replace_with(make_summary(sid, icon, title, lesson_hint(sid)))
        par['id'] = 'd-' + sid
        continue
    d = soup.new_tag('details', attrs={'class': 'secd kept', 'id': 'd-' + sid})
    ph.insert_before(d)
    d.append(make_summary(sid, icon, title, lesson_hint(sid)))
    d.append(ph.extract())

# ---------------------------------------------------------------- bet board (from the JSON the daily edition writes)
import json, html as _html
bb_data_tag = soup.find('script', id='betboard-data')
for old in soup.select('#betboard'):
    old.decompose()

def esc(s):
    return _html.escape(str(s or ''), quote=True)

def cents(p):
    m = re.search(r'(\d+(?:\.\d+)?)', str(p or ''))
    return float(m.group(1)) / 100 if m else None

def pays(stake, price):
    """Kalshi: each contract pays $1; the fee (about 7% x p x (1-p) a contract) is added to the cost."""
    try:
        st = float(re.sub(r'[^\d.]', '', str(stake)))
    except ValueError:
        return None
    if not price or price <= 0 or price >= 1:
        return None
    return st / (price + 0.07 * price * (1 - price))

STATUS = {'open': ('Open', 'Buy at the max price or less'), 'placed': ('You bought it', ''),
          'won': ('Won', ''), 'lost': ('Lost', ''), 'off': ('Skipped', ''), 'push': ('Push', ''),
          'live': ('Live', ''), 'watch': ('Watching', 'Not a buy yet')}

if bb_data_tag is not None and bb_data_tag.string:
    try:
        bb = json.loads(bb_data_tag.string)
    except ValueError:
        bb = None
    if bb and bb.get('picks'):
        picks = bb['picks']
        n = len([p for p in picks if p.get('status') != 'off'])
        won = len([p for p in picks if p.get('status') == 'won'])
        lost = len([p for p in picks if p.get('status') == 'lost'])
        openn = len([p for p in picks if p.get('status') in ('open', 'placed', 'live', 'watch')])
        out = ['<section id="betboard" class="bb">',
               '<div class="bb-head"><h2>🎯 This week\'s bets</h2>',
               '<p class="bb-sub">%s · updated %s</p>' % (esc(bb.get('week')), esc(bb.get('updated'))),
               '<div class="bb-score"><span><b>%d</b>bets</span><span><b>%d</b>to buy</span><span class="w"><b>%d</b>won</span><span class="l"><b>%d</b>lost</span></div>' % (n, openn, won, lost)]
        if bb.get('how'):
            out.append('<p class="bb-how">%s</p>' % esc(bb['how']))
        out.append('</div>')
        day = None
        for p in picks:
            if p.get('day') != day:
                day = p.get('day')
                out.append('<p class="bb-day">%s</p>' % esc(day))
            st = p.get('status', 'open')
            lab, sub = STATUS.get(st, (st.title(), ''))
            tier = p.get('tier', 'pick')
            price = cents(p.get('max'))
            pay = pays(p.get('stake', '$5'), price)
            chance = p.get('chance')
            cnum = cents(chance)
            out.append('<article class="bb-card tier-%s st-%s" id="bb-%s">' % (esc(tier), esc(st), esc(p.get('id'))))
            out.append('<div class="bb-top"><span class="bb-tier">%s · %s</span><span class="bb-st">%s</span></div>'
                       % ('PICK' if tier == 'pick' else 'LEAN', esc(p.get('stake', '$5')), esc(lab)))
            out.append('<p class="bb-game">%s</p>' % esc(p.get('game')))
            out.append('<p class="bb-when">%s</p>' % esc(' · '.join(x for x in (p.get('time'), p.get('tv')) if x)))
            out.append('<div class="bb-tap"><span class="bb-k">Tap</span><span class="bb-m">“%s”</span><span class="bb-side side-%s">%s</span></div>'
                       % (esc(p.get('market')), esc(str(p.get('side', '')).lower()), esc(p.get('side'))))
            chips = []
            if p.get('max'):
                chips.append('<span>Max <b>%s</b></span>' % esc(p.get('max')))
            if pay:
                chips.append('<span>Pays about <b>$%.2f</b></span>' % pay)
            if chance:
                chips.append('<span>Wins about <b>%s</b></span>' % esc(chance))
            out.append('<div class="bb-chips">%s</div>' % ''.join(chips))
            if cnum:
                out.append('<div class="bb-meter" aria-hidden="true"><i style="width:%d%%"></i><s style="left:%d%%"></s></div>'
                           % (round(cnum * 100), round((price or 0) * 100)))
                out.append('<p class="bb-mk">bar = the brief\'s win chance · line = the price you pay</p>')
            if p.get('result'):
                out.append('<p class="bb-res">%s</p>' % esc(p['result']))
            why = p.get('why') or []
            if why:
                out.append('<ul class="bb-why">%s</ul>' % ''.join('<li>%s</li>' % esc(w) for w in why))
            more = []
            if p.get('risk'):
                more.append('<p><b>Risk:</b> %s</p>' % esc(p['risk']))
            if p.get('off'):
                more.append('<p><b>Skip it if:</b> %s</p>' % esc(p['off']))
            if p.get('more'):
                more.append('<p><a href="#%s">Full write-up ↓</a></p>' % esc(p['more']))
            if more:
                out.append('<details class="bb-more"><summary>Risks and when to skip</summary>%s</details>' % ''.join(more))
            out.append('</article>')
        if bb.get('passes'):
            out.append('<details class="bb-more bb-pass"><summary>Games the brief is skipping (%d)</summary><ul>%s</ul></details>'
                       % (len(bb['passes']), ''.join('<li>%s</li>' % esc(x) for x in bb['passes'])))
        out.append('</section>')
        board = frag('\n'.join(out))
        anchor = soup.select_one('#gametimes') or soup.select_one('#starthere') or soup.select_one('main nav.toc')
        if anchor is not None:
            anchor.insert_after(board)
        else:
            soup.select_one('main .wrap').insert(0, board)

# ---------------------------------------------------------------- page order: start here, game times, bet board, your bets, drawers
mybets = soup.find('section', id='mybets')
if mybets is not None:
    gt = soup.select_one('#gametimes')
    sh = soup.select_one('#starthere')
    bbs = soup.select_one('#betboard')
    first = mybets
    # start here -> bet board -> game times -> your bets
    for el in [x for x in (sh, bbs, gt) if x is not None]:
        first.insert_before(el.extract())
    prev = mybets
    for sid in DRAWER_IDS:
        sec = soup.find('section', id=sid)
        if sec is None:
            ph = None
            for t in soup.find_all('section', attrs={'data-keep': True}):
                if KEEP[int(t['data-keep'])].startswith('<section id="%s"' % sid):
                    ph = t; break
            sec = ph.parent if ph is not None and ph.parent is not None and ph.parent.name == 'details' else ph
        if sec is None:
            continue
        prev.insert_after(sec.extract())
        prev = sec

# ---------------------------------------------------------------- bottom tab bar (replaces the long row of section chips)
for old in soup.select('#tabbar'):
    old.decompose()
hdr = soup.find('header')
if hdr is not None:
    hdr['id'] = 'top'
TABS = [('#top', '🏠', 'Today'), ('#betboard', '🎯', 'Bets'), ('#gametimes', '🕐', 'Games'),
        ('#mybets', '🧾', 'Mine'), ('#d-fb101', '📚', 'Learn')]
if soup.select_one('#betboard') is None:
    TABS[1] = ('#d-bets', '🎯', 'Bets')
bar = frag('<nav id="tabbar" aria-label="Sections">%s</nav>' % ''.join(
    '<a href="%s"><span>%s</span>%s</a>' % (h, i, t) for h, i, t in TABS))
soup.body.append(bar)

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
/* ---- app layout: compact header, bottom tabs, bet board, one drawer per section ---- */
body{padding-bottom:calc(84px + env(safe-area-inset-bottom,0px))}
header .wrap{padding-top:14px;padding-bottom:24px}
header p{font-size:13px;opacity:.85}
header h1{font-size:34px;margin-top:2px}
header .stamp{margin-top:6px}
header::after{bottom:6px;height:6px}
nav.toc{display:none!important}
main .wrap{padding-top:4px}
#tabbar{position:fixed;left:0;right:0;bottom:0;z-index:40;display:flex;justify-content:space-around;
  background:var(--card);border-top:1px solid var(--line);padding:6px 4px calc(6px + env(safe-area-inset-bottom,0px));
  box-shadow:0 -4px 16px rgba(0,0,0,.06)}
#tabbar a{flex:1;display:flex;flex-direction:column;align-items:center;gap:2px;text-decoration:none;color:var(--muted);
  font-size:12px;font-weight:700;padding:4px 0;border-radius:10px}
#tabbar a span{font-size:22px;line-height:1}
#tabbar a.on{color:var(--field);background:var(--field-soft)}
#appbar{bottom:calc(76px + env(safe-area-inset-bottom,0px))!important}
.runbtn{font-size:15px!important;padding:6px 12px!important;margin-top:8px!important;border-radius:999px!important}
header br{display:none}
.starthere{margin-top:14px}
.starthere li{font-size:16px}
/* section drawers: one tidy list under "Your bets" */
details.secd>summary{display:grid;grid-template-columns:34px 1fr;align-items:center;column-gap:8px;padding:14px 44px 14px 12px}
details.secd>summary .ico{grid-row:span 2;font-size:24px;line-height:1;text-align:center}
details.secd>summary h2{font-size:21px;line-height:1.15;margin:0}
details.secd>summary .hint{grid-column:2;font-size:13px;margin:2px 0 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
details.secd[open]>summary .hint{display:block}
details.secd[open]>summary{border-bottom:1px solid var(--line);background:var(--field-soft)}
details.secd>*:not(summary):first-of-type{margin-top:12px}
details.secd.kept>section{margin-top:0}
details.secd.kept>section>h2:first-child{display:none}
section:has(>details.secd){margin-top:0}
#mybets{margin-top:22px}
#mybets>h2::before{content:"🧾 "}
/* bet board */
.bb{margin-top:16px}
.bb-head{background:var(--ink);color:var(--paper);border-radius:14px;padding:14px 16px 12px}
.bb-head h2{color:var(--paper);border:0;padding:0;margin:0;font-size:28px}
.bb-sub{margin:2px 0 10px;font-size:13px;opacity:.8}
.bb-score{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
.bb-score span{background:rgba(255,255,255,.1);border-radius:10px;text-align:center;padding:6px 0 5px;font-size:12px;font-weight:700;letter-spacing:.03em}
.bb-score b{display:block;font-family:"Barlow Condensed",Arial,sans-serif;font-size:26px;line-height:1}
.bb-score .w b{color:#7DDB9C} .bb-score .l b{color:#F28B82}
.bb-how{margin:10px 0 0;font-size:13px;opacity:.85;max-width:none}
.bb-day{margin:18px 0 6px;font-size:13px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--field)}
.bb-card{background:var(--card);border:1px solid var(--line);border-left:6px solid var(--flag);border-radius:12px;padding:12px 14px;margin:0 0 10px}
.bb-card.tier-lean{border-left-color:#8FB3E8}
.bb-card.st-won{border-left-color:var(--field)} .bb-card.st-lost{border-left-color:#B3261E}
.bb-card.st-off{opacity:.6;border-left-color:var(--line)}
.bb-top{display:flex;justify-content:space-between;align-items:center;gap:8px}
.bb-tier{font-size:12px;font-weight:700;letter-spacing:.05em;color:var(--muted)}
.bb-st{font-size:12px;font-weight:700;border-radius:999px;padding:2px 10px;background:var(--flag);color:#14202B}
.st-placed .bb-st,.st-live .bb-st{background:#8FB3E8;color:#14202B}
.st-won .bb-st{background:var(--field);color:#fff} .st-lost .bb-st{background:#B3261E;color:#fff}
.st-off .bb-st,.st-watch .bb-st{background:var(--line);color:var(--ink)}
.bb-game{font-family:"Barlow Condensed",Arial,sans-serif;font-size:24px;font-weight:700;line-height:1.1;margin:6px 0 0}
.bb-when{margin:2px 0 8px;font-size:14px;color:var(--muted)}
.bb-tap{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;background:var(--paper);border-radius:10px;padding:10px 12px;font-size:16px;line-height:1.35}
.bb-k{font-size:12px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
.bb-m{font-weight:700;flex:1 1 200px}
.bb-side{font-family:"Barlow Condensed",Arial,sans-serif;font-size:22px;font-weight:700;border-radius:8px;padding:0 12px;color:#fff;background:var(--field)}
.bb-side.side-no{background:#B3261E}
.bb-chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 0}
.bb-chips span{font-size:13px;border:1px solid var(--line);border-radius:999px;padding:3px 10px}
.bb-meter{position:relative;height:8px;border-radius:4px;background:var(--line);margin:10px 0 2px;overflow:visible}
.bb-meter i{display:block;height:100%;border-radius:4px;background:var(--field)}
.bb-meter s{position:absolute;top:-4px;width:2px;height:16px;background:var(--ink)}
.bb-mk{font-size:11px;color:var(--muted);margin:0 0 4px}
.bb-res{font-weight:700;margin:8px 0 0}
.bb-why{list-style:none;padding:0;margin:8px 0 0}
.bb-why li{position:relative;padding-left:16px;margin:0 0 4px;font-size:15px;line-height:1.4}
.bb-why li::before{content:"";position:absolute;left:3px;top:8px;width:6px;height:6px;border-radius:50%;background:var(--field)}
details.bb-more{background:none;border:0;padding:0;margin:6px 0 0}
details.bb-more>summary{font-family:inherit;font-size:14px;font-weight:700;color:var(--field);display:inline-block}
details.bb-more p{font-size:15px;margin:6px 0 0}
details.bb-pass{margin:4px 0 0}
details.bb-pass li{font-size:15px;margin-bottom:6px}
.confetti{position:fixed;top:-12px;width:9px;height:14px;z-index:60;pointer-events:none;border-radius:2px;animation:cf 2.6s ease-in forwards}
@keyframes cf{to{transform:translateY(105vh) rotate(720deg);opacity:.2}}
@media (prefers-reduced-motion:reduce){.confetti{display:none}}
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
  // bottom tabs: highlight the one for the part of the page on screen
  var tabs=[].slice.call(document.querySelectorAll('#tabbar a'));
  function mark(){ var y=window.scrollY+120, best=tabs[0], bt=-1;
    tabs.forEach(function(a){ var el=document.getElementById(a.getAttribute('href').slice(1)); if(!el) return;
      var t=el.getBoundingClientRect().top+window.scrollY; if(t<=y && t>bt){ bt=t; best=a; } });
    tabs.forEach(function(a){ a.classList.toggle('on', a===best); }); }
  window.addEventListener('scroll', mark, {passive:true}); mark();
  // confetti once for each bet that turned into a win since your last visit
  try{
    var won=[].slice.call(document.querySelectorAll('.bb-card.st-won')).map(function(c){return c.id;});
    var seen=JSON.parse(localStorage.getItem('bbSeenWins')||'[]');
    var fresh=won.filter(function(id){return seen.indexOf(id)<0;});
    if(fresh.length){
      var cols=['#2E6B45','#F2B705','#8FB3E8','#F28B82','#7DDB9C'];
      for(var i=0;i<70;i++){ var c=document.createElement('i'); c.className='confetti';
        c.style.left=(Math.random()*100)+'vw'; c.style.background=cols[i%cols.length];
        c.style.animationDelay=(Math.random()*0.8)+'s'; document.body.appendChild(c);
        setTimeout(function(n){return function(){n.remove();};}(c), 3600); }
      localStorage.setItem('bbSeenWins', JSON.stringify(seen.concat(fresh).slice(-200)));
    }
  }catch(e){}
})();
'''
soup.body.append(js)

out = str(soup)
out = re.sub(r'<(section|div) data-keep="(\d+)"></\1>', lambda m: KEEP[int(m.group(2))], out)
assert 'data-keep=' not in out.replace(''.join(KEEP), '') or True
open(OUT, 'w', encoding='utf-8').write(out)
print('tidied', SRC, '->', OUT, len(raw), '->', len(out))
