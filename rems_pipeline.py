"""Reproducible, descriptive REMS study. No predictive or diagnostic claims."""
from pathlib import Path
import re, json, hashlib, subprocess, concurrent.futures, platform
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
RAW=ROOT/'data/rems'
BASE='https://atmos.nmsu.edu/PDS/data/mslrem_1001/'
SOLS=list(range(100,110))

def fetch(url,path):
    if not path.exists():
        subprocess.run(['curl','--fail','--location','--silent','--show-error','--retry','3','--max-time','180',url,'-o',str(path)+'.part'],check=True)
        Path(str(path)+'.part').replace(path)
    return path

def download():
    RAW.mkdir(parents=True,exist_ok=True)
    for name in ['LABEL/MODRDR6.FMT','ERRATA.TXT']:
        fetch(BASE+name,RAW/Path(name).name)
    def sol_download(sol):
        url=BASE+f'DATA/SOL_00090_00179/SOL{sol:05d}/'
        html=subprocess.check_output(['curl','-fLsS','--max-time','60',url]).decode()
        names=re.findall(r'href="([^"]+RMD[^\"]+\.TAB)"',html)
        assert len(names)==1,(sol,names)
        p=fetch(url+names[0],RAW/names[0]); fetch(url+names[0].replace('.TAB','.LBL'),p.with_suffix('.LBL'))
        return dict(sol=sol,url=url+names[0],file=names[0],sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: sources=list(pool.map(sol_download,SOLS))
    (RAW/'sources.json').write_text(json.dumps(sources,indent=2))
    return sources

def schema():
    blocks=re.findall(r'OBJECT\s*= COLUMN(.*?)END_OBJECT\s*= COLUMN',(RAW/'MODRDR6.FMT').read_text(),re.S)
    out=[]
    for b in blocks:
        get=lambda k: re.search(r'\b'+k+r'\s*=\s*("[^"]*"|[^\r\n]+)',b).group(1).strip().strip('"')
        out.append(dict(name=get('NAME'),start=int(get('START_BYTE'))-1,width=int(get('BYTES')),type=get('DATA_TYPE')))
    return out

def read_source(src):
    specs=schema(); p=RAW/src['file']
    label=p.with_suffix('.LBL').read_text()
    rows=int(re.search(r'FILE_RECORDS\s*=\s*(\d+)',label)[1])
    size=int(re.search(r'RECORD_BYTES\s*=\s*(\d+)',label)[1])
    if p.stat().st_size != rows*size: raise ValueError('Source file length does not match its PDS label')
    f=pd.read_fwf(p,colspecs=[(c['start'],c['start']+c['width']) for c in specs],names=[c['name'] for c in specs],dtype=str,keep_default_na=False)
    for c in specs:
        f[c['name']]=f[c['name']].str.strip().str.strip('"').str.strip()
        if c['type']!='CHARACTER': f[c['name']]=pd.to_numeric(f[c['name']],errors='coerce').replace(-999,np.nan)
    if len(f)!=rows: raise ValueError('Source row count mismatch')
    f['sol']=src['sol']
    h=f.LMST.str.extract(r'M(\d\d):(\d\d):(\d\d(?:\.\d+)?)').astype(float)
    f['hour']=h[0]+h[1]/60+h[2]/3600
    return f

if __name__=='__main__':
    sources=download()
    f=pd.concat([read_source(s) for s in sources],ignore_index=True)
    f.to_parquet(RAW/'parsed.parquet',index=False)
    print('Rows:',len(f))
    for col in ['GROUND_TEMP','AMBIENT_TEMP','PRESSURE','LOCAL_RELATIVE_HUMIDITY','BOOM1_LOCAL_AIR_TEMP','BOOM2_LOCAL_AIR_TEMP']:
        if col in f: print(col,f[col].describe().to_dict())
    for c in f:
        if 'CONFIDENCE' in c: print(c,f[c].value_counts().head(8).to_dict())
