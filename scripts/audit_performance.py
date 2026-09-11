#!/usr/bin/env python3
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse
import sys
ROOT=Path(__file__).resolve().parents[1]
PAGES=['index.html','doberman-branding.html','digital-design.html','landscape-design.html','obsidian-line.html','answers.html']
MAX_SINGLE=1_600_000
MAX_PAGE_TOTAL=8_000_000
errors=[]
class P(HTMLParser):
 def __init__(self):super().__init__();self.src=[]
 def handle_starttag(self,t,a):
  if t=='img':
   d=dict(a);v=d.get('src')
   if v:self.src.append(v)
for rel in PAGES:
 p=P();p.feed((ROOT/rel).read_text(encoding='utf-8'));unique=[]
 for src in p.src:
  if src.startswith(('http://','https://','data:')):continue
  clean=src.split('?',1)[0].split('#',1)[0]
  if clean not in unique:unique.append(clean)
 total=0
 for src in unique:
  fp=ROOT/src
  if not fp.exists():continue
  size=fp.stat().st_size;total+=size
  if size>MAX_SINGLE:errors.append(f'{rel}: referenced image exceeds 1.6 MB: {src} ({size} bytes)')
 if total>MAX_PAGE_TOTAL:errors.append(f'{rel}: unique referenced image payload exceeds 8 MB ({total} bytes)')
if errors:
 print('LIONSIGN performance budget FAIL',file=sys.stderr)
 for e in errors:print(' -',e,file=sys.stderr)
 raise SystemExit(1)
print('LIONSIGN performance budget PASS')
