# coding: utf-8



import itertools
import numpy as np
import pandas as pd
from os import path
from .casestudy import CaseStudyBase


def coexist_rules(use1conf,
                  use2conf):
    vscale1, spatial1, time1, mobility1 = use1conf
    vscale2, spatial2, time2, mobility2 = use2conf

    # Rule 1
    if vscale1 != 3 and vscale2 != 3 and vscale1 != vscale2:
        return 0
    # Rule 2
    if mobility1 and mobility2:
        return min(spatial1, spatial2) + min(time1, time2)
    # Rule 3
    return max(spatial1, spatial2) + max(time1, time2)


class MUCCaseStudy(CaseStudyBase):
    def __init__(self,
                 csdir=None,
                 rundir=None,
                 name='unnamed'):

        self.potential_conflict_scores = pd.DataFrame()
        super().__init__(csdir=csdir,
                         rundir=rundir,
                         name='unnamed')

    def get_potential_conflict_score(self, use1id, use2id):
        return self.potential_conflict_scores.loc[use1id, use2id]

    def run(self, uses=None, intensity=False, outputmask=None):
        couses_data = []
        coexist = np.zeros_like(self.grid)
        alluses_iter = self.get_uses().iterrows()
        for _use1, _use2 in itertools.combinations(alluses_iter, 2):
            use1id, use1 = _use1
            use2id, use2 = _use2

            if uses is not None and use1id not in uses and use2id not in uses:
                continue

            score = self.get_potential_conflict_score(use1id, use2id)
            if intensity:
                l1 = use1.layer
                l2 = use2.layer
            else:
                l1 = use1.layer.copy()
                l2 = use2.layer.copy()
                # check mask to avoid unmask on assignment
                l1[~(l1.mask) & (l1 > 0)] = 1
                l2[~(l2.mask) & (l2 > 0)] = 1
            _score = l1 * l2 * score
            l1.mask = self.grid.mask
            l2.mask = self.grid.mask
            if outputmask is not None:
                _score.mask = outputmask

            coexist += _score

            couses_data.append([use1.code,
                                use2.code,
                                _score.sum(),
                                _score[_score > 0].count()
                            ])
            # couses_data.append([use2.label,
            #                     use1.label,
            #                     _score.sum()])
        couses_df = pd.DataFrame(couses_data, columns=['use1', 'use2', 'score',
                                                       'ncells'])
        couses_df.score = couses_df.score.astype(float)
        self.outputs['coexist'] = coexist
        self.outputs['coexist_couses_df'] = couses_df
        return True
    #
    # def dump_inputs(self):
    #     self.coexist_scores.to_csv(self.get_outpath('coexist_scores.csv'))

    def load_inputs(self):
        fpath = path.join(self.inputsdir, 'muc-PCONFLICT.json')
        if path.isfile(fpath):
            df = pd.read_json(fpath)
            _df = df.copy()
            _df.columns = ['score', 'u2', 'u1']
            df = pd.concat([df, _df], ignore_index=True, sort=False)
            df = df.pivot('u1', 'u2', values='score')
            ordered = sorted(df.columns)
            df = df.reindex(ordered, axis=1)
            self.potential_conflict_scores = df

    def dump_outputs(self):
        if 'coexist' in self.outputs:
            self.outputs['coexist'].write_raster(self.get_outpath('coexist.tiff'), dtype='float32')
        if 'coexist_couses_df' in self.outputs:
            self.outputs['coexist_couses_df'].to_csv(self.get_outpath('coexist_couses_df.csv'))
