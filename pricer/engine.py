from dataclasses import dataclass

from pricer.binomial import option_prices as binomial_option_prices
from pricer.blackscholes import call_price, put_price
from pricer.montecarlo import european_option_prices


DEFAULT_BINOMIAL_STEPS = 500


@dataclass
class ModelValuation:
    label: str
    call: float | None
    put: float | None
    available: bool


@dataclass
class ValuationResult:
    effective_method: str
    effective_label: str
    models: dict[str, ModelValuation]


def compute_valuations(
    exercise_style: str,
    s: float,
    k: float,
    r: float,
    q: float,
    sigma: float,
    t: float,
    simulations: int,
) -> ValuationResult:
    models: dict[str, ModelValuation] = {}
    is_american = exercise_style == "Americana"

    bs_label = "Black-Scholes europeo (proxy)" if is_american else "Black-Scholes europeo"
    mc_label = "Monte Carlo europeo (proxy)" if is_american else "Monte Carlo europeo"
    bs_call = call_price(s, k, r, q, sigma, t)
    bs_put = put_price(s, k, r, q, sigma, t)
    mc_call, mc_put = european_option_prices(s, k, r, q, sigma, t, simulations=simulations)

    models["Black-Scholes"] = ModelValuation(
        label=bs_label,
        call=bs_call,
        put=bs_put,
        available=True,
    )
    models["Monte Carlo"] = ModelValuation(
        label=mc_label,
        call=mc_call,
        put=mc_put,
        available=True,
    )

    binomial_call, binomial_put = binomial_option_prices(
        s,
        k,
        r,
        q,
        sigma,
        t,
        steps=DEFAULT_BINOMIAL_STEPS,
        american=is_american,
    )
    models["Binomial"] = ModelValuation(
        label=f"Binomial CRR ({DEFAULT_BINOMIAL_STEPS} pasos)",
        call=binomial_call,
        put=binomial_put,
        available=True,
    )

    effective_method = "Binomial" if is_american else "Black-Scholes"

    effective_output = models[effective_method]
    return ValuationResult(
        effective_method=effective_method,
        effective_label=effective_output.label,
        models=models,
    )
