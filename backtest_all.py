#!/usr/bin/env python3
"""
BACKTEST_ALL — motore di backtest storico per le 4 linee RAPTOR BOND.
════════════════════════════════════════════════════════════════════
Job ONE-SHOT, non schedulato: si lancia manualmente (o via workflow_dispatch),
NON fa parte del cron periodico — il ricalcolo storico dal 2022 e' pesante e
rischia di sforare il timeout di 20 minuti se girasse ad ogni run.

Riusa la logica ESATTA degli script live invece di duplicarla:
  - update_portfolio_bond.py       -> macro_scores, momentum_score_bond, final_scores, optimize_weights
  - update_portfolio_bond_acc.py   -> stesse funzioni, versione acc
  - bond_momentum_strategies.py    -> antonacci_weights, faber_weights

Regime macro storico: letto da data/latest.json (scenario_weights, gia' storicizzato
dal 2015) invece di ricostruirlo da zero via classify() — nessuna nuova dipendenza.

Output: 4 file nav_history_*.json nello stesso schema di quelli esistenti,
con flag "backtest": true sui punti storici ricostruiti.

Cadenza: ribilanciamento SETTIMANALE per tutte e 4 le linee (ogni lunedi').
Capitale: indice base 100 (non un controvalore euro).
Dati: chiusura giornaliera (auto_adjust=True).
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

try:
    import yfinance as yf
except ImportError:
    import os; os.system("pip install yfinance --break-system-packages -q")
    import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent))

import bond_universe as bu
from bond_momentum_strategies import antonacci_weights, faber_weights

BACKTEST_START = "2022-01-01"
DATA_DIR = Path(__file__).parent / "data"


# ══════════════════════════════════════════════════════════════════
# 1. FETCH STORICO BULK — un solo download per tutti i 34 ticker
# ══════════════════════════════════════════════════════════════════
def fetch_history_bulk(tickers: list, start: str) -> dict:
    """
    Scarica storico daily close per tutti i ticker in un colpo solo
    (yf.download supporta liste, molto piu' efficiente di 34 chiamate separate).
    Ritorna {ticker: {date_str: close_float}}.
    """
    print(f"Download storico bulk per {len(tickers)} ticker dal {start}...")
    out = {tk: {} for tk in tickers}
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # yf.download in batch da 10 per volta, per limitare il rischio di timeout/rate-limit
    batch_size = 10
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        try:
            data = yf.download(batch, start=start, end=end, auto_adjust=True,
                                group_by="ticker", progress=False, threads=True)
        except Exception as e:
            print(f"  ⚠ batch {batch} fallito: {e}")
            continue

        for tk in batch:
            try:
                if len(batch) == 1:
                    closes = data["Close"].dropna()
                else:
                    closes = data[tk]["Close"].dropna()
                for dt, px in closes.items():
                    out[tk][dt.strftime("%Y-%m-%d")] = round(float(px), 4)
                print(f"  ✓ {tk}: {len(closes)} punti")
            except Exception as e:
                print(f"  ⚠ {tk}: dati non estraibili ({e})")
        time.sleep(1.5)  # rispetto rate limit tra batch

    return out


# ══════════════════════════════════════════════════════════════════
# 2. REGIME MACRO STORICO — letto da data/latest.json, non ricalcolato
# ══════════════════════════════════════════════════════════════════
def load_historical_regimes() -> list:
    """
    Ritorna lista ordinata di {date, scenarios} da data/latest.json.
    Gia' presente dal 2015 (601 punti settimanali) — nessun ricalcolo necessario.
    """
    path = DATA_DIR / "latest.json"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} non trovato — serve per il regime macro storico. "
            "Verificare che il file sia presente nel repo prima di lanciare il backtest."
        )
    d = json.loads(path.read_text(encoding="utf-8"))
    sw = d.get("scenario_weights", [])
    if not sw:
        raise ValueError("data/latest.json non contiene 'scenario_weights' — impossibile procedere.")
    return sorted(sw, key=lambda x: x["date"])


def regime_asof(history: list, date_str: str) -> dict:
    """Ritorna lo scenario piu' recente con data <= date_str (ultimo noto prima o alla data richiesta)."""
    best = history[0]["scenarios"]
    for point in history:
        if point["date"] <= date_str:
            best = point["scenarios"]
        else:
            break
    return best


# ══════════════════════════════════════════════════════════════════
# 3. FINESTRE DI RENDIMENTO — calcolate su storico bulk, asof una data
# ══════════════════════════════════════════════════════════════════
def prices_asof(history_bulk: dict, tickers: list, date_str: str) -> dict:
    """
    Per ogni ticker, calcola {p, r1w, r4w, r12w, r1m, r3m, r6m, r12m} asof date_str,
    usando i giorni di trading disponibili PRIMA o alla data richiesta.
    r1w~5gg, r4w~21gg, r12w~63gg, r1m~21gg, r3m~63gg, r6m~126gg, r12m~252gg.
    """
    result = {}
    for tk in tickers:
        series = history_bulk.get(tk, {})
        dates_avail = sorted(d for d in series if d <= date_str)
        if not dates_avail:
            result[tk] = {"p": None, "r1w": None, "r4w": None, "r12w": None,
                          "r1m": None, "r3m": None, "r6m": None, "r12m": None}
            continue
        closes = [series[d] for d in dates_avail]
        n = len(closes)
        p = closes[-1]

        def ret(lookback):
            if n > lookback:
                base = closes[-1 - lookback]
                return (p / base - 1) * 100 if base else None
            return None

        result[tk] = {
            "p": p,
            "r1w": ret(5), "r4w": ret(21), "r12w": ret(63),
            "r1m": ret(21), "r3m": ret(63), "r6m": ret(126), "r12m": ret(252),
        }
    return result


# ══════════════════════════════════════════════════════════════════
# 4. SIMULAZIONE SETTIMANALE GENERICA — compounding a indice 100
# ══════════════════════════════════════════════════════════════════
def weekly_mondays(start: str, end: str) -> list:
    """Lista di date (lunedi') tra start e end, formato YYYY-MM-DD."""
    d = datetime.strptime(start, "%Y-%m-%d")
    # porta al lunedi' successivo o uguale
    d += timedelta(days=(7 - d.weekday()) % 7)
    end_d = datetime.strptime(end, "%Y-%m-%d")
    out = []
    while d <= end_d:
        out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=7)
    return out


def price_on_or_before(history_bulk: dict, tk: str, date_str: str):
    series = history_bulk.get(tk, {})
    dates_avail = sorted(d for d in series if d <= date_str)
    return series[dates_avail[-1]] if dates_avail else None


def simulate_line(mondays: list, weight_fn, history_bulk: dict, label: str) -> list:
    """
    weight_fn(date_str) -> dict{ticker: peso%}  — ricalcolato ogni lunedi'.
    Il NAV tra un lunedi' e il successivo segue il rendimento pesato reale
    dei prezzi (non solo lo score), poi si ribilancia ai pesi nuovi.
    """
    nav = 100.0
    weights = {}
    out = []
    prev_prices = {}

    for i, date_str in enumerate(mondays):
        new_weights = weight_fn(date_str)

        if i > 0 and weights:
            # calcola rendimento della settimana appena trascorsa con i pesi PRECEDENTI
            week_ret = 0.0
            for tk, w in weights.items():
                p_now  = price_on_or_before(history_bulk, tk, date_str)
                p_prev = prev_prices.get(tk)
                if p_now and p_prev:
                    week_ret += (w / 100) * (p_now / p_prev - 1)
            nav *= (1 + week_ret)

        weights = new_weights
        prev_prices = {tk: price_on_or_before(history_bulk, tk, date_str) for tk in weights}

        out.append({
            "date": date_str,
            "nav": round(nav, 4),
            "weights": weights,
            "backtest": True,
        })

        if i % 20 == 0:
            print(f"  [{label}] {date_str} -> nav={nav:.2f}")

    return out


# ══════════════════════════════════════════════════════════════════
# 5. WRAPPER PER LE 4 LINEE
# ══════════════════════════════════════════════════════════════════
def make_bond_dist_weight_fn(history_bulk, regimes, bond_dist_module):
    m = bond_dist_module

    def fn(date_str):
        scenarios = regime_asof(regimes, date_str)
        prices = prices_asof(history_bulk, [e["ticker"] for e in bu.BOND_DIST_UNIVERSE], date_str)
        macro = m.macro_scores(scenarios)
        mom = m.momentum_score_bond(prices)
        final = m.final_scores(macro, mom)
        weights, _excl = m.optimize_weights(final, {}, scenarios)
        return weights
    return fn


def make_bond_acc_weight_fn(history_bulk, regimes, bond_acc_module):
    m = bond_acc_module

    def fn(date_str):
        scenarios = regime_asof(regimes, date_str)
        prices = prices_asof(history_bulk, [e["ticker"] for e in bu.BOND_ACC_UNIVERSE], date_str)
        macro = m.macro_scores(scenarios)
        mom = m.momentum_score_acc(prices)
        final = m.final_scores(macro, mom)
        weights, _excl = m.optimize_weights(final, {}, scenarios)
        return weights
    return fn


def make_antonacci_weight_fn(history_bulk):
    tickers = [e["ticker"] for e in bu.MOMENTUM_UNIVERSE]

    def fn(date_str):
        prices = prices_asof(history_bulk, tickers, date_str)
        return antonacci_weights(prices)
    return fn


def make_faber_weight_fn(history_bulk):
    tickers = [e["ticker"] for e in bu.MOMENTUM_UNIVERSE]

    def fn(date_str):
        prices = prices_asof(history_bulk, tickers, date_str)
        return faber_weights(prices)
    return fn


# ══════════════════════════════════════════════════════════════════
# 6. MAIN
# ══════════════════════════════════════════════════════════════════
def run(start=BACKTEST_START, dry_run=False):
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    mondays = weekly_mondays(start, end)
    print(f"Backtest dal {start} al {end} — {len(mondays)} settimane")

    all_tickers = [e["ticker"] for e in bu.all_tickers_unique()]

    if dry_run:
        print("DRY RUN: salto il fetch reale, uso dati sintetici per validare la meccanica")
        history_bulk = _synthetic_history(all_tickers, mondays)
        regimes = _synthetic_regimes(mondays)
    else:
        history_bulk = fetch_history_bulk(all_tickers, start)
        regimes = load_historical_regimes()

    # Import lazy dei moduli live (evita side-effect se backtest_all viene
    # importato altrove senza bisogno degli script completi)
    sys.path.insert(0, str(Path(__file__).parent))
    import update_portfolio_bond as bond_dist_module
    import update_portfolio_bond_acc as bond_acc_module

    lines = {
        "bond":      make_bond_dist_weight_fn(history_bulk, regimes, bond_dist_module),
        "bond_acc":  make_bond_acc_weight_fn(history_bulk, regimes, bond_acc_module),
        "antonacci": make_antonacci_weight_fn(history_bulk),
        "faber":     make_faber_weight_fn(history_bulk),
    }

    for name, weight_fn in lines.items():
        print(f"\n── Simulazione {name} ──")
        series = simulate_line(mondays, weight_fn, history_bulk, name)
        out_path = DATA_DIR / f"nav_history_{name}.json" if name in ("antonacci", "faber") \
            else Path(__file__).parent / f"nav_history_{name}.json"
        # NOTA: bond e bond_acc hanno gia' nav_history_bond.json / _acc.json
        # con dati LIVE in root — il backtest storico va MERGEATO in coda a quelli,
        # non sovrascritto. Qui produco un file separato *_backtest.json per
        # revisione manuale prima del merge, per sicurezza.
        if name in ("bond", "bond_acc"):
            out_path = Path(__file__).parent / f"nav_history_{name}_backtest.json"
        else:
            out_path = Path(__file__).parent / f"nav_history_{name}.json"
        out_path.write_text(json.dumps(series, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  → scritto {out_path} ({len(series)} punti)")


def _synthetic_history(tickers, mondays):
    """Genera prezzi sintetici a random walk per validare la meccanica senza rete."""
    import random
    random.seed(42)
    history = {}
    start_d = datetime.strptime(mondays[0], "%Y-%m-%d") - timedelta(days=380)
    end_d = datetime.strptime(mondays[-1], "%Y-%m-%d")
    for tk in tickers:
        series = {}
        px = 100.0
        d = start_d
        while d <= end_d:
            if d.weekday() < 5:
                px *= (1 + random.gauss(0.0002, 0.004))
                series[d.strftime("%Y-%m-%d")] = round(px, 4)
            d += timedelta(days=1)
        history[tk] = series
    return history


def _synthetic_regimes(mondays):
    """Regimi sintetici alternati per validare la meccanica senza dipendere da data/latest.json."""
    codes = ["GOLDILOCKS", "TIGHTENING", "RISK_OFF", "REFLAZIONE"]
    out = []
    for i, d in enumerate(mondays):
        dominant = codes[i % len(codes)]
        scenarios = {c: (60 if c == dominant else 10) for c in
                     ["GOLDILOCKS","REFLAZIONE","DISINFLAZIONE","TIGHTENING","STAGFLAZIONE",
                      "RECESSIONE","RISK_OFF","EUFORIA","ZIRP","GEO_SHOCK","PANDEMIC",
                      "FINANCIAL","WAR","SOVEREIGN"]}
        out.append({"date": d, "scenarios": scenarios})
    return out


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run(dry_run=dry)
