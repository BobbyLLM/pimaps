import importlib.util, time
from pathlib import Path

spec=importlib.util.spec_from_file_location('builder',Path(__file__).parents[1]/'scripts'/'build-search.py')
builder=importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)

def feature(coords):
    return {'geometry':{'type':'Polygon','coordinates':[coords]}}

def test_only_contained_entrances_are_candidates():
    f=feature([[0,0],[10,0],[10,10],[0,10],[0,0]])
    idx=sorted([(1,1,1,{'lon':1,'lat':1,'type':'main','id':1}),(20,20,2,{'lon':20,'lat':20,'type':'yes','id':2})])
    assert builder.anchor_for(f,idx)['id']==1

def test_large_polygon_lookup_has_no_grid_walk():
    f=feature([[-180,-90],[180,-90],[180,90],[-180,90],[-180,-90]])
    idx=[(x,0,x,{'lon':x,'lat':0,'type':'yes','id':x}) for x in range(-179,180)]
    start=time.monotonic(); result=builder.anchor_for(f,idx); elapsed=time.monotonic()-start
    assert result is not None and elapsed < 1.0
