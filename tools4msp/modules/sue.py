import logging
import numpy as np
import pandas as pd
from SALib.sample import saltelli
from SALib.analyze import sobol
from tools4msp.models import CaseStudyRun

logger = logging.getLogger('tools4msp.sua')


# def run_sua(csrunid, nparams, nruns):
#     csr = CaseStudyRun.objects.get(pk=csrunid)

class CaseStudySUA(object):
    """
    This is a base class for support Sensitivity and Uncertainty Analysis.
    Child classes have to implement "set_problem" and "set_params" methods.
    """
    def __init__(self, module_cs, nparams=40):
        self.module_cs = module_cs
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
            self.module_cs.run(runtypelevel=0)
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

    def get_mean(self):
        mean = self.model_output_stats.mean()

    def get_cv(self):
        mean = self.model_output_stats.get_mean()
        std = self.model_output_stats.std()
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

    def mean(self):
        return self.new_m if self.n else 0.0

    def variance(self):
        return self.new_s / (self.n - 1) if self.n > 1 else 0.0

    def std(self):
        return np.sqrt(self.variance())

    def convergence_arrays(self):
        return [m / self.n for m in self._convergence_arrays]
