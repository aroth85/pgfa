import numpy as np

from pgfa.utils import get_b_cubed_score

import pgfa.feature_allocation_distributions
import pgfa.models.nsfa
import pgfa.updates


def main():
    np.random.seed(0)

    num_iters = 100001
    D = 10
    K = 5
    N_train = 1000
    N_test = 1000

    feat_alloc_dist = pgfa.feature_allocation_distributions.get_feature_allocation_distribution(K)

    params_train = get_test_params(feat_alloc_dist, N_train, D, alpha=10, gamma=0.1, seed=0)

    params_test = get_test_params(feat_alloc_dist, N_test, D, params=params_train, seed=1)

    data_train = get_data(params_train)

    data_test = get_data(params_test)

    singletons_updater = pgfa.models.nsfa.PriorSingletonsUpdater()

    singletons_updater = None

    feat_alloc_updater = pgfa.updates.GibbsMixtureUpdater(
        pgfa.updates.ParticleGibbsUpdater(
            annealed=True,  num_particles=10, singletons_updater=singletons_updater
        )
    )

#     feat_alloc_updater = pgfa.updates.RowGibbsUpdater()

#     feat_alloc_updater = pgfa.updates.GibbsUpdater(singletons_updater=singletons_updater)

    model_updater = pgfa.models.nsfa.ModelUpdater(feat_alloc_updater)

    feat_alloc_dist = pgfa.feature_allocation_distributions.get_feature_allocation_distribution(K)

    model = pgfa.models.nsfa.Model(data_train, feat_alloc_dist)

    print(np.sum(params_train.Z, axis=0))

    print('@' * 100)

    for i in range(num_iters):
        if i % 100 == 0:
            print(
                i,
                model.params.Z.shape[1],
                model.params.gamma,
                model.log_p,
                model.log_predictive_pdf(data_test),
                model.rmse,
            )

            if model.params.K > 0:
                try:
                    print(get_b_cubed_score(params_train.Z, model.params.Z))
                except:
                    pass

            print(np.sum(model.params.Z, axis=0))

            print('#' * 100)

        model_updater.update(model)


def get_data(params):
    data = params.W @ params.F

    data += np.random.multivariate_normal(np.zeros(params.D), np.diag(1 / params.S), size=params.N).T

    return data


def get_test_params(feat_alloc_dist, num_data_points, num_observed_dims, alpha=1, gamma=1, params=None, seed=None):
    if seed is not None:
        np.random.seed(seed)

    D = num_observed_dims
    N = num_data_points

    if params is None:
        Z = feat_alloc_dist.rvs(alpha, D)

        K = Z.shape[1]

        S = 1 * np.ones(D)

        V = np.random.multivariate_normal(np.zeros(K), (1 / gamma) * np.eye(K), size=D)

        F = np.random.normal(0, 1, size=(K, N))

    else:
        alpha = params.alpha

        gamma = params.gamma

        Z = params.Z.copy()

        K = Z.shape[1]

        S = params.S.copy()

        V = params.V.copy()

        F = np.random.normal(0, 1, size=(K, N))

    return pgfa.models.nsfa.Parameters(
        alpha, np.ones(2), gamma, np.ones(2), F, S, np.ones(2), V, Z
    )


def get_min_error(params_pred, params_true):
    import itertools

    W_pred = params_pred.F.T

    W_true = params_true.F.T

    K_pred = W_pred.shape[1]

    K_true = W_true.shape[1]

    min_error = float('inf')

    for perm in itertools.permutations(range(K_pred)):
        error = np.sqrt(np.mean((W_pred[:, perm[:K_true]] - W_true)**2))

        if error < min_error:
            min_error = error

    return min_error


if __name__ == '__main__':
    #     import line_profiler
    #     import pgfa.updates.particle_gibbs
    #
    #     profiler = line_profiler.LineProfiler(
    #         pgfa.models.nsfa.NonparametricSparaseFactorAnalysisModelUpdater.update,
    #         pgfa.updates.particle_gibbs.do_particle_gibbs_update,
    #         pgfa.updates.particle_gibbs._propose_annealed,
    #         pgfa.updates.particle_gibbs._log_target_pdf_annealed
    #     )
    #
    #     profiler.run("main()")
    #
    #     profiler.print_stats()

    main()
