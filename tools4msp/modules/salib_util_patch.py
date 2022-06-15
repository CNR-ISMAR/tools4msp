import SALib.util as salib_util
import numpy as np
import scipy as sp


def _nonuniform_scale_samples(params, bounds, dists):
    """Rescale samples in 0-to-1 range to other distributions

    Arguments
    ---------
    problem : dict
        problem definition including bounds
    params : numpy.ndarray
        numpy array of dimensions num_params-by-N,
        where N is the number of samples
    dists : list
        list of distributions, one for each parameter
            unif: uniform with lower and upper bounds
            triang: triangular with width (scale) and location of peak
                    location of peak is in percentage of width
                    lower bound assumed to be zero
            norm: normal distribution with mean and standard deviation
            lognorm: lognormal with ln-space mean and standard deviation
    """
    b = np.array(bounds)

    # initializing matrix for converted values
    conv_params = np.empty_like(params)

    # loop over the parameters
    for i in range(conv_params.shape[1]):
        # setting first and second arguments for distributions
        b1 = b[i][0]
        b2 = b[i][1]

        if dists[i] == 'triangmod':
            # checking for correct parameters
            if b1 < 0 or b2 <= 0 or b1 > 1 or b2 > 1:
                raise ValueError('''Modified Triangular distribution: Peak on interval [0,1], Confidence on the interval (0, 1]''')
            else:
                loc = min(max(b1 - b2 / 2, 0), 1 - b2)
                scale = b2
                c = (b1 - loc) / scale
                conv_params[:, i] = sp.stats.triang.ppf(
                    params[:, i], c=c, scale=scale, loc=loc)

        elif dists[i] == 'triang':
            # checking for correct parameters
            if b1 <= 0 or b2 <= 0 or b2 >= 1:
                raise ValueError('''Triangular distribution: Scale must be
                    greater than zero; peak on interval [0,1]''')
            else:
                conv_params[:, i] = sp.stats.triang.ppf(
                    params[:, i], c=b2, scale=b1, loc=0)

        elif dists[i] == 'unif':
            if b1 >= b2:
                raise ValueError('''Uniform distribution: lower bound
                    must be less than upper bound''')
            else:
                conv_params[:, i] = params[:, i] * (b2 - b1) + b1

        elif dists[i] == 'norm':
            if b2 <= 0:
                raise ValueError('''Normal distribution: stdev must be > 0''')
            else:
                conv_params[:, i] = sp.stats.norm.ppf(
                    params[:, i], loc=b1, scale=b2)

        # lognormal distribution (ln-space, not base-10)
        # paramters are ln-space mean and standard deviation
        elif dists[i] == 'lognorm':
            # checking for valid parameters
            if b2 <= 0:
                raise ValueError(
                    '''Lognormal distribution: stdev must be > 0''')
            else:
                conv_params[:, i] = np.exp(
                    sp.stats.norm.ppf(params[:, i], loc=b1, scale=b2))

        else:
            valid_dists = ['unif', 'triang', 'norm', 'lognorm', 'triangmod']
            raise ValueError('Distributions: choose one of %s' %
                             ", ".join(valid_dists))

    return conv_params


salib_util.nonuniform_scale_samples = _nonuniform_scale_samples
