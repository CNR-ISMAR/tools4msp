# coding: utf-8

import numpy as np
import pandas as pd
from os import path, listdir
from .casestudy import CaseStudyBase


class ResponseFunction(object):
    def __init__(self, a=None, k=None, c=1, q=1, b=1, m=1, v=1):
        self.c = float(c)
        self.q = float(q)
        self.b = float(b)
        self.m = float(m)
        self.v = float(v)
        if a is None:
            self.a = self.sf(1) / (self.sf(1) - self.sf(0))
        else:
            self.a = float(a)
        if k is None:
            self.k = self.a*(1-self.sf(0))
        else:
            self.k = float(k)

    def run(self, x):
        return self.a + (self.k - self.a)/self.sf(x)

    def sf(self, x):
        return np.power(self.c + self.q * np.exp(-self.b*(x-self.m)), 1./self.v)


class CEACaseStudy(CaseStudyBase):
    def __init__(self,
                 csdir=None,
                 rundir=None,
                 name='unnamed'):
        """ mscf: multiple stressor combination factor
        """

        columns = ['usecode',
                   'precode',
                   'weight',
                   'distance']
        self.weights = pd.DataFrame(columns=columns)

        columns = ['precode',
                   'envcode',
                   'sensitivity',
                   'nrf',  # nonlinear response factor
                   'srf',  # skewness response factor
        ]
        self.sensitivities = pd.DataFrame(columns=columns)

        self.mscf = {}

        self._labels = None
        super().__init__(csdir=csdir,
                         rundir=rundir,
                         name='unnamed')

    def get_score_stats(self, output_type):
        """
        Collect CEA score statistics from module outputs

        :param output_type: one of the CEA outputs e.g. usepressures, presenvs, usesenvs
        :return: dataframe of CEA score statistics
        """
        outs = self.outputs.get(output_type)
        stats = []
        for (k, l) in outs.items():
            (k1, k2) = k.split('--')
            score = l.sum()
            stats.append({
                'k1': k1,
                'k2': k2,
                'score': float(score)
            })
        return pd.DataFrame(stats)

    def run_pressures(self, uses=None, pressures=None,
                      outputmask=None):
        self.outputs['pressures'] = {}
        self.outputs['usepressures'] = {}
        out_pressures = self.outputs['pressures']
        out_usepressures = self.outputs['usepressures']

        pressures_set = set()
        uses_set = set()

        for idx, w in self.weights.sort_values(['precode']).iterrows():
            if uses is not None and w.usecode not in uses:
                continue
            if pressures is not None and w.precode not in pressures:
                continue
            usecode = w.usecode
            precode = w.precode

            usepresid = "{}--{}".format(usecode, precode)

            _pressure_layer = None

            if usepresid in self.layers.index:
                # print usepresid
                _pressure_layer = self.layers.loc[usepresid, 'layer'].copy()
                # print usecode, precode, usepresid
                _use_layer = None
                # _pressure_layer.norm()
            else:
                _use_layer = self.get_layer(usecode)
                if _use_layer is not None:
                    # convolution
                    _pressure_layer = _use_layer.layer.copy()
                    maxval = _pressure_layer.max()

                    _pressure_layer.gaussian_conv(w.distance / 2., truncate=3.)
                    
                    _pressure_layer = _pressure_layer / _pressure_layer.max() * maxval

            if _pressure_layer is not None:
                pressures_set.add(precode)
                uses_set.add(usecode)
                usepressure = _pressure_layer.copy() * w.weight
                usepressure.mask = self.grid==0
                if out_pressures.get(precode) is None:
                    out_pressures[precode] = usepressure.copy()
                else:
                    out_pressures[precode] += usepressure.copy()
                out_usepressures[usepresid] = usepressure.copy()

        # extract single use contribute



        # filtered_dict = {k:v for (k,v) in d.items() if filter_string in k}
        # Modificare per evitare la normalizzazione nel caso di layer espliciti di pressione
        # for key, op in out_pressures.items():
        #    out_pressures[key] = op.norm()

    def run(self, uses=None, envs=None,
                           outputmask=None, fulloutput=True, pressures=None,
                           cienvs_info=True, ciuses_info=True, cipres_info=True,
                           ciscores_info=True, runtypelevel=3):
        self.runtypelevel = runtypelevel
        self.outputs['presenvs'] = {}
        self.outputs['usesenvs'] = {}
        out_presenvs = self.outputs['presenvs']
        out_usesenvs = self.outputs['usesenvs']
        self.run_pressures(uses=uses,
                           pressures=pressures,
                           outputmask=outputmask)

        ci = np.zeros_like(self.grid)

        for idx, e in self.get_envs().iterrows():
            if envs is not None and idx not in envs:
                continue
            env_layer =  self.get_layer(idx).layer.copy()
            filter = self.sensitivities.envcode == idx
            for idx_sens, sens in self.sensitivities[filter].iterrows():
                presenvsid = "{}--{}".format(sens.precode, idx)
                _p = self.outputs['pressures'].get(sens.precode)
                if _p is not None:
                    pressure_layer = _p.copy()
                    sensarray = pressure_layer * env_layer * sens.sensitivity
                    ci += sensarray
                    if runtypelevel >= 2:
                        out_presenvs[presenvsid] = sensarray.copy()

                # collect information for a single use-env CEA
                # assuming linear interactions
                if runtypelevel >= 3:
                    _sum = 0
                    for usepresid, _up in self.outputs['usepressures'].items():
                        useid, presid = usepresid.split('--')
                        if presid == sens.precode and _up is not None:                        
                            _sum += _up.sum()
                            useenvid = "{}--{}".format(useid, idx)
                            if useenvid not in out_usesenvs:
                                _r = np.zeros_like(self.grid)
                                out_usesenvs[useenvid] = _r
                            out_usesenvs[useenvid] += _up.copy() * env_layer * sens.sensitivity
                            # print("##########")
                            # print(usepresid, useenvid, _up.sum())
                    # print(presenvsid, _p.sum(), _sum)

        self.outputs['ci'] = ci
        return True

    def get_main_output(self):
        """
        This function returns the main model output
        """
        return self.outputs['ci']

    def get_SUA_target(self):
        """
        Returns target value for Sensitivity Analysis
        """
        return self.get_main_output().sum()

    # @property
    # def labels(self):
    #     if self._labels is None:
    #         e = self.sensitivities[['envid', 'envlabel']].copy().drop_duplicates()
    #         u = self.sensitivities[['useid', 'uselabel']].copy().drop_duplicates()
    #         p = self.sensitivities[['presid', 'preslabel']].copy().drop_duplicates()
    #         uw = self.weights[['useid', 'uselabel']].copy().drop_duplicates()
    #         pw = self.weights[['presid', 'preslabel']].copy().drop_duplicates()
    #         e.columns = ['id', 'label']
    #         u.columns = ['id', 'label']
    #         p.columns = ['id', 'label']
    #         uw.columns = ['id', 'label']
    #         pw.columns = ['id', 'label']
    #         self._labels = pd.concat([e, u, p, uw, pw]).drop_duplicates()
    #         self._labels.set_index('id', inplace=True)
    #     return self._labels
    #
    # def get_label(self, id):
    #     labels = self.labels
    #     try:
    #         return labels.loc[id].label
    #     except KeyError:
    #         return None

    # def get_id(self, label):
    #     labels = self.labels
    #     r = labels.index[labels.label.str.contains(label, case=False, regex=False)]
    #     if r.shape[0] != 1:
    #         raise ValueError('Invalid label')
    #     return r[0]

    # def inv_cumulative_impact(self, uses=None, envs=None, outputmask=None,
    #                           fulloutput=True, pressures=None, cioutputmask=None):
    #     # ci = self.domain_area_dataset.copy()
    #     bci = np.zeros_like(self.grid)
    #
    #     for sid, s in self.sensitivities.iterrows():
    #         if uses is not None and s.useid not in uses:
    #             continue
    #         if envs is not None and s.envid not in envs:
    #             continue
    #         if pressures is not None and s.presid not in pressures:
    #             continue
    #
    #         self.cumulative_impact(uses=[s.useid],
    #                                envs=[s.envid],
    #                                outputmask=cioutputmask,
    #                                fulloutput=False,
    #                                pressures=[s.presid])
    #
    #         ci = self.outputs['ci']
    #         ci[ci.mask] = 0
    #         # print s
    #         # print ci.sum()
    #
    #         usepresid = "{}{}".format(s.useid, s.presid)
    #         ispressure = False
    #         if usepresid in self.layers.index:
    #             ispressure = True
    #
    #         _use_layer = self.get_layer(s.useid)
    #         _env_layer = self.get_layer(s.envid)
    #
    #         if not ispressure and _use_layer is not None and _env_layer is not None:
    #             print(s.uselabel, s.envlabel, s.preslabel, s.distance, s.score)
    #             use_layer = _use_layer.layer.copy()
    #             ci.gaussian_conv(s.distance / 2., truncate=3.)
    #
    #             _bci = use_layer * ci * s.score
    #             print(_bci.sum())
    #             if outputmask is not None:
    #                 _bci.mask = outputmask
    #
    #             bci += _bci
    #
    #     self.outputs['bci'] = bci

    # def dump_inputs(self):
    #     self.weights.to_csv(self.get_outpath('weights.csv'))
    #     self.sensitivities.to_csv(self.get_outpath('pres_sensitivities.csv'))
    #     super(CEAMixin, self).dump_inputs()

    def load_inputs(self):
        for f in listdir(self.inputsdir):
            filepath = path.join(self.inputsdir, f)
            fname, ext = path.splitext(f)
            if ext == '.json':
                # remove random file suffix
                fname = fname.split('_')[0]
                if fname == 'cea-WEIGHTS':
                    _df = pd.read_json(filepath)
                    if 'c' not in _df.columns:
                        _df['c'] = np.NaN
                    _df.rename(columns={'u': 'usecode',
                                        'p': 'precode',
                                        'd': 'distance',
                                        'w': 'weight',
                                        'c': 'confidence',
                                        }, inplace=True)
                    self.weights = _df
                elif fname == 'cea-SENS':
                    _df = pd.read_json(filepath)
                    if 'c' not in _df.columns:
                        _df['c'] = np.NaN
                    _df.rename(columns={'e': 'envcode',
                                        'p': 'precode',
                                        's': 'sensitivity',
                                        'c': 'confidence',
                                        }, inplace=True)
                    self.sensitivities = _df

                    if 'nrf' not in self.sensitivities.columns:
                        self.sensitivities['nrf'] = None
                    if 'nrf' not in self.sensitivities.columns:
                        self.sensitivities['srf'] = None

        super().load_inputs()

    def dump_outputs(self):
        if 'ci' in self.outputs:
            self.outputs['ci'].write_raster(self.get_outpath('ci.tiff'), dtype='float32')
        if 'ciuses' in self.outputs:
            for (idx, d) in self.outputs['ciuses'].items():
                d.write_raster(self.get_outpath('ciuse_{}.tiff'.format(idx)), dtype='float32')
        if 'cienvs' in self.outputs:
            for (idx, d) in self.outputs['cienvs'].items():
                d.write_raster(self.get_outpath('cienv_{}.tiff'.format(idx)), dtype='float32')
        if 'ciscores' in self.outputs:
            self.outputs['ciscores'].to_csv(self.get_outpath('ciscores.csv'))
        # self.outputs['ci'] = ci
        # self.outputs['ciuses'] = ciuses
        # self.outputs['cienvs'] = cienvs
        # self.outputs['ciconfidence'] = confidence / ci
        # self.outputs['ciscores'] = scores

        super().dump_outputs()


