# SPDX-License-Identifier: AGPL-3.0-only
import html, json, sqlite3, urllib.parse, re, unicodedata, os
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

DB=os.environ.get('SEARCH_DB_PATH','/data/search.sqlite'); WIKI_DB=os.environ.get('WIKI_DB_PATH','/data/wiki-pois.sqlite')
KIWIX_BASE=os.environ.get('KIWIX_BASE','')
WIKI_PREFIX=os.environ.get('WIKI_PREFIX','')
STREET_SUFFIXES=(' street',' road',' highway',' avenue',' drive',' way',' parade',' boulevard',' lane',' crescent',' terrace',' place',' court',' close',' loop')
CLASS_SCORE={'amenity':10000,'tourism':9000,'shop':8000,'place':7000,'leisure':6000,'railway':2500,'public_transport':1500,'highway':1200,'building':500,'other':300}
CANONICAL_SUBCLASS={'university','hospital','school','college','library','museum','theatre','stadium','park','town','city','suburb'}
ALLOWED={'p','a','strong','b','em','i','span','sup','sub'}

def norm(s): return re.sub(r'[^a-z0-9 ]+',' ',unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower()).strip()
def label(d):
 loc=d.get('locality') or d.get('context') or ''
 if d.get('address') and d.get('title')!=d.get('address'): return ' - '.join(x for x in (d['title'],d['address']) if x)+((' - '+loc) if loc else '')
 return ', '.join(x for x in (d.get('title') or d.get('address'),loc) if x)

class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl): return None

class LeadParser(HTMLParser):
 def __init__(self): super().__init__(convert_charrefs=True); self.depth=0; self.started=False; self.done=False; self.parts=[]; self.pchars=[]
 def handle_starttag(self,tag,attrs):
  if self.done:return
  a=dict(attrs)
  if tag=='div' and 'mw-parser-output' in a.get('class','').split(): self.started=True
  if self.started and tag=='p' and self.depth==0: self.depth=1; self.pchars=[]; self.parts.append('<p>'); return
  if self.depth:
   if tag in ALLOWED:
    if tag=='a':
     href=a.get('href',''); p=urllib.parse.urlparse(href)
     if href.startswith(WIKI_PREFIX): href='/wiki/article/'+href[len(WIKI_PREFIX):]
     elif href.startswith('./'): href='/wiki/article/'+href[2:]
     elif href and not href.startswith(('#','/')): href='/wiki/article/'+href
     elif p.scheme or p.netloc or href.startswith('//') or href.startswith('javascript:') or href.startswith('data:'): href=''
     self.parts.append('<a href="'+html.escape(href,quote=True)+'">' if href else '<a>')
    else:self.parts.append('<'+tag+'>')
   elif tag=='p' and self.depth==1: self.done=True
 def handle_endtag(self,tag):
  if self.depth and tag in ALLOWED:
   self.parts.append('</'+tag+'>')
   if tag=='p':
    if self.pchars and ''.join(self.pchars).strip(): self.done=True
    else: self.parts=[]
    self.depth=0
 def handle_data(self,data):
  if self.depth:self.pchars.append(data); self.parts.append(html.escape(data))
 def result(self):
  x=''.join(self.parts).strip()
  return x if x else ''

def wiki_row(typ,oid):
 try: con=sqlite3.connect('file:'+WIKI_DB+'?mode=ro',uri=True)
 except sqlite3.Error: return None
 con.row_factory=sqlite3.Row
 try: return con.execute('SELECT * FROM wiki_pois WHERE osm_type=? AND osm_id=?',(typ,oid)).fetchone()
 finally: con.close()
def wiki_article_path(target):
 p=urllib.parse.urlparse(target).path
 return p[len(WIKI_PREFIX):] if p.startswith(WIKI_PREFIX) else ''
def fetch_lead(target):
 path=wiki_article_path(target)
 if not path: return None
 url=KIWIX_BASE+path
 op=build_opener(NoRedirect)
 try:
  try:r=op.open(Request(url,headers={'Accept':'text/html'}),timeout=8); final=url
  except HTTPError as e:
   if e.code not in (301,302,303,307,308):return None
   loc=e.headers.get('Location',''); final=urllib.parse.urljoin(url,loc)
   if not final.startswith(KIWIX_BASE):return None
   r=op.open(Request(final,headers={'Accept':'text/html'}),timeout=8)
  raw=r.read(600000).decode('utf-8','replace'); p=LeadParser();p.feed(raw); lead=p.result()
  return {'lead_html':lead,'article_path':wiki_article_path(final)} if lead else None
 except (HTTPError,URLError,OSError,TimeoutError): return None

class H(BaseHTTPRequestHandler):
 def log_message(self,*a): pass
 def do_GET(self):
  u=urllib.parse.urlparse(self.path)
  if u.path in ('/search','/health'): return self.search(u) if u.path=='/search' else self.reply({'ok':True})
  if u.path=='/wiki/health': return self.reply({'ok':True})
  if u.path=='/wiki/pois': return self.pois(u)
  if u.path=='/wiki/summary': return self.summary(u)
  if u.path.startswith('/wiki/article/'): return self.article(u)
  self.send_error(404)
 def search(self,u):
  q=urllib.parse.parse_qs(u.query).get('q',[''])[0].strip()
  if not q:return self.reply({'query':'','results':[]})
  tokens=[x for x in norm(q).split() if x]; match=' '.join('"'+x+'"' for x in tokens)
  con=sqlite3.connect('file:'+DB+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
  try: rows=con.execute('SELECT p.*,bm25(places_fts) AS fts_rank FROM places_fts f JOIN places p ON p.id=f.rowid WHERE places_fts MATCH ? LIMIT 300',(match,)).fetchall()
  except sqlite3.OperationalError: rows=[]
  con.close(); qn=norm(q); out=[];seen=set()
  for row in rows:
   d=dict(row); title=norm(d.get('title')); address=norm(d.get('address')); fc=d.get('feature_class',''); fs=d.get('feature_subclass',''); isstreet=(d.get('address') in ('',d.get('title'))) and (fc=='highway' or any(title.endswith(x) for x in STREET_SUFFIXES))
   if isstreet:
    key=('street',title,norm(d.get('locality')))
    if key in seen:continue
    seen.add(key)
   d['exact_title']=title==qn; d['canonical']=(fc in ('amenity','tourism','shop','place','leisure') and fs in CANONICAL_SUBCLASS) or fc=='amenity'
   d['_score']=(100000 if d['exact_title'] else 0)+(50000 if all(t in title.split() for t in tokens) else 0)+CLASS_SCORE.get(fc,0)+(3000 if fs in CANONICAL_SUBCLASS else 0)+(1000 if address==qn else 0)-float(d.get('fts_rank') or 0); out.append(d)
  out.sort(key=lambda x:(-x['_score'],x.get('title',''),x.get('locality',''),x.get('osm_type',''),x.get('osm_id',0)))
  exact=[x for x in out if x['exact_title']]
  for i,d in enumerate(out):
   d['display_label']=label(d); d['auto_resolvable']=len(exact)==1 and i==0
   d.pop('_score',None);d.pop('fts_rank',None);d.pop('search_text',None);d.pop('context',None);d.pop('id',None)
  self.reply({'query':q,'results':out[:12]})
 def pois(self,u):
  q=urllib.parse.parse_qs(u.query); bbox=q.get('bbox',[''])[0].split(',')
  try: con=sqlite3.connect('file:'+WIKI_DB+'?mode=ro',uri=True)
  except sqlite3.Error: return self.reply({'type':'FeatureCollection','features':[]})
  con.row_factory=sqlite3.Row
  try:
   if len(bbox)==4:
    a,b,c,d=map(float,bbox); rows=con.execute('SELECT p.* FROM wiki_pois p JOIN wiki_pois_rtree r ON r.id=p.id WHERE r.max_lon>=? AND r.min_lon<=? AND r.max_lat>=? AND r.min_lat<=? LIMIT 2500',(a,c,b,d)).fetchall()
   else: rows=con.execute('SELECT * FROM wiki_pois LIMIT 2500').fetchall()
  finally:con.close()
  fs=[]
  for r in rows:
   x=dict(r); fs.append({'type':'Feature','geometry':{'type':'Point','coordinates':[x['lon'],x['lat']]},'properties':{'id':x['id'],'osm_type':x['osm_type'],'osm_id':x['osm_id'],'name':x['name'],'feature_class':x['feature_class'],'feature_subclass':x['feature_subclass'],'wikipedia_title':x['wikipedia_title'],'has_fragment':bool(x['wikipedia_fragment']),'wikidata_id':x['wikidata_id']}})
  self.reply({'type':'FeatureCollection','features':fs})
 def summary(self,u):
  q=urllib.parse.parse_qs(u.query); typ=q.get('osm_type',[''])[0]; oid=q.get('osm_id',[''])[0]
  if typ not in ('n','w','r') or not oid.isdigit(): return self.reply({'error':'invalid identity'},400)
  row=wiki_row(typ,int(oid))
  if not row:return self.reply({'error':'not found'},404)
  lead=fetch_lead(row['zim_target']); path=wiki_article_path(row['zim_target'])
  out={'name':row['name'],'wikipedia_title':row['wikipedia_title'],'wikipedia_fragment':row['wikipedia_fragment'],'lead_html':lead['lead_html'] if lead else '','article_url':'./wiki/article/'+path+('#'+urllib.parse.quote(row['wikipedia_fragment']) if row['wikipedia_fragment'] else ''),'local':True,'summary_available':bool(lead)}
  self.reply(out)
 def article(self,u):
  if not KIWIX_BASE or not WIKI_PREFIX: return self.reply({'error':'Wikipedia FULL mode is not configured'},503)
  title=urllib.parse.unquote(u.path[len('/wiki/article/'):])
  if not title or '/' in title: return self.reply({'error':'invalid article'},400)
  try:
   url=KIWIX_BASE.rstrip('/')+'/'+urllib.parse.quote(title,safe='()_,.-')
   op=build_opener(NoRedirect)
   try:r=op.open(Request(url,headers={'Accept':'text/html'}),timeout=15)
   except HTTPError as e:
    if e.code not in (301,302,303,307,308): return self.reply({'error':'article unavailable'},502)
    loc=urllib.parse.urljoin(url,e.headers.get('Location',''))
    if not loc.startswith(KIWIX_BASE.rstrip('/')+'/'): return self.reply({'error':'invalid article redirect'},502)
    r=op.open(Request(loc,headers={'Accept':'text/html'}),timeout=15)
   body=r.read(2000000); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
  except (HTTPError,URLError,OSError,TimeoutError): self.reply({'error':'article unavailable'},502)
 def reply(self,obj,status=200):
  b=json.dumps(obj,separators=(',',':')).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)

ThreadingHTTPServer(('0.0.0.0',8787),H).serve_forever()
