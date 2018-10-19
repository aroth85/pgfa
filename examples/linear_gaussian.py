import numpy as np
import scipy.stats

from pgfa.utils import get_b_cubed_score

import pgfa.feature_allocation_priors
import pgfa.models.linear_gaussian
import pgfa.updates


def main():
    np.random.seed(0)

    num_iters = 10001
    D = 10
    K = None
    N = 100

    data, data_true, params = simulate_data(D, N, K=K, tau_v=1, tau_x=1)

    model_updater = get_model_updater(
        collapsed_singletons=False, feat_alloc_updater_type='g', ibp=(K is None), mixed_updates=True
    )

    model = get_model(data, K=K)

    print(np.sum(params.Z, axis=0))

    print('@' * 100)

    for i in range(num_iters):
        if i % 10 == 0:
            print(
                i,
                model.params.K,
                model.log_p,
                model.data_dist.log_p(model.data, model.params)
            )

            if model.params.K > 0:
                print(get_b_cubed_score(params.Z, model.params.Z))

            print(np.sum(model.params.Z, axis=0))

            print(compute_l2_error(data, data_true, model.params))

            print('#' * 100)

        model_updater.update(model)


def get_model(data, K=None):
    if K is None:
        feat_alloc_prior = pgfa.feature_allocation_priors.IndianBuffetProcessDistribution()

    else:
        feat_alloc_prior = pgfa.feature_allocation_priors.BetaBernoulliFeatureAllocationDistribution(1, 1, 4)

    return pgfa.models.linear_gaussian.LinearGaussianModel(data, feat_alloc_prior, collapsed=False)


def get_model_updater(collapsed_singletons=False, feat_alloc_updater_type='g', ibp=True, mixed_updates=False):
    if ibp:
        if collapsed_singletons:
            singletons_updater = pgfa.models.linear_gaussian.CollapsedSingletonUpdater()

        else:
            singletons_updater = pgfa.models.linear_gaussian.PriorSingletonsUpdater()

    else:
        singletons_updater = None

    if feat_alloc_updater_type == 'g':
        feat_alloc_updater = pgfa.updates.GibbsUpdater(singletons_updater=singletons_updater)

    elif feat_alloc_updater_type == 'pg':
        feat_alloc_updater = pgfa.updates.ParticleGibbsUpdater(
            annealed=False, num_particles=10, singletons_updater=singletons_updater
        )

    elif feat_alloc_updater_type == 'pga':
        feat_alloc_updater = pgfa.updates.ParticleGibbsUpdater(
            annealed=True, num_particles=10, singletons_updater=singletons_updater
        )

    elif feat_alloc_updater_type == 'rg':
        feat_alloc_updater = pgfa.updates.RowGibbsUpdater(singletons_updater=singletons_updater)

    if mixed_updates:
        feat_alloc_updater = pgfa.updates.GibbsMixtureUpdater(feat_alloc_updater)

    return pgfa.models.linear_gaussian.LinearGaussianModelUpdater(feat_alloc_updater)


def simulate_data(D, N, K=None, tau_v=1, tau_x=1):
    if K is None:
        feat_alloc_prior = pgfa.feature_allocation_priors.IndianBuffetProcessDistribution()

    else:
        feat_alloc_prior = pgfa.feature_allocation_priors.BetaBernoulliFeatureAllocationDistribution(1, 1, K)

    Z = feat_alloc_prior.rvs(N)

    K = Z.shape[1]

    V = scipy.stats.matrix_normal.rvs(
        mean=np.zeros((K, D)),
        rowcov=(1 / tau_v) * np.eye(K),
        colcov=np.eye(D)
    )

    data_true = scipy.stats.matrix_normal.rvs(
        mean=Z @ V,
        rowcov=(1 / tau_x) * np.eye(N),
        colcov=np.eye(D)
    )

    mask = np.random.uniform(0, 1, size=data_true.shape) <= 0.05

    data = data_true.copy()

    data[mask] = np.nan

    params = pgfa.models.linear_gaussian.Parameters(tau_v, tau_x, V, Z)

    return data, data_true, params


def compute_l2_error(data, data_true, params):
    idxs = np.isnan(data)

    data_pred = params.Z @ params.V

    return (1 / np.sum(idxs)) * np.sum(np.square(data_pred[idxs] - data_true[idxs]))


if __name__ == '__main__':
    main()
