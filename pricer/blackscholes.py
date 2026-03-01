from math import erf, exp, log, pi, sqrt

def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return exp(-0.5 * x * x) / sqrt(2.0 * pi)


def d1(s: float, k: float, r: float, q: float, sigma: float, t: float) -> float:
    return (log(s / k) + (r - q + 0.5 * sigma**2) * t) / (sigma * sqrt(t))


def d2(s: float, k: float, r: float, q: float, sigma: float, t: float) -> float:
    return d1(s, k, r, q, sigma, t) - sigma * sqrt(t)


def call_price(s: float, k: float, r: float, q: float, sigma: float, t: float) -> float:
    d_1 = d1(s, k, r, q, sigma, t)
    d_2 = d2(s, k, r, q, sigma, t)
    return s * exp(-q * t) * norm_cdf(d_1) - k * exp(-r * t) * norm_cdf(d_2)


def put_price(s: float, k: float, r: float, q: float, sigma: float, t: float) -> float:
    d_1 = d1(s, k, r, q, sigma, t)
    d_2 = d2(s, k, r, q, sigma, t)
    return k * exp(-r * t) * norm_cdf(-d_2) - s * exp(-q * t) * norm_cdf(-d_1)


def greeks(s: float, k: float, r: float, q: float, sigma: float, t: float) -> dict[str, float]:
    d_1 = d1(s, k, r, q, sigma, t)
    d_2 = d2(s, k, r, q, sigma, t)
    sqrt_t = sqrt(t)
    discounted_spot = s * exp(-q * t)
    discounted_strike = k * exp(-r * t)
    pdf_d1 = norm_pdf(d_1)

    call_delta = exp(-q * t) * norm_cdf(d_1)
    put_delta = exp(-q * t) * (norm_cdf(d_1) - 1.0)
    gamma = exp(-q * t) * pdf_d1 / (s * sigma * sqrt_t)
    vega = discounted_spot * pdf_d1 * sqrt_t / 100.0
    call_theta = (
        -(discounted_spot * pdf_d1 * sigma) / (2.0 * sqrt_t)
        - r * discounted_strike * norm_cdf(d_2)
        + q * discounted_spot * norm_cdf(d_1)
    ) / 365.0
    put_theta = (
        -(discounted_spot * pdf_d1 * sigma) / (2.0 * sqrt_t)
        + r * discounted_strike * norm_cdf(-d_2)
        - q * discounted_spot * norm_cdf(-d_1)
    ) / 365.0
    call_rho = discounted_strike * t * norm_cdf(d_2) / 100.0
    put_rho = -discounted_strike * t * norm_cdf(-d_2) / 100.0

    return {
        "call_delta": call_delta,
        "put_delta": put_delta,
        "gamma": gamma,
        "vega": vega,
        "call_theta": call_theta,
        "put_theta": put_theta,
        "call_rho": call_rho,
        "put_rho": put_rho,
    }
