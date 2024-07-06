# coding: utf-8

import logging
import itertools
import numpy as np
import pandas as pd
from os import path
from os import path, listdir
from .casestudy import CaseStudyBase

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

TESTPARAMS = [
      {
              "value": 3,
              "paramtype": "DEFAULT",
              "paramname": "TBB",
              "_type": "number",
              "_min": 0,
              "_max": 10
            },
      {
              "value": 1.0,
              "paramtype": "DEFAULT",
              "paramname": "OTB",
              "_type": "number"
            },
      {
              "value": 1,
              "paramtype": "DEFAULT",
              "paramname": "SSF",
              "_type": 'select',
              "_options": [
                  [1, 'Bottom layer'],
                  [2, 'Surface layer'],
                  [3, 'Entire water column']
              ]
            },
      {
              "value": "lba",
              "paramtype": "DEFAULT",
              "paramname": "LBA",
              "_type": "text"
            },
      {
              "value": 'medium',
              "paramtype": "DEFAULT",
              "paramname": "TMAR",
              "_type": "select",
              "_options": [
                  ['low', 'Low'],
                  ['medium', 'Medium'],
                  ['high', 'High']
              ]
            }
    ]

class TESTCaseStudy(CaseStudyBase):
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

    def run(self, uses=None, intensity=False, outputmask=None, pivot_layer=None):
        self.outputs['testmodule_result'] = {'success': True}
        return True
    #
    # def dump_inputs(self):
    #     self.coexist_scores.to_csv(self.get_outpath('coexist_scores.csv'))

    def load_inputs(self):
        pass
    
    def dump_outputs(self):
        pass
