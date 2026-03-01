# AJAX Options Terminal

**AJAX = Advanced Pricing Analytics eXecution**

AJAX is a Python desktop options valuation terminal focused on practical pricing workflows: market snapshot loading, option chain inspection, Greeks, and side-by-side comparison of **Black-Scholes**, **Binomial CRR**, and **Monte Carlo** outputs.

The project was built as a compact trading-style interface to explore how theoretical option values compare with market quotes across different underlyings and exercise styles.

## Features

- Dark terminal-style desktop GUI built with `tkinter`
- Live market snapshot and option chain retrieval through `yfinance`
- Underlying search with Yahoo-based ticker suggestions
- Support for multiple underlying categories:
  - Equities
  - Indices
  - ETFs
  - Commodities proxies
  - Rates proxies
  - Benchmarks
  - FX proxies
- Automatic loading of:
  - spot price
  - dividend yield
  - implied volatility reference
  - option expiries and strikes
  - underlying chart
- Automatic risk-free rate proxy:
  - `^TNX` for USD assets
  - German 10Y proxy for European assets when available
- Pricing engines:
  - Black-Scholes
  - Binomial CRR
  - Monte Carlo
- Comparison table between model prices and market mid prices
- Greeks panel
- In-panel binomial tree view

## Pricing Logic

The application computes all three model outputs and then chooses a primary model depending on the inferred exercise style:

- **European-style** assets: `Black-Scholes` is treated as the primary model
- **American-style** assets: `Binomial` is treated as the primary model
- `Monte Carlo` and `Black-Scholes` can still be shown as reference proxies for comparison

This is intentional: the tool is designed to compare methodologies, not to hide alternative outputs.

## Stack

- Python
- `tkinter`
- `yfinance`
- `matplotlib`

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/YOUR_USER/ajax-options-terminal.git
cd ajax-options-terminal
pip install -r requirements.txt
```

## Run

Launch the GUI with:

```bash
python3 main.py
```

If `tkinter` is not available in the current Python environment, the project falls back to a simple console mode.

## How It Works

1. Choose an underlying category.
2. Search or type a ticker.
3. Load market data and option chain.
4. Select expiry and strike.
5. Inspect:
   - theoretical prices
   - market mids
   - pricing errors
   - Greeks
   - underlying chart or binomial tree

## Notes and Limitations

- Market data is sourced from `yfinance`, which relies on Yahoo Finance public endpoints and is **not** institutional market data infrastructure.
- Option availability depends on Yahoo Finance coverage for each ticker.
- Risk-free rates are proxy-based, not full curve bootstraps.
- Monte Carlo is implemented as a European reference engine, not a full American early-exercise Monte Carlo framework such as Longstaff-Schwartz.
- The application is designed as an educational / interview / prototyping tool, not a production trading system.

## Project Structure

```text
main.py
pricer/
  blackscholes.py
  binomial.py
  engine.py
  marketdata.py
  montecarlo.py
requirements.txt
```

## Why This Project

This project was built to turn option pricing theory into a usable interface:

- compare model outputs against observed market prices
- reason about European vs American exercise assumptions
- visualize binomial pricing mechanics
- connect pricing intuition with real market data

## Future Improvements

- Async market/search loading to avoid UI blocking
- Better metadata and exchange-aware ticker filtering
- Full implied volatility workflow by strike
- Volatility surface tooling
- Better rate curve selection by currency and maturity
- Export of pricing runs and screenshots

## Disclaimer

This repository is for educational and demonstration purposes only. It is not investment advice, execution infrastructure, or production-grade valuation software.
