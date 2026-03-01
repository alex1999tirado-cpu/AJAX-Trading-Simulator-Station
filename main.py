from datetime import date, datetime, timedelta
from pricer.blackscholes import greeks
from pricer.binomial import build_tree_levels
from pricer.engine import DEFAULT_BINOMIAL_STEPS, ValuationResult, compute_valuations
from pricer.marketdata import (
    build_underlying_figure,
    fetch_market_snapshot,
    fetch_option_chain,
    search_tickers,
    ticker_has_options,
)

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ModuleNotFoundError:
    tk = None
    messagebox = None
    ttk = None


UNDERLYING_TYPES: dict[str, dict[str, str]] = {
    "Acciones": {
        "example": "AAPL",
        "help": "USA + Europa. Ejemplos: AAPL, MSFT, NVDA, ASML.AS, MC.PA, SAN.MC",
    },
    "Indices": {
        "example": "^STOXX50E",
        "help": "USA + Europa. Ejemplos: ^SPX, ^NDX, ^DJI, ^STOXX50E, ^GDAXI, ^FCHI",
    },
    "ETFs": {
        "example": "SPY",
        "help": "ETFs optionables. Ejemplos: SPY, QQQ, IWM, TLT, GLD, SLV, VGK, EEM",
    },
    "Commodities": {
        "example": "GLD",
        "help": "Proxy ETF optionable. Ejemplos: GLD, SLV, USO, UNG, DBA, CORN",
    },
    "Rates Proxies": {
        "example": "TLT",
        "help": "Proxy ETF de rates. Ejemplos: TLT, IEF, SHY, BIL, SGOV, TIP",
    },
    "Benchmarks": {
        "example": "^TNX",
        "help": "Referencias de tipos y yields. Ejemplos: ^TNX, DE10Y.BD, ^IRX, SOFR proxies",
    },
    "FX": {
        "example": "FXE",
        "help": "Proxy ETF/ETN optionable. Ejemplos: FXE, FXB, FXY, FXA, FXC, FXF",
    },
}

SYMBOLS_BY_TYPE: dict[str, list[str]] = {
    "Acciones": [
        "AAPL", "AMZN", "ASML.AS", "AZN.L", "BMW.DE", "BNP.PA", "IBE.MC", "IFX.DE",
        "MC.PA", "META", "MSFT", "NESN.SW", "NOVO-B.CO", "NVDA", "OR.PA", "RACE.MI",
        "RMS.PA", "SAN.MC", "SAP.DE", "SHEL.L", "SIE.DE", "SU.PA", "TSLA", "ULVR.L",
    ],
    "Indices": [
        "^AEX", "^BFX", "^DJI", "^FCHI", "^FTMIB", "^FTSE", "^GDAXI", "^IBEX", "^N100",
        "^NDX", "^RUT", "^SMI", "^SPX", "^STOXX50E", "^VIX",
    ],
    "ETFs": [
        "DIA", "EEM", "EFA", "EWG", "EWQ", "EWU", "EZU", "FEZ", "GLD", "HYG",
        "IEF", "IWM", "LQD", "QQQ", "SHY", "SLV", "SPY", "TIP", "TLT", "VGK",
    ],
    "Commodities": [
        "CORN", "CPER", "DBA", "GLD", "IAU", "SLV", "SOYB", "UNG", "USO", "WEAT",
    ],
    "Rates Proxies": [
        "BIL", "BSV", "GOVT", "HYG", "IEF", "LQD", "MINT", "SGOV", "SHY", "TIP", "TLT", "VGSH",
    ],
    "Benchmarks": [
        "DE10Y.BD", "^FVX", "^IRX", "^TNX", "^TYX",
    ],
    "FX": [
        "CYB", "FXA", "FXB", "FXC", "FXE", "FXF", "FXY", "UUP",
    ],
}

INFERRED_STYLE_BY_TYPE: dict[str, str] = {
    "Acciones": "Americana",
    "Indices": "Europea",
    "ETFs": "Americana",
    "Commodities": "Americana",
    "Rates Proxies": "Americana",
    "Benchmarks": "Europea",
    "FX": "Americana",
}

EUROPEAN_SYMBOL_SUFFIXES = (".AS", ".BR", ".CO", ".DE", ".L", ".MC", ".MI", ".PA", ".SW")
US_INDEX_SYMBOLS = {"^DJI", "^NDX", "^RUT", "^SPX", "^VIX"}
EUROPEAN_CURRENCIES = {"EUR", "GBP", "CHF", "DKK", "NOK", "SEK"}
EUROPEAN_EXCHANGE_MARKERS = ("EURONEXT", "XETRA", "BME", "BMV", "LSE", "SIX", "MILAN", "PARIS", "MADRID", "FRANKFURT")

DEFAULT_MC_COMPARISON_SIMULATIONS = 25000


def calculate_years_to_maturity(expiry_text: str) -> float:
    expiry_date = parse_expiry_date(expiry_text)
    valuation_date = get_valuation_date()
    days_to_expiry = (expiry_date - valuation_date).days

    if days_to_expiry <= 0:
        raise ValueError("La fecha de vencimiento debe ser posterior a la fecha de valoracion.")

    return days_to_expiry / 365.0


def get_valuation_date() -> date:
    today = date.today()
    weekday = today.weekday()

    if weekday == 5:
        return today + timedelta(days=2)
    if weekday == 6:
        return today + timedelta(days=1)

    return today


def parse_expiry_date(expiry_text: str) -> date:
    normalized_text = expiry_text.strip()
    try:
        return datetime.strptime(normalized_text, "%d/%m/%Y").date()
    except ValueError as error:
        raise ValueError("Fecha no valida. Usa el formato DD/MM/AAAA.") from error


def iso_to_display_date(expiration: str) -> str:
    return datetime.strptime(expiration, "%Y-%m-%d").strftime("%d/%m/%Y")


def display_to_iso_date(expiration: str) -> str:
    return datetime.strptime(expiration, "%d/%m/%Y").strftime("%Y-%m-%d")


def format_price(value: float | None) -> str:
    return "-" if value is None else f"{value:.4f}"


def format_number(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def calculate_error(model_value: float | None, market_value: float | None) -> tuple[str, str]:
    if model_value is None or market_value is None:
        return "-", "-"
    abs_error = model_value - market_value
    pct_error = abs_error / market_value * 100.0 if market_value else 0.0
    return f"{abs_error:+.4f}", f"{pct_error:+.2f}%"


def infer_exercise_style(
    underlying_type: str,
    symbol: str,
    currency: str | None = None,
    exchange: str | None = None,
) -> str:
    normalized_symbol = symbol.strip().upper()
    normalized_currency = (currency or "").strip().upper()
    normalized_exchange = (exchange or "").strip().upper()

    if normalized_currency in EUROPEAN_CURRENCIES:
        return "Europea"
    if any(marker in normalized_exchange for marker in EUROPEAN_EXCHANGE_MARKERS):
        return "Europea"
    if normalized_symbol.endswith(EUROPEAN_SYMBOL_SUFFIXES):
        return "Europea"
    if normalized_symbol in US_INDEX_SYMBOLS:
        return "Americana"
    if symbol.startswith("^"):
        return "Europea"
    return INFERRED_STYLE_BY_TYPE.get(underlying_type, "Americana")


def resolve_exercise_style(
    underlying_type: str,
    symbol: str,
    currency: str | None = None,
    exchange: str | None = None,
) -> tuple[str, str]:
    inferred_style = infer_exercise_style(underlying_type, symbol, currency=currency, exchange=exchange)
    return inferred_style, f"{inferred_style} (inferida)"


def run_cli() -> None:
    print("tkinter no esta disponible en este Python. Se usa modo consola.")
    print(f"Fecha de valoracion: {get_valuation_date().isoformat()}")
    try:
        underlying_type = input("Tipo de subyacente (Acciones/Indices/ETFs/Commodities/Rates Proxies/Benchmarks/FX): ").strip() or "Acciones"
        symbol = input("Simbolo: ").strip() or UNDERLYING_TYPES["Acciones"]["example"]
        s = float(input("Precio actual del activo (S): "))
        k = float(input("Precio de ejercicio (K): "))
        r = float(input("Tasa libre de riesgo (r): "))
        q = float(input("Dividend yield (q): "))
        sigma = float(input("Volatilidad (sigma): "))
        expiry_text = input("Fecha de vencimiento (DD/MM/AAAA): ")

        t = calculate_years_to_maturity(expiry_text)
        simulations = int(input("Numero de simulaciones Monte Carlo (referencia): ") or DEFAULT_MC_COMPARISON_SIMULATIONS)

        effective_style, style_label = resolve_exercise_style(underlying_type, symbol)
        valuation = compute_valuations(
            effective_style,
            s,
            k,
            r,
            q,
            sigma,
            t,
            simulations=simulations,
        )
        selected_output = valuation.models[valuation.effective_method]
        call = selected_output.call
        put = selected_output.put
        effective_model = valuation.effective_label
    except ValueError as error:
        print(f"\nError: {error}")
        return

    print("\nModo de valoracion: automatico")
    print(f"Estilo de ejercicio: {style_label}")
    print(f"Modelo principal: {effective_model}")
    print(f"\nT: {t:.6f} anos")
    print(f"Simulaciones MC referencia: {simulations}")
    print(f"Precio Call: {call:.4f}" if call is not None else "Precio Call: n/a")
    print(f"Precio Put: {put:.4f}" if put is not None else "Precio Put: n/a")


def build_app() -> "Tk":
    root = tk.Tk()
    root.title("Valorador de opciones")
    left_panel_width = 520
    colors = {
        "bg": "#090909",
        "panel": "#101112",
        "panel_alt": "#171819",
        "panel_soft": "#1f2124",
        "border": "#2a2b2e",
        "text": "#ececec",
        "muted": "#8a8d93",
        "accent": "#4f6f8f",
        "accent_soft": "#29394a",
        "amber": "#f0c24f",
        "green": "#0c8d2b",
        "green_bright": "#20c35a",
        "red": "#a11b17",
        "red_bright": "#ea4f46",
        "row": "#111214",
        "row_alt": "#17181b",
        "atm": "#6b5b1f",
        "atm_text": "#f7f7f7",
        "atm_border": "#fff2b3",
    }
    root.configure(bg=colors["bg"])
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", background=colors["bg"], foreground=colors["text"], fieldbackground=colors["panel"], font=("Menlo", 10))
    style.configure("TFrame", background=colors["bg"])
    style.configure("Panel.TFrame", background=colors["panel"])
    style.configure(
        "TLabelframe",
        background=colors["panel"],
        bordercolor=colors["border"],
        relief="solid",
        borderwidth=1,
    )
    style.configure("TLabelframe.Label", background=colors["panel"], foreground=colors["muted"], font=("Menlo", 10, "bold"))
    style.configure("TLabel", background=colors["bg"], foreground=colors["text"], font=("Menlo", 10))
    style.configure("Panel.TLabel", background=colors["panel"], foreground=colors["text"], font=("Menlo", 10))
    style.configure("Muted.TLabel", background=colors["panel"], foreground=colors["muted"], font=("Menlo", 9))
    style.configure(
        "TButton",
        background=colors["panel_soft"],
        foreground=colors["text"],
        bordercolor=colors["border"],
        focusthickness=0,
        padding=(10, 7),
    )
    style.map("TButton", background=[("active", colors["accent"])], foreground=[("active", colors["text"])])
    style.configure("Accent.TButton", background=colors["panel_soft"], foreground=colors["text"], bordercolor=colors["accent"])
    style.map("Accent.TButton", background=[("active", colors["accent_soft"])])
    style.configure(
        "TCombobox",
        fieldbackground=colors["panel_alt"],
        background=colors["panel_alt"],
        foreground=colors["text"],
        arrowcolor=colors["muted"],
        bordercolor=colors["border"],
        padding=5,
    )
    style.map("TCombobox", fieldbackground=[("readonly", colors["panel_alt"])], foreground=[("readonly", colors["text"])])
    style.configure(
        "TEntry",
        fieldbackground=colors["panel_alt"],
        foreground=colors["text"],
        insertcolor=colors["text"],
        bordercolor=colors["border"],
        padding=5,
    )
    style.configure("TRadiobutton", background=colors["panel"], foreground=colors["text"])
    style.map("TRadiobutton", foreground=[("selected", colors["amber"])])
    style.configure(
        "Treeview",
        background=colors["row"],
        fieldbackground=colors["row"],
        foreground=colors["text"],
        bordercolor=colors["border"],
        rowheight=24,
    )
    style.map("Treeview", background=[("selected", "#31485e")], foreground=[("selected", "#ffffff")])
    style.configure("Treeview.Heading", background=colors["panel_alt"], foreground=colors["muted"], relief="flat")
    style.configure("Vertical.TScrollbar", background=colors["panel_alt"], troughcolor=colors["bg"])

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.geometry(f"{screen_width}x{screen_height}")
    root.minsize(1260, 820)
    root.resizable(True, True)
    try:
        root.state("zoomed")
    except tk.TclError:
        pass

    main_frame = ttk.Frame(root, padding=10, style="Panel.TFrame")
    main_frame.pack(fill="both", expand=True)
    main_frame.columnconfigure(0, weight=0, minsize=left_panel_width)
    main_frame.columnconfigure(1, weight=1)
    main_frame.rowconfigure(1, weight=1)

    header = ttk.Frame(main_frame, style="Panel.TFrame")
    header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    header.columnconfigure(0, weight=1)
    header.columnconfigure(1, weight=1)
    header.columnconfigure(2, weight=1)

    tk.Label(
        header,
        text="AJAX Trading Simulation Station",
        font=("Menlo", 16, "bold"),
        bg=colors["bg"],
        fg=colors["text"],
    ).grid(row=0, column=0, sticky="w")
    tk.Label(
        header,
        text="By Alejandro Tirado Pulgarin",
        font=("Menlo", 10),
        bg=colors["bg"],
        fg=colors["muted"],
    ).grid(row=1, column=0, sticky="w", pady=(4, 0))
    tk.Label(
        header,
        text=f"Fecha de valoracion: {get_valuation_date().isoformat()}",
        font=("Menlo", 10),
        bg=colors["bg"],
        fg=colors["muted"],
    ).grid(row=0, column=2, sticky="e")

    left_panel = ttk.Frame(main_frame, style="Panel.TFrame")
    left_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
    left_panel.configure(width=left_panel_width)
    left_panel.columnconfigure(0, weight=1)
    left_panel.rowconfigure(0, weight=0)
    left_panel.rowconfigure(1, weight=1)
    left_panel.grid_propagate(False)

    right_panel = ttk.Frame(main_frame, style="Panel.TFrame")
    right_panel.grid(row=1, column=1, sticky="nsew")
    right_panel.columnconfigure(0, weight=1)
    right_panel.rowconfigure(0, weight=0)
    right_panel.rowconfigure(1, weight=6)
    right_panel.rowconfigure(2, weight=8)

    input_frame = ttk.LabelFrame(left_panel, text="Datos", padding=10)
    input_frame.grid(row=0, column=0, sticky="ew")
    input_frame.columnconfigure(0, weight=0, minsize=128)
    input_frame.columnconfigure(1, weight=1)

    results_frame = ttk.LabelFrame(left_panel, text="Resultados", padding=10)
    results_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
    results_frame.columnconfigure(0, weight=1)
    results_frame.rowconfigure(1, weight=1)

    market_frame = ttk.LabelFrame(right_panel, text="Mercado", padding=10)
    market_frame.grid(row=0, column=0, sticky="ew")
    for column in range(5):
        market_frame.columnconfigure(column, weight=1)

    chain_frame = ttk.LabelFrame(right_panel, text="Cadena", padding=8)
    chain_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 8))
    chain_frame.columnconfigure(0, weight=1)
    chain_frame.rowconfigure(1, weight=1)

    center_display = ttk.Frame(right_panel, style="Panel.TFrame")
    center_display.grid(row=2, column=0, sticky="nsew")
    center_display.columnconfigure(0, weight=1)
    center_display.columnconfigure(1, weight=24)
    center_display.rowconfigure(0, weight=1)

    quote_frame = ttk.LabelFrame(center_display, text="Quote", padding=10)
    quote_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    quote_frame.columnconfigure(0, weight=1)

    chart_host = ttk.Frame(center_display, style="Panel.TFrame")
    chart_host.grid(row=0, column=1, sticky="nsew")
    chart_host.columnconfigure(0, weight=1)
    chart_host.rowconfigure(0, weight=1)
    chart_host.grid_propagate(False)

    chart_frame = ttk.LabelFrame(chart_host, text="Grafico", padding=8)
    chart_frame.grid(row=0, column=0, sticky="nsew")
    chart_frame.columnconfigure(0, weight=1)
    chart_frame.rowconfigure(0, weight=1)
    chart_frame.grid_propagate(False)

    compare_frame = ttk.LabelFrame(results_frame, text="Compare", padding=8)
    compare_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
    compare_frame.columnconfigure(0, weight=1)
    compare_frame.rowconfigure(0, weight=1)

    underlying_type_var = tk.StringVar(value="Acciones")
    ticker_var = tk.StringVar(value=UNDERLYING_TYPES["Acciones"]["example"])
    expiry_var = tk.StringVar()
    strike_var = tk.StringVar()
    ticker_help_var = tk.StringVar(value=UNDERLYING_TYPES["Acciones"]["help"])
    inferred_style_var = tk.StringVar(value="Estilo ejercicio: Americana")
    chain_header_var = tk.StringVar(value="Ticker: -    Vencimiento: -")
    chain_selection_var = tk.StringVar(value="Seleccion actual: -")
    chart_status_var = tk.StringVar(value="")
    chart_view_var = tk.StringVar(value="Grafico")
    monitor_symbol_var = tk.StringVar(value="SYMBOL")
    monitor_spot_var = tk.StringVar(value="Spot -")
    monitor_change_var = tk.StringVar(value="Chg -")
    monitor_iv_var = tk.StringVar(value="IV ATM -")
    monitor_style_var = tk.StringVar(value="Style -")
    monitor_expiry_var = tk.StringVar(value="Expiry -")
    result_method = tk.StringVar(value="-")
    result_style = tk.StringVar(value="-")
    result_model = tk.StringVar(value="-")
    result_t = tk.StringVar(value="-")
    result_simulations = tk.StringVar(value="-")
    result_market_call = tk.StringVar(value="-")
    result_market_put = tk.StringVar(value="-")
    result_call = tk.StringVar(value="-")
    result_put = tk.StringVar(value="-")
    summary_call_put_var = tk.StringVar(value="- / -")
    quote_call_bid_var = tk.StringVar(value="Call bid: -")
    quote_call_ask_var = tk.StringVar(value="Call ask: -")
    quote_call_mid_var = tk.StringVar(value="Call mid: -")
    quote_put_bid_var = tk.StringVar(value="Put bid: -")
    quote_put_ask_var = tk.StringVar(value="Put ask: -")
    quote_put_mid_var = tk.StringVar(value="Put mid: -")
    quote_spread_var = tk.StringVar(value="Spread: -")
    quote_oi_var = tk.StringVar(value="OI: -")
    quote_volume_var = tk.StringVar(value="Vol: -")
    quote_currency_var = tk.StringVar(value="")
    greek_delta_var = tk.StringVar(value="Delta: -")
    greek_gamma_var = tk.StringVar(value="Gamma: -")
    greek_vega_var = tk.StringVar(value="Vega: -")
    greek_theta_var = tk.StringVar(value="Theta: -")
    greek_rho_var = tk.StringVar(value="Rho: -")
    status_var = tk.StringVar(value="Ready")

    entries: dict[str, ttk.Entry] = {}
    market_state: dict[str, object] = {
        "snapshot": None,
        "calls": {},
        "puts": {},
        "chart_canvas": None,
        "chart_widget": None,
        "chart_figure": None,
        "chart_resize_binding": None,
        "last_tree_inputs": None,
        "market_job": None,
        "chain_job": None,
        "ticker_search_job": None,
        "ticker_suggestion_map": {},
        "ticker_meta_map": {},
        "ticker_suggestion_labels": [],
    }

    def normalize_ticker_input(raw_value: str) -> str:
        return raw_value.strip().split()[0].upper() if raw_value.strip() else ""

    def hide_ticker_suggestions() -> None:
        suggestion_listbox.selection_clear(0, tk.END)
        suggestion_listbox.delete(0, tk.END)
        market_state["ticker_suggestion_labels"] = []
        suggestion_frame.grid_remove()

    def show_ticker_suggestions(labels: list[str]) -> None:
        suggestion_listbox.delete(0, tk.END)
        for label in labels:
            suggestion_listbox.insert(tk.END, label)
        market_state["ticker_suggestion_labels"] = labels
        if labels:
            suggestion_frame.grid()
            suggestion_listbox.selection_set(0)
        else:
            suggestion_frame.grid_remove()

    def render_binomial_tree(
        s: float,
        k: float,
        r: float,
        q: float,
        sigma: float,
        t: float,
        american: bool,
    ) -> None:
        display_steps = 6
        tree_levels = build_tree_levels(
            s,
            k,
            r,
            q,
            sigma,
            t,
            steps=display_steps,
            american=american,
        )
        clear_chart()
        canvas = tk.Canvas(chart_container, bg=colors["bg"], highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        market_state["chart_widget"] = canvas

        container_width = max(chart_container.winfo_width(), 640)
        container_height = max(chart_container.winfo_height(), 360)
        canvas_width = container_width - 8
        canvas_height = container_height - 8
        x_margin = 70
        y_margin = 22
        max_step = len(tree_levels) - 1
        x_spacing = (canvas_width - 2 * x_margin) / max(max_step, 1)
        node_radius = 18

        for step, level in enumerate(tree_levels):
            if len(level) == 1:
                y_positions = [canvas_height / 2]
            else:
                y_spacing = (canvas_height - 2 * y_margin) / (len(level) - 1)
                y_positions = [y_margin + index * y_spacing for index in range(len(level))]
            x_position = x_margin + step * x_spacing

            if step < max_step:
                next_level = tree_levels[step + 1]
                if len(next_level) == 1:
                    next_y_positions = [canvas_height / 2]
                else:
                    next_y_spacing = (canvas_height - 2 * y_margin) / (len(next_level) - 1)
                    next_y_positions = [y_margin + index * next_y_spacing for index in range(len(next_level))]
                next_x_position = x_margin + (step + 1) * x_spacing
                for index in range(len(level)):
                    canvas.create_line(
                        x_position + node_radius,
                        y_positions[index],
                        next_x_position - node_radius,
                        next_y_positions[index],
                        fill="#47607c",
                        width=1,
                    )
                    canvas.create_line(
                        x_position + node_radius,
                        y_positions[index],
                        next_x_position - node_radius,
                        next_y_positions[index + 1],
                        fill="#33465c",
                        width=1,
                    )

            for index, node in enumerate(level):
                y_position = y_positions[index]
                canvas.create_oval(
                    x_position - node_radius,
                    y_position - node_radius,
                    x_position + node_radius,
                    y_position + node_radius,
                    fill=colors["panel_alt"],
                    outline=colors["accent"] if step == 0 else colors["border"],
                    width=2 if step == 0 else 1,
                )
                canvas.create_text(
                    x_position,
                    y_position,
                    text=f"{step},{index}",
                    fill=colors["text"],
                    font=("Menlo", 9, "bold"),
                )
                canvas.create_text(
                    x_position,
                    y_position + 34,
                    text=f"S {node['spot']:.2f}",
                    fill=colors["amber"],
                    font=("Menlo", 9),
                )
                canvas.create_text(
                    x_position,
                    y_position + 50,
                    text=f"C {node['call']:.2f}",
                    fill=colors["green"],
                    font=("Menlo", 9),
                )
                canvas.create_text(
                    x_position,
                    y_position + 66,
                    text=f"P {node['put']:.2f}",
                    fill=colors["red"],
                    font=("Menlo", 9),
                )

    def update_chart_view(*_: object) -> None:
        selected_view = chart_view_var.get()
        if selected_view == "Binomial":
            tree_inputs = market_state.get("last_tree_inputs")
            if tree_inputs is None:
                chart_status_var.set("")
                return
            render_binomial_tree(**tree_inputs)
            chart_status_var.set("")
            return

        render_chart()

    fields = [
        ("Precio actual del activo (S)", "Spot (S)", "100"),
        ("Precio de ejercicio (K)", "Strike (K)", "100"),
        ("Tasa libre de riesgo (r)", "Tasa (r)", "0.05"),
        ("Dividend yield (q)", "Dividendo (q)", "0.00"),
        ("Volatilidad (sigma)", "Volatilidad", "0.2"),
        ("Fecha de vencimiento (DD/MM/AAAA)", "Vencimiento", ""),
        ("Numero de simulaciones", "Simulaciones", "10000"),
    ]

    ttk.Label(input_frame, text="Tipo", style="Panel.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
    underlying_type_combo = ttk.Combobox(
        input_frame,
        textvariable=underlying_type_var,
        state="readonly",
        values=list(UNDERLYING_TYPES),
        width=14,
    )
    underlying_type_combo.grid(row=0, column=1, sticky="ew", pady=3)

    ttk.Label(input_frame, text="Simbolo", style="Panel.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=3)
    ticker_entry = ttk.Entry(input_frame, textvariable=ticker_var, width=16)
    ticker_entry.grid(row=1, column=1, sticky="ew", pady=3)

    suggestion_frame = ttk.Frame(input_frame, style="Panel.TFrame")
    suggestion_frame.grid(row=2, column=1, sticky="ew")
    suggestion_frame.columnconfigure(0, weight=1)
    suggestion_frame.rowconfigure(0, weight=1)
    suggestion_listbox = tk.Listbox(
        suggestion_frame,
        height=6,
        bg=colors["panel_alt"],
        fg=colors["text"],
        selectbackground="#31485e",
        selectforeground="#ffffff",
        highlightthickness=1,
        highlightbackground=colors["border"],
        relief="flat",
        font=("Menlo", 10),
    )
    suggestion_listbox.grid(row=0, column=0, sticky="ew")
    suggestion_scrollbar = ttk.Scrollbar(suggestion_frame, orient="vertical", command=suggestion_listbox.yview, style="Vertical.TScrollbar")
    suggestion_scrollbar.grid(row=0, column=1, sticky="ns")
    suggestion_listbox.configure(yscrollcommand=suggestion_scrollbar.set)
    suggestion_frame.grid_remove()

    tk.Label(
        input_frame,
        textvariable=monitor_symbol_var,
        bg=colors["panel"],
        fg=colors["text"],
        font=("Menlo", 11, "bold"),
    ).grid(row=3, column=1, sticky="e", pady=(0, 2))

    ttk.Label(input_frame, textvariable=ticker_help_var, style="Muted.TLabel", wraplength=260, justify="left").grid(
        row=4, column=0, columnspan=2, sticky="w", pady=(0, 4)
    )

    ttk.Label(input_frame, text="Vencimiento mdo", style="Panel.TLabel").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=3)
    expiry_combo = ttk.Combobox(input_frame, textvariable=expiry_var, state="readonly", values=[], width=14)
    expiry_combo.grid(row=5, column=1, sticky="ew", pady=3)

    ttk.Label(input_frame, text="Strike mdo", style="Panel.TLabel").grid(row=6, column=0, sticky="w", padx=(0, 8), pady=3)
    strike_combo = ttk.Combobox(input_frame, textvariable=strike_var, state="readonly", values=[], width=14)
    strike_combo.grid(row=6, column=1, sticky="ew", pady=3)

    ttk.Label(
        input_frame,
        text="Mercado y grafico se cargan solos. La cadena se refresca al cambiar vencimiento.",
        style="Muted.TLabel",
    ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 4))

    for row, (field_key, label_text, default_value) in enumerate(fields, start=8):
        ttk.Label(input_frame, text=label_text, style="Panel.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
        entry = ttk.Entry(input_frame, width=16)
        entry.insert(0, default_value)
        entry.grid(row=row, column=1, sticky="ew", pady=2)
        entries[field_key] = entry

    ttk.Label(input_frame, textvariable=inferred_style_var, style="Muted.TLabel").grid(
        row=15, column=0, columnspan=2, sticky="w", pady=(4, 0)
    )

    market_actions_frame = ttk.Frame(input_frame, style="Panel.TFrame")
    market_actions_frame.grid(row=16, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    market_actions_frame.columnconfigure(0, weight=1)
    market_actions_frame.columnconfigure(1, weight=1)
    market_actions_frame.columnconfigure(2, weight=1)
    ttk.Button(market_actions_frame, text="Cargar mercado", command=lambda: load_market_data()).grid(
        row=0, column=0, sticky="ew", padx=(0, 4)
    )
    ttk.Button(market_actions_frame, text="Cargar cadena", command=lambda: load_option_chain()).grid(
        row=0, column=1, sticky="ew", padx=(4, 0)
    )
    ttk.Button(market_actions_frame, text="Calcular", style="Accent.TButton", command=lambda: on_calculate()).grid(
        row=0, column=2, sticky="ew", padx=(4, 0)
    )

    monitor_spot_label = tk.Label(market_frame, textvariable=monitor_spot_var, bg=colors["panel"], fg=colors["amber"], font=("Menlo", 12, "bold"))
    monitor_change_label = tk.Label(market_frame, textvariable=monitor_change_var, bg=colors["panel"], fg=colors["muted"], font=("Menlo", 12, "bold"))
    monitor_iv_label = tk.Label(market_frame, textvariable=monitor_iv_var, bg=colors["panel"], fg="#6bc1ff", font=("Menlo", 10))
    monitor_style_label = tk.Label(market_frame, textvariable=monitor_style_var, bg=colors["panel"], fg=colors["text"], font=("Menlo", 10))
    monitor_expiry_label = tk.Label(market_frame, textvariable=monitor_expiry_var, bg=colors["panel"], fg=colors["text"], font=("Menlo", 10))
    monitor_spot_label.grid(row=0, column=0, sticky="w")
    monitor_change_label.grid(row=0, column=1, sticky="w")
    monitor_iv_label.grid(row=0, column=2, sticky="w")
    monitor_style_label.grid(row=0, column=3, sticky="w")
    monitor_expiry_label.grid(row=0, column=4, sticky="w")

    ttk.Label(chain_frame, textvariable=chain_header_var, style="Panel.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 4))
    ttk.Label(chain_frame, textvariable=chain_selection_var, style="Muted.TLabel").grid(row=0, column=1, sticky="e", pady=(0, 4))

    chain_columns = (
        "call_bid",
        "call_ask",
        "call_mid",
        "call_iv",
        "strike",
        "put_iv",
        "put_mid",
        "put_bid",
        "put_ask",
    )
    chain_tree = ttk.Treeview(chain_frame, columns=chain_columns, show="headings", height=14)
    chain_tree.heading("call_bid", text="Call bid")
    chain_tree.heading("call_ask", text="Call ask")
    chain_tree.heading("call_mid", text="Call mid")
    chain_tree.heading("call_iv", text="Call IV")
    chain_tree.heading("strike", text="[ STRIKE ]")
    chain_tree.heading("put_iv", text="Put IV")
    chain_tree.heading("put_mid", text="Put mid")
    chain_tree.heading("put_bid", text="Put bid")
    chain_tree.heading("put_ask", text="Put ask")
    for column, width in {
        "call_bid": 78,
        "call_ask": 78,
        "call_mid": 82,
        "call_iv": 72,
        "strike": 92,
        "put_iv": 72,
        "put_mid": 90,
        "put_bid": 78,
        "put_ask": 78,
    }.items():
        chain_tree.column(column, width=width, anchor="center" if column == "strike" else "e")
    chain_tree.grid(row=1, column=0, columnspan=2, sticky="nsew")
    chain_scrollbar = ttk.Scrollbar(chain_frame, orient="vertical", command=chain_tree.yview, style="Vertical.TScrollbar")
    chain_scrollbar.grid(row=1, column=2, sticky="ns")
    chain_tree.configure(yscrollcommand=chain_scrollbar.set)
    chain_tree.tag_configure("even", background=colors["row"])
    chain_tree.tag_configure("odd", background=colors["row_alt"])
    chain_tree.tag_configure("atm", background=colors["atm"], foreground=colors["atm_text"], font=("Menlo", 10, "bold"))
    chain_tree.tag_configure("itm_call", foreground=colors["green_bright"])
    chain_tree.tag_configure("itm_put", foreground=colors["red_bright"])

    chart_buttons_frame = ttk.Frame(chart_host, style="Panel.TFrame")
    chart_buttons_frame.place(relx=0.5, y=2, anchor="n")
    ttk.Button(chart_buttons_frame, text="Grafico", command=lambda: chart_view_var.set("Grafico")).grid(row=0, column=0, padx=(0, 4))
    ttk.Button(chart_buttons_frame, text="Binomial", command=lambda: chart_view_var.set("Binomial")).grid(row=0, column=1)

    chart_container = ttk.Frame(chart_frame, style="Panel.TFrame")
    chart_container.grid(row=0, column=0, sticky="nsew")
    chart_container.columnconfigure(0, weight=1)
    chart_container.rowconfigure(0, weight=1)
    chart_container.grid_propagate(False)

    price_header_frame = ttk.Frame(quote_frame, style="Panel.TFrame")
    price_header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 4))
    price_header_frame.columnconfigure(0, weight=1)
    price_header_frame.columnconfigure(1, weight=0)
    market_header_price_label = tk.Label(
        price_header_frame,
        text="-.--",
        bg=colors["panel"],
        fg=colors["text"],
        font=("Menlo", 28, "bold"),
        anchor="w",
    )
    market_header_price_label.grid(row=0, column=0, sticky="w")
    market_header_currency_label = tk.Label(
        price_header_frame,
        textvariable=quote_currency_var,
        bg=colors["panel"],
        fg=colors["muted"],
        font=("Menlo", 14, "bold"),
        anchor="e",
    )
    market_header_currency_label.grid(row=0, column=1, sticky="e", padx=(8, 0))
    market_header_change_label = tk.Label(
        quote_frame,
        text="No market data",
        bg=colors["panel"],
        fg=colors["green_bright"],
        font=("Menlo", 12, "bold"),
        anchor="w",
    )
    market_header_change_label.grid(row=1, column=0, sticky="ew", pady=(0, 10))

    quote_value_labels: list[tk.Label] = []
    for row_index, variable in enumerate(
        [
            quote_call_bid_var,
            quote_call_ask_var,
            quote_call_mid_var,
            quote_put_bid_var,
            quote_put_ask_var,
            quote_put_mid_var,
            quote_spread_var,
            quote_oi_var,
            quote_volume_var,
        ],
        start=2,
    ):
        label = tk.Label(
            quote_frame,
            textvariable=variable,
            bg=colors["panel"],
            fg=colors["text"] if row_index not in (2, 3, 5, 6) else colors["muted"],
            font=("Menlo", 11),
            anchor="w",
            justify="left",
        )
        label.grid(row=row_index, column=0, sticky="ew", pady=2)
        quote_value_labels.append(label)

    summary_quote_frame = ttk.Frame(quote_frame, style="Panel.TFrame")
    summary_quote_frame.grid(row=11, column=0, sticky="ew", pady=(12, 0))
    summary_quote_frame.columnconfigure(0, weight=1)
    summary_quote_frame.columnconfigure(1, weight=1)
    tk.Label(summary_quote_frame, textvariable=result_market_call, bg=colors["panel"], fg=colors["amber"], font=("Menlo", 12, "bold")).grid(row=0, column=0, sticky="w")
    tk.Label(summary_quote_frame, textvariable=result_market_put, bg=colors["panel"], fg=colors["amber"], font=("Menlo", 12, "bold")).grid(row=0, column=1, sticky="w")
    tk.Label(summary_quote_frame, text="CALL MKT", bg=colors["panel"], fg=colors["muted"], font=("Menlo", 9)).grid(row=1, column=0, sticky="w")
    tk.Label(summary_quote_frame, text="PUT MKT", bg=colors["panel"], fg=colors["muted"], font=("Menlo", 9)).grid(row=1, column=1, sticky="w")

    greeks_frame = ttk.Frame(header, style="Panel.TFrame")
    greeks_frame.grid(row=0, column=1, rowspan=2)
    for column in range(5):
        greeks_frame.columnconfigure(column, weight=1)
    tk.Label(greeks_frame, textvariable=greek_delta_var, bg=colors["bg"], fg=colors["text"], font=("Menlo", 9)).grid(row=0, column=0, padx=6)
    tk.Label(greeks_frame, textvariable=greek_gamma_var, bg=colors["bg"], fg=colors["text"], font=("Menlo", 9)).grid(row=0, column=1, padx=6)
    tk.Label(greeks_frame, textvariable=greek_vega_var, bg=colors["bg"], fg="#6bc1ff", font=("Menlo", 9)).grid(row=0, column=2, padx=6)
    tk.Label(greeks_frame, textvariable=greek_theta_var, bg=colors["bg"], fg=colors["red_bright"], font=("Menlo", 9)).grid(row=0, column=3, padx=6)
    tk.Label(greeks_frame, textvariable=greek_rho_var, bg=colors["bg"], fg=colors["green_bright"], font=("Menlo", 9)).grid(row=0, column=4, padx=6)

    def schedule_market_load(delay_ms: int = 250) -> None:
        scheduled_job = market_state.get("market_job")
        if scheduled_job is not None:
            root.after_cancel(scheduled_job)
        market_state["market_job"] = root.after(delay_ms, load_market_data)

    def schedule_chain_load(delay_ms: int = 250) -> None:
        scheduled_job = market_state.get("chain_job")
        if scheduled_job is not None:
            root.after_cancel(scheduled_job)
        market_state["chain_job"] = root.after(delay_ms, load_option_chain)

    def schedule_ticker_search(delay_ms: int = 250) -> None:
        scheduled_job = market_state.get("ticker_search_job")
        if scheduled_job is not None:
            root.after_cancel(scheduled_job)
        market_state["ticker_search_job"] = root.after(delay_ms, update_ticker_suggestions)

    def update_ticker_suggestions() -> None:
        market_state["ticker_search_job"] = None
        query = ticker_var.get().strip()
        base_symbols = SYMBOLS_BY_TYPE[underlying_type_var.get()]
        if not query:
            market_state["ticker_suggestion_map"] = {symbol: symbol for symbol in base_symbols}
            market_state["ticker_meta_map"] = {symbol: {"symbol": symbol, "has_options": True} for symbol in base_symbols}
            hide_ticker_suggestions()
            return

        suggestion_map: dict[str, str] = {}
        suggestion_meta_map: dict[str, dict[str, object]] = {}
        suggestions: list[str] = []
        try:
            search_results = search_tickers(query, max_results=12, underlying_type=underlying_type_var.get())
            prioritized_results: list[dict[str, str]] = []
            for result in search_results:
                symbol = result.get("symbol", "").strip().upper()
                label = result.get("label", "").strip() or symbol
                if not symbol or not label or label in suggestion_map:
                    continue
                meta = {
                    "symbol": symbol,
                    "label": label,
                    "quote_type": result.get("quote_type", ""),
                    "exchange": result.get("exchange", ""),
                    "has_options": None,
                }
                suggestion_meta_map[label] = meta
                prioritized_results.append(result)
            for result in prioritized_results:
                symbol = result.get("symbol", "").strip().upper()
                label = result.get("label", "").strip() or symbol
                if symbol and label and label not in suggestion_map:
                    suggestion_map[label] = symbol
                    suggestions.append(label)
        except Exception:
            suggestions = []

        merged_values: list[str] = []
        normalized_query = normalize_ticker_input(query)
        if normalized_query:
            suggestion_map[normalized_query] = normalized_query
            merged_values.append(normalized_query)
            suggestion_meta_map.setdefault(normalized_query, {"symbol": normalized_query, "has_options": False})
        for label in suggestions:
            if label not in merged_values:
                merged_values.append(label)
        for symbol in base_symbols:
            suggestion_map.setdefault(symbol, symbol)
            suggestion_meta_map.setdefault(symbol, {"symbol": symbol, "has_options": True})
            if symbol not in merged_values:
                merged_values.append(symbol)
        market_state["ticker_suggestion_map"] = suggestion_map
        market_state["ticker_meta_map"] = suggestion_meta_map
        show_ticker_suggestions(merged_values[:10])

    def commit_ticker_selection(*_: object) -> None:
        raw_value = ticker_var.get().strip()
        suggestion_map = market_state.get("ticker_suggestion_map", {})
        suggestion_meta_map = market_state.get("ticker_meta_map", {})
        normalized_symbol = suggestion_map.get(raw_value, normalize_ticker_input(raw_value))
        if not normalized_symbol:
            return
        selected_meta = suggestion_meta_map.get(raw_value)
        if (
            underlying_type_var.get() != "Benchmarks"
            and selected_meta is not None
        ):
            has_options = selected_meta.get("has_options")
            if has_options is None:
                has_options = ticker_has_options(normalized_symbol)
                selected_meta["has_options"] = has_options
            if not has_options:
                messagebox.showerror(
                    "Ticker no optionable",
                    "Ese resultado no tiene opciones disponibles en Yahoo Finance. Elige otro ticker optionable.",
                )
                return
        ticker_var.set(normalized_symbol)
        hide_ticker_suggestions()
        on_ticker_change()

    def commit_selected_suggestion(*_: object) -> str | None:
        selection = suggestion_listbox.curselection()
        if not selection:
            return None
        label = suggestion_listbox.get(selection[0])
        ticker_var.set(label)
        commit_ticker_selection()
        return "break"

    def move_suggestion_selection(offset: int) -> str:
        labels = market_state.get("ticker_suggestion_labels", [])
        if not labels:
            return "break"
        selection = suggestion_listbox.curselection()
        current_index = selection[0] if selection else 0
        next_index = max(0, min(len(labels) - 1, current_index + offset))
        suggestion_listbox.selection_clear(0, tk.END)
        suggestion_listbox.selection_set(next_index)
        suggestion_listbox.see(next_index)
        return "break"

    def update_underlying_type(*_: object) -> None:
        underlying_type = underlying_type_var.get()
        market_state["ticker_suggestion_map"] = {symbol: symbol for symbol in SYMBOLS_BY_TYPE[underlying_type]}
        market_state["ticker_meta_map"] = {symbol: {"symbol": symbol, "has_options": True} for symbol in SYMBOLS_BY_TYPE[underlying_type]}
        ticker_var.set(SYMBOLS_BY_TYPE[underlying_type][0])
        hide_ticker_suggestions()
        ticker_help_var.set(UNDERLYING_TYPES[underlying_type]["help"])
        inferred_style_var.set(f"Estilo ejercicio: {infer_exercise_style(underlying_type, ticker_var.get())}")
        expiry_var.set("")
        strike_var.set("")
        expiry_combo.configure(values=[])
        strike_combo.configure(values=[])
        market_state["snapshot"] = None
        market_state["calls"] = {}
        market_state["puts"] = {}
        market_state["last_tree_inputs"] = None
        clear_chain_table()
        clear_chart()
        update_market_results(None, None)
        update_quote_panel(None, None)
        update_monitor_strip()
        comparison_tree.delete(*comparison_tree.get_children())
        summary_call_put_var.set("- / -")
        greek_delta_var.set("Delta: -")
        greek_gamma_var.set("Gamma: -")
        greek_vega_var.set("Vega: -")
        greek_theta_var.set("Theta: -")
        greek_rho_var.set("Rho: -")
        status_var.set("Cargando mercado...")
        schedule_market_load()

    def update_market_results(call_market: float | None, put_market: float | None) -> None:
        result_market_call.set("-" if call_market is None else f"{call_market:.4f}")
        result_market_put.set("-" if put_market is None else f"{put_market:.4f}")

    def update_monitor_strip() -> None:
        snapshot = market_state["snapshot"]
        symbol = ticker_var.get().strip().upper() or "SYMBOL"
        inferred_style = infer_exercise_style(
            underlying_type_var.get(),
            symbol,
            currency=None if snapshot is None else snapshot.currency,
            exchange=None if snapshot is None else snapshot.exchange,
        )
        inferred_style_var.set(f"Estilo ejercicio: {inferred_style}")
        monitor_symbol_var.set(symbol)
        if snapshot is None or not snapshot.history_closes:
            monitor_spot_var.set("Spot -")
            monitor_change_var.set("Chg -")
            monitor_iv_var.set("IV ATM -")
            monitor_style_var.set("Style -")
            monitor_expiry_var.set("Expiry -")
            market_header_price_label.configure(text="-.--")
            quote_currency_var.set("")
            market_header_change_label.configure(text="No market data")
            return

        spot = snapshot.spot_price
        previous = snapshot.history_closes[-2] if len(snapshot.history_closes) > 1 else spot
        change = spot - previous
        pct = (change / previous * 100.0) if previous else 0.0
        monitor_spot_var.set(f"Spot {spot:.2f}")
        monitor_change_var.set(f"Chg {change:+.2f} / {pct:+.2f}%")
        monitor_iv_var.set(f"IV ATM {entries['Volatilidad (sigma)'].get() or '-'}")
        market_header_price_label.configure(text=f"{spot:.2f}")
        quote_currency_var.set(snapshot.currency or "")
        market_header_change_label.configure(text=f"{change:+.2f}   {pct:+.2f}%")
        monitor_change_label.configure(fg=colors["green_bright"] if change >= 0 else colors["red_bright"])
        market_header_change_label.configure(fg=colors["green_bright"] if change >= 0 else colors["red_bright"])
        monitor_style_var.set(f"Style {inferred_style}")
        monitor_expiry_var.set(f"Expiry {expiry_var.get().strip() or '-'}")

    def update_quote_panel(call_quote, put_quote) -> None:
        call_spread = None
        put_spread = None
        if call_quote is not None and call_quote.bid is not None and call_quote.ask is not None:
            call_spread = call_quote.ask - call_quote.bid
        if put_quote is not None and put_quote.bid is not None and put_quote.ask is not None:
            put_spread = put_quote.ask - put_quote.bid
        spread_text = "-"
        if call_spread is not None or put_spread is not None:
            spread_text = f"C {format_price(call_spread)} | P {format_price(put_spread)}"

        open_interest = None
        volume = None
        if call_quote is not None:
            open_interest = call_quote.open_interest
            volume = call_quote.volume
        if put_quote is not None:
            open_interest = max(open_interest or 0, put_quote.open_interest or 0) if (open_interest or put_quote.open_interest) else None
            volume = max(volume or 0, put_quote.volume or 0) if (volume or put_quote.volume) else None

        quote_call_bid_var.set(f"Call bid: {format_price(None if call_quote is None else call_quote.bid)}")
        quote_call_ask_var.set(f"Call ask: {format_price(None if call_quote is None else call_quote.ask)}")
        quote_call_mid_var.set(f"Call mid: {format_price(None if call_quote is None else call_quote.mid_price)}")
        quote_put_bid_var.set(f"Put bid: {format_price(None if put_quote is None else put_quote.bid)}")
        quote_put_ask_var.set(f"Put ask: {format_price(None if put_quote is None else put_quote.ask)}")
        quote_put_mid_var.set(f"Put mid: {format_price(None if put_quote is None else put_quote.mid_price)}")
        quote_spread_var.set(f"Spread: {spread_text}")
        quote_oi_var.set(f"OI: {'-' if open_interest is None else open_interest}")
        quote_volume_var.set(f"Vol: {'-' if volume is None else volume}")
        for label, fg in zip(
            quote_value_labels,
            (
                colors["green_bright"],
                colors["red_bright"],
                colors["amber"],
                colors["green_bright"],
                colors["red_bright"],
                colors["amber"],
                colors["muted"],
                colors["text"],
                colors["text"],
            ),
        ):
            label.configure(fg=fg)

    def find_quote(quotes: dict[float, object], strike: float):
        if strike in quotes:
            return quotes[strike]
        if not quotes:
            return None
        nearest = min(quotes, key=lambda current_strike: abs(current_strike - strike))
        if abs(nearest - strike) < 0.01:
            return quotes[nearest]
        return None

    def update_comparison_tree(
        market_call: float | None,
        market_put: float | None,
        valuation: ValuationResult,
    ) -> None:
        comparison_tree.delete(*comparison_tree.get_children())
        rows = [
            ("Mercado", market_call, market_put),
            ("Black-Scholes", valuation.models["Black-Scholes"].call, valuation.models["Black-Scholes"].put),
            ("Binomial", valuation.models["Binomial"].call, valuation.models["Binomial"].put),
            ("Monte Carlo", valuation.models["Monte Carlo"].call, valuation.models["Monte Carlo"].put),
        ]
        for model, call_value, put_value in rows:
            err_call, err_put = "-", "-"
            tags: list[str] = []
            if model != "Mercado":
                _, err_call = calculate_error(call_value, market_call)
                _, err_put = calculate_error(put_value, market_put)
                if (
                    call_value is not None
                    and put_value is not None
                    and market_call is not None
                    and market_put is not None
                ):
                    total_error = abs(call_value - market_call) + abs(put_value - market_put)
                    tags.append("good" if total_error < 1.0 else "bad")
            else:
                tags.append("market")
            comparison_tree.insert(
                "",
                "end",
                values=(
                    model,
                    format_price(call_value),
                    format_price(put_value),
                    err_call,
                    err_put,
                ),
                tags=tuple(tags),
            )

    def update_greeks_panel(s: float, k: float, r: float, q: float, sigma: float, t: float) -> None:
        bs_greeks = greeks(s, k, r, q, sigma, t)
        greek_delta_var.set(f"Delta C/P: {bs_greeks['call_delta']:.4f} / {bs_greeks['put_delta']:.4f}")
        greek_gamma_var.set(f"Gamma: {bs_greeks['gamma']:.6f}")
        greek_vega_var.set(f"Vega: {bs_greeks['vega']:.4f}")
        greek_theta_var.set(f"Theta C/P: {bs_greeks['call_theta']:.4f} / {bs_greeks['put_theta']:.4f}")
        greek_rho_var.set(f"Rho C/P: {bs_greeks['call_rho']:.4f} / {bs_greeks['put_rho']:.4f}")

    def clear_chain_table() -> None:
        chain_tree.delete(*chain_tree.get_children())
        chain_header_var.set("Ticker: -    Vencimiento: -")
        chain_selection_var.set("Seleccion actual: -")

    def update_chain_header(selected_strike: str | None = None) -> None:
        chain_header_var.set(
            f"Ticker: {ticker_var.get().strip().upper() or '-'}    Vencimiento: {expiry_var.get().strip() or '-'}"
        )
        if selected_strike is None:
            chain_selection_var.set("Seleccion actual: -")
        else:
            chain_selection_var.set(f"Seleccion actual: strike {selected_strike}")

    def refresh_chain_table(calls: dict[float, object], puts: dict[float, object]) -> None:
        clear_chain_table()
        update_chain_header(strike_var.get().strip() or None)
        strikes = sorted(set(calls) | set(puts))
        spot_text = entries["Precio actual del activo (S)"].get().strip()
        try:
            spot_value = float(spot_text)
        except ValueError:
            spot_value = None
        atm_strike = min(strikes, key=lambda current_strike: abs(current_strike - spot_value)) if strikes and spot_value is not None else None
        atm_item_id = None
        for strike in strikes:
            call_quote = calls.get(strike)
            put_quote = puts.get(strike)
            call_bid = format_price(None if call_quote is None else call_quote.bid)
            call_ask = format_price(None if call_quote is None else call_quote.ask)
            call_mid = format_price(None if call_quote is None else call_quote.mid_price)
            put_bid = format_price(None if put_quote is None else put_quote.bid)
            put_ask = format_price(None if put_quote is None else put_quote.ask)
            put_mid = format_price(None if put_quote is None else put_quote.mid_price)
            call_iv = "-" if call_quote is None or call_quote.implied_volatility is None else f"{call_quote.implied_volatility:.4f}"
            put_iv = "-" if put_quote is None or put_quote.implied_volatility is None else f"{put_quote.implied_volatility:.4f}"
            is_even = len(chain_tree.get_children()) % 2 == 0
            tags = ["even" if is_even else "odd"]
            if atm_strike is not None and abs(strike - atm_strike) < 0.01:
                tags.append("atm")
            elif spot_value is not None and strike < spot_value:
                tags.append("itm_call")
            elif spot_value is not None and strike > spot_value:
                tags.append("itm_put")
            item_id = f"{strike:.4f}"
            chain_tree.insert(
                "",
                "end",
                iid=item_id,
                values=(call_bid, call_ask, call_mid, call_iv, f"{strike:.2f}", put_iv, put_mid, put_bid, put_ask),
                tags=tuple(tags),
            )
            if atm_strike is not None and abs(strike - atm_strike) < 0.01:
                atm_item_id = item_id

        if atm_item_id is not None:
            chain_tree.selection_set(atm_item_id)
            chain_tree.focus(atm_item_id)
            def center_atm_row() -> None:
                children = chain_tree.get_children()
                try:
                    atm_index = children.index(atm_item_id)
                except ValueError:
                    return

                row_height = 24
                widget_height = max(chain_tree.winfo_height(), row_height)
                visible_rows = max(1, widget_height // row_height)
                first_row = max(0, atm_index - visible_rows // 2)
                total_rows = max(1, len(children))
                max_first_row = max(0, total_rows - visible_rows)
                if max_first_row == 0:
                    chain_tree.yview_moveto(0.0)
                    return

                first_row = min(first_row, max_first_row)
                chain_tree.yview_moveto(first_row / total_rows)

            root.after_idle(center_atm_row)

    def clear_chart() -> None:
        widget = market_state["chart_widget"]
        resize_binding = market_state["chart_resize_binding"]
        if resize_binding is not None:
            chart_container.unbind("<Configure>", resize_binding)
        if widget is not None:
            widget.destroy()
        market_state["chart_canvas"] = None
        market_state["chart_widget"] = None
        market_state["chart_figure"] = None
        market_state["chart_resize_binding"] = None
        chart_status_var.set("")

    def render_chart() -> None:
        if chart_view_var.get() != "Grafico":
            return
        snapshot = market_state["snapshot"]
        if snapshot is None:
            clear_chart()
            return

        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

            clear_chart()
            try:
                selected_strike = float(entries["Precio de ejercicio (K)"].get())
            except ValueError:
                selected_strike = None
            figure = build_underlying_figure(
                ticker_var.get().strip().upper(),
                snapshot,
                selected_strike=selected_strike,
            )
            canvas = FigureCanvasTkAgg(figure, master=chart_container)
            canvas.draw()
            widget = canvas.get_tk_widget()
            widget.grid(row=0, column=0, sticky="nsew")
            market_state["chart_canvas"] = canvas
            market_state["chart_widget"] = widget
            market_state["chart_figure"] = figure

            def resize_chart(event: object) -> None:
                current_figure = market_state["chart_figure"]
                current_canvas = market_state["chart_canvas"]
                if current_figure is None or current_canvas is None:
                    return
                width = max(chart_container.winfo_width(), 320)
                height = max(chart_container.winfo_height(), 220)
                dpi = current_figure.get_dpi()
                current_figure.set_size_inches(width / dpi, height / dpi, forward=False)
                current_canvas.draw_idle()

            binding_id = chart_container.bind("<Configure>", resize_chart)
            market_state["chart_resize_binding"] = binding_id
            chart_status_var.set("")
        except Exception as error:
            chart_status_var.set(str(error))

    def sync_market_selection(*_: object) -> None:
        expiration_display = expiry_var.get().strip()
        strike_display = strike_var.get().strip()
        if not expiration_display or not strike_display:
            return

        try:
            strike = float(strike_display)
        except ValueError:
            return

        entries["Precio de ejercicio (K)"].delete(0, tk.END)
        entries["Precio de ejercicio (K)"].insert(0, f"{strike:.2f}")
        entries["Fecha de vencimiento (DD/MM/AAAA)"].delete(0, tk.END)
        entries["Fecha de vencimiento (DD/MM/AAAA)"].insert(0, expiration_display)

        call_quote = find_quote(market_state["calls"], strike)
        put_quote = find_quote(market_state["puts"], strike)
        iv_values = [
            quote.implied_volatility
            for quote in (call_quote, put_quote)
            if quote is not None and quote.implied_volatility is not None
        ]
        if iv_values:
            iv = sum(iv_values) / len(iv_values)
            entries["Volatilidad (sigma)"].delete(0, tk.END)
            entries["Volatilidad (sigma)"].insert(0, f"{iv:.4f}")

        call_market = call_quote.mid_price if call_quote is not None else None
        put_market = put_quote.mid_price if put_quote is not None else None
        update_market_results(call_market, put_market)
        update_quote_panel(call_quote, put_quote)
        update_monitor_strip()
        update_chain_header(f"{strike:.2f}")

    def load_option_chain() -> None:
        market_state["chain_job"] = None
        if underlying_type_var.get() == "Benchmarks":
            messagebox.showerror(
                "Cadena no disponible",
                "Benchmarks es una categoria de referencia. No se carga cadena de opciones para este tipo de activo.",
            )
            return
        ticker_symbol = ticker_var.get().strip().upper()
        expiration_display = expiry_var.get().strip()
        if not ticker_symbol or not expiration_display:
            return

        try:
            calls, puts = fetch_option_chain(ticker_symbol, display_to_iso_date(expiration_display))
        except Exception as error:
            messagebox.showerror("Datos de mercado", str(error))
            return

        market_state["calls"] = calls
        market_state["puts"] = puts
        status_var.set("Cadena cargada")
        strikes = sorted(set(calls) | set(puts))
        strike_combo.configure(values=[f"{strike:.2f}" for strike in strikes])
        refresh_chain_table(calls, puts)

        if strikes:
            spot_value = float(entries["Precio actual del activo (S)"].get())
            closest = min(strikes, key=lambda strike: abs(strike - spot_value))
            strike_var.set(f"{closest:.2f}")
            sync_market_selection()

    def load_market_data() -> None:
        market_state["market_job"] = None
        ticker_symbol = ticker_var.get().strip().upper()
        if not ticker_symbol:
            return
        try:
            snapshot = fetch_market_snapshot(ticker_symbol)
        except Exception as error:
            messagebox.showerror("Datos de mercado", str(error))
            return

        market_state["snapshot"] = snapshot
        status_var.set("Mercado cargado")
        entries["Precio actual del activo (S)"].delete(0, tk.END)
        entries["Precio actual del activo (S)"].insert(0, f"{snapshot.spot_price:.4f}")
        entries["Dividend yield (q)"].delete(0, tk.END)
        entries["Dividend yield (q)"].insert(0, f"{snapshot.dividend_yield:.4f}")
        if snapshot.risk_free_rate is not None:
            entries["Tasa libre de riesgo (r)"].delete(0, tk.END)
            entries["Tasa libre de riesgo (r)"].insert(0, f"{snapshot.risk_free_rate:.4f}")

        expiry_values = [iso_to_display_date(expiration) for expiration in snapshot.expirations]
        expiry_combo.configure(values=expiry_values)
        strike_combo.configure(values=[])
        strike_var.set("")
        market_state["calls"] = {}
        market_state["puts"] = {}
        clear_chain_table()
        update_market_results(None, None)
        update_quote_panel(None, None)
        update_monitor_strip()
        comparison_tree.delete(*comparison_tree.get_children())

        if expiry_values:
            expiry_var.set(expiry_values[0])
            entries["Fecha de vencimiento (DD/MM/AAAA)"].delete(0, tk.END)
            entries["Fecha de vencimiento (DD/MM/AAAA)"].insert(0, expiry_values[0])
        render_chart()

    def on_ticker_change(*_: object) -> None:
        ticker_symbol = normalize_ticker_input(ticker_var.get())
        ticker_var.set(ticker_symbol)
        monitor_symbol_var.set(ticker_symbol or "SYMBOL")
        clear_chart()
        clear_chain_table()
        strike_combo.configure(values=[])
        strike_var.set("")
        update_market_results(None, None)
        update_quote_panel(None, None)
        status_var.set("Cargando mercado...")
        if ticker_symbol:
            schedule_market_load()

    def on_expiry_change(*_: object) -> None:
        entries["Fecha de vencimiento (DD/MM/AAAA)"].delete(0, tk.END)
        entries["Fecha de vencimiento (DD/MM/AAAA)"].insert(0, expiry_var.get().strip())
        strike_combo.configure(values=[])
        strike_var.set("")
        update_market_results(None, None)
        update_chain_header(None)
        if market_state["snapshot"] is not None and expiry_var.get().strip():
            status_var.set("Cargando cadena...")
            schedule_chain_load()

    def on_chain_select(_: object) -> None:
        selected_items = chain_tree.selection()
        if not selected_items:
            return
        selected_values = chain_tree.item(selected_items[0], "values")
        if len(selected_values) < 5:
            return
        selected_strike = selected_values[4]
        strike_var.set(selected_strike)

    def on_calculate() -> None:
        try:
            s = float(entries["Precio actual del activo (S)"].get())
            k = float(entries["Precio de ejercicio (K)"].get())
            r = float(entries["Tasa libre de riesgo (r)"].get())
            q = float(entries["Dividend yield (q)"].get())
            sigma = float(entries["Volatilidad (sigma)"].get())
            expiry_text = entries["Fecha de vencimiento (DD/MM/AAAA)"].get()
            t = calculate_years_to_maturity(expiry_text)
            effective_style, style_label = resolve_exercise_style(
                underlying_type_var.get(),
                ticker_var.get().strip().upper(),
                currency=None if market_state["snapshot"] is None else market_state["snapshot"].currency,
                exchange=None if market_state["snapshot"] is None else market_state["snapshot"].exchange,
            )
            simulations = int(entries["Numero de simulaciones"].get() or DEFAULT_MC_COMPARISON_SIMULATIONS)
            valuation = compute_valuations(
                effective_style,
                s,
                k,
                r,
                q,
                sigma,
                t,
                simulations=simulations,
            )
            effective_output = valuation.models[valuation.effective_method]
        except ValueError as error:
            messagebox.showerror("Entrada no valida", str(error))
            return
        except Exception as error:
            messagebox.showerror("Error", str(error))
            return

        status_var.set("Valoracion actualizada")
        market_state["last_tree_inputs"] = {
            "s": s,
            "k": k,
            "r": r,
            "q": q,
            "sigma": sigma,
            "t": t,
            "american": effective_style == "Americana",
        }
        result_method.set(valuation.effective_method)
        result_style.set(style_label)
        result_model.set(valuation.effective_label)
        result_t.set(f"{t:.4f} a")
        result_simulations.set(str(simulations))
        result_call.set(format_price(effective_output.call))
        result_put.set(format_price(effective_output.put))
        summary_call_put_var.set(f"{format_price(effective_output.call)} / {format_price(effective_output.put)}")
        selected_call_quote = find_quote(market_state["calls"], k)
        selected_put_quote = find_quote(market_state["puts"], k)
        market_call = selected_call_quote.mid_price if selected_call_quote is not None else None
        market_put = selected_put_quote.mid_price if selected_put_quote is not None else None
        update_comparison_tree(market_call, market_put, valuation)
        update_greeks_panel(s, k, r, q, sigma, t)
        if chart_view_var.get() == "Binomial":
            update_chart_view()

    summary_frame = ttk.Frame(results_frame, style="Panel.TFrame")
    summary_frame.grid(row=0, column=0, sticky="ew")
    for column in range(4):
        summary_frame.columnconfigure(column, weight=1)

    def add_result_card(row: int, column: int, title: str, variable: tk.StringVar, value_color: str) -> None:
        card = ttk.Frame(summary_frame, style="Panel.TFrame")
        card.grid(row=row, column=column, sticky="ew", padx=(0, 6), pady=(0, 6))
        ttk.Label(card, text=title, style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        tk.Label(card, textvariable=variable, bg=colors["panel"], fg=value_color, font=("Menlo", 10, "bold")).grid(
            row=1, column=0, sticky="w"
        )

    add_result_card(0, 0, "Metodo", result_method, colors["text"])
    add_result_card(0, 1, "Estilo", result_style, colors["text"])
    add_result_card(0, 2, "Modelo", result_model, colors["muted"])
    add_result_card(0, 3, "T", result_t, colors["text"])
    add_result_card(1, 0, "Sims", result_simulations, colors["muted"])
    add_result_card(1, 1, "Call mkt", result_market_call, colors["amber"])
    add_result_card(1, 2, "Put mkt", result_market_put, colors["amber"])
    add_result_card(1, 3, "Call / Put", summary_call_put_var, colors["green"])

    comparison_tree = ttk.Treeview(
        compare_frame,
        columns=("model", "call", "put", "err_call", "err_put"),
        show="headings",
        height=4,
    )
    for heading, text, width in (
        ("model", "Model", 120),
        ("call", "Call", 90),
        ("put", "Put", 90),
        ("err_call", "Err C", 90),
        ("err_put", "Err P", 90),
    ):
        comparison_tree.heading(heading, text=text)
        comparison_tree.column(heading, width=width, anchor="e" if heading != "model" else "w")
    comparison_tree.grid(row=0, column=0, sticky="nsew")
    comparison_tree.tag_configure("market", background="#2a3f59", foreground="#ffffff")
    comparison_tree.tag_configure("good", foreground=colors["green_bright"])
    comparison_tree.tag_configure("bad", foreground=colors["red_bright"])

    underlying_type_var.trace_add("write", update_underlying_type)
    chart_view_var.trace_add("write", update_chart_view)
    expiry_var.trace_add("write", on_expiry_change)
    strike_var.trace_add("write", sync_market_selection)
    chain_tree.bind("<<TreeviewSelect>>", on_chain_select)
    ticker_entry.bind("<KeyRelease>", lambda event: schedule_ticker_search() if event.keysym not in {"Up", "Down", "Return", "Escape"} else None)
    ticker_entry.bind("<Down>", lambda *_: move_suggestion_selection(1))
    ticker_entry.bind("<Up>", lambda *_: move_suggestion_selection(-1))
    ticker_entry.bind("<Return>", commit_selected_suggestion)
    ticker_entry.bind("<Escape>", lambda *_: (hide_ticker_suggestions(), "break")[1])
    ticker_entry.bind("<FocusOut>", lambda *_: root.after(150, hide_ticker_suggestions))
    suggestion_listbox.bind("<ButtonRelease-1>", commit_selected_suggestion)
    suggestion_listbox.bind("<Return>", commit_selected_suggestion)

    update_underlying_type()
    ticker_entry.focus()
    return root


def main() -> None:
    if tk is None:
        run_cli()
        return

    app = build_app()
    app.mainloop()


if __name__ == "__main__":
    main()
