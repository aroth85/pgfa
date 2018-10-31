import numba
import numpy as np

from pgfa.math_utils import discrete_rvs, log_normalize, log_sum_exp

from pgfa.updates.base import FeatureAllocationMatrixUpdater


class ParticleGibbsUpdater(FeatureAllocationMatrixUpdater):
    def __init__(self, annealed=False, num_particles=10, resample_threshold=0.5, singletons_updater=None):
        self.annealed = annealed

        self.num_particles = num_particles

        self.resample_threshold = resample_threshold

        self.singletons_updater = singletons_updater

    def update_row(self, cols, data, dist, feat_probs, params, row_idx):
        return do_particle_gibbs_update(
            cols,
            data,
            dist,
            feat_probs,
            params,
            row_idx,
            annealed=self.annealed,
            num_particles=self.num_particles,
            resample_threshold=self.resample_threshold
        )


def do_particle_gibbs_update(
        cols,
        data,
        dist,
        feat_probs,
        params,
        row_idx,
        annealed=True,
        num_particles=10,
        resample_threshold=0.5):

    T = len(cols)

    log_p = np.zeros(num_particles)

    log_p_old = np.zeros(num_particles)

    log_W = np.zeros(num_particles)

    particles = np.zeros((num_particles, T), dtype=np.int64)

    z = params.Z[row_idx].copy()

    z_test = z.copy()

    z_test[cols] = 0

    for t in range(T):
        particles[0, t] = z[cols[t]]

        log_W = log_normalize(log_W)

        log_p_old[:] = log_p[:]

        if t > 0:
            log_W, particles = _resample(log_W, particles, conditional=True, threshold=resample_threshold)

        for i in range(num_particles):
            if i == 0:
                idx = particles[0, t]

            else:
                idx = -1

            z_test[cols[:t]] = particles[i, :t]

            particles[i, t], log_p[i], log_norm = _propose(
                cols[:(t + 1)], data, dist, feat_probs, params, row_idx, z_test, T, annealed=annealed, idx=idx
            )

            log_w = log_norm - log_p_old[i]

            log_W[i] = log_W[i] + log_w

    log_W = log_normalize(log_W)

    W = np.exp(log_W)

    idx = discrete_rvs(W)

    z[cols] = particles[idx]

    params.Z[row_idx] = z

    return params


@numba.njit(cache=True)
def _log_target_pdf(cols, feat_probs, log_p_x, z):

    log_p = 0

    log_p += np.sum(z[cols] * np.log(feat_probs[cols]))

    log_p += np.sum((1 - z[cols]) * np.log(1 - feat_probs[cols]))

    log_p += log_p_x

    return log_p


@numba.njit(cache=True)
def _log_target_pdf_annealed(cols, feat_probs, log_p_x, z, T):
    t = len(cols)

    log_p = 0

    log_p += np.sum(z[cols] * np.log(feat_probs[cols]))

    log_p += np.sum((1 - z[cols]) * np.log(1 - feat_probs[cols]))

    log_p += (t / T) * log_p_x

    return log_p


def _propose(cols, data, dist, feat_probs, params, row_idx, z, T, annealed=False, idx=-1):
    cols = np.array(cols, dtype=np.int64)

    log_p = np.zeros(2)

    for val in [0, 1]:
        z[cols[-1]] = val

        params.Z[row_idx] = z

        log_p_x = dist.log_p_row(data, params, row_idx)

        if annealed:
            log_p[val] = _log_target_pdf_annealed(cols, feat_probs, log_p_x, z, T)

        else:
            log_p[val] = _log_target_pdf(cols, feat_probs, log_p_x, z)

    log_norm = log_sum_exp(log_p)

    if idx == -1:
        p = np.exp(log_p - log_norm)

        idx = discrete_rvs(p)

    idx = int(idx)

    return idx, log_p[idx], log_norm


def _get_ess(log_W):
    W = np.exp(log_W)

    return 1 / np.sum(np.square(W))


def _resample(log_W, particles, conditional=True, threshold=0.5):
    num_features = len(log_W)

    num_particles = particles.shape[0]

    if (_get_ess(log_W) / num_particles) <= threshold:
        new_particles = np.zeros(particles.shape, dtype=np.int64)

        W = np.exp(log_W)

        W = W + 1e-10

        W = W / np.sum(W)

        if conditional:
            new_particles[0] = particles[0]

            multiplicity = np.random.multinomial(num_particles - 1, W)

            idx = 1

        else:
            multiplicity = np.random.multinomial(num_particles, W)

            idx = 0

        for k in range(num_features):
            for _ in range(multiplicity[k]):
                new_particles[idx] = particles[k]

                idx += 1

        log_W = -np.log(num_particles) * np.ones(num_particles)

        particles = new_particles

    return log_W, particles