import numba
import numpy as np
import scipy.stats


class CollapsedLinearGaussianModel(object):
    def __init__(self, data, K=None, params=None, priors=None):
        self.data = data

        self.ibp = (K is None)

        if params is None:
            params = get_params_from_data(data, K=K)

        self.params = params

        if priors is None:
            priors = Priors()

        self.priors = priors

    def log_p(self, data, params):
        """ Log of joint pdf.
        """
        pass

    def log_predictive_p(self, data, params):
        """ Log of predicitve pdf.
        """
        pass

    def update(self):
        self.params = self.feat_alloc_updater.update(self.data, self.data_dist, self.feat_alloc_prior, self.params)

        self.params = update_alpha(self.params, self.priors)

        self.params = update_V(self.data, self.params)

        self.params = update_tau_a(self.params, self.priors)

        self.params = update_tau_x(self.data, self.params, self.priors)


class LinearGaussianModel(object):
    def __init__(self, data, feat_alloc_prior, feat_alloc_updater, params=None, priors=None):
        self.data = data

        self.feat_alloc_updater = feat_alloc_updater

        self.feat_alloc_prior = feat_alloc_prior

        self.data_dist = DataDistribution()

        if params is None:
            params = get_params_from_data(data, feat_alloc_prior)

        self.params = params

        if priors is None:
            priors = Priors()

        self.priors = priors

    @property
    def log_p(self):
        """ Log of joint pdf.
        """
        t_a = self.params.tau_a
        t_x = self.params.tau_x
        V = self.params.V
        Z = self.params.Z
        X = self.data

        D = self.params.D
        K = self.params.K
        N = self.params.N

        log_p = 0

        # Binary matrix prior
        log_p += self.feat_alloc_prior.log_p(self.params.Z)

        # Gamma prior on $\tau_{a}$
        a = self.priors.tau_a[0]
        b = self.priors.tau_a[1]
        log_p += scipy.stats.gamma.logpdf(t_a, a, scale=(1 / b))

        # Gamma prior on $\tau_{x}$
        a = self.priors.tau_x[0]
        b = self.priors.tau_x[1]
        log_p += scipy.stats.gamma.logpdf(t_x, a, scale=(1 / b))

        # Prior on V
        log_p += scipy.stats.matrix_normal.logpdf(
            V,
            mean=np.zeros((K, D)),
            colcov=np.eye(D),
            rowcov=(1 / t_x) * np.eye(K)
        )

        log_p += scipy.stats.matrix_normal.logpdf(
            X,
            mean=Z @ V,
            colcov=np.eye(D),
            rowcov=(1 / t_x) * np.eye(N)
        )

        return log_p

    def log_predictive_p(self, data, params):
        """ Log of predicitve pdf.
        """
        pass

    def update(self):
        self.params = self.feat_alloc_updater.update(self.data, self.data_dist, self.feat_alloc_prior, self.params)

        if self.params.K > 0:
            self.params = update_V(self.data, self.params)

        self.params = update_tau_a(self.params, self.priors)

        self.params = update_tau_x(self.data, self.params, self.priors)


#=========================================================================
# Updates
#=========================================================================
def update_alpha(params, priors):
    a = params.K + priors.alpha[0]

    b = np.sum(1 / np.arange(1, params.N + 1)) + priors.alpha[1]

    params.alpha = np.random.gamma(a, 1 / b)

    return params


def update_V(data, params):
    t_a = params.tau_a
    t_x = params.tau_x
    Z = params.Z
    X = data

    M = np.linalg.inv(Z.T @ Z + (t_a / t_x) * np.eye(params.K))

    params.V = scipy.stats.matrix_normal.rvs(
        mean=M @ Z.T @ X,
        rowcov=(1 / t_x) * M,
        colcov=np.eye(params.D)
    )

    return params


def update_tau_a(params, priors):
    V = params.V

    a = priors.tau_a[0] + 0.5 * params.K * params.D

    b = priors.tau_a[1] + 0.5 * np.trace(V.T @ V)

    params.tau_a = np.random.gamma(a, 1 / b)

    return params


def update_tau_x(data, params, priors):
    V = params.V
    Z = params.Z
    X = data

    a = priors.tau_x[0] + 0.5 * params.N * params.D

    Y = X - Z @ V

    b = priors.tau_x[1] + 0.5 * np.trace(Y.T @ Y)

    params.tau_x = np.random.gamma(a, 1 / b)

    return params


#=========================================================================
# Container classes
#=========================================================================
def get_params_from_data(data, feat_alloc_prior):
    D = data.shape[1]
    N = data.shape[0]

    Z = feat_alloc_prior.rvs(N)

    K = Z.shape[1]

    V = np.random.multivariate_normal(np.zeros(D), np.eye(D), size=K)

    return Parameters(1, 1, V, Z)


@numba.jitclass([
    ('tau_a', numba.float64),
    ('tau_x', numba.float64),
    ('V', numba.float64[:, :]),
    ('Z', numba.int64[:, :])
])
class Parameters(object):
    def __init__(self, tau_a, tau_x, V, Z):
        self.tau_a = tau_a

        self.tau_x = tau_x

        self.V = V

        self.Z = Z

    @property
    def D(self):
        return self.V.shape[1]

    @property
    def K(self):
        return self.Z.shape[1]

    @property
    def N(self):
        return self.Z.shape[0]

    def copy(self):
        return Parameters(
            self.tau_a,
            self.tau_x,
            self.V.copy(),
            self.Z.copy()
        )


class Priors(object):
    def __init__(self, alpha=None, tau_a=None, tau_x=None):
        if alpha is None:
            alpha = np.ones(2)

        self.alpha = alpha

        if tau_a is None:
            tau_a = np.ones(2)

        self.tau_a = tau_a

        if tau_x is None:
            tau_x = np.ones(2)

        self.tau_x = tau_x


#=========================================================================
# Densities and proposals
#=========================================================================
@numba.jitclass([])
class DataDistribution(object):
    def __init__(self):
        pass

    def log_p(self, data, params):
        log_p = 0

        for row_idx in range(params.N):
            log_p += self.log_p_row(data, params, row_idx)

        return log_p

    def log_p_row(self, data, params, row_idx):
        t_x = params.tau_x
        V = params.V
        x = data[row_idx]
        z = params.Z[row_idx]

        D = params.D

        log_p = 0.5 * D * (np.log(t_x) - np.log(2 * np.pi))

        for d in range(D):
            m = np.sum(V[:, d] * z)

            log_p -= 0.5 * t_x * (x[d] - m)**2

        return log_p


class LinearGaussianMarginalDensity(object):
    def __init__(self, row_idx):
        self.row_idx = row_idx
#
#         self.t_a = t_a
#
#         self.t_x = t_x
#
#         self.rank_one = rank_one
#
#         if rank_one:
#             K = Z.shape[1]
#
#             M_inv = Z.T @ Z + (t_a / t_x) * np.eye(K)
#
#             L, _ = scipy.linalg.cho_factor(M_inv, lower=True)
#
#             z = Z[row]
#
#             cholesky_update(L, z, alpha=-1, inplace=True)
#
#             self.L_i = L

    def log_p(self, data, params):
        t_a = params.tau_a
        t_x = params.tau_x
        Z = params.Z
        X = data

        D = params.D
        K = params.K
        N = params.N

        log_p = 0
        log_p += 0.5 * (N - K) * D * t_x
        log_p += 0.5 * K * D * t_a
        log_p -= 0.5 * N * D * np.log(2 * np.pi)

#         if self.rank_one:
#             L_i = self.L_i
#
#             z = Z[self.row]
#
#             L = cholesky_update(L_i, z, alpha=1, inplace=False)
#
#             MZ = scipy.linalg.cho_solve((L, True), Z.T)
#
#             log_det_M = -1 * cholesky_log_det(L)
#
#             log_p += 0.5 * D * log_det_M
#             log_p -= 0.5 * t_x * np.trace(X.T @ (np.eye(N) - Z @ MZ) @ X)
#
#         else:
        M = np.linalg.inv(Z.T @ Z + (t_a / t_x) * np.eye(K))

        log_p += 0.5 * D * np.log(np.linalg.det(M))
        log_p -= 0.5 * t_x * np.trace(X.T @ (np.eye(N) - Z @ M @ Z.T) @ X)

        return log_p


class CollapsedProposal(object):
    def __init__(self, row_idx):
        self.row_idx = row_idx

    def rvs(self, data, params, num_singletons):
        m = np.sum(params.Z, axis=0)

        m -= params.Z[self.row_idx]

        non_singletons_idxs = np.atleast_1d(np.squeeze(np.where(m > 0)))

        num_non_singleton = len(non_singletons_idxs)

        K_new = num_non_singleton + num_singletons

        Z_new = np.zeros((params.N, K_new), dtype=np.int64)

        Z_new[:, :num_non_singleton] = params.Z[:, non_singletons_idxs]

        Z_new[self.row_idx, num_non_singleton:] = 1

        V_new = np.zeros((K_new, params.D))

        return Parameters(
            params.tau_a,
            params.tau_x,
            V_new,
            Z_new
        )


class UncollapsedProposal(object):
    def __init__(self, row_idx):
        self.row_idx = row_idx

    def rvs(self, data, params, num_singletons):
        m = np.sum(params.Z, axis=0)

        m -= params.Z[self.row_idx]

        non_singletons_idxs = np.atleast_1d(np.squeeze(np.where(m > 0)))

        num_non_singleton = len(non_singletons_idxs)

        K_new = num_non_singleton + num_singletons

        Z_new = np.zeros((params.N, K_new), dtype=np.int64)

        Z_new[:, :num_non_singleton] = params.Z[:, non_singletons_idxs]

        Z_new[self.row_idx, num_non_singleton:] = 1

        V_new = np.zeros((K_new, params.D))

        V_new[:num_non_singleton] = params.V[non_singletons_idxs]

        V_new[num_non_singleton:] = np.random.multivariate_normal(
            np.zeros(params.D), (1 / params.tau_a) * np.eye(params.D), size=num_singletons
        )

        return Parameters(
            params.alpha,
            params.tau_a,
            params.tau_x,
            V_new,
            Z_new
        )
