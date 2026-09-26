#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build a small, read-only Pi Maps search database from an OSM PBF.

The output is written to <output>.next, checked with PRAGMA integrity_check,
and atomically promoted.  This intentionally uses only public OSM tags and
geometry; it never invents coordinates.  Optional route anchors may be
provided as a JSON object keyed by ``osm_type/osm_id`` when a project-specific
anchor pass has been run.
"""
import argparse, bisect, json, os, re, sqlite3, subprocess, tempfile
from pathlib import Path

CLASSES = ('amenity','tourism','shop','place','leisure','railway','public_transport','highway','building','other')
CANONICAL = {'university','hospital','school','college','library','museum','theatre','stadium','park','town','city','suburb'}
FILTER = ['nwr/name=*','nwr/addr:housenumber=*','nwr/addr:street=*','nwr/amenity=*','nwr/tourism=*','nwr/shop=*','nwr/place=*','nwr/leisure=*','nwr/railway=*','nwr/highway=*','nwr/public_transport=*','nwr/building=*','nwr/entrance=*']

def centre(g):
    pts=[]
    def walk(x):
        if isinstance(x,list) and len(x)>=2 and all(isinstance(v,(int,float)) for v in x[:2]): pts.append((float(x[0]),float(x[1])))
        elif isinstance(x,list):
            for y in x: walk(y)
    walk((g or {}).get('coordinates'))
    if not pts:return None
    return sum(x for x,_ in pts)/len(pts),sum(y for _,y in pts)/len(pts)

def identity(fid):
    s=str(fid or '')
    return (s[0],int(s[1:])) if len(s)>1 and s[0] in 'nwr' and s[1:].isdigit() else ('',0)

def classify(t):
    for k in ('amenity','tourism','shop','place','leisure','railway','public_transport','highway','building'):
        if t.get(k): return k,str(t[k])
    return 'other',''

def point_inside(x,y,g):
    typ=(g or {}).get('type'); c=(g or {}).get('coordinates')
    rings=[]
    if typ=='Polygon': rings=c or []
    elif typ=='MultiPolygon': rings=[r for p in (c or []) for r in p]
    for ring in rings:
        hit=False
        for i in range(len(ring)):
            x1,y1=ring[i-1]; x2,y2=ring[i]
            if ((y1>y)!=(y2>y)) and x < (x2-x1)*(y-y1)/(y2-y1)+x1: hit=not hit
        if hit:return True
    return False

def anchor_for(feature, anchor_index):
    g=feature.get('geometry') or {}; typ=g.get('type')
    if typ not in ('Polygon','MultiPolygon'): return None
    pts0=[]
    def walk(v):
        if isinstance(v,list) and len(v)>=2 and all(isinstance(z,(int,float)) for z in v[:2]): pts0.append((v[0],v[1]))
        elif isinstance(v,list):
            for z in v: walk(z)
    walk(g.get('coordinates') or [])
    if not pts0:return None
    minx,maxx=min(x for x,y in pts0),max(x for x,y in pts0); miny,maxy=min(y for x,y in pts0),max(y for x,y in pts0)
    lo=bisect.bisect_left(anchor_index,(minx,-float('inf'),-1))
    hi=bisect.bisect_right(anchor_index,(maxx,float('inf'),float('inf')))
    pts=[a for _,_,_,a in anchor_index[lo:hi] if miny<=a['lat']<=maxy and point_inside(a['lon'],a['lat'],g)]
    if not pts:return None
    pts.sort(key=lambda a:(0 if a['type']=='main' else 1,a['id']))
    return pts[0]

def row(feature, anchors, anchor_index):
    t=feature.get('properties') or {}; c=centre(feature.get('geometry'))
    if not c:return None
    title=str(t.get('name') or t.get('official_name') or t.get('ref') or t.get('addr:street') or '').strip()
    if not title:return None
    typ,oid=identity(feature.get('id'))
    if not typ:return None
    fc,fs=classify(t); street=str(t.get('addr:street') or '').strip(); house=str(t.get('addr:housenumber') or '').strip()
    locality=str(t.get('addr:city') or t.get('addr:suburb') or t.get('is_in:city') or '').strip()
    postcode=str(t.get('addr:postcode') or '').strip(); address=str(t.get('addr:full') or ' '.join(x for x in (house,street) if x)).strip()
    context=str(t.get('addr:state') or t.get('addr:country') or '').strip()
    key=f'{typ}/{oid}'; a=anchors.get(key,{})
    if not a:
        found=anchor_for(feature,anchor_index)
        if found: a={'route_lon':found['lon'],'route_lat':found['lat'],'route_anchor_type':found['type'],'route_anchor_osm_type':'n','route_anchor_osm_id':found['id']}
    search=' '.join(x for x in (title,address,street,house,locality,postcode,context,fs) if x)
    return (typ,oid,fc,fs,title,address,street,house,locality,postcode,context,c[1],c[0],search,a.get('route_lon'),a.get('route_lat'),a.get('route_anchor_type'),a.get('route_anchor_osm_type'),a.get('route_anchor_osm_id'))

def main(a):
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True); nxt=Path(str(out)+'.next')
    anchors=json.loads(Path(a.anchors).read_text()) if a.anchors else {}
    with tempfile.TemporaryDirectory(prefix='pi-maps-search-') as td:
        filtered=Path(td)/'filtered.pbf'; seq=Path(td)/'objects.geojsonseq'
        subprocess.run(['osmium','tags-filter',a.osm,*FILTER,'-o',str(filtered),'--overwrite'],check=True)
        subprocess.run(['osmium','export',str(filtered),'-f','geojsonseq','-u','type_id','-o',str(seq),'--overwrite'],check=True)
        features=[]
        with seq.open(encoding='utf-8') as f:
            for line in f:
                if not line.strip():continue
                features.append(json.loads(line.lstrip('\x1e')))
        anchor_points=[]
        for feature in features:
            t=feature.get('properties') or {}; typ,oid=identity(feature.get('id')); g=feature.get('geometry') or {}
            c=centre(g)
            if typ=='n' and c and str(t.get('entrance','')).lower() in ('main','yes'):
                anchor_points.append((c[0],c[1],oid,{'lon':c[0],'lat':c[1],'type':str(t.get('entrance')).lower(),'id':oid}))
        anchor_index=sorted(anchor_points)
        rows=[]; seen=set()
        for feature in features:
                r=row(feature,anchors,anchor_index)
                if r and (r[0],r[1]) not in seen: seen.add((r[0],r[1])); rows.append(r)
    if nxt.exists():nxt.unlink()
    d=sqlite3.connect(nxt)
    d.executescript('''PRAGMA journal_mode=DELETE;
CREATE TABLE places(id INTEGER PRIMARY KEY,osm_type TEXT NOT NULL,osm_id INTEGER NOT NULL,feature_class TEXT NOT NULL,feature_subclass TEXT,title TEXT NOT NULL,address TEXT,street TEXT,house_number TEXT,locality TEXT,postcode TEXT,context TEXT,lat REAL NOT NULL,lon REAL NOT NULL,search_text TEXT NOT NULL,route_lon REAL,route_lat REAL,route_anchor_type TEXT,route_anchor_osm_type TEXT,route_anchor_osm_id INTEGER,UNIQUE(osm_type,osm_id));
CREATE VIRTUAL TABLE places_fts USING fts5(title,address,street,house_number,locality,postcode,search_text,content=places,content_rowid=id);
CREATE INDEX places_coords ON places(lat,lon); CREATE INDEX places_title ON places(title);''')
    d.executemany('INSERT INTO places(osm_type,osm_id,feature_class,feature_subclass,title,address,street,house_number,locality,postcode,context,lat,lon,search_text,route_lon,route_lat,route_anchor_type,route_anchor_osm_type,route_anchor_osm_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',rows)
    d.execute("INSERT INTO places_fts(rowid,title,address,street,house_number,locality,postcode,search_text) SELECT id,title,address,street,house_number,locality,postcode,search_text FROM places")
    d.commit(); ok=d.execute('PRAGMA integrity_check').fetchone()[0]; d.close()
    if ok!='ok': raise SystemExit('integrity_check='+ok)
    os.replace(nxt,out)
    print(json.dumps({'output':str(out),'rows':len(rows),'integrity':ok}))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--osm',required=True); p.add_argument('--output',required=True); p.add_argument('--anchors'); main(p.parse_args())
