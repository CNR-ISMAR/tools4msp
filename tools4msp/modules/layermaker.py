# coding: utf-8

import logging
import itertools
import numpy as np
import pandas as pd
from os import path, listdir, mkdir
from .casestudy import CaseStudyBase
import tempfile
from pathlib import Path
import random
import json
import subprocess
import rectifiedgrid as rg
from PIL import Image

logger = logging.getLogger(__name__)

# def coexist_rules(use1conf,
#                   use2conf):
#     vscale1, spatial1, time1, mobility1 = use1conf
#     vscale2, spatial2, time2, mobility2 = use2conf
#
#     # Rule 1
#     if vscale1 != 3 and vscale2 != 3 and vscale1 != vscale2:
#         return 0
#     # Rule 2
#     if mobility1 and mobility2:
#         return min(spatial1, spatial2) + min(time1, time2)
#     # Rule 3
#     return max(spatial1, spatial2) + max(time1, time2)

PMARPARAMS = [
      {
              "value": "general",
              "paramtype": "PMAR-CONF",
              "paramname": "PMAR-PCHAR",
              "_type": "select",
              "_options": [
                  ['general', 'General floating particle, e.g. larvae, floating litter'],
                  # ['sediment_15', 'Sediment [15 micron]'],
                  # ['sediment_45', 'Sediment [45 micron], microplastic [0.5 mm]'],
                  # ['sediment_150', 'Sediment [150 micron], microplastic [2.5 mm]'],
                  ['bacteria', 'Coliform bacteria'],
              ]
            },
      {
              "value": 2018,
              "paramtype": "PMAR-CONF",
              "paramname": "PMAR-STARTYEAR",
              "_type": "select",
              "_options": [
                  [2018, 2018],
              ]
            },
      {
              "value": 2020,
              "paramtype": "PMAR-CONF",
              "paramname": "PMAR-ENDYEAR",
              "_type": "select",
              "_options": [
                  [2018, 2018],
                  [2019, 2019],
                  [2020, 2020],
              ]
            },
      {
              "value": "active_only",
              "paramtype": "PMAR-CONF",
              "paramname": "PMAR-PARTICLE-STATUS",
              "_type": "select",
              "_options": [
                  ['active_only', 'Active only'],
                  # ['stranded', 'Stranded only'],
                  # ['all', 'All'],
              ]
            },
      {
              "value": "mean",
              "paramtype": "PMAR-CONF",
              "paramname": "PMAR-AGGREGATE",
              "_type": "select",
              "_options": [
                  ['mean', 'Mean'],
                  ['max', 'Max'],
              ]
            },
    ]

CONF = {
    "version": 1,
    "runs": [
    ]
}

class LayermakerCaseStudy(CaseStudyBase):
    def __init__(self,
                 csdir=None,
                 rundir=None,
                 name='unnamed'):

        # self.potential_conflict_scores = pd.DataFrame()
        super().__init__(csdir=csdir,
                         rundir=rundir,
                         name='unnamed')

    def get_potential_conflict_score(self, use1id, use2id):
        return self.potential_conflict_scores.loc[use1id, use2id]

    def setup_lpt_dir(self, selected_layers=None, df_domain_area=None):
        conf = {"version": 1, "runs": []}
        self.outputs['pmar_result_layers'] = {}
        with tempfile.TemporaryDirectory() as tmpdirname:
            # if True:
            # tmpdirname = '/tmp/prova'
            # Path(tmpdirname).mkdir(exist_ok=True)
            print('created temporary directory', tmpdirname)
            mkdir(Path(tmpdirname) / 'outputs')
            mkdir(Path(tmpdirname) / 'input_layers')
            
            self.load_layers()
            self.load_inputs()
            input_params = self.input_params
            pmar_run_params = {}
            # start_time='2019-01-01' # regolarla in base all'input dell'utente
            # duration_days=30 # va bene, e' la durata della simulazione
            # reps = 12  
            pressure_char = input_params['PMAR-PCHAR']
            if pressure_char=='general':
                pmar_run_params['decay_rate'] = 0.1
            elif  pressure_char=='bacteria':
                pmar_run_params['decay_rate'] = 0.5

            startyear = int(input_params['PMAR-STARTYEAR'])
            endyear = int(input_params['PMAR-ENDYEAR'])
            # TODO: parametrizzare e verificare con durata dei modelli e il spillup
            # reps = int(endyear - startyear)
            start_time = f'{startyear}-01-01'
            reps_per_year = 5
            reps = (endyear - startyear + 1) * reps_per_year
            tshift = 70
            
            pmar_run_params['start_time'] = start_time
            pmar_run_params['reps'] = reps
            pmar_run_params['tshift'] = tshift

            pmar_run_params['particle_status'] = input_params['PMAR-PARTICLE-STATUS']
                    
            pmar_run_params['aggregate'] = input_params['PMAR-AGGREGATE']
            
            if df_domain_area is not None:
                path_domain_area = Path(tmpdirname) / 'input_layers' / 'domain_area.shp'
                df_domain_area.to_crs(epsg=4326).to_file(path_domain_area)
                pmar_run_params['poly_path'] = str(path_domain_area) # this has to be an absolute path
            
            for idx, l in self.layers.iterrows():
                name = l.code
                if selected_layers is not None and name not in selected_layers:
                    continue
                # if name=='GRID':
                #     continue
                p = Path(tmpdirname) / 'input_layers' / f'{name}.tiff'
                l.layer.write_raster(p)
                run_conf = dict(id=name,
                               context='bs-cmems',
                                layer= str(Path('input_layers') / f'{name}.tiff'),
                               **pmar_run_params)
                conf['runs'].append(run_conf)
                 
            with open(Path(tmpdirname) / 'conf.json', 'w') as outfile:
                json.dump(conf, outfile)
            print(tmpdirname, conf)
            process = subprocess.run(['/opt/miniconda3/bin/conda', 'run', '-n', 'pmar', 'python', '/opt/pmar/pmar/scripts/tools4msp_wrapper.py', tmpdirname])

            with open(Path(tmpdirname) / 'results.json') as rfile:
                results = json.load(rfile)
            for out in results['outputs']:
                self.outputs['pmar_result_layers'][out['id']] = {'output': rg.read_raster(Path(tmpdirname) / out['output']),
                                                                 'thumbnail': Image.open(Path(tmpdirname) / out['thumbnail'])
                                                                 }
            
            # import time
            # time.sleep(20)

    def run(self, selected_layers=None, df_domain_area=None, runtypelevel=3):
        self.setup_lpt_dir(selected_layers=selected_layers, df_domain_area=df_domain_area)
            
        self.outputs['pmar_result'] = {'success': True}
        return True
    #
    # def dump_inputs(self):
    #     self.coexist_scores.to_csv(self.get_outpath('coexist_scores.csv'))

    def load_inputs(self):
        for f in listdir(self.inputsdir):
            filepath = path.join(self.inputsdir, f)
            fname, ext = path.splitext(f)
            if ext == '.json':
                # remove random file suffix
                fname = fname.split('_')[0]
                if fname == 'pmar-PMAR-CONF': # deprecated
                    _df = pd.read_json(filepath)
                    params = _df.set_index('paramname')['value'].to_dict()
                    self.input_params = params
        super().load_inputs()

    
    def dump_outputs(self):
        pass
