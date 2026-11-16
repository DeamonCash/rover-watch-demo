import json
import numpy as np
import pandas as pd
from rems_analysis import quality_mask, ROOT

def test_pressure_oscillator_is_not_quality_bit():
    assert quality_mask(pd.Series(['01','11','10','XX','-999.00']),[1]).tolist()==[True,True,False,False,False]

def test_ground_all_required_bits():
    assert quality_mask(pd.Series(['1111','1101','XXXX']),[0,1,2,3]).tolist()==[True,False,False]

def test_export_invariants():
    p=json.loads((ROOT/'web/data/rems.json').read_text())
    assert p['raw_rows']==sum(a['rows'] for a in p['audit'])//4
    for a in p['audit']: assert a['missing']+a['quality_excluded']+a['retained']==a['rows']
    for ch in p['channels'].values():
        assert len(ch['values'])==len(p['x'])==len(ch['score'])
        assert -999 not in ch['values']
        assert ch['summary']['sensitivity']['3']>=ch['summary']['flagged']>=ch['summary']['sensitivity']['4.5']
    assert abs(sum(p['pca']['explained'])-1)<1e-10
    assert np.max(np.abs(p['pca']['loadings']))<=1+1e-10
    assert p['pca']['n']>100
    assert not p['duplicates']
