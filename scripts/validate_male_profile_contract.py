#!/usr/bin/env python3
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
errors=[]
profile=(ROOT/'profiles/male.html').read_text(encoding='utf-8')
submit=(ROOT/'submit.html').read_text(encoding='utf-8')
schema=json.loads((ROOT/'schemas/registry.schema.json').read_text(encoding='utf-8'))
dob=schema['$defs']['doberman']['properties']
health=dob['health']['properties']
identity=dob['identity']['properties']
publication=dob['publication']['properties']
if 'additional_tests' in health: errors.append('schema still exposes additional_tests')
if 'health_summary' in submit: errors.append('owner form still exposes health_summary')
for orphan in ['call_name','microchip_number','breeding_status']:
    if orphan in identity: errors.append('identity schema still exposes orphan field: '+orphan)
for token in ['name="call_name"','name="microchip"','name="breeding_status"']:
    if token in submit: errors.append('owner form still exposes orphan identity control: '+token)
for orphan in ['featured_title','notes_internal']:
    if orphan in publication: errors.append('publication schema still exposes unused field: '+orphan)
for token in ['DM:testView(health.dm','vWD:testView(health.vwd','HD:testView(health.hd','ED:testView(health.ed','DCM clinical','Thyroid:testView(health.thyroid','Eyes:testView(health.eyes']:
    if token not in profile: errors.append('male profile missing health contract token: '+token)
for token in ['Shows:numberOrDash(performance.shows_count)','Titles:array(performance.titles).length','"Working exams":array(performance.working_exams).length','Sports:array(performance.sports).length']:
    if token not in profile: errors.append('male profile missing performance contract token: '+token)
for token in ['lifeStage,lifeStatus,lifeSpan:lifespan||"—"','studServiceStatus,profileId:recordId','lifeStage:"Life stage",lifeStatus:"Life status",lifeSpan:"Life span"','studServiceStatus:"Stud service status"','id="lifeStatusBadge"','const isDeceased=lifecycleState==="deceased"','lifecycleState==="living"?""']:
    if token not in profile: errors.append('male profile missing Details contract token: '+token)
for token in ['Litters:numberOrDash(reproduction.litters_count)','Offspring:numberOrDash(reproduction.offspring_count)','"Champion offspring":numberOrDash(reproduction.champion_offspring_count)','"Export countries":array(reproduction.export_countries).length']:
    if token not in profile: errors.append('male profile missing breeding contract token: '+token)
if 'name="stud_service_status"' not in submit: errors.append('owner form is missing Stud service status in About')
if 'name="breeding_availability"' in submit: errors.append('owner form still exposes legacy breeding_availability control')
if schema.get('properties',{}).get('schema_version',{}).get('const') != '1.1.0': errors.append('canonical schema is not v1.1.0')
if set(identity.get('life_stage',{}).get('enum',[])) != {'puppy','junior','adult','veteran','unknown'}: errors.append('life_stage enum is incorrect')
if set(identity.get('life_status',{}).get('enum',[])) != {'living','deceased','unknown'}: errors.append('life_status enum is incorrect')
if 'Balance:present(structure.balance),Evaluator:' in profile: errors.append('Structure accidentally includes Evaluator card')
if 'profileData.titles.slice(0,2)' not in profile: errors.append('hero title rail is not capped to the two-title master composition')
if errors:
    print('Male profile contract FAIL')
    for e in errors: print('-',e)
    sys.exit(1)
print('Male profile contract PASS')
