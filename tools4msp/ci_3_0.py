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
                 mscf=None):
        """ mscf: multiple stressor combination factor
        """
        columns = ['useid', 'uselabel',
                   'envid', 'envlabel',
                   'presid', 'preslabel',
                   'score', 'distance', 'confidence',
                   'nrf',  # nonlinear response factor
                   'srf',  # skewness response factor
                  ]
        self.sensitivities = pd.DataFrame(columns=columns)

        columns = ['useid', 'uselabel',
                   'presid', 'preslabel',
                   'weight', 'distance']
        self.weights = pd.DataFrame(columns=columns)

        columns = ['presid', 'preslabel',
                   'envid', 'envlabel',
                   'sensitivity',
                   'nrf',  # nonlinear response factor
                   'srf',  # skewness response factor
        ]
        self.pres_sensitivities = pd.DataFrame(columns=columns)

        columns = ['useid', 'uselabel',
                   'presid', 'preslabel',
                   'layer'
        ]
        self.pressures = pd.DataFrame(columns=columns)

        if mscf is None:
            mscf = {}
        self.mscf = mscf

        self._labels = None
        super(CumulativeImpactMixin, self).__init__(grid, basedir=basedir,
                                                    name='unnamed',
                                                    version='v1', rtype='full')

    def add_weights(self, useid, uselabel, presid, preslabel,
                    weight, distance):
        sid = self.weights.shape[0]
        self.weights.loc[sid] = (useid, uselabel, presid, preslabel,
                                 weight, distance)

    def add_pres_sensitivities(self, presid, preslabel, envid, envlabel,
                               sensitivity, nrf=None, srf=None):
        sid = self.pres_sensitivities.shape[0]
        self.pres_sensitivities.loc[sid] = (presid, preslabel,
                                            envid, envlabel,
                                            sensitivity,
                                            nrf, srf)

    def add_sensitivity(self, useid, uselabel, envid, envlabel,
                        presid, preslabel, score, dist, conf,
                        nrf=None, srf=None):
        sid = self.sensitivities.shape[0]
        self.sensitivities.loc[sid] = (useid, uselabel, envid, envlabel,
                                       presid, preslabel, score, dist, conf,
                                       nrf, srf)

    def run_pressures(self, uses=None, pressures=None,
                      outputmask=None):
        self.outputs['pressures'] = {}
        self.outputs['usepressures'] = {}
        out_pressures = self.outputs['pressures']
        out_usepressures = self.outputs['usepressures']

        pressures_set = set()
        uses_set = set()

        for idx, w in self.weights.sort_values(['presid']).iterrows():
            if uses is not None and w.useid not in uses:
                continue
            if pressures is not None and w.presid not in pressures:
                continue
            useid = w.useid
            presid = w.presid

            usepresid = "{}{}".format(useid, presid)

            _pressure_layer = None

            if usepresid in self.layers.index:
                # print usepresid
                _pressure_layer = self.layers.loc[usepresid, 'layer'].copy()
                # print useid, presid, usepresid
                _use_layer = None
                _pressure_layer.norm()
            else:
                _use_layer = self.get_layer(useid)
                if _use_layer is not None:
                    # convolution
                    _pressure_layer = _use_layer.layer.copy()

                    _pressure_layer.gaussian_conv(w.distance / 2., truncate=3.)
                    _pressure_layer.norm()

            if _pressure_layer is not None:
                pressures_set.add(presid)
                uses_set.add(useid)
                usepressure = _pressure_layer.copy() * w.weight
                if out_pressures.get(presid) is None:
                    out_pressures[presid] = usepressure
                else:
                    out_pressures[presid] += usepressure

                out_usepressures[usepresid] = usepressure

        # extract single use contribute



        # filtered_dict = {k:v for (k,v) in d.items() if filter_string in k}

        # for key, op in out_pressures.iteritems():
        #     out_pressures[key] = op.norm()

    def cumulative_impact3(self, uses=None, envs=None,
                           outputmask=None, fulloutput=True, pressures=None,
                           cienvs_info=True, ciuses_info=True, cipres_info=True,
                           ciscores_info=True):
        self.run_pressures(uses=uses,
                           pressures=pressures,
                           outputmask=outputmask)

        ci = np.zeros_like(self.grid)

        for idx, e in self.get_envs().iterrows():
            if envs is not None and idx not in envs:
                continue
            env_layer =  self.get_layer(idx).layer.copy()
            filter = self.pres_sensitivities.envid==idx
            for idx_sens, sens in self.pres_sensitivities[filter].iterrows():
                _p = self.outputs['pressures'].get(sens.presid)
                if _p is not None:
                    pressure_layer = _p.copy()
                    sensarray = pressure_layer * env_layer * sens.sensitivity
                    ci += sensarray

        self.outputs['ci'] = ci
        return True

    def cumulative_impact(self, uses=None, envs=None,
                          outputmask=None, fulloutput=True, pressures=None,
                          cienvs_info=True, ciuses_info=True, cipres_info=True,
                          ciscores_info=True):
        self.cienvs_info = cienvs_info
        self.ciuses_info = ciuses_info
        self.cipres_info = cipres_info
        self.ciscores_info = ciscores_info
        # confidence = np.zeros_like(self.domain_area_dataset)
        self.outputs['cienvs'] = {}
        self.outputs['cipres'] = {}
        self.outputs['ciuses'] = {}
        self.outputs['ciscores'] = []

        prev_env = None
        cur_env = None
        prev_pres = None
        cur_pres = None

        cienv_cur_pres = np.zeros_like(self.grid)
        cienv_dominant = np.zeros_like(self.grid)
        cienv_dominant_pid = np.zeros(self.grid.shape,
                                      dtype='S6')
        cienv_additive = np.zeros_like(self.grid)
        cienv_pressures = {}
        # cienv_uses = {}
        cienv_pressures_uses = {}

        for sid, s in self.sensitivities.sort_values(['envid', 'presid']).iterrows():
            if uses is not None and s.useid not in uses:
                continue
            if envs is not None and s.envid not in envs:
                continue
            if pressures is not None and s.presid not in pressures:
                continue

            # print sid
            useid = s.useid
            presid = s.presid
            envid = s.envid
            usepresid = "{}{}".format(useid, presid)

            ispressure = False

            # save previous values
            prev_env = cur_env
            prev_pres = cur_pres

            # set new values
            cur_env = s.envid
            cur_pres = s.presid

            if (cur_env != prev_env or cur_pres != prev_pres) and prev_pres is not None:
                cienv_pressures[prev_pres] = cienv_cur_pres
                self.apply_pressure(cienv_dominant, cienv_dominant_pid,
                                    cienv_additive, prev_pres,
                                    cienv_cur_pres)

                # reset arrays
                cienv_cur_pres = np.zeros_like(self.grid)

            if cur_env != prev_env and prev_env is not None:
                self.apply_env(prev_env, cienv_dominant, cienv_dominant_pid,
                               cienv_additive, cienv_pressures, cienv_pressures_uses)
                # reset arrays
                cienv_dominant = np.zeros_like(self.grid)
                cienv_dominant_pid = np.zeros(self.grid.shape,
                                              dtype='S6')
                cienv_additive = np.zeros_like(self.grid)
                cienv_pressures = {}
                cienv_uses = {}
                cienv_pressures_uses = {}

            if usepresid in self.layers.index:
                # print usepresid
                _pressure_layer = self.layers.loc[usepresid, 'layer']
                # print useid, presid, usepresid
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
                else:
                    # print "Using a pressure layer"
                    pressure_layer = _pressure_layer.copy()

                rfunc = None
                if s.nrf is not None and not np.isnan(s.nrf) and s.srf is not None and not np.isnan(s.srf):
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

                # sum uses contributions over pressure and env
                cienv_cur_pres += sensarray
                # print envid, useid, presid, sensarray.sum(), cienv_cur_pres.sum()

                if self.ciuses_info:
                    if presid not in cienv_pressures_uses:
                        cienv_pressures_uses[presid] = {}
                    if useid not in cienv_pressures_uses[presid]:
                        cienv_pressures_uses[presid][useid] = sensarray

                    # if useid not in cienv_uses:
                    #     cienv_uses[useid] = {}
                    #     cienv_uses[useid] = np.zeros_like(self.domain_area_dataset)
                    # cienv_uses[useid] += sensarray

                # TODO: calcolare il contributo per singolo uso
                # cienvsdominant_uid[_env_layer.lid] = np.zeros(self.domain_area_dataset.shape,
                #                                         dtype='S6')
                # cienvsdominant_uid[_env_layer.lid][:] = useid
                # #
                # cienvsdominant_uid[_env_layer.lid][sensarray > cienvsdominant[_env_layer.lid]] = useid

                # TODO: verificare se si vuole calcolare la confidence
                # if fulloutput:
                #     _confidence = sensarray * s.confidence

                #     # if useid not in ciuses:
                #     #     ciuses[useid] = sensarray.copy()
                #     # else:
                #     #     ciuses[useid] += sensarray

                #     # if presid not in cipres:
                #     #     cipres[presid] = sensarray.copy()
                #     # else:
                #     #     cipres[presid] += sensarray

                #     # if envid not in cienvs:
                #     #    cienvs[envid] = sensarray.copy()
                #     # else:
                #     #    cienvs[envid] += sensarray

                #     # results['nsens'][sensarray > 0] += 1
                #     confidence += _confidence

                #     _scores.append([useid, s.uselabel,
                #                     envid, s.envlabel,
                #                     presid, s.preslabel,
                #                     sensarray.sum(),
                #                     s.confidence
                #                 ])

        # apply last env - pressure
        cienv_pressures[cur_pres] = cienv_cur_pres
        self.apply_pressure(cienv_dominant, cienv_dominant_pid,
                            cienv_additive, cur_pres,
                            cienv_cur_pres)
        self.apply_env(cur_env, cienv_dominant, cienv_dominant_pid,
                       cienv_additive, cienv_pressures, cienv_pressures_uses)

        # global CI computation
        ci = np.zeros_like(self.grid)
        for k, e in self.outputs['cienvs'].items():
            ci += e

            # for uk, u in ciuses.iteritems():
            #     _ciuses = np.zeros_like(self.domain_area_dataset)
            #     # for k, a in cienvs.iteritems():
            #     #     _cienvsdominant = cienvsdominant[k]
            #     #     _cienvsdominant_uid = cienvsdominant_uid[k]
            #     #     _ciuses[_cienvsdominant_uid == uk] += _cienvsdominant[_cienvsdominant_uid == uk]
            #     # ciuses[uk] = u * (1. - self.mscf) + _ciuses * self.mscf

        self.outputs['ci'] = ci

        # TODO: compute scores
        # if fulloutput:
        #     scores = pd.DataFrame(_scores, columns=['useid', 'uselabel',
        #                                             'envid', 'envlabel',
        #                                             'presid', 'preslabel',
        #                                             'score', 'confidence'])
        #     # self.outputs['ciuses'] = ciuses
        #     # self.outputs['cienvs'] = cienvs
        #     # self.outputs['cipres'] = cipres
        #     # self.outputs['ciconfidence'] = confidence / ci
        #     self.outputs['ciscores'] = scores
        #     # self.outputs['cimax'] = cimax
        #     # self.outputs['cienvsdominant_uid'] = cienvsdominant_uid
        #     # self.outputs['cienvsdominant_pid'] = cienvsdominant_pid
        #     # self.outputs['cienvsdominant'] = cienvsdominant

        if not self.cienvs_info:
            ci['cienvs'] = None

        if self.ciscores_info:
            ciscores = self.outputs['ciscores']
            ciscores = pd.DataFrame(ciscores, columns=['useid', 'uselabel',
                                                             'envid', 'envlabel',
                                                             'presid', 'preslabel',
                                                             'score', 'confidence'])
            self.outputs['ciscores'] = ciscores

        self.outputs['ciconfidence'] = np.zeros_like(self.grid)
        return True

    def apply_pressure(self, cienv_dominant, cienv_dominant_pid,
                       cienv_additive, prev_pres,
                       cienv_cur_pres):

        cienv_dominant_pid[prev_pres > cienv_dominant] = prev_pres
        cienv_dominant = np.fmax(cienv_dominant, cienv_cur_pres)
        cienv_additive += cienv_cur_pres

    def apply_env(self, envid, cienv_dominant, cienv_dominant_pid,
                  cienv_additive, cienv_pressures, cienv_pressures_uses):
        cienvs = self.outputs['cienvs']
        if envid not in cienvs:
            cienvs[envid] = np.zeros_like(self.grid)
        mscf = self.mscf.get(envid, 0)
        cienvs[envid] = cienv_additive * (1. - mscf) \
                        + cienv_dominant * mscf

        # print "envid", envid, cienvs[envid].sum()

        if self.cipres_info:
            cipres = self.outputs['cipres']
            for pid, p in cienv_pressures.items():
                if pid not in cipres:
                    cipres[pid] = np.zeros_like(self.grid)

                _cipres = np.zeros_like(self.grid)
                _cipres[cienv_dominant_pid == pid] += cienv_dominant[cienv_dominant_pid == pid]

                _cipres_env = p * (1. - mscf) + _cipres * mscf
                cipres[pid] += _cipres_env

        if self.ciuses_info:
            ciuses = self.outputs['ciuses']
            for pid, udict in cienv_pressures_uses.items():
                for uid, u in udict.items():
                    _ciuse = np.zeros_like(self.grid)
                    _ciuse[cienv_dominant_pid == pid] += u[cienv_dominant_pid == pid]
                    _ciuse_env_pres = u * (1. - mscf) + _ciuse * mscf
                    self.outputs['ciscores'].append([uid, self.get_label(uid),
                                                   envid, self.get_label(envid),
                                                   pid, self.get_label(pid),
                                                   _ciuse_env_pres.sum(),
                                                   0])

                    if uid not in ciuses:
                        ciuses[uid] = np.zeros_like(self.grid)
                    ciuses[uid] += _ciuse_env_pres

    @property
    def labels(self):
        if self._labels is None:
            e = self.sensitivities[['envid', 'envlabel']].copy().drop_duplicates()
            u = self.sensitivities[['useid', 'uselabel']].copy().drop_duplicates()
            p = self.sensitivities[['presid', 'preslabel']].copy().drop_duplicates()
            uw = self.weights[['useid', 'uselabel']].copy().drop_duplicates()
            pw = self.weights[['presid', 'preslabel']].copy().drop_duplicates()
            e.columns = ['id', 'label']
            u.columns = ['id', 'label']
            p.columns = ['id', 'label']
            uw.columns = ['id', 'label']
            pw.columns = ['id', 'label']
            self._labels = pd.concat([e, u, p, uw, pw]).drop_duplicates()
            self._labels.set_index('id', inplace=True)
        return self._labels

    def get_label(self, id):
        labels = self.labels
        try:
            return labels.loc[id].label
        except KeyError:
            return None

    def get_id(self, label):
        labels = self.labels
        r = labels.index[labels.label.str.contains(label, case=False, regex=False)]
        if r.shape[0] != 1:
            raise ValueError('Invalid label')
        return r[0]

    def inv_cumulative_impact(self, uses=None, envs=None, outputmask=None,
                              fulloutput=True, pressures=None, cioutputmask=None):
        # ci = self.domain_area_dataset.copy()
        bci = np.zeros_like(self.grid)

        for sid, s in self.sensitivities.iterrows():
            if uses is not None and s.useid not in uses:
                continue
            if envs is not None and s.envid not in envs:
                continue
            if pressures is not None and s.presid not in pressures:
                continue

            self.cumulative_impact(uses=[s.useid],
                                   envs=[s.envid],
                                   outputmask=cioutputmask,
                                   fulloutput=False,
                                   pressures=[s.presid])

            ci = self.outputs['ci']
            ci[ci.mask] = 0
            # print s
            # print ci.sum()

            usepresid = "{}{}".format(s.useid, s.presid)
            ispressure = False
            if usepresid in self.layers.index:
                ispressure = True

            _use_layer = self.get_layer(s.useid)
            _env_layer = self.get_layer(s.envid)

            if not ispressure and _use_layer is not None and _env_layer is not None:
                print(s.uselabel, s.envlabel, s.preslabel, s.distance, s.score)
                use_layer = _use_layer.layer.copy()
                ci.gaussian_conv(s.distance / 2., truncate=3.)

                _bci = use_layer * ci * s.score
                print(_bci.sum())
                if outputmask is not None:
                    _bci.mask = outputmask

                bci += _bci

        self.outputs['bci'] = bci

    def dump_inputs(self):
        self.sensitivities.to_csv(self.get_outpath('cisensitivities.csv'))
        self.weights.to_csv(self.get_outpath('weights.csv'))
        self.pres_sensitivities.to_csv(self.get_outpath('pres_sensitivities.csv'))
        super(CumulativeImpactMixin, self).dump_inputs()

    def load_inputs(self):
        try:
            self.weights = pd.read_csv(self.get_outpath('weights.csv'), index_col=0)
        except IOError:
            self.weights = pd.read_csv(self.get_outpath('weights.csv', rtype='full'), index_col=0)
        try:
            self.pres_sensitivities = pd.read_csv(self.get_outpath('pres_sensitivities.csv'), index_col=0)
        except IOError:
            self.pres_sensitivities = pd.read_csv(self.get_outpath('pres_sensitivities.csv', rtype='full'), index_col=0)

        try:
            self.sensitivities = pd.read_csv(self.get_outpath('cisensitivities.csv'), index_col=0)
        except IOError:
            self.sensitivities = pd.read_csv(self.get_outpath('cisensitivities.csv', rtype='full'), index_col=0)
        if 'nrf' not in self.sensitivities.columns:
            self.sensitivities['nrf'] = None
        if 'nrf' not in self.sensitivities.columns:
            self.sensitivities['srf'] = None

        super(CumulativeImpactMixin, self).load_inputs()

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

        super(CumulativeImpactMixin, self).dump_outputs()
