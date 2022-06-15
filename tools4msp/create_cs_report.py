import pandas as pd
from pandas import ExcelWriter


cs = CaseStudy.objects.get(pk=240)
module_cs = cs.module_cs
module_cs.load_layers()
module_cs.load_inputs()
uses = {}
envs = {}
for idx, l in module_cs.layers.iterrows():
    raster = l.layer
    code = l.code
    cl = CodedLabel.objects.get(code=code)
    area = raster[raster>0].count() * raster.resolution * raster.resolution / 1000 / 1000
    print(idx, raster[raster>0].shape, area)
    if cl.group == 'env':
        envs[code] = {'code': code, 'area': area, 'label': cl.label}
    elif cl.group == 'use':
        uses[code] = {'code': code, 'area': area, 'label': cl.label}
dfuses = pd.DataFrame.from_dict(uses, orient="index")[['code', 'label', 'area']].sort_values('code')
dfenvs = pd.DataFrame.from_dict(envs, orient="index")[['code', 'label', 'area']].sort_values('code')
pres = {}
for code in module_cs.sensitivities.sort_values('precode').precode.unique():
    cl = CodedLabel.objects.get(code=code)
    label = cl.label
    pres[code] = {'code': code, 'label': label}
dfpres = pd.DataFrame.from_dict(pres, orient="index")[['code', 'label']].sort_values('code') 

dfsens = module_cs.sensitivities.sort_values(['precode', 'envcode'])[['precode', 'envcode', 'sensitivity', 'confidence']]
dfweights = module_cs.weights.sort_values(['usecode', 'precode'])[['usecode', 'precode', 'weight', 'distance', 'confidence']]


with ExcelWriter('/tmp/b.xlsx') as writer:
    dfuses.to_excel(writer, sheet_name='uses')
    dfenvs.to_excel(writer, sheet_name='envs')
    dfpres.to_excel(writer, sheet_name='pres')
    dfweights.to_excel(writer, sheet_name='weights')
    dfsens.to_excel(writer, sheet_name='sensitivities')


