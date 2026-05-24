"""
api/precios.py — Serverless function para Vercel
Obtiene precios de Yahoo Finance (vía yfinance) y el tipo de cambio USD/MXN.

Endpoint: GET /api/precios?tickers=AAPL,MSFT,GOOGL,...
Respuesta: { "precios": { "AAPL": 195.0, ... }, "tc": 17.50, "fecha": "2025-05-23" }
"""

from http.server import BaseHTTPRequestHandler
import json
import pandas as pd
import yfinance as yf
from urllib.parse import urlparse, parse_qs
from datetime import date


def get_prices(tickers: list[str]) -> dict[str, float]:
    """Descarga precios de cierre más recientes para una lista de tickers."""
    precios = {}
    if not tickers:
        return precios

    try:
        raw = yf.download(
            tickers,
            period="2d",
            progress=False,
            auto_adjust=True,
        )

        if raw.empty:
            return precios

        closes = raw["Close"]

        if isinstance(closes, pd.Series):
            # Un solo ticker: la serie tiene índice de fecha
            if len(tickers) == 1 and not closes.empty:
                last = closes.dropna()
                if not last.empty:
                    precios[tickers[0]] = round(float(last.iloc[-1]), 4)
        else:
            # Múltiples tickers: DataFrame con columnas = tickers
            last_row = closes.dropna(how="all").iloc[-1]
            for t in tickers:
                if t in last_row.index and pd.notna(last_row[t]):
                    precios[t] = round(float(last_row[t]), 4)

    except Exception as exc:
        print(f"[precios] Error yf.download: {exc}")

    return precios


def get_exchange_rate() -> float:
    """Obtiene el tipo de cambio USD/MXN de Yahoo Finance."""
    try:
        ticker = yf.Ticker("MXN=X")
        hist = ticker.history(period="2d")
        if not hist.empty:
            return round(float(hist["Close"].dropna().iloc[-1]), 4)
    except Exception as exc:
        print(f"[precios] Error T/C: {exc}")
    return 17.50  # fallback razonable


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parsear query string
        query = parse_qs(urlparse(self.path).query)
        raw_tickers = query.get("tickers", [""])[0]
        tickers = [t.strip().upper() for t in raw_tickers.split(",") if t.strip()]

        if not tickers:
            self._respond(400, {"error": "Parámetro 'tickers' requerido."})
            return

        precios = get_prices(tickers)
        tc = get_exchange_rate()

        self._respond(200, {
            "precios": precios,
            "tc": tc,
            "fecha": str(date.today()),
        })

    def do_OPTIONS(self):
        # Preflight CORS (aunque mismo dominio Vercel no lo necesita)
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def _respond(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt, *args):
        pass  # silenciar logs internos de BaseHTTPRequestHandler
