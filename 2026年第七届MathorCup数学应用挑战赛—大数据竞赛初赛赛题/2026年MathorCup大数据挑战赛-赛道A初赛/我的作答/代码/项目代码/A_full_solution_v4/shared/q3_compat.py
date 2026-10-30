"""问题三所需的兼容性数学工具函数。"""


from __future__ import annotations
import math
import numpy as np

SENSORY_COLUMNS = [
    "A_malt_all", "A_malt_grain", "A_malt_bread", "A_malt_cara", "A_malt_burn",
    "A_hops_all", "A_hops_citrus", "A_hops_tropical", "A_hops_noble", "A_hops_woody",
    "A_esters_all", "A_esters_ethac", "A_esters_isoaa", "A_esters_flower", "A_esters_fruity",
    "F_malt_all", "F_malt_grain", "F_malt_bread", "F_malt_cara", "F_malt_burn",
    "F_hops_all", "F_hops_citrus", "F_hops_tropical", "F_hops_noble", "F_hops_woody",
    "F_esters_all", "F_esters_ethac", "F_esters_isoaa", "F_esters_flower", "F_esters_fruity",
    "acidity", "bitternes", "sweetness", "X4vg", "diacetyl", "dms", "metallic",
    "stale_hops", "t2n", "orange", "coriander", "clove", "lactic", "acetic", "barnyard",
    "alcohol", "aftertaste", "body", "co2", "overall",
]

def normal_ppf(p: np.ndarray) -> np.ndarray:
    """使用 Acklam 有理逼近计算标准正态分位数。"""
    p = np.clip(np.asarray(p, float), 1e-10, 1.0 - 1e-10)
    a = [-39.6968302866538, 220.946098424521, -275.928510446969,
         138.357751867269, -30.6647980661472, 2.50662827745924]
    b = [-54.4760987982241, 161.585836858041, -155.698979859887,
         66.8013118877197, -13.2806815528857]
    c = [-0.00778489400243029, -0.322396458041136, -2.40075827716184,
         -2.54973253934373, 4.37466414146497, 2.93816398269878]
    d = [0.00778469570904146, 0.32246712907004, 2.445134137143,
         3.75440866190742]
    plow = 0.02425
    phigh = 1.0 - plow
    out = np.empty_like(p)
    low = p < plow
    high = p > phigh
    mid = ~(low | high)
    if np.any(low):
        q = np.sqrt(-2.0 * np.log(p[low]))
        num = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
        den = ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        out[low] = num / den
    if np.any(high):
        q = np.sqrt(-2.0 * np.log(1.0 - p[high]))
        num = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
        den = ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        out[high] = -num / den
    if np.any(mid):
        q = p[mid] - 0.5
        r = q * q
        num = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        den = (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
        out[mid] = num / den
    return out

def normal_cdf(x: np.ndarray) -> np.ndarray:
    flat = np.asarray(x, float).ravel()
    vals = np.array([0.5 * (1.0 + math.erf(float(v) / math.sqrt(2.0))) for v in flat])
    return vals.reshape(np.asarray(x).shape)
