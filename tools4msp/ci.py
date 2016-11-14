# coding: utf-8

from __future__ import absolute_import

import itertools
import numpy as np
import pandas as pd


class CumulativeImpactMixin(object):
    def __init__(self, grid, basedir=None,
                 name='unnamed', version='v1', rtype='full'):
        columns = ['useid', 'uselabel',
                   'envid', 'envlabel',
                   'presid', 'preslabel',
                   'score', 'distance', 'confidence']
        self.sensitivities = pd.DataFrame(columns=columns)
        super(CumulativeImpactMixin, self).__init__(grid, basedir=basedir,
                                                    name='unnamed',
                                                    version='v1', rtype='full')

    def add_sensitivity(self, useid, uselabel, envid, envlabel,
                        presid, preslabel, score, dist, conf):
        sid = self.sensitivities.shape[0]
        self.sensitivities.loc[sid] = (useid, uselabel, envid, envlabel,
                                       presid, preslabel, score, dist, conf)

    def cumulative_impact(self, uses=None, envs=None, outputmask=None, fulloutput=True):
        # ci = self.grid.copy()
        ci = np.zeros_like(self.grid)
        confidence = np.zeros_like(self.grid)
        ciuses = {}
        cienvs = {}
        _scores = []

        for sid, s in self.sensitivities.iterrows():
            if uses is not None and s.useid not in uses:
                continue
            if envs is not None and s.envid not in envs:
                continue

            _use_layer = self.get_layer(s.useid)
            _env_layer = self.get_layer(s.envid)

            if _use_layer is not None and _env_layer is not None:
                max_value = _use_layer.layer.max()
                use_layer = _use_layer.layer.copy()
                env_layer = _env_layer.layer.copy()
                # convolution
                use_layer.gaussian_filter(s.distance / self.grid.resolution / 2., truncate=3.)
                if use_layer.max() != 0.: # TODO spostare il controllo nella funzione norm()
                    use_layer = use_layer.norm() * max_value
                # li passo già sistemati così ho più controllo
                # use_layer.lognorm()
                # use_layer.norm()

                # env_layer.norm()

                sensarray = use_layer * env_layer * s.score
                if outputmask is not None:
                    sensarray.mask = outputmask
                ci += sensarray

                if fulloutput:
                    _confidence = sensarray * s.confidence

                    if _use_layer.lid not in ciuses:
                        ciuses[_use_layer.lid] = sensarray.copy()
                    else:
                        ciuses[_use_layer.lid] += sensarray

                    if _env_layer.lid not in cienvs:
                        cienvs[_env_layer.lid] = sensarray.copy()
                    else:
                        cienvs[_env_layer.lid] += sensarray

                    # results['nsens'][sensarray > 0] += 1
                    confidence += _confidence

                    _scores.append([s.useid, s.uselabel,
                                    s.envid, s.envlabel,
                                    s.presid, s.preslabel,
                                    sensarray.sum(),
                                    s.confidence
                                ])

        if fulloutput:
            scores = pd.DataFrame(_scores, columns=['useid', 'uselabel',
                                                    'envid', 'envlabel',
                                                    'presid', 'preslabel',
                                                    'score', 'confidence'])
        if fulloutput:
            self.outputs['ci'] = ci
            self.outputs['ciuses'] = ciuses
            self.outputs['cienvs'] = cienvs
            self.outputs['ciconfidence'] = confidence / ci
            self.outputs['ciscores'] = scores
            return True
        else:
            self.outputs['ci'] = ci
            return True

    def inv_cumulative_impact(self, uses=None, envs=None, outputmask=None,
                              envmask=None, fulloutput=True):
        # ci = self.grid.copy()
        ci = np.zeros_like(self.grid)
        confidence = np.zeros_like(self.grid)
        ciuses = {}
        cienvs = {}
        _scores = []

        for sid, s in self.sensitivities.iterrows():
            if uses is not None and s.useid not in uses:
                continue
            if envs is not None and s.envid not in envs:
                continue

            _use_layer = self.get_layer(s.useid)
            _env_layer = self.get_layer(s.envid)

            if _use_layer is not None and _env_layer is not None:
                max_value = _use_layer.layer.max()
                use_layer = _use_layer.layer.copy()
                env_layer = _env_layer.layer.copy()
                if envmask is not None:
                    env_layer[envmask] = 0
                use_layer_convolution = use_layer.copy()
                use_layer_convolution.gaussian_filter(s.distance / self.grid.resolution / 2., truncate=3.)
                max_use_convolution = use_layer_convolution.max()
                # convolution
                env_layer.gaussian_filter(s.distance / self.grid.resolution / 2., truncate=3.)
                # TODO: da rivedere la noramlizzazione perché andava bene per gli usi
                if env_layer.max() != 0.: # TODO spostare il controllo nella funzione norm()
                    env_layer = (env_layer / max_use_convolution) * max_value
                # li passo già sistemati così ho più controllo
                # use_layer.lognorm()
                # use_layer.norm()

                # env_layer.norm()

                sensarray = use_layer * env_layer * s.score
                if outputmask is not None:
                    sensarray.mask = outputmask
                ci += sensarray

                if fulloutput:
                    _confidence = sensarray * s.confidence

                    if _use_layer.lid not in ciuses:
                        ciuses[_use_layer.lid] = sensarray.copy()
                    else:
                        ciuses[_use_layer.lid] += sensarray

                    if _env_layer.lid not in cienvs:
                        cienvs[_env_layer.lid] = sensarray.copy()
                    else:
                        cienvs[_env_layer.lid] += sensarray

                    # results['nsens'][sensarray > 0] += 1
                    confidence += _confidence

                    _scores.append([s.useid, s.uselabel,
                                    s.envid, s.envlabel,
                                    s.presid, s.preslabel,
                                    sensarray.sum(),
                                    s.confidence
                                ])

        if fulloutput:
            scores = pd.DataFrame(_scores, columns=['useid', 'uselabel',
                                                    'envid', 'envlabel',
                                                    'presid', 'preslabel',
                                                    'score', 'confidence'])
        if fulloutput:
            return ci, ciuses, cienvs, confidence / ci, scores
        else:
            return ci

    def dump_inputs(self):
        self.sensitivities.to_csv(self.get_outpath('cisensitivities.csv'))
        super(CumulativeImpactMixin, self).dump_inputs()

    def load_inputs(self):
        try:
            self.sensitivities = pd.DataFrame.from_csv(self.get_outpath('cisensitivities.csv'))
        except IOError:
            self.sensitivities = pd.DataFrame.from_csv(self.get_outpath('cisensitivities.csv', rtype='full'))
        super(CumulativeImpactMixin, self).load_inputs()

    def dump_outputs(self):
        if 'ci' in self.outputs:
            self.outputs['ci'].write_raster(self.get_outpath('ci.tiff'))
        if 'ciuses' in self.outputs:
            for (idx, d) in self.outputs['ciuses'].iteritems():
                d.write_raster(self.get_outpath('ciuse_{}.tiff'.format(idx)))
        if 'cienvs' in self.outputs:
            for (idx, d) in self.outputs['cienvs'].iteritems():
                d.write_raster(self.get_outpath('cienv_{}.tiff'.format(idx)))
        if 'ciscores' in self.outputs:
            self.outputs['ciscores'].to_csv(self.get_outpath('ciscores.csv'))
        # self.outputs['ci'] = ci
        # self.outputs['ciuses'] = ciuses
        # self.outputs['cienvs'] = cienvs
        # self.outputs['ciconfidence'] = confidence / ci
        # self.outputs['ciscores'] = scores

        super(CumulativeImpactMixin, self).dump_outputs()
