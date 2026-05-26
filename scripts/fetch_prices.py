"""
scripts/fetch_prices.py — Corre en GitHub Actions, guarda prices.json en la raíz del repo.

Estrategia ante rate limit de Yahoo Finance:
  1. Intenta descarga en bloque (más rápida)
  2. Si falla, reintenta ticker por ticker con delays
  3. Si aún falla, conserva el prices.json existente sin marcar error
"""

import json
import sys
import time
from pathlib import Path
from datetime import date

import pandas as pd
import yfinance as yf

ROOT         = Path(__file__).parent.parent
PRICES_FILE  = ROOT / "prices.json"
TICKERS_FILE = ROOT / "tickers.json"
FALLBACK_TC  = 17.50

MAX_RETRIES    = 3
RETRY_DELAY_S  = 8   # segundos entre reintentos


def get_prices_bulk(tickers: list[str]) -> dict[str, float]:
    """Descarga todos los tickers en una sola llamada (más rápido)."""
    precios = {}
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
    return precios


def get_price_single(ticker: str) -> float | None:
    """Descarga un ticker individual via Ticker().history()."""
    hist = yf.Ticker(ticker).history(period="2d")
    if hist.empty:
        return None
    last = hist["Close"].dropna()
    return round(float(last.iloc[-1]), 4) if not last.empty else None


def get_prices(tickers: list[str]) -> dict[str, float]:
    """Intenta bulk primero; si falla, reintenta uno por uno con backoff."""
    # ── Intento 1: descarga en bloque ──────────────────────────
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[fetch_prices] Bulk attempt {attempt}/{MAX_RETRIES}…")
            precios = get_prices_bulk(tickers)
            if precios:
                print(f"[fetch_prices] Bulk OK — {len(precios)}/{len(tickers)} tickers")
                return precios
        except Exception as e:
            print(f"[fetch_prices] Bulk error: {e}")
        if attempt < MAX_RETRIES:
            print(f"[fetch_prices] Esperando {RETRY_DELAY_S}s antes de reintentar…")
            time.sleep(RETRY_DELAY_S)

    # ── Intento 2: ticker por ticker ───────────────────────────
    print("[fetch_prices] Bulk falló — intentando ticker por ticker…")
    precios = {}
    for i, ticker in enumerate(tickers):
        if i > 0:
            time.sleep(3)
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                precio = get_price_single(ticker)
                if precio is not None:
                    precios[ticker] = precio
                    print(f"  ✓ {ticker}: {precio}")
                    break
            except Exception as e:
                print(f"  ✗ {ticker} (intento {attempt}): {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY_S)

    return precios


def get_exchange_rate() -> float:
    """Obtiene USD/MXN con reintentos."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            hist = yf.Ticker("MXN=X").history(period="2d")
            if not hist.empty:
                tc = round(float(hist["Close"].dropna().iloc[-1]), 4)
                print(f"[fetch_prices] T/C: {tc}")
                return tc
        except Exception as e:
            print(f"[fetch_prices] T/C error (intento {attempt}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_S)
    print(f"[fetch_prices] T/C fallback: {FALLBACK_TC}")
    return FALLBACK_TC


def load_existing_prices() -> dict:
    """Lee el prices.json actual como respaldo."""
    if PRICES_FILE.exists():
        try:
            return json.loads(PRICES_FILE.read_text())
        except Exception:
            pass
    return {}


def main():
    if not TICKERS_FILE.exists():
        print(f"[fetch_prices] ERROR: {TICKERS_FILE} not found", file=sys.stderr)
        sys.exit(1)

    tickers = json.loads(TICKERS_FILE.read_text())
    print(f"[fetch_prices] Tickers: {tickers}")

    precios = get_prices(tickers)
    tc      = get_exchange_rate()

    if not precios:
        # Conservar prices.json existente — salir sin error para no spamear correos
        existing = load_existing_prices()
        if existing:
            print("[fetch_prices] Rate limited — conservando prices.json existente.")
            print(f"[fetch_prices] Última fecha: {existing.get('fecha','desconocida')}")
            sys.exit(0)   # ← exit 0: no es un fallo, es rate limit temporal
        else:
            print("[fetch_prices] ERROR: sin precios y sin fallback.", file=sys.stderr)
            sys.exit(1)

    # Si obtuvimos algunos pero no todos, completar con los existentes
    existing = load_existing_prices()
    if existing and len(precios) < len(tickers):
        faltantes = [t for t in tickers if t not in precios]
        for t in faltantes:
            if t in existing.get("precios", {}):
                precios[t] = existing["precios"][t]
                print(f"[fetch_prices] {t}: usando precio anterior ({precios[t]})")

    output = {"precios": precios, "tc": tc, "fecha": str(date.today())}
    PRICES_FILE.write_text(json.dumps(output, indent=2))
    print(f"[fetch_prices] ✓ Guardados {len(precios)} precios, T/C={tc}, fecha={output['fecha']}")


if __name__ == "__main__":
    main()
