"""
scripts/fetch_prices.py — Corre en GitHub Actions, guarda prices.json en la raíz del repo.
"""

import json
import sys
from pathlib import Path
from datetime import date

import pandas as pd
import yfinance as yf

ROOT        = Path(__file__).parent.parent
PRICES_FILE = ROOT / "prices.json"
TICKERS_FILE = ROOT / "tickers.json"
FALLBACK_TC  = 17.50


def get_prices(tickers: list[str]) -> dict[str, float]:
    if not tickers:
        return {}
    precios = {}
    try:
        raw = yf.download(tickers, period="2d", progress=False, auto_adjust=True)
        if raw.empty:
            return precios
        closes = raw["Close"]
        if isinstance(closes, pd.Series):
            last = closes.dropna()
            if not last.empty and len(tickers) == 1:
                precios[tickers[0]] = round(float(last.iloc[-1]), 4)
        else:
            last_row = closes.dropna(how="all").iloc[-1]
            for t in tickers:
                if t in last_row.index and pd.notna(last_row[t]):
                    precios[t] = round(float(last_row[t]), 4)
    except Exception as e:
        print(f"[fetch_prices] yf.download error: {e}", file=sys.stderr)
    return precios


def get_exchange_rate() -> float:
    try:
        hist = yf.Ticker("MXN=X").history(period="2d")
        if not hist.empty:
            return round(float(hist["Close"].dropna().iloc[-1]), 4)
    except Exception as e:
        print(f"[fetch_prices] T/C error: {e}", file=sys.stderr)
    return FALLBACK_TC


def main():
    if not TICKERS_FILE.exists():
        print(f"[fetch_prices] ERROR: {TICKERS_FILE} not found", file=sys.stderr)
        sys.exit(1)

    tickers = json.loads(TICKERS_FILE.read_text())
    print(f"[fetch_prices] Fetching {len(tickers)} tickers: {tickers}")

    precios = get_prices(tickers)
    tc      = get_exchange_rate()

    if not precios:
        print("[fetch_prices] WARNING: no prices returned — keeping existing prices.json", file=sys.stderr)
        sys.exit(1)

    output = {"precios": precios, "tc": tc, "fecha": str(date.today())}
    PRICES_FILE.write_text(json.dumps(output, indent=2))
    print(f"[fetch_prices] Saved {len(precios)} prices, T/C={tc}")


if __name__ == "__main__":
    main()
