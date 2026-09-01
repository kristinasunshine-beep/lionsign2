"use strict";

// Execute the production renderers, not a duplicate implementation.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = path.resolve(__dirname, "..");
const male = fs.readFileSync(path.join(root, "profiles/male.html"), "utf8");
const index = fs.readFileSync(path.join(root, "index.html"), "utf8");
const DIName = require("../assets/js/display-name.js");
const DIMedia = require("../assets/js/media-presentation.js");

function profileHarness(fetch = async () => { throw new Error("No fixture response"); }) {
  const elements = new Map();
  const source = male.match(/<script>\s*(const repoRoot=[\s\S]+?)\s*initializeProfile\(\)\.catch/)[1];
  const document = {
    baseURI: "https://example.invalid/profiles/male.html",
    getElementById: id => {
      if (!elements.has(id)) elements.set(id, { innerHTML: "" });
      return elements.get(id);
    },
  };
  const api = vm.runInNewContext(`${source}\n({ buildBloodline, buildRelated, loadPedigreeIdentities, canonicalToProfile, metrics, bloodline, related, heroMetadata, core, gallery, setRegistry:value=>registryRecords=value, setProfile:value=>profileData=value });`, {
    document, URL, URLSearchParams, window: { DIName, DIMedia }, fetch,
  });
  return { api, elements };
}

function cssRule(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const rules = [...male.matchAll(new RegExp(`${escaped}\\{([^}]+)\\}`, "g"))];
  return rules.map(match => match[1]).join(";");
}

function testPortalRecognition() {
  const selector = '.featured-record[data-entity-type="doberman"]';
  const portalRule = suffix => {
    const escaped = (selector + suffix).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return [...index.matchAll(new RegExp(`${escaped}\\s*\\{([^}]+)\\}`, "g"))].map(match => match[1]).join(";");
  };
  assert.match(portalRule(""), /grid-template-rows:auto/);
  assert.match(portalRule(" .featured-record-media"), /aspect-ratio:4\s*\/\s*5/);
  assert.match(portalRule(" .featured-record-media"), /background:var\(--paper\)/);
  const imageRule = portalRule(" .featured-record-media img");
  assert.match(imageRule, /object-fit:contain/);
  assert.match(imageRule, /object-position:center/);
  assert.match(imageRule, /transform:none/);
  assert.match(imageRule, /width:100%/);
  assert.match(imageRule, /height:100%/);
  assert.doesNotMatch(imageRule, /cover|scale\(|translate\(/);
  // Equal specificity: the recognition rule must follow the legacy hover zoom.
  assert.ok(index.indexOf(selector + " .featured-record-media img{") > index.indexOf("transform:scale(1.018)"));

  const element = tag => ({
    tag, children: [], dataset: {}, style: {}, attributes: {},
    append(...nodes) { this.children.push(...nodes); },
    replaceChildren() { this.children = []; },
    setAttribute(name, value) { this.attributes[name] = value; },
  });
  const hosts = new Map(["males", "females", "puppies", "kennels"].map(category => [category, element("section")]));
  const focalCalls = [];
  const document = {
    baseURI: "https://example.invalid/index.html",
    createElement: element,
    querySelector: query => hosts.get(query.match(/data-showcase="([^"]+)"/)[1]),
  };
  const normalization = index.slice(index.indexOf("let registryRecords = []"), index.indexOf("const updateRegistryTicker ="));
  const renderer = index.slice(index.indexOf("const homepageShowcaseAsset ="), index.indexOf("const loadHomepageShowcases ="));
  const api = vm.runInNewContext(`${normalization}\n${renderer}\n({setRecords:values=>registryRecords=values.map(normalizeRegistryRecord), renderHomepageShowcase, publicDobermanStatus});`, {
    document, URL, window: { DIName, DIMedia: { ...DIMedia, applyFocalPoint: (image, point) => focalCalls.push({ image, point }) } },
  });
  // Synthetic future records only; no production JSON or IDs are written.
  const fixtures = [
    { record_id: "QA-MALE", entity_type: "doberman", registered_name: "COWBOY LUCKY LUCK DI ALTOBELLO", sex: "male", life_stage: "adult" },
    { record_id: "QA-FEMALE", entity_type: "doberman", registered_name: "FELICITA FLAIR VON ASHANTI LEGENDE", sex: "female", life_stage: "adult" },
    { record_id: "QA-PUPPY", entity_type: "doberman", registered_name: "McExample di ROMA", sex: "female", life_stage: "puppy" },
    { record_id: "QA-KENNEL", entity_type: "kennel", name: "OFFICIAL KENNEL NAME" },
  ].map(record => ({ ...record, status: "published", life_status: "living", hero: `media/${record.record_id}/hero.png`, hero_focal_point: { x: 12, y: 88 }, kennel_name: "SIEMPRE PELIGROSO", location: "Belgrade" }));
  const before = JSON.stringify(fixtures);
  api.setRecords(fixtures);
  for (const [i, category] of ["males", "females", "puppies", "kennels"].entries()) {
    const record = fixtures[i];
    api.renderHomepageShowcase(category, [record.record_id]);
    const host = hosts.get(category);
    assert.equal(host.hidden, false);
    assert.equal(host.children.length, 1);
    const card = host.children[0];
    const [media, copy] = card.children;
    const [image, label] = media.children;
    assert.equal(card.dataset.entityType, record.entity_type);
    assert.equal(card.href, `profile.html?id=${record.record_id}`);
    assert.equal(image.src, `https://example.invalid/${record.hero}`);
    assert.equal(copy.children[0].textContent, record.record_id);
    if (record.entity_type === "doberman") {
      assert.equal(label, undefined, "Living Doberman cards must not render the sequence/LIVE badge");
      assert.equal(media.children.length, 1);
      assert.equal(focalCalls.length, 0, "Portal Doberman recognition must not apply the Hero focal point");
      assert.deepEqual(image.style, {});
      assert.equal(copy.children[1].className, "registered-name");
      assert.equal(copy.children[1].textContent, DIName.displayRegisteredName(record.registered_name));
      assert.doesNotMatch(copy.children[1].textContent, /\n|<br/i);
      assert.equal(copy.children[2].textContent, "Siempre Peligroso · Belgrade");
    } else {
      assert.equal(label.textContent, "01 / LIVE", "Unrelated entity labels remain unchanged");
      assert.equal(focalCalls.length, 1, "Non-Doberman media treatment remains unchanged");
      assert.equal(copy.children[1].textContent, "OFFICIAL KENNEL NAME");
      assert.equal(copy.children[1].className, undefined);
    }
  }
  assert.equal(api.publicDobermanStatus("living"), "");
  assert.equal(api.publicDobermanStatus("deceased"), "DECEASED");
  assert.equal(api.publicDobermanStatus("LIVING"), "");
  assert.equal(JSON.stringify(fixtures), before, "Portal renderer must not mutate input data");
}

async function main() {
  testPortalRecognition();
  const thumbnailRules = [...index.matchAll(/\.search-result-thumb\s*\{([^}]+)\}/g)].map(match => match[1]).join(";");
  assert.match(thumbnailRules, /aspect-ratio:\s*4\s*\/\s*5/);
  assert.doesNotMatch(thumbnailRules, /height:\s*\d/);
  assert.match(thumbnailRules, /background:\s*var\(--paper\)/);
  const thumbnailImage = index.match(/\.search-result-thumb img\s*\{([^}]+)\}/)[1];
  assert.match(thumbnailImage, /object-fit:\s*contain/);
  assert.match(thumbnailImage, /object-position:\s*center/);
  assert.doesNotMatch(thumbnailImage, /cover|transform/);
  const thumbRenderer = index.slice(index.indexOf("thumb.className = 'search-result-thumb'"), index.indexOf("const text = document.createElement('span')", index.indexOf("thumb.className = 'search-result-thumb'")));
  assert.doesNotMatch(thumbRenderer, /applyFocalPoint|objectPosition|transform/);
  assert.match(index, /displayKennelName\(record.kennel_name\)/);
  assert.match(index, /detail.textContent = \[record.kennel, record.location/);

  const kpi = cssRule("#performanceRail .metric strong");
  for (const rule of ["top:14px", "right:12px", "bottom:auto", "z-index:3", "background:inherit", "padding:8px 10px 10px"]) assert.ok(kpi.includes(rule), rule);
  assert.match(cssRule("#performanceRail .metric"), /background:#191919/);
  assert.match(cssRule("#performanceRail .metric.highlight"), /background:var\(--acid\)/);
  assert.match(cssRule("#performanceRail .metric::before"), /z-index:0/);
  assert.match(cssRule("#performanceRail .metric-badge"), /top:24px;left:22px/);
  assert.match(cssRule("#performanceRail .metric em"), /bottom:46px/);
  assert.doesNotMatch(male, /Country not submitted/);
  assert.match(cssRule("#heroMeta .hero-credentials"), /text-transform:uppercase/);
  assert.match(cssRule("#heroMeta .hero-credentials"), /font-weight:400/);
  assert.match(cssRule(".dossier-copy strong"), /font-size:18px;font-weight:900/);
  for (const selector of [".ancestor h4", ".related-copy strong"]) {
    assert.match(cssRule(selector), /white-space:normal/);
    assert.match(cssRule(selector), /text-transform:none/);
    assert.match(cssRule(selector), /text-wrap:balance/);
    assert.doesNotMatch(cssRule(selector), /text-overflow:ellipsis|white-space:nowrap/);
  }
  for (const selector of [".ancestor-top", ".related-card-top", ".related-copy span"]) assert.match(cssRule(selector), /text-transform:uppercase/);
  assert.match(index, /\.featured-record-copy strong\.registered-name\s*\{[^}]*text-transform:none/);
  assert.match(index, /record.entity_type === 'doberman'\) name.className = 'registered-name'/);
  const portalNameRule = [...index.matchAll(/\.featured-record-copy strong\.registered-name\s*\{([^}]+)\}/g)].map(match => match[1]).join(";");
  assert.match(portalNameRule, /white-space:nowrap/);
  assert.match(portalNameRule, /letter-spacing:-\.035em/);
  assert.match(portalNameRule, /word-spacing:\.06em/);
  assert.match(portalNameRule, /text-transform:none/);
  assert.doesNotMatch(portalNameRule, /scaleX|text-transform:uppercase/);
  const searchNameRule = index.match(/\.search-result-copy strong\s*\{([^}]+)\}/)[1];
  assert.match(searchNameRule, /white-space:\s*nowrap/);
  assert.match(searchNameRule, /letter-spacing:\s*-\.035em/);
  assert.match(searchNameRule, /word-spacing:\s*\.06em/);
  assert.match(searchNameRule, /text-transform:\s*none/);
  assert.doesNotMatch(index, /headerTitle\.textContent\s*=\s*mode === 'puppies' \? 'Live registry view'/);
  assert.match(index, /publicDobermanStatus\(record\.life_status\)/);

  assert.match(cssRule('.visual-card[data-frame-fit="contain"] img'), /object-fit:contain/);
  assert.match(male, /\.visual-card\[data-frame-fit="contain"\]:hover img,[^{]+\{transform:none\}/);
  assert.match(male, /width:calc\(100vw - 48px\);\s*max-width:calc\(100vw - 48px\);\s*height:auto/);
  assert.match(male, /\.gallery-rail\{align-items:flex-start\}/);

  const { api, elements } = profileHarness();
  const parentNames = Object.freeze({ sire_name: "COWBOY LUCKY LUCK DI ALTOBELLO", sire_registration: "JR 708334", dam_name: "FELICITA FLAIR VON ASHANTI LEGENDE", dam_registration: "JR 713394" });
  const sourceNames = JSON.stringify(parentNames);
  const expectedNames = ["Cowboy Lucky Luck di Altobello", "Felicita Flair von Ashanti Legende"];
  assert.equal(JSON.stringify(api.buildBloodline(parentNames).map(x => x.name)), JSON.stringify(expectedNames));
  assert.equal(JSON.stringify(api.buildRelated("DI-M-000001", parentNames).map(x => x.name)), JSON.stringify(expectedNames));
  assert.equal(JSON.stringify(parentNames), sourceNames);
  for (const gen of [1, 2, 3, 4, 5, 6, 7]) {
    assert.equal(api.buildBloodline({ pedigree_nodes: [{ gen, role: "Ancestor", name: "CASA DI ROMA" }] })[0].name, "Casa di Roma");
    assert.equal(api.buildBloodline({ pedigree_nodes: [{ gen, role: "Ancestor", name: "McExample di ROMA" }] })[0].name, "McExample di ROMA");
  }
  api.setRegistry([{ record_id: "DI-M-000002", entity_type: "doberman", status: "published", registered_name: "McExample di ROMA" }, { record_id: "DI-L-000001", entity_type: "litter", status: "published", name: "OFFICIAL LITTER NAME" }]);
  assert.equal(api.buildBloodline({ sire_id: "DI-M-000002", sire_name: "FALLBACK" })[0].name, "McExample di ROMA");
  assert.equal(api.buildRelated("DI-M-000001", { sire_id: "DI-M-000002" })[0].name, "McExample di ROMA");
  assert.equal(api.buildRelated("DI-M-000001", { litter_id: "DI-L-000001" })[0].name, "OFFICIAL LITTER NAME");
  api.setRegistry([]);
  const renderBloodline = nodes => {
    api.setProfile({ bloodline: nodes }); api.bloodline();
    return elements.get("bloodlineRail").innerHTML;
  };
  let nodes = api.buildBloodline({ sire_name: "SIRE", sire_registration: "JR 708334", dam_name: "DAM" });
  let html = renderBloodline(nodes);
  assert.ok(html.includes("<p>JR 708334</p>"));
  assert.equal((html.match(/<p>/g) || []).length, 1);
  assert.doesNotMatch(html, /<br>|not submitted/);
  const registry = [{ record_id: "DI-M-000002", entity_type: "doberman", status: "published", registered_name: "INDEXED SIRE", country: "Serbia", path: "data/dobermans/DI-M-000002.json" }];
  api.setRegistry(registry);
  nodes = api.buildBloodline({ sire_id: "DI-M-000002", sire_name: "SIRE", sire_registration: "JR 1" });
  assert.equal(nodes[0].country, "Serbia");
  assert.match(renderBloodline(nodes), /<p>JR 1<br>Serbia<\/p>/);
  nodes = api.buildBloodline({ pedigree_nodes: [{ gen: 2, role: "Ancestor", name: "NAME", registration: "REG", country: "Italy", titles: "CH" }] });
  assert.match(renderBloodline(nodes), /<p>REG<br>CH<br>Italy<\/p>/);
  nodes = api.buildBloodline({ pedigree_nodes: [{ gen: 2, name: "NAME", titles: " ", country: null }] });
  assert.doesNotMatch(renderBloodline(nodes), /<p>|<br>/);
  nodes = api.buildBloodline({ pedigree_nodes: [{ gen: 2, name: "NAME", record_id: "DI-M-000002" }] });
  assert.equal(nodes[0].country, "Serbia");
  assert.match(renderBloodline(nodes), /<p>Serbia<\/p>/);

  let requests = 0;
  const fetched = profileHarness(async () => {
    requests++;
    return { ok: true, json: async () => ({ record_id: "DI-M-000002", entity_type: "doberman", status: "published", doberman: { identity: { registered_name: "INDEXED SIRE", registration_number: "REAL REG", country: "Italy" } } }) };
  });
  fetched.api.setRegistry(registry);
  const parentage = { sire_id: "DI-M-000002", sire_name: "SIRE", pedigree_nodes: [] };
  const identities = await fetched.api.loadPedigreeIdentities(parentage);
  nodes = fetched.api.buildBloodline(parentage, identities);
  assert.equal(requests, 1);
  assert.equal(nodes[0].registration, "REAL REG");
  assert.equal(nodes[0].country, "Italy");
  const unavailable = profileHarness(); unavailable.api.setRegistry(registry);
  assert.equal((await unavailable.api.loadPedigreeIdentities(parentage)).size, 0);
  const mismatched = profileHarness(async () => ({ ok: true, json: async () => ({ record_id: "DI-M-000099", entity_type: "doberman", status: "published" }) }));
  mismatched.api.setRegistry(registry);
  assert.equal((await mismatched.api.loadPedigreeIdentities(parentage)).size, 0);

  for (const value of [1, 2, 7, 12, 100]) {
    api.metrics("performanceRail", { Shows: value, Titles: value, "Working exams": value, Sports: value }, 1);
    html = elements.get("performanceRail").innerHTML;
    for (const initial of ["S", "T", "W"]) assert.ok(html.includes(`data-initial="${initial}"`));
    assert.equal((html.match(new RegExp(`<strong>${value}</strong>`, "g")) || []).length, 4);
  }
  api.setProfile({ kennel: "Siempre Peligroso", country: "Serbia", titles: ["TITLE ONE", "TITLE TWO", "TITLE THREE"] });
  api.heroMetadata(); html = elements.get("heroMeta").innerHTML;
  assert.match(html, /class="hero-identity">Siempre Peligroso · Serbia<\/span>/);
  assert.match(html, /class="hero-credentials"><span>TITLE ONE<\/span><span>TITLE TWO<\/span>/);
  assert.doesNotMatch(html, /TITLE THREE/);
  api.setProfile({ kennel: "<Kennel>", titles: [] }); api.heroMetadata();
  assert.match(elements.get("heroMeta").innerHTML, /&lt;Kennel&gt;/);
  assert.doesNotMatch(elements.get("heroMeta").innerHTML, /hero-credentials/);

  const dantePath = path.join(root, "data/dobermans/DI-M-000001.json");
  if (fs.existsSync(dantePath)) {
    const canonical = JSON.parse(fs.readFileSync(dantePath, "utf8"));
    const before = JSON.stringify(canonical);
    api.setRegistry(JSON.parse(fs.readFileSync(path.join(root, "data/registry.json"), "utf8")).records);
    const view = api.canonicalToProfile(canonical, canonical.record_id);
    assert.equal(view.core.profileId, "DI-M-000001");
    assert.equal(view.kennel, DIName.displayKennelName(canonical.doberman.identity.kennel_name));
    assert.equal(view.core.kennel, view.kennel);
    assert.equal(view.core.lifeStatus, "", "Living is an internal default and must not render publicly");
    assert.equal(view.statusBadge, "", "Living records must not have a public status badge");
    api.setProfile(view);
    api.gallery();
    const galleryHTML = elements.get("visualSlider").innerHTML;
    assert.match(galleryHTML, /data-media-role="profile"[^>]+data-frame-fit="contain"/);
    assert.match(galleryHTML, /data-media-role="stack"[^>]+data-frame-fit="contain"/);
    assert.match(galleryHTML, /data-media-role="gallery"[^>]+data-frame-fit="contain"/);
    assert.equal(JSON.stringify(canonical), before, "renderer must not mutate canonical input");
    assert.equal(fs.readFileSync(dantePath, "utf8").includes('"record_id": "DI-M-000001"'), true);
    // A source file can appear in both Hero and additional Gallery without changing its Hero crop.
    const fixture = JSON.parse(before);
    fixture.doberman.media.gallery = [{ path: fixture.doberman.media.hero, focal_point: { x: 50, y: 50 }, fit_mode: "contain", caption: "Gallery 02" }];
    const reused = api.canonicalToProfile(fixture, fixture.record_id);
    const gallery02 = reused.gallery.find(item => item[0] === "Gallery 02");
    assert.equal(gallery02[1], reused.heroImage);
    assert.equal(gallery02[3], "50% 50%");
    assert.equal(gallery02[4], "gallery");
    assert.equal(gallery02[5], "contain");
    assert.equal(reused.heroPosition, view.heroPosition);
    const deceased = JSON.parse(before);
    deceased.doberman.identity.life_status = "deceased";
    deceased.doberman.identity.date_of_death = "2026-08-30";
    const deceasedView = api.canonicalToProfile(deceased, deceased.record_id);
    assert.equal(deceasedView.core.lifeStatus, "DECEASED");
    assert.match(deceasedView.statusBadge, /^DECEASED(?: · |$)/);
  }
  console.log("Public UI v5.9.35 PASS (living lifecycle labels suppressed; deceased preserved; Search/Portal names kept on one line; structural media contained; mobile frame ratios and canonical data preserved)");
}

if (require.main === module) main().catch(error => { console.error(error); process.exitCode = 1; });
module.exports = { profileHarness };
