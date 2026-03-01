from math import exp, sqrt


def option_prices(
    s: float,
    k: float,
    r: float,
    q: float,
    sigma: float,
    t: float,
    steps: int = 500,
    american: bool = True,
) -> tuple[float, float]:
    if s <= 0 or k <= 0:
        raise ValueError("S y K deben ser mayores que 0.")
    if sigma <= 0:
        raise ValueError("La volatilidad debe ser mayor que 0.")
    if t <= 0:
        raise ValueError("El tiempo a vencimiento debe ser mayor que 0.")
    if steps <= 0:
        raise ValueError("El numero de pasos binomiales debe ser mayor que 0.")

    dt = t / steps
    up = exp(sigma * sqrt(dt))
    down = 1.0 / up
    growth = exp((r - q) * dt)
    probability = (growth - down) / (up - down)

    if not 0.0 < probability < 1.0:
        raise ValueError("Parametros no validos para el arbol binomial.")

    discount = exp(-r * dt)

    call_values = [0.0] * (steps + 1)
    put_values = [0.0] * (steps + 1)

    for i in range(steps + 1):
        terminal_price = s * (up ** (steps - i)) * (down ** i)
        call_values[i] = max(terminal_price - k, 0.0)
        put_values[i] = max(k - terminal_price, 0.0)

    for step in range(steps - 1, -1, -1):
        for i in range(step + 1):
            continuation_call = discount * (
                probability * call_values[i] + (1.0 - probability) * call_values[i + 1]
            )
            continuation_put = discount * (
                probability * put_values[i] + (1.0 - probability) * put_values[i + 1]
            )

            if american:
                spot = s * (up ** (step - i)) * (down ** i)
                exercise_call = max(spot - k, 0.0)
                exercise_put = max(k - spot, 0.0)
                call_values[i] = max(continuation_call, exercise_call)
                put_values[i] = max(continuation_put, exercise_put)
            else:
                call_values[i] = continuation_call
                put_values[i] = continuation_put

    return call_values[0], put_values[0]


def build_tree_levels(
    s: float,
    k: float,
    r: float,
    q: float,
    sigma: float,
    t: float,
    steps: int = 6,
    american: bool = True,
) -> list[list[dict[str, float]]]:
    if s <= 0 or k <= 0:
        raise ValueError("S y K deben ser mayores que 0.")
    if sigma <= 0:
        raise ValueError("La volatilidad debe ser mayor que 0.")
    if t <= 0:
        raise ValueError("El tiempo a vencimiento debe ser mayor que 0.")
    if steps <= 0:
        raise ValueError("El numero de pasos binomiales debe ser mayor que 0.")

    dt = t / steps
    up = exp(sigma * sqrt(dt))
    down = 1.0 / up
    growth = exp((r - q) * dt)
    probability = (growth - down) / (up - down)

    if not 0.0 < probability < 1.0:
        raise ValueError("Parametros no validos para el arbol binomial.")

    discount = exp(-r * dt)

    stock_levels: list[list[float]] = []
    for step in range(steps + 1):
        level = []
        for i in range(step + 1):
            level.append(s * (up ** (step - i)) * (down ** i))
        stock_levels.append(level)

    call_levels: list[list[float]] = [[0.0] * (step + 1) for step in range(steps + 1)]
    put_levels: list[list[float]] = [[0.0] * (step + 1) for step in range(steps + 1)]

    for i, terminal_price in enumerate(stock_levels[-1]):
        call_levels[-1][i] = max(terminal_price - k, 0.0)
        put_levels[-1][i] = max(k - terminal_price, 0.0)

    for step in range(steps - 1, -1, -1):
        for i in range(step + 1):
            continuation_call = discount * (
                probability * call_levels[step + 1][i] + (1.0 - probability) * call_levels[step + 1][i + 1]
            )
            continuation_put = discount * (
                probability * put_levels[step + 1][i] + (1.0 - probability) * put_levels[step + 1][i + 1]
            )

            if american:
                spot = stock_levels[step][i]
                exercise_call = max(spot - k, 0.0)
                exercise_put = max(k - spot, 0.0)
                call_levels[step][i] = max(continuation_call, exercise_call)
                put_levels[step][i] = max(continuation_put, exercise_put)
            else:
                call_levels[step][i] = continuation_call
                put_levels[step][i] = continuation_put

    tree_levels: list[list[dict[str, float]]] = []
    for step in range(steps + 1):
        level_nodes: list[dict[str, float]] = []
        for i in range(step + 1):
            level_nodes.append(
                {
                    "spot": stock_levels[step][i],
                    "call": call_levels[step][i],
                    "put": put_levels[step][i],
                }
            )
        tree_levels.append(level_nodes)

    return tree_levels
