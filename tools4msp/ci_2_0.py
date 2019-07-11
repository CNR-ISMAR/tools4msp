# coding: utf-8



import itertools
import numpy as np
import pandas as pd


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


class CumulativeImpactMixin(object):
    def __init__(self, grid, basedir=None,
                 name='unnamed', version='v1', rtype='full',
                 mscf=0.):
        """ mscf: multiple stressor combination factor
        """
        columns = ['useid', 'uselabel',
                   'envid', 'envlabel',
                   'presid', 'preslabel',
                   'score', 'distance', 'confidence'
                   'nrf',  # nonlinear response factor
                   'srf',  # skewness response factor
        ]
        self.sensitivities = pd.DataFrame(columns=columns)

        columns = ['useid', 'uselabel',
                   'presid', 'preslabel',
                   'layer'
        ]
        self.pressures = pd.DataFrame(columns=columns)

        self.mscf = mscf

        super(CumulativeImpactMixin, self).__init__(grid, basedir=basedir,
                                                    name='unnamed',
                                                    version='v1', rtype='full')

    def add_sensitivity(self, useid, uselabel, envid, envlabel,
                        presid, preslabel, score, dist, conf,
                        nrf=None, srf=None):
        sid = self.sensitivities.shape[0]
        self.sensitivities.loc[sid] = (useid, uselabel, envid, envlabel,
                                       presid, preslabel, score, dist, conf,
                                       nrf, srf)

    def cumulative_impact(self, uses=None, envs=None,
                          outputmask=None, fulloutput=True):
        # ci = self.domain_area_dataset.copy()
        ci = np.zeros_like(self.grid)
        cimax = np.zeros_like(self.grid)
        confidence = np.zeros_like(self.grid)
        ciuses = {}
        cienvs = {}
        cipres = {}
        _scores = []

        for sid, s in self.sensitivities.iterrows():
            if uses is not None and s.useid not in uses:
                continue
            if envs is not None and s.envid not in envs:
                continue

            useid = s.useid
            presid = s.presid
            usepresid = "{}{}".format(useid, presid)

            ispressure = False

            if usepresid in self.pressures.index:
                # print usepresid
                _pressure_layer = self.pressures.loc[usepresid, 'layer']
                _use_layer = None
                ispressure = True
            else:
                _pressure_layer = None
                _use_layer = self.get_layer(useid)

            _env_layer = self.get_layer(s.envid)

            if (_use_layer is not None or _pressure_layer is not None) and _env_layer is not None:
                env_layer = _env_layer.layer.copy()

                if not ispressure:
                    # convolution
                    max_value = _use_layer.layer.max()
                    pressure_layer = _use_layer.layer.copy()
                    pressure_layer.gaussian_conv(s.distance / 2., truncate=3.)
                    if pressure_layer.max() != 0.: # TODO spostare il controllo nella funzione norm()
                        pressure_layer = pressure_layer.norm() * max_value
                    # li passo già sistemati così ho più controllo
                    # use_layer.lognorm()
                    # use_layer.norm()

                    # env_layer.norm()
                else:
                    # print "Using a pressure layer"
                    pressure_layer = _pressure_layer.copy()

                rfunc = None
                if s.nrf is not None and s.srf is not None:
                    rfunc = ResponseFunction(v=1, m=s.srf, b=s.nrf, q=1)
                if rfunc is not None:
                    # print '\nRFUNC'
                    # print s.nrf, s.srf
                    # print np.mean(use_layer), np.mean(rfunc.run(use_layer))
                    # print np.std(use_layer), np.std(rfunc.run(use_layer))
                    # print np.sum(use_layer), np.sum(rfunc.run(use_layer))
                    # print np.min(use_layer), np.min(rfunc.run(use_layer))
                    # print np.max(use_layer), np.max(rfunc.run(use_layer))
                    sensarray = rfunc.run(pressure_layer) * env_layer * s.score
                else:
                    sensarray = pressure_layer * env_layer * s.score
                if outputmask is not None:
                    sensarray.mask = outputmask
                ci += sensarray
                cimax = np.fmax(cimax, sensarray)
                if fulloutput:
                    _confidence = sensarray * s.confidence

                    if useid not in ciuses:
                        ciuses[useid] = sensarray.copy()
                    else:
                        ciuses[useid] += sensarray

                    if _env_layer.lid not in cienvs:
                        cienvs[_env_layer.lid] = sensarray.copy()
                    else:
                        cienvs[_env_layer.lid] += sensarray

                    if presid not in cipres:
                        cipres[presid] = sensarray.copy()
                    else:
                        cipres[presid] += sensarray

                    # results['nsens'][sensarray > 0] += 1
                    confidence += _confidence

                    _scores.append([useid, s.uselabel,
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

        if self.mscf is not None:
            self.outputs['ci'] = ci * (1. - self.mscf) + cimax * self.mscf
        else:
            self.outputs['ci'] = ci
        if fulloutput:
            self.outputs['ciuses'] = ciuses
            self.outputs['cienvs'] = cienvs
            self.outputs['cipres'] = cipres
            self.outputs['ciconfidence'] = confidence / ci
            self.outputs['ciscores'] = scores
            self.outputs['cimax'] = cimax
        return True

    def inv_cumulative_impact(self, uses=None, envs=None, outputmask=None,
                              envmask=None, fulloutput=True):
        # ci = self.domain_area_dataset.copy()
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
                use_layer_convolution.gaussian_conv(s.distance / 2., truncate=3.)
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
        if 'nrf' not in self.sensitivities.columns:
            self.sensitivities['nrf'] = None
        if 'nrf' not in self.sensitivities.columns:
            self.sensitivities['srf'] = None

        super(CumulativeImpactMixin, self).load_inputs()

    def dump_outputs(self):
        if 'ci' in self.outputs:
            self.outputs['ci'].write_raster(self.get_outpath('ci.tiff'))
        if 'ciuses' in self.outputs:
            for (idx, d) in self.outputs['ciuses'].items():
                d.write_raster(self.get_outpath('ciuse_{}.tiff'.format(idx)))
        if 'cienvs' in self.outputs:
            for (idx, d) in self.outputs['cienvs'].items():
                d.write_raster(self.get_outpath('cienv_{}.tiff'.format(idx)))
        if 'ciscores' in self.outputs:
            self.outputs['ciscores'].to_csv(self.get_outpath('ciscores.csv'))
        # self.outputs['ci'] = ci
        # self.outputs['ciuses'] = ciuses
        # self.outputs['cienvs'] = cienvs
        # self.outputs['ciconfidence'] = confidence / ci
        # self.outputs['ciscores'] = scores

        super(CumulativeImpactMixin, self).dump_outputs()
