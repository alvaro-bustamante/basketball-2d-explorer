"""Empirical-Bayes shrinkage and uncertainty ellipses.

Two conjugate models, with the prior estimated from the league itself:

* Beta-Binomial for rates built from counts (3P%, eFG%, TOV%, USG%...).
* Normal-Normal for continuous metrics with an approximate standard error
  (offensive rating, points per game...).

Both return a posterior mean (the "adjusted" value, pulled towards the league
average in proportion to how little data there is) and a posterior SD, which
we use to draw uncertainty ellipses. A natural next step is a full
hierarchical model in PyMC; this module keeps the same inputs and outputs so
it can be swapped later.
"""
from __future__ import annotations

import numpy as np

_EPS = 1e-12
# Lower bound for the between-entity ("true talent") variance, as a share of the
# observed variance. Avoids complete pooling in small or noisy samples.
MIN_SPREAD_SHARE = 0.2


def eb_beta_binomial(successes, trials):
    """Posterior mean and SD of a proportion for every entity.

    The prior Beta(m*kappa, (1-m)*kappa) is fitted by the method of moments:
    the observed spread of rates minus the spread expected from binomial noise
    is the "true talent" spread tau^2.
    """
    s = np.asarray(successes, float)
    n = np.asarray(trials, float)
    s = np.clip(s, 0, np.where(np.isfinite(n), n, np.inf))
    ok = np.isfinite(s) & np.isfinite(n) & (n > 0)
    mean = np.full(s.shape, np.nan)
    sd = np.full(s.shape, np.nan)
    if ok.sum() == 0:
        return mean, sd, np.nan
    m = s[ok].sum() / n[ok].sum()
    p = s[ok] / n[ok]
    var_w = np.average((p - m) ** 2, weights=n[ok])
    noise = m * (1 - m) * ok.sum() / n[ok].sum()
    # Floor on the true-talent spread: never assume everyone is identical.
    tau2 = max(var_w - noise, MIN_SPREAD_SHARE * var_w, 1e-6)
    kappa = max(m * (1 - m) / tau2 - 1, 1.0)
    a = m * kappa + s[ok]
    b = (1 - m) * kappa + n[ok] - s[ok]
    mean[ok] = a / (a + b)
    sd[ok] = np.sqrt(mean[ok] * (1 - mean[ok]) / (a + b + 1))
    return mean, sd, kappa


def eb_normal(values, std_errors):
    """Normal-Normal shrinkage: prior N(mu, tau^2) estimated from the league."""
    y = np.asarray(values, float)
    se = np.asarray(std_errors, float)
    ok = np.isfinite(y) & np.isfinite(se) & (se > 0)
    mean = y.copy()
    sd = np.where(np.isfinite(se), se, np.nan)
    if ok.sum() < 3:
        return mean, sd, np.nan
    mu = y[ok].mean()
    tau2 = max(y[ok].var() - np.mean(se[ok] ** 2), MIN_SPREAD_SHARE * y[ok].var(), _EPS)
    w_data = 1 / se[ok] ** 2
    w_prior = 1 / tau2
    post_var = 1 / (w_data + w_prior)
    mean[ok] = post_var * (y[ok] * w_data + mu * w_prior)
    sd[ok] = np.sqrt(post_var)
    return mean, sd, tau2


def ellipse_scale(level: float) -> float:
    """Radius multiplier for a 2D Gaussian credible region.

    For two independent normal dimensions the squared Mahalanobis distance is
    chi-square with 2 d.o.f., whose quantile has a closed form: -2 ln(1-level).
    """
    return float(np.sqrt(-2.0 * np.log(1.0 - level)))


def ellipse_path(cx, cy, rx, ry, n_points: int = 48):
    t = np.linspace(0, 2 * np.pi, n_points)
    return cx + rx * np.cos(t), cy + ry * np.sin(t)
