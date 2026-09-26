#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Build the local Pi Maps Wikipedia POI sidecar from OSM and Kiwix.

The input OSM source and active ZIM are immutable inputs. The output is always
written to a caller-selected staging database; promotion is a separate step.
"""
import argparse, concurrent.futures, datetime as dt, hashlib, json, math, os, re, shutil, sqlite3, subprocess, tempfile, time
from pathlib import Path
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, unquote
from urllib.request import Request, build_opener, HTTPRedirectHandler

LANG_RE = re.compile(r'^\s*(?:en\s*:\s*)?(.*?)\s*$')
REDIRECTS = {301,302,303,307,308}
MAP_CLASSES = {'amenity','tourism','shop','place','leisure','railway','historic','natural','aeroway','man_made','boundary','building'}
SEMANTIC = {'amenity':100,'tourism':95,'place':90,'leisure':85,'railway':80,'historic':78,'natural':75,'aeroway':75,'shop':70,'man_made':65,'boundary':60,'building':20,'other':0}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None

def feature_points(g):
    if not g: return []
    def walk(x):
        if isinstance(x, (list,tuple)) and len(x) >= 2 and all(isinstance(v,(int,float)) for v in x[:2]): return [(float(x[0]),float(x[1]))]
        out=[]
        if isinstance(x,list):
            for y in x: out.extend(walk(y))
        return out
    return walk(g.get('coordinates'))

def centre(g):
    pts=feature_points(g)
    if not pts: return None
    return (sum(p[0] for p in pts)/len(pts), sum(p[1] for p in pts)/len(pts))

def classify(tags):
    for key in ('amenity','tourism','place','leisure','railway','historic','natural','aeroway','shop','man_made','boundary','building'):
        if tags.get(key): return key, str(tags.get(key))
    return 'other', ''

def osm_identity(fid):
    fid=str(fid or '')
    return (fid[0], int(fid[1:])) if len(fid)>1 and fid[0] in 'nwr' and fid[1:].isdigit() else ('',0)

def title_parts(raw):
    raw=str(raw or '').strip()
    if raw.lower().startswith('en:'): raw=raw[3:].strip()
    if not raw: return None
    if '#' in raw: title,frag=raw.split('#',1); frag=frag.strip()
    else: title,frag=raw,''
    title=title.strip()
    return (raw,title,frag) if title else None

def title_key(title, fragment=''):
    return (re.sub(r'[^a-z0-9]','',str(title).casefold()), re.sub(r'[^a-z0-9]','',str(fragment).casefold()))

def article_url(base,title):
    return urljoin(base.rstrip('/')+'/', quote(title.replace(' ','_'), safe='()_,.-'))

def resolve(base,title,timeout):
    op=build_opener(NoRedirect); initial=article_url(base,title)
    try:
        try:
            r=op.open(Request(initial,method='HEAD'),timeout=timeout); code=r.getcode(); loc=r.headers.get('Location')
        except HTTPError as e: code=e.code; loc=e.headers.get('Location')
        if code==200: return ('DIRECT_MATCH', initial, initial)
        if code==404: return ('NOT_FOUND', '', initial)
        if code in REDIRECTS and loc:
            target=urljoin(initial,loc)
            if not target.startswith(base.rstrip('/')+'/'): return ('ERROR','','external-redirect')
            try:
                r2=op.open(Request(target,method='HEAD'),timeout=timeout); code2=r2.getcode()
            except HTTPError as e2: code2=e2.code
            return ('REDIRECT_MATCH',target,initial) if code2==200 else ('ERROR','','redirect-final-'+str(code2))
        return ('ERROR','','http-'+str(code))
    except (URLError, TimeoutError, OSError) as e:
        return ('ERROR','','network-'+type(e).__name__)

def run(args):
    tmp=tempfile.mkdtemp(prefix='wiki-builder-')
    pbf=os.path.join(tmp,'wiki.pbf'); seq=os.path.join(tmp,'wiki.geojsonseq'); opl=os.path.join(tmp,'wiki.opl')
    try:
        subprocess.run(['osmium','tags-filter',args.osm,'n/wikipedia=*','w/wikipedia=*','r/wikipedia=*','-o',pbf,'--overwrite'],check=True)
        subprocess.run(['osmium','export',pbf,'-f','geojsonseq','-u','type_id','-o',seq,'--overwrite'],check=True)
        subprocess.run(['osmium','cat',pbf,'-f','opl','-o',opl,'--overwrite'],check=True)
        relation_ids={}
        with open(opl,encoding='utf8') as f:
            for line in f:
                if not line.startswith('r'): continue
                m=re.search(r'^r(\d+).*? T(.*?) M',line)
                if not m: continue
                tags={}
                for item in m.group(2).split(','):
                    if '=' in item:
                        k,v=item.split('=',1); tags[k]=unquote(v)
                parts=title_parts(tags.get('wikipedia'))
                if parts: relation_ids[title_key(parts[1],parts[2])]=int(m.group(1))
        rows=[]; raw=0; english=0
        with open(seq,'rb') as f:
            for line in f:
                line=line.lstrip(b'\x1e').strip()
                if not line: continue
                obj=json.loads(line); tags=obj.get('properties') or {}; parts=title_parts(tags.get('wikipedia'))
                if not parts or not str(tags.get('wikipedia','')).lower().startswith('en:'): continue
                raw+=1; english+=1; c=centre(obj.get('geometry')); 
                if not c: continue
                fc,fs=classify(tags); typ,oid=osm_identity(obj.get('id'))
                if not typ:
                    oid=relation_ids.get(title_key(parts[1],parts[2]),0); typ='r' if oid else ''
                if not typ: continue
                if fc not in MAP_CLASSES: continue
                rows.append({'osm_type':typ,'osm_id':oid,'name':tags.get('name') or parts[1],'feature_class':fc,'feature_subclass':fs,'lon':c[0],'lat':c[1],'wikipedia_raw':parts[0],'wikipedia_title':parts[1],'wikipedia_fragment':parts[2],'wikidata_id':tags.get('wikidata','') or ''})
        # Keep distinct nearby real objects, but deterministically collapse same-entity shells.
        groups={}
        for r in rows: groups.setdefault((r['wikipedia_title'].casefold(),r['wikipedia_fragment'].casefold()),[]).append(r)
        canon=[]; dupgroups=0
        for key,items in groups.items():
            items.sort(key=lambda r:(-SEMANTIC.get(r['feature_class'],0), r['feature_class']=='building', r['osm_type'], r['osm_id']))
            kept=[]
            for r in items:
                if any(abs(r['lon']-k['lon'])<0.005 and abs(r['lat']-k['lat'])<0.005 for k in kept):
                    dupgroups+=1; continue
                r['canonical_rank']=len(kept)+1; kept.append(r)
            canon.extend(kept)
        # Geometry/reference expansion can repeat one OSM identity. Keep the
        # semantically strongest deterministic record before the UNIQUE insert.
        by_identity={}
        for r in canon:
            key=(r['osm_type'],r['osm_id'])
            old=by_identity.get(key)
            if old is None or (-SEMANTIC.get(r['feature_class'],0),r['wikipedia_title'],r['lon'],r['lat']) < (-SEMANTIC.get(old['feature_class'],0),old['wikipedia_title'],old['lon'],old['lat']):
                by_identity[key]=r
        canon=list(by_identity.values())
        titles=sorted({r['wikipedia_title'] for r in canon})
        results={}
        start=time.monotonic()
        def one(t): return t,resolve(args.kiwix,t,args.timeout)
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4,max(1,args.workers))) as ex:
            for t,res in ex.map(one,titles): results[t]=res
        # Retry only transient transport failures, sequentially and bounded.
        for t,res in list(results.items()):
            if res[0]=='ERROR': results[t]=resolve(args.kiwix,t,args.timeout*2)
        published=[]; counts={'DIRECT_MATCH':0,'REDIRECT_MATCH':0,'NOT_FOUND':0,'ERROR':0}
        for r in canon:
            kind,target,initial=results[r['wikipedia_title']]; counts[kind]=counts.get(kind,0)+1
            if kind in ('DIRECT_MATCH','REDIRECT_MATCH'):
                x=dict(r); x['zim_target']=target; x['zim_resolution_type']=kind; published.append(x)
        out=Path(args.output); nxt=Path(str(out)+'.next'); out.parent.mkdir(parents=True,exist_ok=True)
        if nxt.exists(): nxt.unlink()
        con=sqlite3.connect(nxt); con.executescript('''PRAGMA journal_mode=DELETE; CREATE TABLE wiki_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE wiki_pois(id INTEGER PRIMARY KEY,osm_type TEXT NOT NULL,osm_id INTEGER NOT NULL,name TEXT,feature_class TEXT,feature_subclass TEXT,lon REAL NOT NULL,lat REAL NOT NULL,wikipedia_language TEXT NOT NULL,wikipedia_raw TEXT NOT NULL,wikipedia_title TEXT NOT NULL,wikipedia_fragment TEXT,wikidata_id TEXT,zim_target TEXT NOT NULL,zim_resolution_type TEXT NOT NULL,canonical_rank INTEGER NOT NULL,UNIQUE(osm_type,osm_id)); CREATE VIRTUAL TABLE wiki_pois_rtree USING rtree(id,min_lon,max_lon,min_lat,max_lat); CREATE INDEX idx_wiki_osm ON wiki_pois(osm_type,osm_id); CREATE INDEX idx_wiki_title ON wiki_pois(wikipedia_title); CREATE INDEX idx_wiki_qid ON wiki_pois(wikidata_id);''')
        for r in published:
            cur=con.execute('INSERT INTO wiki_pois(osm_type,osm_id,name,feature_class,feature_subclass,lon,lat,wikipedia_language,wikipedia_raw,wikipedia_title,wikipedia_fragment,wikidata_id,zim_target,zim_resolution_type,canonical_rank) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(r.get(k,'') for k in ('osm_type','osm_id','name','feature_class','feature_subclass','lon','lat'))+('en',r['wikipedia_raw'],r['wikipedia_title'],r['wikipedia_fragment'],r['wikidata_id'],r['zim_target'],r['zim_resolution_type'],r['canonical_rank']))
            con.execute('INSERT INTO wiki_pois_rtree VALUES (?,?,?,?,?)',(cur.lastrowid,r['lon'],r['lon'],r['lat'],r['lat']))
        st=os.stat(args.osm); zst=os.stat(args.zim)
        meta={'osm_source_path':args.osm,'osm_source_size':str(st.st_size),'osm_source_date':dt.datetime.fromtimestamp(st.st_mtime,dt.timezone.utc).isoformat(),'zim_name':os.path.basename(args.zim),'zim_uuid':args.zim_uuid,'zim_date':args.zim_date,'zim_size':str(zst.st_size),'builder_version':'1.0.0','build_timestamp':dt.datetime.now(dt.timezone.utc).isoformat(),'raw_candidate_count':str(raw),'map_worthy_candidate_count':str(len(rows)),'canonical_poi_count':str(len(canon)),'duplicate_groups':str(dupgroups),'published_count':str(len(published)),'direct_match_count':str(counts.get('DIRECT_MATCH',0)),'redirect_match_count':str(counts.get('REDIRECT_MATCH',0)),'excluded_count':str(len(canon)-len(published)),'build_seconds':str(round(time.monotonic()-start,1))}
        con.executemany('INSERT INTO wiki_meta VALUES (?,?)',meta.items()); con.commit(); con.execute('PRAGMA wal_checkpoint(TRUNCATE)'); check=con.execute('PRAGMA integrity_check').fetchone()[0]; con.close()
        if check!='ok': raise RuntimeError('integrity_check='+check)
        os.replace(nxt,out)
        print(json.dumps({'meta':meta,'resolution_counts':counts,'integrity':check},indent=2))
    finally: shutil.rmtree(tmp,ignore_errors=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--osm',required=True); p.add_argument('--zim',required=True); p.add_argument('--output',required=True); p.add_argument('--kiwix',required=True); p.add_argument('--zim-uuid',default=''); p.add_argument('--zim-date',default=''); p.add_argument('--workers',type=int,default=4); p.add_argument('--timeout',type=float,default=5); run(p.parse_args())
