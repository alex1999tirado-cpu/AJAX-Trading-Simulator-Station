import os
import tempfile
from dataclasses import dataclass

_OPTIONS_CACHE: dict[str, bool] = {}


@dataclass
class OptionQuote:
    strike: float
    implied_volatility: float | None
    last_price: float | None
    bid: float | None
    ask: float | None
    mid_price: float | None
    volume: int | None
    open_interest: int | None


@dataclass
class MarketSnapshot:
    spot_price: float
    currency: str | None
    exchange: str | None
    dividend_yield: float
    risk_free_rate: float | None
    expirations: list[str]
    history_dates: list[object]
    history_opens: list[float]
    history_highs: list[float]
    history_lows: list[float]
    history_closes: list[float]


def _require_yfinance():
    try:
        import yfinance as yf
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(
            "Falta yfinance. Instala dependencias con: pip install -r requirements.txt"
        ) from error

    return yf


def _friendly_market_data_error(error: Exception) -> ValueError:
    message = str(error)
    lowered = message.lower()

    if "timed out" in lowered or "timeout" in lowered:
        return ValueError(
            "Yahoo Finance ha tardado demasiado en responder. Vuelve a intentarlo en unos segundos."
        )
    if "could not resolve host" in lowered or "dns" in lowered:
        return ValueError(
            "No se pudo resolver el servidor de Yahoo Finance. Revisa la conexion a internet."
        )
    if "recv failure" in lowered or "connection" in lowered:
        return ValueError(
            "Fallo de conexion con Yahoo Finance. Vuelve a intentarlo."
        )

    return ValueError(f"No se pudieron cargar datos de mercado: {message}")


def _require_plotting():
    try:
        os.environ.setdefault(
            "MPLCONFIGDIR",
            os.path.join(tempfile.gettempdir(), "valorador_opciones_mpl"),
        )
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(
            "Falta matplotlib. Instala dependencias con: pip install -r requirements.txt"
        ) from error

    return plt


def fetch_market_snapshot(ticker_symbol: str, history_period: str = "1y") -> MarketSnapshot:
    yf = _require_yfinance()
    ticker = yf.Ticker(ticker_symbol)

    try:
        history = ticker.history(period=history_period, auto_adjust=False)
        if history.empty:
            raise ValueError("No se han encontrado datos historicos para ese ticker.")

        latest_close = float(history["Close"].dropna().iloc[-1])
        info = ticker.info or {}
        currency = info.get("currency")
        exchange = info.get("exchange") or info.get("fullExchangeName")
        raw_dividend_yield = info.get("dividendYield")
        annual_dividend_rate = info.get("trailingAnnualDividendRate") or info.get("dividendRate")
        dividend_yield = _normalize_dividend_yield(
            raw_dividend_yield=raw_dividend_yield,
            annual_dividend_rate=annual_dividend_rate,
            spot_price=latest_close,
        )
        risk_free_rate = fetch_risk_free_rate(ticker_symbol)
        expirations = list(ticker.options)
        if not expirations:
            raise ValueError(
                "No hay vencimientos de opciones disponibles para este ticker. "
                "Prueba con un ETF o proxy optionable."
            )
    except ValueError:
        raise
    except Exception as error:
        raise _friendly_market_data_error(error) from error

    return MarketSnapshot(
        spot_price=latest_close,
        currency=currency,
        exchange=exchange,
        dividend_yield=dividend_yield,
        risk_free_rate=risk_free_rate,
        expirations=expirations,
        history_dates=list(history.index),
        history_opens=[float(value) for value in history["Open"].tolist()],
        history_highs=[float(value) for value in history["High"].tolist()],
        history_lows=[float(value) for value in history["Low"].tolist()],
        history_closes=[float(value) for value in history["Close"].tolist()],
    )


def fetch_option_chain(ticker_symbol: str, expiration: str) -> tuple[dict[float, OptionQuote], dict[float, OptionQuote]]:
    yf = _require_yfinance()
    ticker = yf.Ticker(ticker_symbol)

    try:
        chain = ticker.option_chain(expiration)
        calls = _build_quotes(chain.calls)
        puts = _build_quotes(chain.puts)

        if not calls and not puts:
            raise ValueError("No hay strikes disponibles para ese vencimiento.")
    except ValueError:
        raise
    except Exception as error:
        raise _friendly_market_data_error(error) from error

    return calls, puts


def search_tickers(query: str, max_results: int = 8, underlying_type: str | None = None) -> list[dict[str, str]]:
    yf = _require_yfinance()
    normalized_query = query.strip()
    if not normalized_query:
        return []

    search = yf.Search(normalized_query, max_results=max_results, news_count=0, lists_count=0)
    results: list[dict[str, str]] = []
    filtered_quotes = _filter_quotes_by_underlying_type(search.quotes, underlying_type)

    for quote in filtered_quotes:
        symbol = quote.get("symbol")
        if not symbol:
            continue

        shortname = quote.get("shortname") or quote.get("longname") or ""
        quote_type = quote.get("quoteType") or ""
        exchange = quote.get("exchange") or ""
        label_parts = [symbol]
        if shortname:
            label_parts.append(shortname)
        if quote_type:
            label_parts.append(f"[{quote_type}]")
        if exchange:
            label_parts.append(f"({exchange})")

        results.append(
            {
                "symbol": symbol.strip().upper(),
                "label": " ".join(label_parts),
                "name": shortname,
                "quote_type": quote_type,
                "exchange": exchange,
            }
        )

    results.sort(key=lambda item: _search_rank(item, normalized_query))
    return results


def ticker_has_options(ticker_symbol: str) -> bool:
    normalized_symbol = ticker_symbol.strip().upper()
    cached_result = _OPTIONS_CACHE.get(normalized_symbol)
    if cached_result is not None:
        return cached_result

    yf = _require_yfinance()
    try:
        expirations = list(yf.Ticker(normalized_symbol).options)
        has_options = bool(expirations)
    except Exception:
        has_options = False

    _OPTIONS_CACHE[normalized_symbol] = has_options
    return has_options


def fetch_risk_free_rate(ticker_symbol: str) -> float | None:
    yf = _require_yfinance()
    rate_symbol = _risk_free_proxy_symbol(ticker_symbol)
    candidates = [rate_symbol]
    if rate_symbol != "^TNX":
        candidates.append("^TNX")

    for candidate in candidates:
        try:
            history = yf.Ticker(candidate).history(period="5d", auto_adjust=False)
            if history.empty:
                continue
            latest_close = float(history["Close"].dropna().iloc[-1])
            return _normalize_rate_quote(latest_close)
        except Exception:
            continue

    return None


def _filter_quotes_by_underlying_type(quotes, underlying_type: str | None):
    if not underlying_type:
        return list(quotes)

    allowed_types = {
        "Acciones": {"equity"},
        "Indices": {"index"},
        "ETFs": {"etf", "fund"},
        "Commodities": {"etf", "fund", "equity"},
        "Rates Proxies": {"etf", "fund", "bond"},
        "Benchmarks": {"index", "bond", "currency"},
        "FX": {"currency", "etf", "fund"},
    }.get(underlying_type, set())

    filtered = []
    for quote in quotes:
        quote_type = str(quote.get("quoteType") or "").strip().lower()
        if not allowed_types or quote_type in allowed_types:
            filtered.append(quote)
    return filtered or list(quotes)


def _search_rank(item: dict[str, str], query: str) -> tuple[int, str]:
    normalized_query = query.casefold()
    symbol = item["symbol"].casefold()
    label = item["label"].casefold()
    name = item.get("name", "").casefold()

    if symbol == normalized_query:
        score = 0
    elif symbol.startswith(normalized_query):
        score = 1
    elif normalized_query in name:
        score = 2
    elif normalized_query in label:
        score = 3
    else:
        score = 4

    return (score, item["label"].casefold())


def _build_quotes(frame) -> dict[float, OptionQuote]:
    quotes: dict[float, OptionQuote] = {}
    for row in frame.itertuples(index=False):
        iv = getattr(row, "impliedVolatility", None)
        last_price = getattr(row, "lastPrice", None)
        bid = getattr(row, "bid", None)
        ask = getattr(row, "ask", None)
        volume = getattr(row, "volume", None)
        open_interest = getattr(row, "openInterest", None)
        strike = float(getattr(row, "strike"))
        bid_value = float(bid) if bid is not None else None
        ask_value = float(ask) if ask is not None else None
        mid_price = _mid_price(bid_value, ask_value, float(last_price) if last_price is not None else None)
        quotes[strike] = OptionQuote(
            strike=strike,
            implied_volatility=float(iv) if iv is not None else None,
            last_price=float(last_price) if last_price is not None else None,
            bid=bid_value,
            ask=ask_value,
            mid_price=mid_price,
            volume=int(volume) if volume is not None and volume == volume else None,
            open_interest=int(open_interest) if open_interest is not None and open_interest == open_interest else None,
        )
    return quotes


def _mid_price(bid: float | None, ask: float | None, last_price: float | None) -> float | None:
    if bid is not None and ask is not None and bid > 0 and ask > 0:
        return (bid + ask) / 2.0
    if last_price is not None:
        return last_price
    return None


def _normalize_dividend_yield(
    raw_dividend_yield: float | None,
    annual_dividend_rate: float | None,
    spot_price: float,
) -> float:
    if annual_dividend_rate is not None and spot_price > 0:
        annual_dividend_rate = float(annual_dividend_rate)
        if annual_dividend_rate > 0:
            return annual_dividend_rate / spot_price

    if raw_dividend_yield is None:
        return 0.0

    dividend_yield = float(raw_dividend_yield)
    if dividend_yield > 0.2:
        return dividend_yield / 100.0
    return dividend_yield


def _risk_free_proxy_symbol(ticker_symbol: str) -> str:
    european_suffixes = (".AS", ".BR", ".CO", ".DE", ".L", ".MC", ".MI", ".PA", ".SW")
    european_indices = {"^AEX", "^BFX", "^FCHI", "^FTMIB", "^FTSE", "^GDAXI", "^IBEX", "^N100", "^SMI", "^STOXX50E"}
    normalized_symbol = ticker_symbol.strip().upper()

    if normalized_symbol in european_indices or normalized_symbol.endswith(european_suffixes):
        return "DE10Y.BD"
    return "^TNX"


def _normalize_rate_quote(value: float) -> float:
    if value > 1.0:
        return value / 100.0
    return value


def plot_underlying_history(ticker_symbol: str, snapshot: MarketSnapshot) -> None:
    plt = _require_plotting()

    figure, axis = plt.subplots(figsize=(9, 4.8))
    _draw_candlesticks(axis, snapshot)
    axis.set_title(f"{ticker_symbol.upper()}")
    axis.set_xlabel("Fecha")
    axis.set_ylabel("Precio")
    axis.grid(alpha=0.25)
    figure.autofmt_xdate()
    plt.tight_layout()
    plt.show()


def build_underlying_figure(
    ticker_symbol: str,
    snapshot: MarketSnapshot,
    selected_strike: float | None = None,
):
    os.environ.setdefault(
        "MPLCONFIGDIR",
        os.path.join(tempfile.gettempdir(), "valorador_opciones_mpl"),
    )
    from matplotlib.figure import Figure
    from matplotlib import dates as mdates
    from matplotlib.ticker import MaxNLocator

    figure = Figure(figsize=(8.8, 4.8), dpi=100)
    figure.patch.set_facecolor("#101112")
    axis = figure.add_subplot(111)
    axis.set_facecolor("#121315")
    _draw_candlesticks(axis, snapshot)
    y_min, y_max = _chart_price_limits(snapshot.history_lows, snapshot.history_highs)
    last_spot = snapshot.history_closes[-1]
    previous_close = snapshot.history_closes[-2] if len(snapshot.history_closes) > 1 else last_spot
    price_change = last_spot - previous_close
    price_color = "#20c35a" if price_change >= 0 else "#ea4f46"
    right_edge = mdates.date2num(snapshot.history_dates[-1]) + 4.2

    axis.axhline(last_spot, color="#f0c24f", linewidth=0.9, linestyle="--", alpha=0.65)
    if selected_strike is not None and y_min <= selected_strike <= y_max:
        axis.axhline(selected_strike, color="#d6655d", linewidth=0.9, linestyle=":", alpha=0.8)
    axis.set_ylim(y_min, y_max)
    axis.set_xlim(
        mdates.date2num(snapshot.history_dates[0]) - 3,
        right_edge,
    )
    axis.text(
        0.015,
        0.97,
        f"{ticker_symbol.upper()}  {last_spot:.2f}",
        transform=axis.transAxes,
        va="top",
        ha="left",
        color="#ececec",
        fontsize=14,
        fontweight="bold",
    )
    axis.text(
        0.015,
        0.915,
        f"{price_change:+.2f}",
        transform=axis.transAxes,
        va="top",
        ha="left",
        color=price_color,
        fontsize=11,
    )
    axis.text(
        right_edge - 2.3,
        last_spot,
        f"{last_spot:.2f}",
        va="center",
        ha="left",
        color="#101112",
        fontsize=10,
        fontweight="bold",
        bbox={
            "boxstyle": "round,pad=0.2,rounding_size=0.12",
            "facecolor": "#f0c24f",
            "edgecolor": "#f0c24f",
            "linewidth": 0.0,
        },
        zorder=5,
        clip_on=False,
    )
    axis.yaxis.tick_right()
    axis.yaxis.set_label_position("right")
    axis.yaxis.set_major_locator(MaxNLocator(nbins=8))
    axis.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    axis.tick_params(axis="x", colors="#8f9499", labelsize=9, length=0, pad=8)
    axis.tick_params(axis="y", colors="#d6d6d6", labelsize=10, length=0, pad=8)
    axis.spines["left"].set_visible(False)
    axis.spines["top"].set_visible(False)
    axis.spines["bottom"].set_color("#2a2b2e")
    axis.spines["right"].set_color("#2a2b2e")
    axis.grid(axis="y", color="#2d2f33", alpha=0.35, linewidth=0.8)
    axis.grid(axis="x", visible=False)
    axis.margins(x=0.02)
    figure.subplots_adjust(left=0.02, right=0.915, top=0.96, bottom=0.12)
    return figure


def _draw_candlesticks(axis, snapshot: MarketSnapshot) -> None:
    from matplotlib import dates as mdates
    from matplotlib.patches import Rectangle

    x_values = mdates.date2num(snapshot.history_dates)
    candle_width = max(0.18, min(0.72, 210 / max(len(x_values), 1)))

    for x_value, open_price, high_price, low_price, close_price in zip(
        x_values,
        snapshot.history_opens,
        snapshot.history_highs,
        snapshot.history_lows,
        snapshot.history_closes,
    ):
        color = "#21c55d" if close_price >= open_price else "#e4584f"
        wick_color = "#8fd4aa" if close_price >= open_price else "#f0a099"
        axis.vlines(x_value, low_price, high_price, color=wick_color, linewidth=0.9, alpha=0.9, zorder=2)
        body_low = min(open_price, close_price)
        body_height = abs(close_price - open_price)
        if body_height < 0.001:
            axis.hlines(close_price, x_value - candle_width / 2, x_value + candle_width / 2, color=color, linewidth=1.4, zorder=3)
            continue
        axis.add_patch(
            Rectangle(
                (x_value - candle_width / 2, body_low),
                candle_width,
                body_height,
                facecolor=color,
                edgecolor=color,
                linewidth=0,
                zorder=3,
            )
        )

    axis.xaxis_date()


def _chart_price_limits(history_lows: list[float], history_highs: list[float]) -> tuple[float, float]:
    min_price = min(history_lows)
    max_price = max(history_highs)
    price_range = max_price - min_price

    if price_range == 0:
        padding = max(abs(max_price) * 0.05, 1.0)
        return min_price - padding, max_price + padding

    padding = price_range * 0.08
    return min_price - padding, max_price + padding
