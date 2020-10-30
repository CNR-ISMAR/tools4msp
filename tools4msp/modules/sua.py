import logging
import numpy as np
import pandas as pd
from SALib.sample import saltelli
from SALib.analyze import sobol

logger = logging.getLogger('tools4msp.sua')


def run_sua(module_cs, nparams, nruns, kwargs_run={}):
    module_cs.load_layers()
    module_cs.load_grid()
    module_cs.load_inputs()
    module_cs.run(**kwargs_run)

    module_cs_sua = CEACaseStudySUA(module_cs, nparams=nparams, kwargs_run=kwargs_run)
    module_cs_sua.runall(nruns)

    return module_cs_sua


class CaseStudySUA(object):
    """
    This is a base class for support Sensitivity and Uncertainty Analysis.
    Child classes have to implement "set_problem" and "set_params" methods.
    """
    def __init__(self, module_cs, nparams=40, kwargs_run={}):
        self.module_cs = module_cs
        self.kwargs_run = kwargs_run
        # check runtypelevel
        if self.module_cs.runtypelevel is None or self.module_cs.runtypelevel < 3:
            raise Exception("Case Study doesn't have a sufficient runlevel")
            pass
        # TODO: casestudy should store info on input parameters (e.g. uses,
        #  pres, envs) in order to allow multiple runs
        self.problem = {
            'num_vars': 0,
            'names': [],  # ['mscf'],  # , 'rfunc_b', 'rfuncb_m'],
            'bounds': [],  # [[0, 1]],  # , [1, 30], [0.3, 0.7]],
            'dists': [],  # ['unif'],  # 'unif', 'unif'],
            'groups': [],  # ['mscf'],  # 'rfunc', 'rfunc']
        }

        self.var_index = []
        self.model_output_stats = None
        self.target_values = None
        self.nparams = nparams

    def set_problem(self):
        """This is override by child classes"""
        pass

    def set_params(self, params):
        """This is override by child classes"""
        pass

    def add_problem_var(self, var_idx, bound, dist, group=None):
        name = ' '.join(var_idx)
        self.problem['num_vars'] += 1
        self.problem['names'].append(name)
        self.problem['bounds'].append(bound)
        self.problem['dists'].append(dist)
        if group is not None:
            self.problem['groups'].append(group)
        else:
            self.problem['groups'].append(name)

        self.var_index.append(var_idx)

    def sample(self, nruns, calc_second_order=True):
        return saltelli.sample(self.problem, nruns,
                               calc_second_order=calc_second_order)

    def runall(self, nruns, calc_second_order=False):
        self.set_problem()
        samples = self.sample(nruns, calc_second_order)
        model_output_stats = RunningStats2D(percentiles=[25, 50, 75])
        target_values = []
        for i, params in enumerate(samples):
            self.set_params(params)
            self.module_cs.run(runtypelevel=0, **self.kwargs_run)
            model_output = self.module_cs.get_main_output()
            model_output_stats.push(model_output)
            target_value = self.module_cs.get_SUA_target()
            target_values.append(target_value)
            logger.debug('run {} target={}'.format(i, target_value))
        self.model_output_stats = model_output_stats
        self.target_values = np.array(target_values)

    def analyze(self, calc_second_order=False):
        sa_results = sobol.analyze(self.problem,
                                   self.model_output_stats,
                                   calc_second_order=calc_second_order)
        return sa_results

    @property
    def mean(self):
        return self.model_output_stats.mean

    @property
    def std(self):
        return self.model_output_stats.std

    @property
    def cv(self):
        mean = self.mean
        std = self.std
        return std/mean


class RunningStats2D:
    """
    This is a class for online computation of mean, variance and convergence arrays.
    """
    def __init__(self, percentiles=None):
        """
        :param percentiles: list-like (list, tuple, ecc) of percentile threshold values. E.g. [25, 50, 75].
        """
        self.n = 0
        self.old_m = None
        self.new_m = None
        self.old_s = None
        self.new_s = None
        self.initialized = False

        self.percentiles = percentiles
        self._convergence_arrays = []

    def clear(self):
        self.n = 0

    def push(self, x):
        self.n += 1

        # mean and variances
        if self.n == 1:
            self.old_m = self.new_m = x
            self.old_s = np.zeros_like(x)
            if self.percentiles is not None:
                for p in self.percentiles:
                    self._convergence_arrays.append(np.zeros_like(x))
        else:
            self.new_m = self.old_m + (x - self.old_m) / self.n
            self.new_s = self.old_s + (x - self.old_m) * (x - self.new_m)

            self.old_m = self.new_m
            self.old_s = self.new_s

        if self.percentiles is not None:
            pvals = np.percentile(np.ndarray.flatten(x[~x.mask]),
                                  self.percentiles)
            logger.debug('min={} max={} pvals={}'.format(x.min(), x.max(), pvals))
            for i, pval in enumerate(pvals):
                r = x.copy()
                r[x<pval] = 0
                r[x>=pval] = 1
                self._convergence_arrays[i] += r

    @property
    def mean(self):
        return self.new_m if self.n else 0.0

    @property
    def variance(self):
        return self.new_s / (self.n - 1) if self.n > 1 else 0.0

    @property
    def std(self):
        return np.sqrt(self.variance)

    def convergence_arrays(self):
        return [m / self.n for m in self._convergence_arrays]


class CEACaseStudySUA(CaseStudySUA):
    def set_problem(self):
        nparams = self.nparams
        module_cs = self.module_cs
        self.normalize_distance = None

        sensitivities = module_cs.sensitivities
        sensitivities.fillna({'confidence': 0.2},
                             inplace=True)
        sensitivities['sua_var_name'] = sensitivities['precode'] + '--' + sensitivities['envcode']
        df_presenvs = module_cs.get_score_stats('presenvs')
        df_presenvs = df_presenvs.merge(sensitivities,
                                        left_on=['k1', 'k2'],
                                        right_on=['precode', 'envcode']
                                        )
        topsensitivities = df_presenvs.sort_values('score', ascending=False)[:nparams]
        for i, s in topsensitivities.iterrows():
            label = s.sua_var_name
            confidence = s.confidence
            int_confidence = 1. - confidence
            if int_confidence == 0:
                int_confidence = 0.1
            sensitivity_score = s.sensitivity

            self.add_problem_var(['sensitivities', 'sensitivity', label],
                                 [sensitivity_score,
                                  int_confidence],
                                 'triang',
                                 'sensitivity'
                                 )

        weighs = module_cs.weights
        self.normalize_distance = weighs.distance.max() * 2
        weighs['sua_var_name'] = weighs['usecode'] + '--' + weighs['precode']
        df_usepressures = module_cs.get_score_stats('usepressures')
        df_usepressures = df_usepressures.merge(weighs,
                                                left_on=['k1', 'k2'],
                                                right_on=['usecode', 'precode']
                                                )
        topweights = df_usepressures.sort_values('score', ascending=False)[:nparams]
        for i, s in topweights.iterrows():
            label = s.sua_var_name
            confidence = 0.5
            int_confidence = 1. - confidence
            if int_confidence == 0:
                int_confidence = 0.1
            weight = s.weight
            distance = s.distance / self.normalize_distance
            if distance == 0:
                distance = 0.0001

            self.add_problem_var(['weights', 'weight', label],
                                 [weight,
                                  int_confidence],
                                 'triang',
                                 'weight'
                                 )

            self.add_problem_var(['weights', 'distance', label],
                                 [distance,
                                  int_confidence],
                                 'triang',
                                 'distance'
                                 )

    def set_params(self, params):
        for i, (var_type, var_column, var_name) in enumerate(self.var_index):
            df = getattr(self.module_cs, var_type)
            # print(obj[obj.sua_var_name == var_name])
            val = params[i]
            if var_column == 'distance':
                val = val * self.normalize_distance
            df.loc[df.sua_var_name == var_name, var_column] = val