import hashlib, importlib.util, json, os, tempfile
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

def load(path):
 spec=importlib.util.spec_from_file_location('bootstrap',path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

@contextmanager
def http_fixture(directory):
    handler=partial(SimpleHTTPRequestHandler,directory=str(directory))
    server=ThreadingHTTPServer(('127.0.0.1',0),handler)
    thread=Thread(target=server.serve_forever,daemon=True); thread.start()
    try: yield f'http://127.0.0.1:{server.server_port}'
    finally: server.shutdown(); thread.join()

def test_bootstrap_verifies_and_promotes(tmp_path):
 src=tmp_path/'source'; data=tmp_path/'data'; src.mkdir()
 payload=b'verified regional asset'; (src/'map.pmtiles').write_bytes(payload)
 digest=hashlib.sha256(payload).hexdigest()
 with http_fixture(src) as base:
  manifest={'schema_version':1,'edition_id':'test','data_version':'1','assets':[{'path':'map.pmtiles','url':f'{base}/map.pmtiles','size':len(payload),'sha256':digest}]}
  mf=tmp_path/'edition.json'; mf.write_text(json.dumps(manifest))
  os.environ['MAPS_DATA']=str(data); os.environ['EDITION_MANIFEST']=str(mf)
  mod=load(Path(__file__).parents[1]/'scripts'/'bootstrap.py'); mod.main()
  assert (data/'map.pmtiles').read_bytes()==payload
  assert (data/'.edition-complete').read_text()=='test/1\n'

def test_bad_checksum_does_not_promote(tmp_path):
 src=tmp_path/'source'; data=tmp_path/'data'; src.mkdir(); data.mkdir()
 (data/'map.pmtiles').write_bytes(b'old')
 (src/'map.pmtiles').write_bytes(b'new')
 with http_fixture(src) as base:
  manifest={'schema_version':1,'edition_id':'test','data_version':'2','assets':[{'path':'map.pmtiles','url':f'{base}/map.pmtiles','size':3,'sha256':'0'*64}]}
  mf=tmp_path/'edition.json'; mf.write_text(json.dumps(manifest))
  os.environ['MAPS_DATA']=str(data); os.environ['EDITION_MANIFEST']=str(mf)
  mod=load(Path(__file__).parents[1]/'scripts'/'bootstrap.py')
  try: mod.main()
  except ValueError: pass
  else: raise AssertionError('checksum mismatch was accepted')
  assert (data/'map.pmtiles').read_bytes()==b'old'

def test_bad_size_preserves_previous_file(tmp_path, monkeypatch):
 src=tmp_path/'source'; data=tmp_path/'data'; src.mkdir(); data.mkdir()
 (data/'asset.bin').write_bytes(b'old'); (src/'asset.bin').write_bytes(b'new')
 with http_fixture(src) as base:
  manifest={'schema_version':1,'edition_id':'test','data_version':'3','assets':[{'path':'asset.bin','url':f'{base}/asset.bin','size':99,'sha256':hashlib.sha256(b'new').hexdigest()}]}
  mf=tmp_path/'edition.json'; mf.write_text(json.dumps(manifest))
  monkeypatch.setenv('MAPS_DATA',str(data)); monkeypatch.setenv('EDITION_MANIFEST',str(mf)); monkeypatch.setenv('ZIM_DOWNLOAD_RATE_MIB','5')
  mod=load(Path(__file__).parents[1]/'scripts'/'bootstrap.py')
  try: mod.main()
  except ValueError as exc: assert 'size mismatch' in str(exc)
  else: raise AssertionError('bad size was accepted')
  assert (data/'asset.bin').read_bytes()==b'old'
  assert not list(data.rglob('*.part'))

def test_zero_rate_fails_safely(tmp_path, monkeypatch):
 mf=tmp_path/'edition.json'; mf.write_text(json.dumps({'schema_version':1,'edition_id':'test','data_version':'4','assets':[]}))
 monkeypatch.setenv('MAPS_DATA',str(tmp_path/'data')); monkeypatch.setenv('EDITION_MANIFEST',str(mf)); monkeypatch.setenv('ZIM_DOWNLOAD_RATE_MIB','0')
 mod=load(Path(__file__).parents[1]/'scripts'/'bootstrap.py')
 try: mod.main()
 except ValueError as exc: assert 'greater than zero' in str(exc)
 else: raise AssertionError('zero rate was accepted')

def test_existing_zim_is_reused(tmp_path, monkeypatch):
 src=tmp_path/'source'; data=tmp_path/'data'; zim=tmp_path/'existing'; src.mkdir(); data.mkdir(); zim.mkdir()
 payload=b'existing zim'; existing=zim/'book.zim'; existing.write_bytes(payload)
 with http_fixture(src) as base:
  manifest={'schema_version':1,'edition_id':'test','data_version':'5','assets':[{'path':'zim/book.zim','url':f'{base}/book.zim','size':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),'optional':True}]}
  mf=tmp_path/'edition.json'; mf.write_text(json.dumps(manifest))
  monkeypatch.setenv('MAPS_DATA',str(data)); monkeypatch.setenv('EDITION_MANIFEST',str(mf)); monkeypatch.setenv('INCLUDE_OPTIONAL','1'); monkeypatch.setenv('WIKI_ZIM_DIR',str(zim)); monkeypatch.setenv('WIKI_ZIM_NAME','book.zim'); monkeypatch.setenv('ZIM_DOWNLOAD_RATE_MIB','5')
  mod=load(Path(__file__).parents[1]/'scripts'/'bootstrap.py'); mod.main()
  assert existing.read_bytes()==payload
  assert not (data/'zim'/'book.zim').exists()
