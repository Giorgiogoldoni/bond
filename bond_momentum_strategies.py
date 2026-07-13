#!/usr/bin/env python3
"""
BOND MOMENTUM STRATEGIES — Antonacci (Dual Momentum) + Faber (GTAA aggressivo)
════════════════════════════════════════════════════════════════════════════
Ribilanciamento settimanale per entrambe. Universo condiviso: bond_universe.MOMENTUM_UNIVERSE.
Capitale virtuale: indice base 100 (non euro), coerente con le altre 3 linee.

ANTONACCI — dual momentum, filtro assoluto 12M PER SINGOLO STRUMENTO:
  - ogni ETF candidato deve avere rendimento_12m > 0 per essere eligible
  - se nessun eligible -> 100% XEON (cash)
  - altrimenti Top1=60%, Top2=40% (o 100% se un solo eligible) tra gli eligible,
    ordinati per rendimento_12m decrescente

FABER (versione aggressiva) — momentum puro, nessun filtro di trend:
  - composite = 0.40*r1m + 0.35*r3m + 0.25*r6m  (piu' peso al breve termine)
  - Top3 pesi 50/30/20 su TUTTO l'universo (XEON incluso in classifica)
  - nessun filtro di conferma trend -> piu' reattivo, piu' whipsaw
"""

import time
from datetime import datetime, timezone, timedelta

try:
    import yfinance as yf
except ImportError:
    import os; os.system("pip install yfinance --break-system-packages -q")
    import yfinance as yf

from bond_universe import MOMENTUM_UNIVERSE, MOMENTUM_ABS_FILTER_BENCH

CASH_TICKER = "XEON.MI"


# ── FETCH PREZZI ESTESO (serve r24w ~6M e r52w ~12M per Antonacci/Faber) ──
def fetch_prices_extended(tickers: list) -> dict:
    """
    Come rc.fetch_prices ma con finestra piu' ampia (380gg) per calcolare
    anche r24w (~6 mesi) e r52w (~12 mesi), necessari ad Antonacci e Faber.
    """
    result = {}
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=380)
    for tk in tickers:
        for suffix in [tk, tk.replace(".MI", ".L"), tk.replace(".MI", ".PA")]:
            try:
                hist = yf.Ticker(suffix).history(
                    start=start.strftime("%Y-%m-%d"),
                    end=end.strftime("%Y-%m-%d"),
                    auto_adjust=True)
                if len(hist) < 60:
                    continue
                closes = hist["Close"].dropna()
                n = len(closes)
                p    = float(closes.iloc[-1])
                r1m  = (closes.iloc[-1]/closes.iloc[-21]-1)*100 if n>21 else None
                r3m  = (closes.iloc[-1]/closes.iloc[-63]-1)*100 if n>63 else None
                r6m  = (closes.iloc[-1]/closes.iloc[-126]-1)*100 if n>126 else None
                r12m = (closes.iloc[-1]/closes.iloc[-252]-1)*100 if n>252 else None
                result[tk] = {"p": round(p,4), "r1m": r1m, "r3m": r3m, "r6m": r6m, "r12m": r12m}
                print(f"  ✓ {tk} p={p:.2f}" + (f" r12m={r12m:.1f}%" if r12m else " r12m=N/D (storico insufficiente)"))
                break
            except Exception:
                continue
        if tk not in result:
            print(f"  ⚠  {tk} — non disponibile")
            result[tk] = {"p": None, "r1m": None, "r3m": None, "r6m": None, "r12m": None}
        time.sleep(0.2)
    return result


# ── ANTONACCI ──────────────────────────────────────────────────────────
def antonacci_weights(prices: dict) -> dict:
    """
    prices: output di fetch_prices_extended, deve includere tutti i ticker
    di MOMENTUM_UNIVERSE (incluso XEON.MI).
    Ritorna dict {ticker: peso_percentuale}, somma = 100.
    """
    candidates = [e["ticker"] for e in MOMENTUM_UNIVERSE if e["ticker"] != CASH_TICKER]

    eligible = []
    for tk in candidates:
        r12m = prices.get(tk, {}).get("r12m")
        if r12m is not None and r12m > 0:
            eligible.append((tk, r12m))

    if not eligible:
        return {CASH_TICKER: 100}

    eligible.sort(key=lambda x: x[1], reverse=True)

    if len(eligible) == 1:
        return {eligible[0][0]: 100}

    top1, top2 = eligible[0][0], eligible[1][0]
    return {top1: 60, top2: 40}


# ── FABER (aggressivo) ──────────────────────────────────────────────────
def faber_weights(prices: dict) -> dict:
    """
    prices: output di fetch_prices_extended, deve includere tutti i ticker
    di MOMENTUM_UNIVERSE (incluso XEON.MI, che partecipa al ranking).
    Nessun filtro di trend — solo ranking per momentum composito.
    Ritorna dict {ticker: peso_percentuale}, somma = 100.
    """
    all_tickers = [e["ticker"] for e in MOMENTUM_UNIVERSE]

    composites = []
    for tk in all_tickers:
        d = prices.get(tk, {})
        vals = {"r1m": d.get("r1m"), "r3m": d.get("r3m"), "r6m": d.get("r6m")}
        w    = {"r1m": 0.40, "r3m": 0.35, "r6m": 0.25}
        valid_w = sum(w[k] for k,v in vals.items() if v is not None)
        if valid_w == 0:
            continue
        c = sum(vals[k]*w[k] for k in vals if vals[k] is not None) / valid_w
        composites.append((tk, c))

    if not composites:
        return {CASH_TICKER: 100}

    composites.sort(key=lambda x: x[1], reverse=True)
    top3 = composites[:3]

    weights_scheme = [50, 30, 20]
    result = {}
    for i, (tk, _) in enumerate(top3):
        result[tk] = weights_scheme[i]

    # Se ci sono meno di 3 strumenti con dati validi, redistribuisci
    # proporzionalmente il residuo sul primo classificato invece di lasciarlo scoperto
    if len(top3) < 3:
        missing_w = sum(weights_scheme[len(top3):])
        result[top3[0][0]] += missing_w

    return result
