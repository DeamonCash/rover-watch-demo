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

def test_hourly_export_matches_median_of_accepted_raw_observations():
    from rems_pipeline import RAW
    from rems_analysis import VARIABLES, quality_mask
    frame = pd.read_parquet(RAW/'parsed.parquet')
    spec = VARIABLES['BOOM1_LOCAL_AIR_TEMP']
    mask = (frame.sol == 100) & (frame.hour >= 0) & (frame.hour < 1)
    mask &= quality_mask(frame[spec['flag']], spec['bits'])
    values = frame.loc[mask, 'BOOM1_LOCAL_AIR_TEMP'].dropna() - spec['offset']
    export = json.loads((ROOT/'web/data/rems-hourly.json').read_text())
    index = next(i for i, (sol, hour) in enumerate(zip(export['sol'], export['hour'])) if sol == 100 and hour == 0.5)
    assert len(values) >= 10
    assert abs(export['channels']['BOOM1_LOCAL_AIR_TEMP']['values'][index] - values.median()) < 0.0001

def test_raw_export_keeps_each_accepted_measurement():
    import gzip
    from rems_pipeline import RAW
    from rems_analysis import VARIABLES, quality_mask
    frame = pd.read_parquet(RAW/'parsed.parquet')
    frame = frame.loc[frame.sol == 100]
    with gzip.open(ROOT/'web/data/raw/sol-100.json.gz', 'rt') as f:
        exported = json.load(f)
    assert len(exported['hour']) == len(frame)
    for key, spec in VARIABLES.items():
        expected = frame[key].notna() & quality_mask(frame[spec['flag']], spec['bits'])
        assert sum(value is not None for value in exported['channels'][key]) == int(expected.sum())
        assert len(exported['channels'][key]) == len(frame)
