import itertools
import numba
import numpy as np

from pgfa.math_utils import discrete_rvs, log_normalize


def do_row_gibbs_update(density, a, b, cols, row_idx, data, params):
    Zs = list(map(np.array, itertools.product([0, 1], repeat=len(cols))))

    Zs = np.array(Zs, dtype=np.int)

    return _do_row_gibbs_update(density, a, b, cols, row_idx, data, params, Zs)


@numba.jit
def _do_row_gibbs_update(density, a, b, cols, row_idx, data, params, Zs):
    log_a = np.log(a[cols])

    log_b = np.log(b[cols])

    log_p = np.zeros(len(Zs))

    z = np.ones(params.K)

    for idx in range(len(Zs)):
        # Work around because Numba won't allow params.Z[row_idx, cols] = Zs[idx]
        z[cols] = Zs[idx]

        params.Z[row_idx] = z

        log_p[idx] = np.sum(Zs[idx] * log_a) + np.sum((1 - Zs[idx]) * log_b) + density.log_p(data, params)

    log_p = log_normalize(log_p)

    idx = discrete_rvs(np.exp(log_p))

    z[cols] = Zs[idx]

    params.Z[row_idx] = z

    return params
