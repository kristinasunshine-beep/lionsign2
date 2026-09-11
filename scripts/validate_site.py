#!/usr/bin/env python3
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image
import json,re,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
ERRORS=[]
def ok(c,m):
    if not c: ERRORS.append(m)
def text(rel): return (ROOT/rel).read_text(encoding='utf-8')

PUBLIC=[
 ('index.html','https://www.lionsignstudio.com/'),
 ('doberman-branding.html','https://www.lionsignstudio.com/doberman-branding.html'),
 ('digital-design.html','https://www.lionsignstudio.com/digital-design.html'),
 ('landscape-design.html','https://www.lionsignstudio.com/landscape-design.html'),
 ('obsidian-line.html','https://www.lionsignstudio.com/obsidian-line.html'),
 ('answers.html','https://www.lionsignstudio.com/answers.html'),
 ('insights/doberman-kennel-branding/index.html','https://www.lionsignstudio.com/insights/doberman-kennel-branding/'),
 ('insights/identity-systems/index.html','https://www.lionsignstudio.com/insights/identity-systems/'),
 ('insights/landscape-design-belgrade/index.html','https://www.lionsignstudio.com/insights/landscape-design-belgrade/'),
 ('insights/digital-brand-direction/index.html','https://www.lionsignstudio.com/insights/digital-brand-direction/'),
]

ok((ROOT/'CNAME').exists() and text('CNAME').strip()=='www.lionsignstudio.com','CNAME must be www.lionsignstudio.com')
for rel in [p for p,_ in PUBLIC]+['privacy.html','404.html','robots.txt','sitemap.xml','manifest.json','llms.txt','humans.txt','.nojekyll']:
    ok((ROOT/rel).exists(),f'missing required file: {rel}')
ok(not (ROOT/'sw.js').exists(),'stale sw.js must not be public')
ok(not (ROOT/'assets/manifest.json').exists(),'stale assets/manifest.json must not be public')

og=ROOT/'assets/lionsign-og-image-identity-20260907-final.png'
ok(og.exists(),'final OG image missing')
if og.exists():
    with Image.open(og) as im: ok(im.size==(1200,630),f'OG must be 1200x630, got {im.size}')

# Background contract: light public pages use a cool near-white #fbfaff. Obsidian remains intentionally dark.
for rel in ['index.html','doberman-branding.html','digital-design.html','landscape-design.html','answers.html','privacy.html','404.html',
            'insights/doberman-kennel-branding/index.html','insights/identity-systems/index.html','insights/landscape-design-belgrade/index.html','insights/digital-brand-direction/index.html']:
    s=text(rel).lower(); ok('#fbfaff' in s,f'{rel}: cool near-white background token missing')

index=text('index.html')
for token in ["content: 'D' !important", "content: 'L' !important", "content: 'O' !important", '#services .svc-card:nth-child(4) .svc-num', '--focus-card-bg: #111111 !important', 'color: #ffffff !important']:
    ok(token in index,f'portal contract missing: {token}')
ok('DB, DG, LS and OL' not in index and 'DB, DD, LS and OL' not in index,'FAQ must not mention obsolete double-letter card labels')
ok('novalidate' not in index,'contact form must use native HTML validation')
for token in ['emailInput.checkValidity()', "Please select a service.", 'method="post"', 'target="_blank"', 'ml-submit', 'anticsrf']:
    ok(token in index,f'contact reliability contract missing: {token}')
ok("mode: 'no-cors'" not in index and 'AbortController' not in index,'opaque no-cors contact submission must not return')

for rel,_ in PUBLIC:
    s=text(rel)
    ok('animateCursor' not in s,f'custom cursor runtime must be removed from {rel}')

for rel in ['app.html','blog-doberman.html','privacy.html','404.html']:
    s=text(rel).lower(); ok('noindex' in s,f'{rel} must be noindex')

# JSON-LD validity and local refs for all HTML, including knowledge pages.
for p in ROOT.rglob('*.html'):
    if '/.git/' in p.as_posix(): continue
    s=p.read_text(encoding='utf-8')
    for n,block in enumerate(re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',s,re.I|re.S),1):
        try: json.loads(block)
        except Exception as e: ERRORS.append(f'{p.relative_to(ROOT)}: invalid JSON-LD block {n}: {e}')
    for ref in re.findall(r'\b(?:href|src)=["\']([^"\']+)["\']',s,re.I):
        if ref.startswith(('#','mailto:','tel:','data:','http://','https://','//')): continue
        path=ref.split('#',1)[0].split('?',1)[0]
        if not path: continue
        target=(ROOT/path.lstrip('/')) if path.startswith('/') else (p.parent/path)
        if target.is_dir(): target=target/'index.html'
        ok(target.exists(),f'{p.relative_to(ROOT)}: broken local reference {ref}')

ns={'sm':'http://www.sitemaps.org/schemas/sitemap/0.9'}
urls=[e.text for e in ET.parse(ROOT/'sitemap.xml').getroot().findall('sm:url/sm:loc',ns)]
expected=[u for _,u in PUBLIC]
ok(urls==expected,f'sitemap URL contract mismatch: {urls}')
for rel,url in PUBLIC:
    s=text(rel); m=re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)',s,re.I)
    ok(bool(m) and m.group(1)==url,f'{rel}: canonical mismatch')

if ERRORS:
    print('LIONSIGN QA FAIL')
    for e in ERRORS: print(' -',e)
    sys.exit(1)
print('LIONSIGN QA PASS')
print('10 canonical pages; cool near-white background; reliable MailerLite POST; local references valid.')
