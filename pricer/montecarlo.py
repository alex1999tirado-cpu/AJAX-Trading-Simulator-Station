from math import exp, sqrt
from random import Random


def _validate_inputs(s: float, k: float, sigma: float, t: float, simulations: int) -> None:
    if s <= 0:
        raise ValueError("El precio actual del activo debe ser mayor que 0.")
    if k <= 0:
        raise ValueError("El precio de ejercicio debe ser mayor que 0.")
    if sigma <= 0:
        raise ValueError("La volatilidad debe ser mayor que 0.")
    if t <= 0:
        raise ValueError("El tiempo a vencimiento debe ser mayor que 0.")
    if simulations <= 0:
        raise ValueError("El numero de simulaciones debe ser mayor que 0.")


def european_option_prices(
    s: float,
    k: float,
    r: float,
    q: float,
    sigma: float,
    t: float,
    simulations: int = 10000,
    seed: int | None = 42,
) -> tuple[float, float]:
    _validate_inputs(s, k, sigma, t, simulations)

    rng = Random(seed)
    drift = (r - q - 0.5 * sigma**2) * t
    diffusion = sigma * sqrt(t)
    discount_factor = exp(-r * t)

    call_payoff_sum = 0.0
    put_payoff_sum = 0.0

    for _ in range(simulations):
        z = rng.gauss(0.0, 1.0)
        terminal_price = s * exp(drift + diffusion * z)
        call_payoff_sum += max(terminal_price - k, 0.0)
        put_payoff_sum += max(k - terminal_price, 0.0)

    call_price = discount_factor * (call_payoff_sum / simulations)
    put_price = discount_factor * (put_payoff_sum / simulations)

    return call_price, put_price
