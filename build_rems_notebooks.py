"""Generate and execute notebooks, preserving actual outputs for the web reader."""
from pathlib import Path
import json
import nbformat as nbf
from nbclient import NotebookClient
ROOT=Path(__file__).resolve().parent
setup="""from pathlib import Path
import sys, json
root = next((p for p in [Path.cwd(), *Path.cwd().parents] if (p / 'rems_analysis.py').exists()), None)
if root is None:
    raise RuntimeError('Run this notebook inside the RoverWatch repository; see README.md.')
sys.path.insert(0, str(root))
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from rems_analysis import make_analysis
result, observations = make_analysis()
"""
specs=[('01','01-rems-data.ipynb','Source & quality','Inspect the real measurements and the explicit exclusion rules.',[
('markdown','# 01 · Source and quality\nNASA PDS REMS MODRDR, sols 100–109. This is an exploratory historical study, not a detector benchmark. Download and parse source data first with `python rems_pipeline.py`. Then run this notebook in the project environment.'),('code',setup),('code',"pd.DataFrame(result['audit'])"),('code',"pd.DataFrame(result['example']).round(3)"),('markdown','Missing sentinel −999 becomes unavailable. Quality masks retain air reliability bit 7, pressure no-shadow bit 1, and ground bits 0–3. The flags have different meanings: do not reject pressure oscillator 1 merely because its bit is 0. No imputation; at least ten accepted observations per ten-minute local-time bin. These criteria are conservative study choices, not a universal validity certificate.'),('code',"pd.DataFrame(result['sources'])[['sol','file','sha256']]"),('code',"result['environment']")]),
('02','02-rems-patterns.ipynb','Daily cycles & unusual bins','Describe patterns and inspect sensitivity without imposing an anomaly percentage.',[
('markdown','# 02 · Daily cycles and candidate outliers\nQuestion: which changes remain unusual after accounting for local time of day? All accepted data contribute to this descriptive analysis. No train/test split and no predictive claims.'),('code',setup),('code',"fig, axes = plt.subplots(2,2,figsize=(11,7))\nfor ax,(key,ch) in zip(axes.flat,result['channels'].items()):\n    ax.scatter(observations.x,observations[key],s=3)\n    ax.set(title=ch['name'],xlabel='Sol + fraction of local mean solar day',ylabel=ch['unit'])\nplt.tight_layout(); plt.show()"),('markdown','Residual r = binned observation minus the median at the same local-time bin across available sols; require at least five sols. Score = |r − median(r)| / (1.4826 × MAD(r)). A zero MAD gives an unavailable score. Threshold 3.5 is a review heuristic, not a confidence level. Sensitivity at 3.0 and 4.5 is reported. Shared-data baselines may mask persistent anomalies; no failure annotations exist here.'),('code',"pd.DataFrame({ch['name']:ch['summary'] for ch in result['channels'].values()}).T"),('code',"pd.DataFrame(result['channels']['PRESSURE']['events'])"),('markdown','The pooled 1.5×IQR count is a descriptive comparison, not the preferred anomaly rule: pooling day and night can confuse expected daily extremes with unusual events. Do not remove candidate points automatically.')]),
('03','03-rems-relationships.ipynb','Relationships & PCA','Separate common daily rhythms from residual associations.',[
('markdown','# 03 · Relationships and PCA\nQuestions: which measurements co-vary, and how much does the daily cycle explain? PCA uses complete aligned bins and standardized variables. It cannot infer sensor identity or establish causality.'),('code',setup),('code',"names=[v['name'] for v in result['channels'].values()]\npd.DataFrame(result['correlation'],index=names,columns=names)"),('code',"pd.DataFrame(result['residual_correlation'],index=names,columns=names)"),('code',"p=result['pca']\nprint('Complete bins:',p['n'])\nprint('Explained variance:',np.round(p['explained'],4))\nfig,ax=plt.subplots(figsize=(6,6))\nax.add_patch(plt.Circle((0,0),1,fill=False,color='gray'))\nfor name,(x,y) in zip(names,p['loadings']):\n    ax.arrow(0,0,x,y,head_width=.035,length_includes_head=True)\n    ax.text(x*.8,y*.8,name,fontsize=8)\nax.set(xlim=(-1.2,1.2),ylim=(-1.2,1.2),xlabel='PC1',ylabel='PC2',title='Variable–component correlations')\nax.set_aspect('equal');plt.show()"),('markdown','PCA is computed by SVD after centering and sample-standard-deviation scaling. The circle coordinates are eigenvector loadings times sqrt(eigenvalue). Similar directions indicate positive association only to the extent captured by the plane. Nearby points in the observation plot are similar profiles, not nearby physical sensors. Temporal dependence, uneven coverage and the short interval limit interpretation; no p-values are claimed.')])]
(ROOT/'web/notebooks').mkdir(parents=True,exist_ok=True)
index=[]
for number,file,title,desc,cells in specs:
    nb=nbf.v4.new_notebook(cells=[nbf.v4.new_markdown_cell(s) if kind=='markdown' else nbf.v4.new_code_cell(s) for kind,s in cells],metadata={'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'}})
    NotebookClient(nb,timeout=180,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}}).execute()
    # Keep public outputs free of local filesystem paths.
    text=nbf.writes(nb)
    assert '/Users/' not in text
    (ROOT/'web/notebooks'/file).write_text(text)
    index.append(dict(number=number,file=file,title=title,description=desc)); print('Executed',file,flush=True)
(ROOT/'web/notebooks/rems-index.json').write_text(json.dumps(index,indent=2))
