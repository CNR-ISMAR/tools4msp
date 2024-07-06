# coding: utf-8

import logging
import itertools
import numpy as np
import pandas as pd
import geopandas as gpd
from os import path, listdir, mkdir
from .casestudy import CaseStudyBase, aggregate_layers_to_gdf
import tempfile
from pathlib import Path
import random
import json
import subprocess
import rectifiedgrid as rg
from PIL import Image
from shapely.geometry import Polygon
from rasterstats import zonal_stats, point_query

logger = logging.getLogger(__name__)

class GeoDataMakerCaseStudy(CaseStudyBase):
    def __init__(self,
                 csdir=None,
                 rundir=None,
                 name='unnamed'):

        # self.potential_conflict_scores = pd.DataFrame()
        super().__init__(csdir=csdir,
                         rundir=rundir,
                         name='unnamed')

    def run(self, selected_layers=None, runtypelevel=3):
        
        if selected_layers is not None:
            # GRID must be included into the selected layer
            _filter = self.layers.index.isin(selected_layers + ['GRID'])
            layers = self.layers[_filter].copy()
        else:
            layers = self.layers.copy()
                                        
        self.outputs['layers'] = layers
        self.outputs['aggregated_gdf'] = aggregate_layers_to_gdf({code: l['layer'] for code, l in layers.iterrows()}, melt=True)
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
