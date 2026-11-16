"""Descriptive analysis of aligned REMS observations; export reproducible results."""
import json, platform, subprocess
from pathlib import Path
import numpy as np
import pandas as pd
from rems_pipeline import ROOT, RAW, read_source
VARIABLES={
 'BOOM1_LOCAL_AIR_TEMP':{'name':'Air temperature · Boom 1','unit':'°C','flag':'ATS_BOOM1_CONFIDENCE_LEVEL','bits':[7],'offset':273.15},
 'BOOM2_LOCAL_AIR_TEMP':{'name':'Air temperature · Boom 2','unit':'°C','flag':'ATS_BOOM2_CONFIDENCE_LEVEL','bits':[7],'offset':273.15},
 'PRESSURE':{'name':'Atmospheric pressure','unit':'Pa','flag':'PS_CONFIDENCE_LEVEL','bits':[1],'offset':0},
 'BRIGHTNESS_TEMP':{'name':'Ground brightness temperature','unit':'°C','flag':'GTS_CONFIDENCE_LEVEL','bits':[0,1,2,3],'offset':273.15},
}

def quality_mask(flags,bits):
    flags=flags.str.strip().str.strip('"').str.strip()
    return pd.concat([flags.str[i].eq('1') for i in bits],axis=1).all(axis=1)

def make_analysis(minutes=10):
    if minutes not in (10, 60): raise ValueError("Supported intervals are 10 and 60 minutes")
    bins_per_hour = 60 // minutes
    sources=json.loads((RAW/'sources.json').read_text())
    f=pd.read_parquet(RAW/'parsed.parquet'); total=len(f)
    duplicates=int(f.duplicated(['sol','TIMESTAMP']).sum())
    if duplicates: raise ValueError('Duplicate timestamps require source-level review; no silent deletion')
    f['bin']=(f.hour*bins_per_hour).astype(int) # Local-mean-solar-time intervals.
    audit=[]
    for key,v in VARIABLES.items():
        good=quality_mask(f[v['flag']],v['bits'])&f[key].notna()
        audit.append(dict(key=key,name=v['name'],rows=total,missing=int(f[key].isna().sum()),quality_excluded=int((f[key].notna()&~good).sum()),retained=int(good.sum())))
        f[key]=f[key].where(good)-v['offset']
    cols=list(VARIABLES)
    grouped=f.groupby(['sol','bin'])
    med=grouped[cols].median(); count=grouped[cols].count()
    # Sparse windows excluded independently per measure; never interpolate missing values.
    med=med.where(count>=10).reset_index(); med['hour']=(med['bin']+.5)/bins_per_hour
    med['x']=med.sol+med.hour/24
    channels={}
    for k,v in VARIABLES.items():
        a=med[k]; valid=a.dropna(); baseline=med.groupby('bin')[k].median()
        supports=med.groupby('bin')[k].count()
        resid=(a-med['bin'].map(baseline)).where(med['bin'].map(supports)>=5)
        center=resid.median(); mad=(resid-center).abs().median(); scale=1.4826*mad
        score=(resid-center).abs()/scale if scale>0 else pd.Series(np.nan,index=med.index)
        flagged=score>3.5
        events=[]
        for i in score.sort_values(ascending=False).dropna().index[:8]:
            events.append(dict(sol=int(med.loc[i,'sol']),hour=float(med.loc[i,'hour']),x=float(med.loc[i,'x']),value=float(a[i]),residual=float(resid[i]),score=float(score[i]),flagged=bool(flagged[i])))
        cyclic=med.groupby('bin')[k].agg(['median','count']).reset_index()
        q=valid.quantile([.25,.75]);iqr=q.loc[.75]-q.loc[.25]
        channels[k]={**v,'summary':{'min':float(valid.min()),'max':float(valid.max()),'median':float(valid.median()),'bins':int(valid.size),'scored':int(score.notna().sum()),'flagged':int(flagged.sum()),'residual_center':float(center),'mad':float(mad),'iqr_flagged':int(((a<q.loc[.25]-1.5*iqr)|(a>q.loc[.75]+1.5*iqr)).sum()),'sensitivity':{str(t):int((score>t).sum()) for t in [3,3.5,4.5]}},'values':a.round(4).tolist(),'score':score.round(4).tolist(),'residual':resid.round(4).tolist(),'counts':count[k].tolist(),'cycle':{'hour':((cyclic['bin']+.5)/bins_per_hour).tolist(),'median':cyclic['median'].round(4).tolist(),'n':cyclic['count'].tolist()},'events':events}
    # Common bins, standardized numeric variables. No independent-sample significance claims.
    complete=med.dropna(subset=cols)
    z=(complete[cols]-complete[cols].mean())/complete[cols].std(ddof=1)
    u,s,vt=np.linalg.svd(z.to_numpy(),full_matrices=False)
    variance=s*s/(len(z)-1); ratios=variance/variance.sum()
    load=vt.T*np.sqrt(variance)
    pc=u[:,:2]*s[:2]
    residuals=pd.DataFrame({k:(med[k]-med.groupby('bin')[k].transform('median')).where(med.groupby('bin')[k].transform('count')>=5) for k in cols}).dropna()
    cpu = subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip() if platform.system()=='Darwin' else platform.processor() or platform.machine()
    payload={'interval_minutes':minutes,'study':'Curiosity REMS · Sols 100–109','source': 'MSL-M-REMS-5-MODRDR-V1.0','raw_rows':total,'duplicates':duplicates,'sources':sources,'audit':audit,'channels':channels,'x':med.x.tolist(),'sol':med.sol.tolist(),'hour':med.hour.tolist(),'pca':{'n':len(z),'variables':cols,'explained':ratios.tolist(),'loadings':load[:,:2].tolist(),'scores':pc.tolist(),'sol':complete.sol.tolist(),'hour':complete.hour.tolist()},'correlation':complete[cols].corr().to_numpy().tolist(),'residual_correlation':residuals.corr().to_numpy().tolist(),'residual_n':len(residuals),'environment':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'cpu':cpu,'architecture':platform.machine(),'gpu':'Not used'},'example':med.dropna(subset=cols).head(5)[['sol','hour']+cols].to_dict('records')}
    out=ROOT/'web/data';out.mkdir(parents=True,exist_ok=True)
    # pandas JSON serialization maps unavailable numeric results to JSON null.
    text=json.dumps(payload,allow_nan=True)
    import re
    text=re.sub(r'\bNaN\b','null',text)
    (out/('rems.json' if minutes==10 else 'rems-hourly.json')).write_text(text)
    med.to_csv(out/('rems-observations.csv' if minutes==10 else 'rems-hourly-observations.csv'),index=False)
    (out/'rems-manifest.json').write_text(json.dumps({'sources':sources,'audit':audit,'environment':payload['environment']},indent=2))
    return payload,med

if __name__=='__main__':
    make_analysis(60)
    p,m=make_analysis(10);print(json.dumps({'rows':p['raw_rows'],'audit':p['audit'],'pca':p['pca']['explained'],'complete':p['pca']['n']},indent=2))
