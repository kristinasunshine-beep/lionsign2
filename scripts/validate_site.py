#!/usr/bin/env python3
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse
from PIL import Image
import json, re, sys, xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
ERRORS=[]
def ok(c,m):
    if not c: ERRORS.append(m)

def text(rel): return (ROOT/rel).read_text(encoding='utf-8')

ok((ROOT/'CNAME').exists() and text('CNAME').strip()=='www.lionsignstudio.com','CNAME must be www.lionsignstudio.com')
for rel in ['index.html','doberman-branding.html','digital-design.html','landscape-design.html','obsidian-line.html','answers.html','privacy.html','404.html','robots.txt','sitemap.xml','manifest.json','llms.txt','humans.txt','.nojekyll']:
    ok((ROOT/rel).exists(),f'missing required file: {rel}')
ok(not (ROOT/'sw.js').exists(),'stale sw.js must not be public')
ok(not (ROOT/'assets/manifest.json').exists(),'stale assets/manifest.json must not be public')

expected_og='assets/lionsign-og-image-identity-20260907-final.png'
og=ROOT/expected_og
ok(og.exists(),'final OG image missing')
if og.exists():
    with Image.open(og) as im: ok(im.size==(1200,630),f'OG must be 1200x630, got {im.size}')

index=text('index.html')
for token in ["content: 'D' !important", "content: 'L' !important", "content: 'O' !important", '#services .svc-card:nth-child(4) .svc-num', 'background: #111111 !important', 'color: #ffffff !important']:
    ok(token in index,f'portal contract missing: {token}')
ok('DB, DG, LS and OL' not in index and 'DB, DD, LS and OL' not in index,'FAQ must not mention obsolete double-letter card labels')
ok('novalidate' not in index,'contact form must use native HTML validation')
for token in ['emailInput.checkValidity()', "Please select a service.", 'AbortController', 'form-error']:
    ok(token in index,f'contact hardening missing: {token}')
ok('animateCursor' not in index,'custom cursor runtime must be removed from portal')

for rel in ['doberman-branding.html','digital-design.html','landscape-design.html','obsidian-line.html','answers.html']:
    s=text(rel)
    ok('animateCursor' not in s,f'custom cursor runtime must be removed from {rel}')

for rel in ['app.html','blog-doberman.html','privacy.html','404.html']:
    s=text(rel).lower()
    ok('noindex' in s,f'{rel} must be noindex')

# Validate JSON-LD blocks.
for p in ROOT.glob('*.html'):
    s=p.read_text(encoding='utf-8')
    for n,block in enumerate(re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',s,re.I|re.S),1):
        try: json.loads(block)
        except Exception as e: ERRORS.append(f'{p.name}: invalid JSON-LD block {n}: {e}')

# Validate local href/src refs.
attr_re=re.compile(r'\b(?:href|src)=["\']([^"\']+)["\']',re.I)
for p in ROOT.glob('*.html'):
    s=p.read_text(encoding='utf-8')
    for ref in attr_re.findall(s):
        if ref.startswith(('#','mailto:','tel:','data:','http://','https://','//')): continue
        path=ref.split('#',1)[0].split('?',1)[0]
        if not path: continue
        if path=='/': target=ROOT/'index.html'
        elif path.startswith('/'): target=ROOT/path.lstrip('/')
        else: target=p.parent/path
        ok(target.exists(),f'{p.name}: broken local reference {ref}')

# Sitemap/canonical contract.
ns={'sm':'http://www.sitemaps.org/schemas/sitemap/0.9'}
tree=ET.parse(ROOT/'sitemap.xml')
urls=[e.text for e in tree.getroot().findall('sm:url/sm:loc',ns)]
expected=['https://www.lionsignstudio.com/','https://www.lionsignstudio.com/doberman-branding.html','https://www.lionsignstudio.com/digital-design.html','https://www.lionsignstudio.com/landscape-design.html','https://www.lionsignstudio.com/obsidian-line.html','https://www.lionsignstudio.com/answers.html']
ok(urls==expected,f'sitemap URL contract mismatch: {urls}')
for rel,url in zip(['index.html','doberman-branding.html','digital-design.html','landscape-design.html','obsidian-line.html','answers.html'],expected):
    s=text(rel)
    m=re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)',s,re.I)
    ok(bool(m) and m.group(1)==url,f'{rel}: canonical mismatch')
    ok(expected_og in s,f'{rel}: final OG reference missing')

if ERRORS:
    print('LIONSIGN QA FAIL')
    for e in ERRORS: print(' -',e)
    sys.exit(1)
print('LIONSIGN QA PASS')
print('6 canonical indexable pages; OG 1200x630; native cursor; hardened contact form; local references valid.')
