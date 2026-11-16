"""Export quality-accepted individual REMS observations, grouped by sol."""
import gzip, json
from pathlib import Path
import numpy as np
import pandas as pd
from rems_analysis import VARIABLES, quality_mask
from rems_pipeline import ROOT, RAW

def export_raw():
    frame = pd.read_parquet(RAW/'parsed.parquet')
    out = ROOT/'web/data/raw'; out.mkdir(parents=True, exist_ok=True)
    for key, spec in VARIABLES.items():
        accepted = frame[key].notna() & quality_mask(frame[spec['flag']], spec['bits'])
        frame[key] = (frame[key].where(accepted) - spec['offset']).round(4)
    for sol, df in frame.groupby('sol', sort=True):
        # Time is reported in LMST hours; null means unavailable or excluded.
        payload={'sol':int(sol),'hour':df['hour'].round(7).tolist(),'channels':{k:df[k].tolist() for k in VARIABLES}}
        text=json.dumps(payload,allow_nan=True,separators=(',',':')).replace('NaN','null')
        with gzip.open(out/f'sol-{sol}.json.gz','wt',encoding='utf-8',compresslevel=9) as f: f.write(text)
        print(sol,len(df),flush=True)
if __name__=='__main__': export_raw()
