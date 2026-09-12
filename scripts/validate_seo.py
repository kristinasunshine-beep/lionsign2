#!/usr/bin/env python3
"""Validate sitemap, canonical pages, metadata, structured data and crawl policy."""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from build_seo import relation_ids


ROOT=Path(__file__).resolve().parents[1]
ORIGIN="https://"+(ROOT/"CNAME").read_text(encoding="utf-8").strip()
ID_RE=re.compile(r"^DI-(M|F|K|L)-\d{6}$")
ALLOWED_TYPES={"WebSite","WebPage","AboutPage","CollectionPage","Thing","Organization","PropertyValue","BreadcrumbList","ListItem","ImageObject","ItemList","Dataset","DataCatalog","Place"}
FORBIDDEN_KEYS={"review","reviews","aggregaterating","ratingvalue","ratingcount","reviewcount"}
errors=[]


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title=[];self.in_title=False;self.in_jsonld=False;self.jsonld=[];self.current_json=[]
        self.meta={};self.canonicals=[];self.h1=0;self.main=0;self.images=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=="title":self.in_title=True
        if tag=="script" and values.get("type")=="application/ld+json":self.in_jsonld=True;self.current_json=[]
        if tag=="meta":
            key=values.get("name") or values.get("property")
            if key:self.meta.setdefault(key,[]).append(values.get("content",""))
        if tag=="link" and values.get("rel")=="canonical":self.canonicals.append(values.get("href",""))
        if tag=="h1":self.h1+=1
        if tag=="main":self.main+=1
        if tag=="img":self.images.append(values)
        if tag=="a" and values.get("href"):self.links.append(values["href"])
    def handle_endtag(self,tag):
        if tag=="title":self.in_title=False
        if tag=="script" and self.in_jsonld:
            self.in_jsonld=False;self.jsonld.append("".join(self.current_json).strip())
    def handle_data(self,data):
        if self.in_title:self.title.append(data)
        if self.in_jsonld:self.current_json.append(data)


def parse_page(path):
    parser=PageParser();parser.feed(path.read_text(encoding="utf-8"));return parser


def walk_json(value):
    if isinstance(value,dict):
        for key,item in value.items():
            yield key,item
            yield from walk_json(item)
    elif isinstance(value,list):
        for item in value:yield from walk_json(item)


def check_public_page(path,metadata,label):
    page=parse_page(path)
    title="".join(page.title).strip()
    if title!=metadata["title"]:errors.append(f"{label}: title mismatch")
    descriptions=page.meta.get("description",[])
    if descriptions!=[metadata["description"]]:errors.append(f"{label}: one exact meta description required")
    if page.canonicals!=[metadata["canonical"]]:errors.append(f"{label}: one exact canonical required")
    if page.meta.get("robots")!=["index,follow,max-image-preview:large"]:errors.append(f"{label}: public robots meta missing")
    for key,want in (("og:title",metadata["title"]),("og:description",metadata["description"]),("og:url",metadata["canonical"]),("twitter:title",metadata["title"]),("twitter:description",metadata["description"])):
        if page.meta.get(key)!=[want]:errors.append(f"{label}: {key} mismatch")
    if page.h1<1 or page.main!=1:errors.append(f"{label}: semantic main/H1 contract failed")
    for image in page.images:
        if "alt" not in image:errors.append(f"{label}: image missing alt attribute")
    if not page.jsonld:errors.append(f"{label}: JSON-LD missing")
    for block in page.jsonld:
        try:data=json.loads(block)
        except json.JSONDecodeError as exc:errors.append(f"{label}: invalid JSON-LD: {exc}");continue
        if data.get("@context")!="https://schema.org":errors.append(f"{label}: Schema.org context missing")
        for key,value in walk_json(data):
            if key.lower() in FORBIDDEN_KEYS:errors.append(f"{label}: unsupported rating/review claim: {key}")
            if key=="@type":
                types=value if isinstance(value,list) else [value]
                for item in types:
                    if item not in ALLOWED_TYPES:errors.append(f"{label}: unapproved JSON-LD type {item}")
    return page


registry=json.loads((ROOT/"data/registry.json").read_text(encoding="utf-8"))
manifest=json.loads((ROOT/"data/seo-manifest.json").read_text(encoding="utf-8"))
records=[item for item in registry.get("records",[]) if item.get("status")=="published"]
record_ids={item["record_id"] for item in records}
if set(manifest.get("records",{}))!=record_ids:errors.append("SEO manifest record set differs from published registry")
if manifest.get("generated_from_registry")!=registry.get("generated_at"):errors.append("SEO manifest is stale")

static_paths={"/":ROOT/"index.html","/about.html":ROOT/"about.html","/records/":ROOT/"records/index.html"}
all_titles=[];all_descriptions=[]
for route,path in static_paths.items():
    metadata=manifest.get("static_pages",{}).get(route)
    if not metadata:errors.append(f"static SEO manifest missing {route}");continue
    check_public_page(path,metadata,route);all_titles.append(metadata["title"]);all_descriptions.append(metadata["description"])

directory=parse_page(ROOT/"records/index.html")
for record in records:
    record_id=record["record_id"]
    if not ID_RE.fullmatch(record_id):errors.append(f"invalid published ID: {record_id}");continue
    metadata=manifest["records"][record_id]
    path=ROOT/"records"/record_id/"index.html"
    if not path.is_file():errors.append(f"canonical record page missing: {record_id}");continue
    page=check_public_page(path,metadata,record_id)
    try:
        graph=json.loads(page.jsonld[0]).get("@graph",[])
    except Exception:
        graph=[]
    types={node.get("@type") for node in graph if isinstance(node,dict)}
    if "Dataset" not in types or "DataCatalog" not in types:errors.append(f"{record_id}: Dataset/DataCatalog semantics missing")
    dataset=next((node for node in graph if isinstance(node,dict) and node.get("@type")=="Dataset"),{})
    if dataset.get("identifier",{}).get("value")!=record_id:errors.append(f"{record_id}: Dataset identifier mismatch")
    if dataset.get("includedInDataCatalog",{}).get("@id")!=f"{ORIGIN}/records/#catalog":errors.append(f"{record_id}: Dataset catalog link mismatch")
    if not dataset.get("measurementTechnique") or not dataset.get("variableMeasured"):errors.append(f"{record_id}: Dataset provenance/variables missing")
    if f"../../profile.html?id={record_id}" not in page.links:errors.append(f"{record_id}: backward-compatible profile link missing")
    if f"{record_id}/" not in directory.links:errors.append(f"record directory missing {record_id}")
    for _,related_id in relation_ids(record,records):
        if f"../{related_id}/" not in page.links:errors.append(f"{record_id}: canonical relation link missing: {related_id}")
    if record_id not in metadata["title"] or record_id not in metadata["description"]:errors.append(f"{record_id}: title/description must be record-unique")
    if metadata["canonical"]!=f"{ORIGIN}/records/{record_id}/":errors.append(f"{record_id}: clean canonical mismatch")
    all_titles.append(metadata["title"]);all_descriptions.append(metadata["description"])

if len(all_titles)!=len(set(all_titles)):errors.append("public page titles must be unique")
if len(all_descriptions)!=len(set(all_descriptions)):errors.append("public page descriptions must be unique")

for relative in ("index.html","about.html","records/index.html"):
    page=parse_page(ROOT/relative)
    try: graph=json.loads(page.jsonld[0]).get("@graph",[])
    except Exception: graph=[]
    types={node.get("@type") for node in graph if isinstance(node,dict)}
    if "DataCatalog" not in types:errors.append(f"{relative}: DataCatalog semantic entity missing")
    if "Organization" not in types:errors.append(f"{relative}: publisher Organization missing")

submit=parse_page(ROOT/"submit.html")
if submit.meta.get("robots")!=["noindex,follow"]:errors.append("submit.html must be crawlable noindex,follow")

namespace={"sm":"http://www.sitemaps.org/schemas/sitemap/0.9"}
try:sitemap=ET.parse(ROOT/"sitemap.xml")
except (ET.ParseError,OSError) as exc:errors.append(f"invalid sitemap: {exc}");sitemap=None
expected={f"{ORIGIN}/",f"{ORIGIN}/about.html",f"{ORIGIN}/records/",*[f"{ORIGIN}/records/{record_id}/" for record_id in record_ids]}
if sitemap is not None:
    locations={node.text for node in sitemap.findall("sm:url/sm:loc",namespace)}
    if locations!=expected:errors.append("sitemap URLs differ from public canonical set")
    if any("profile.html" in value or "/profiles/" in value or "prototype" in value for value in locations):errors.append("sitemap contains a compatibility/prototype URL")

robots=(ROOT/"robots.txt").read_text(encoding="utf-8")
for token in ("User-agent: *","Disallow: /data/","Disallow: /work/","Disallow: /SEO-STRATEGY.md","Disallow: /records/README.md",f"Sitemap: {ORIGIN}/sitemap.xml"):
    if token not in robots:errors.append(f"robots.txt missing: {token}")
for relative in ("profile.html","profiles/male.html","profiles/female.html","profiles/puppy.html","profiles/kennel-concept.html","profiles/litter.html"):
    page=parse_page(ROOT/relative)
    if page.meta.get("robots")!=["noindex,follow"]:errors.append(f"compatibility/prototype page must be noindex: {relative}")

workflow=(ROOT/".github/workflows/build-registry.yml").read_text(encoding="utf-8")
for token in ("python scripts/build_seo.py","python scripts/validate_seo.py","node scripts/test_seo_runtime.js","python scripts/audit_performance.py","data/seo-manifest.json","records","sitemap.xml"):
    if token not in workflow:errors.append(f"workflow missing SEO step: {token}")

if errors:
    print("Comprehensive SEO validation FAIL",file=sys.stderr)
    for error in errors:print(f" - {error}",file=sys.stderr)
    raise SystemExit(1)
print(f"Comprehensive SEO validation PASS ({len(static_paths)} static pages + {len(records)} canonical record pages)")
