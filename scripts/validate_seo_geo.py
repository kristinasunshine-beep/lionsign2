#!/usr/bin/env python3
from pathlib import Path
from html.parser import HTMLParser
from xml.etree import ElementTree as ET
import json,re,sys
ROOT=Path(__file__).resolve().parents[1]
ORIGIN='https://www.lionsignstudio.com/'
PAGES=['index.html','answers.html','digital-design.html','doberman-branding.html','landscape-design.html','obsidian-line.html']
errors=[]
class P(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.meta={};self.can=[];self.h1=0;self.main=0;self.json=[];self._j=False;self._buf=[];self.images=[];self.icons=[]
 def handle_starttag(self,t,a):
  d=dict(a)
  if t=='meta':
   k=d.get('name') or d.get('property')
   if k:self.meta.setdefault(k,[]).append(d.get('content',''))
  if t=='link' and d.get('rel')=='canonical':self.can.append(d.get('href',''))
  if t=='link' and d.get('rel') in {'icon','apple-touch-icon'}:self.icons.append((d.get('rel'),d.get('sizes'),d.get('href')))
  if t=='h1':self.h1+=1
  if t=='main':self.main+=1
  if t=='img':self.images.append(d)
  if t=='script' and d.get('type')=='application/ld+json':self._j=True;self._buf=[]
 def handle_data(self,d):
  if self._j:self._buf.append(d)
 def handle_endtag(self,t):
  if t=='script' and self._j:self._j=False;self.json.append(''.join(self._buf))
def parse(path):p=P();p.feed(path.read_text(encoding='utf-8'));return p
for f in PAGES:
 p=parse(ROOT/f)
 if p.h1!=1:errors.append(f'{f}: exactly one H1 required')
 if p.main!=1:errors.append(f'{f}: exactly one main required')
 if len(p.can)!=1 or not p.can[0].startswith(ORIGIN):errors.append(f'{f}: one canonical required')
 if p.meta.get('robots')!=['index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1']:errors.append(f'{f}: public robots contract mismatch')
 for im in p.images:
  if 'alt' not in im:errors.append(f'{f}: image missing alt')
 if len(p.json)!=1:errors.append(f'{f}: exactly one JSON-LD graph required');continue
 try:data=json.loads(p.json[0])
 except Exception as e:errors.append(f'{f}: invalid JSON-LD {e}');continue
 graph=data.get('@graph',[]);types=[n.get('@type') for n in graph if isinstance(n,dict)]
 for need in ('Organization','Person','WebSite','WebPage'):
  if need not in types:errors.append(f'{f}: missing {need} entity')
 org=next((n for n in graph if n.get('@id')==ORIGIN+'#organization'),{})
 if org.get('foundingDate')!='2019' or org.get('founder',{}).get('@id')!=ORIGIN+'#founder':errors.append(f'{f}: organization identity incomplete')
 if f=='index.html':
  wp=next((n for n in graph if n.get('@type')=='WebPage'),{})
  if wp.get('@id')!=ORIGIN+'#webpage':errors.append('index.html: webpage @id not normalized')
 if f=='landscape-design.html':
  svc=next((n for n in graph if n.get('@type')=='Service'),{})
  if 'Worldwide' in str(svc.get('areaServed')):errors.append('landscape-design.html: worldwide areaServed contradicts page scope')
 if f=='obsidian-line.html':
  prod=next((n for n in graph if n.get('@type')=='Product'),{})
  if prod.get('offers',{}).get('seller',{}).get('@id')!=ORIGIN+'#organization':errors.append('obsidian-line.html: product seller missing')
for f in ['app.html','blog-doberman.html','privacy.html','404.html']:
 p=parse(ROOT/f)
 if not p.meta.get('robots') or 'noindex' not in p.meta['robots'][0]:errors.append(f'{f}: utility page must be noindex')
ns={'sm':'http://www.sitemaps.org/schemas/sitemap/0.9'}
locs=[n.text for n in ET.parse(ROOT/'sitemap.xml').findall('sm:url/sm:loc',ns)]
expected=[ORIGIN,ORIGIN+'doberman-branding.html',ORIGIN+'digital-design.html',ORIGIN+'landscape-design.html',ORIGIN+'obsidian-line.html',ORIGIN+'answers.html']
if set(locs)!=set(expected):errors.append('sitemap canonical page set mismatch')
if errors:
 print('LIONSIGN SEO/GEO validation FAIL',file=sys.stderr)
 for e in errors:print(' -',e,file=sys.stderr)
 raise SystemExit(1)
print('LIONSIGN SEO/GEO validation PASS (6 canonical pages)')
