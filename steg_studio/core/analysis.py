"""Chi-square LSB-pairs detectability test (Westfeld & Pfitzmann, 1999).

Pure-Python / numpy implementation. The χ² survival function is computed
via the regularized upper incomplete gamma Q(a, x) using the
Numerical-Recipes series + continued-fraction split — avoids a scipy
dependency.

Score convention
----------------
We collapse the per-channel p-values into a single 0–10 score, where
0 = histogram looks pristine and 10 = embedding is highly suspected.
StegExpose flags scores ≥ 3.5 as suspicious.
"""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np
from PIL import Image


# ── χ² survival function via regularized incomplete gamma ────────────────────

def _gser(a: float, x: float, itmax: int = 200, eps: float = 3e-16) -> float:
    gln = math.lgamma(a)
    ap = a
    summ = 1.0 / a
    delta = summ
    for _ in range(itmax):
        ap += 1.0
        delta *= x / ap
        summ += delta
        if abs(delta) < abs(summ) * eps:
            break
    return summ * math.exp(-x + a * math.log(x) - gln)


def _gcf(a: float, x: float, itmax: int = 200, eps: float = 3e-16) -> float:
    gln = math.lgamma(a)
    fpmin = 1e-300
    b = x + 1.0 - a
    c = 1.0 / fpmin
    d = 1.0 / b
    h = d
    for i in range(1, itmax + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < fpmin:
            d = fpmin
        c = b + an / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return math.exp(-x + a * math.log(x) - gln) * h


def chi2_sf(chi2: float, df: int) -> float:
    """Survival function (1 − CDF) of the χ² distribution. df ≥ 1."""
    if df <= 0 or chi2 <= 0:
        return 1.0
    a = df / 2.0
    x = chi2 / 2.0
    if x < a + 1.0:
        return max(0.0, 1.0 - _gser(a, x))
    return _gcf(a, x)


# ── LSB-pairs test ───────────────────────────────────────────────────────────

# StegExpose convention: scores ≥ this are flagged suspicious.
SUSPICIOUS_THRESHOLD = 3.5


def _channel_p_value(channel: np.ndarray) -> tuple[float, float, int]:
    """Return (p_value, chi2, df) for a single 8-bit channel."""
    hist = np.bincount(channel.ravel(), minlength=256).astype(np.float64)
    chi2 = 0.0
    df = 0
    for i in range(0, 256, 2):
        expected = (hist[i] + hist[i + 1]) / 2.0
        if expected > 5.0:
            chi2 += (hist[i] - expected) ** 2 / expected
            df += 1
    if df == 0:
        return 0.0, 0.0, 0
    return chi2_sf(chi2, df), chi2, df


def chi_square_score(img: Image.Image,
                     channels: Iterable[int] = (0, 1, 2)) -> dict:
    """Run the LSB-pairs χ² test on selected channels of *img*.

    Returns
    -------
    dict with keys:
        ``p_values``  per-channel p-values (high p ⇒ embedding suspected)
        ``p_mean``    mean p across channels
        ``score``     0..10 where 10 = obviously modified
        ``verdict``   "PASS" or "SUSPICIOUS" (vs SUSPICIOUS_THRESHOLD)
    """
    arr = np.array(img.convert("RGB"), dtype=np.uint8)
    p_values = []
    for c in channels:
        p, _chi2, _df = _channel_p_value(arr[:, :, c])
        p_values.append(p)
    p_mean = sum(p_values) / len(p_values) if p_values else 0.0
    score = p_mean * 10.0
    return {
        "p_values": p_values,
        "p_mean": p_mean,
        "score": score,
        "verdict": "PASS" if score < SUSPICIOUS_THRESHOLD else "SUSPICIOUS",
    }
