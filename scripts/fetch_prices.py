"""
scripts/fetch_prices.py — Usa Finnhub API (sin rate limit desde GitHub Actions).

Requiere: variable de entorno FINNHUB_API_KEY (GitHub Actions secret).
Plan gratuito Finnhub: 60 llamadas/min — más que suficiente para 6 tickers.

Fuentes:
  - Precios de acciones: Finnhub /quote
  - Tipo de cambio USD/MXN: open.er-api.com (sin token) → Finnhub fallback
"""

import json
import os
import sys
import time
import requests
from pathlib import Path
from datetime import date, datetime, timezone

ROOT         = Path(__file__).parent.parent
PRICES_FILE  = ROOT / "prices.json"
TICKERS_FILE = ROOT / "tickers.json"
FALLBACK_TC  = 17.50

FINNHUB_BASE = "https://finnhub.io/api/v1"
MAX_RETRIES  = 3
RETRY_DELAY  = 5   # segundos entre reintentos


# ── Precios de acciones ────────────────────────────────────────────────────

def get_price_finnhub(ticker: str, token: str) -> float | None:
    """Obtiene precio actual de un ticker via Finnhub /quote."""
    url = f"{FINNHUB_BASE}/quote"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(url, params={"symbol": ticker, "token": token}, timeout=10)
            r.raise_for_status()
            data = r.json()
            price = data.get("c")   # 'c' = current price
            if price and float(price) > 0:
                return round(float(price), 4)
            # Si c=0 el mercado puede estar cerrado; usar prev close
            pc = data.get("pc")
            if pc and float(pc) > 0:
                print(f"  ~ {ticker}: mercado cerrado, usando prev close {pc}")
                return round(float(pc), 4)
        except Exception as e:
            print(f"  ✗ {ticker} (intento {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    return None


def get_prices(tickers: list[str], token: str) -> dict[str, float]:
    """Descarga precios para todos los tickers (con pequeño delay entre calls)."""
    precios = {}
    for i, ticker in enumerate(tickers):
        if i > 0:
            time.sleep(0.5)   # 0.5s entre calls → máx 2 calls/s, bien bajo el límite
        precio = get_price_finnhub(ticker, token)
        if precio is not None:
            precios[ticker] = precio
            print(f"  ✓ {ticker}: {precio}")
        else:
            print(f"  ✗ {ticker}: no se pudo obtener precio")
    return precios


# ── Tipo de cambio USD/MXN ─────────────────────────────────────────────────

def get_exchange_rate(token: str) -> float:
    """
    Obtiene USD/MXN.
    Fuente primaria : open.er-api.com (gratis, sin token)
    Fallback        : Finnhub /forex/rates
    """
    # Intento 1: open.er-api (no requiere token, muy confiable)
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        r.raise_for_status()
        data = r.json()
        mxn = data.get("rates", {}).get("MXN")
        if mxn and float(mxn) > 0:
            tc = round(float(mxn), 4)
            print(f"[fetch_prices] T/C (open.er-api): {tc}")
            return tc
    except Exception as e:
        print(f"[fetch_prices] T/C open.er-api error: {e}")

    # Intento 2: Finnhub /forex/rates
    try:
        r = requests.get(
            f"{FINNHUB_BASE}/forex/rates",
            params={"base": "USD", "token": token},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        mxn = data.get("quote", {}).get("MXN")
        if mxn and float(mxn) > 0:
            tc = round(float(mxn), 4)
            print(f"[fetch_prices] T/C (Finnhub): {tc}")
            return tc
    except Exception as e:
        print(f"[fetch_prices] T/C Finnhub error: {e}")

    print(f"[fetch_prices] T/C fallback: {FALLBACK_TC}")
    return FALLBACK_TC


# ── Utilidades ─────────────────────────────────────────────────────────────

def load_existing_prices() -> dict:
    """Lee el prices.json actual como respaldo."""
    if PRICES_FILE.exists():
        try:
            return json.loads(PRICES_FILE.read_text())
        except Exception:
            pass
    return {}


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    token = os.environ.get("FINNHUB_API_KEY", "").strip()
    if not token:
        print("[fetch_prices] ERROR: FINNHUB_API_KEY no está definida.", file=sys.stderr)
        sys.exit(1)

    if not TICKERS_FILE.exists():
        print(f"[fetch_prices] ERROR: {TICKERS_FILE} not found", file=sys.stderr)
        sys.exit(1)

    tickers = json.loads(TICKERS_FILE.read_text())
    print(f"[fetch_prices] Tickers: {tickers}")
    print(f"[fetch_prices] Usando Finnhub API…")

    precios = get_prices(tickers, token)
    tc      = get_exchange_rate(token)

    if not precios:
        existing = load_existing_prices()
        if existing:
            print("[fetch_prices] Sin precios nuevos — conservando prices.json existente.")
            print(f"[fetch_prices] Última fecha: {existing.get('fecha', 'desconocida')}")
            sys.exit(0)
        else:
            print("[fetch_prices] ERROR: sin precios y sin fallback.", file=sys.stderr)
            sys.exit(1)

    # Completar tickers faltantes con precio anterior
    existing = load_existing_prices()
    if existing and len(precios) < len(tickers):
        faltantes = [t for t in tickers if t not in precios]
        for t in faltantes:
            if t in existing.get("precios", {}):
                precios[t] = existing["precios"][t]
                print(f"[fetch_prices] {t}: usando precio anterior ({precios[t]})")

    output = {
        "precios":    precios,
        "tc":         tc,
        "fecha":      str(date.today()),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    PRICES_FILE.write_text(json.dumps(output, indent=2))
    print(
        f"[fetch_prices] ✓ Guardados {len(precios)} precios, "
        f"T/C={tc}, fecha={output['fecha']}, updated_at={output['updated_at']}"
    )


if __name__ == "__main__":
    main()
