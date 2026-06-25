#!/usr/bin/env python3
"""
RAPTOR COMMON — funzioni condivise tra i motori di portafoglio
════════════════════════════════════════════════════════════════
Usato da update_portfolio.py (portafoglio principale, 25 ETF)
e da update_portfolio_etp.py (Portfolio ETP, 14 strumenti).

Contiene: fetch prezzi, fetch benchmark, NAV tracking.
"""

import json, os, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

def install(pkg):
    os.system(f"pip install {pkg} --break-system-packages -q")

try:
    import yfinance as yf
except ImportError:
    install("yfinance"); import yfinance as yf


# ── FETCH PREZZI UNIVERSO ──────────────────────────────────────────
def fetch_prices(tickers: list) -> dict:
    """
    Scarica prezzi e rendimenti (1W/4W/12W) per una lista di ticker.
    Prova suffissi alternativi (.L, .PA) se .MI non disponibile.
    """
    result = {}
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=95)
    for tk in tickers:
        for suffix in [tk, tk.replace(".MI", ".L"), tk.replace(".MI", ".PA")]:
            try:
                hist = yf.Ticker(suffix).history(
                    start=start.strftime("%Y-%m-%d"),
                    end=end.strftime("%Y-%m-%d"),
                    auto_adjust=True)
                if len(hist) < 10:
                    continue
                closes = hist["Close"].dropna()
                p    = float(closes.iloc[-1])
                r1w  = (closes.iloc[-1]/closes.iloc[-6]-1)*100  if len(closes)>6  else None
                r4w  = (closes.iloc[-1]/closes.iloc[-21]-1)*100 if len(closes)>21 else None
                r12w = (closes.iloc[-1]/closes.iloc[-61]-1)*100 if len(closes)>61 else None
                result[tk] = {"p": round(p,4), "r1w": r1w, "r4w": r4w, "r12w": r12w}
                print(f"  ✓ {tk} p={p:.2f}" + (f" r1w={r1w:.1f}%" if r1w else ""))
                break
            except Exception:
                continue
        if tk not in result:
            print(f"  ⚠  {tk} — non disponibile")
            result[tk] = {"p": None, "r1w": None, "r4w": None, "r12w": None}
        time.sleep(0.2)
    return result


# ── FETCH PREZZI BENCHMARK (solo ultimo prezzo) ────────────────────
def fetch_benchmark_prices(tickers: list) -> dict:
    """Scarica solo l'ultimo prezzo disponibile per i benchmark (IWMO, VNGA80)."""
    result = {}
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=10)
    for tk in tickers:
        try:
            hist = yf.Ticker(tk).history(
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                auto_adjust=True)
            if len(hist) >= 1:
                result[tk] = float(hist["Close"].dropna().iloc[-1])
                print(f"  ✓ {tk} = {result[tk]:.4f}")
        except Exception as e:
            print(f"  ⚠  {tk}: {e}")
        time.sleep(0.2)
    return result


# ── MOMENTUM SCORE (ranking relativo 0-100) ─────────────────────────
def momentum_score(prices: dict) -> dict:
    """
    Combina r1w/r4w/r12w (pesi 30/40/30) in un composito,
    poi normalizza 0-100 relativamente all'universo passato.
    """
    composites = {}
    for tk, d in prices.items():
        vals  = [d["r1w"], d["r4w"], d["r12w"]]
        valid = [v for v in vals if v is not None]
        if not valid:
            composites[tk] = None
            continue
        keys  = ["r1w","r4w","r12w"]
        w     = [0.30, 0.40, 0.30]
        c     = sum(d[k]*w[i] for i,k in enumerate(keys) if d[k] is not None)
        wsum  = sum(w[i] for i,k in enumerate(keys) if d[k] is not None)
        composites[tk] = c / wsum if wsum else None

    known = {tk: v for tk,v in composites.items() if v is not None}
    if not known:
        return {tk: 50 for tk in prices}
    vmin, vmax = min(known.values()), max(known.values())
    scores = {}
    for tk, c in composites.items():
        if c is None:
            scores[tk] = 50
        elif vmax == vmin:
            scores[tk] = 50
        else:
            scores[tk] = round((c - vmin) / (vmax - vmin) * 100)
    return scores


# ── NAV TRACKING ────────────────────────────────────────────────────
def update_nav_history(nav_file: Path, portfolio_list: list, prices_bench: dict, today_str: str):
    """
    Calcola NAV portafoglio (prezzi correnti vs precedenti) e benchmark IWMO/VNGA80.
    Appende un punto al file nav_file passato (path specifico per ogni portafoglio).
    """
    nav_history = []
    if nav_file.exists():
        try:
            with open(nav_file, encoding="utf-8") as f:
                nav_history = json.load(f)
        except Exception as e:
            print(f"⚠  Errore lettura {nav_file.name}: {e}")

    if not nav_history:
        # ── INIZIALIZZAZIONE: NAV = 100 ──────────────────────────
        entry = {
            "date":       today_str,
            "nav":        100.0,
            "iwmo":       100.0,
            "vnga80":     100.0,
            "prices":     {e["ticker_full"]: e["price"] for e in portfolio_list if e["price"]},
            "bench_px":   prices_bench,
            "weights":    {e["ticker_full"]: e["weight"] for e in portfolio_list},
            "ret_port":   0.0,
            "ret_iwmo":   0.0,
            "ret_vnga80": 0.0,
        }
        nav_history.append(entry)
        print(f"\n💹 NAV inizializzata a 100.00 — {today_str}")
    else:
        prev       = nav_history[-1]
        prev_px    = prev.get("prices", {})
        prev_bench = prev.get("bench_px", {})
        prev_nav   = prev.get("nav",    100.0)
        prev_iwmo  = prev.get("iwmo",   100.0)
        prev_vnga  = prev.get("vnga80", 100.0)

        # Rendimento portafoglio pesato
        ret_port = 0.0
        for etf in portfolio_list:
            tk     = etf["ticker_full"]
            w      = etf["weight"] / 100.0
            px_new = etf.get("price")
            px_old = prev_px.get(tk)
            if px_new and px_old and px_old > 0:
                ret_port += w * (px_new / px_old - 1)

        # Rendimento benchmark
        ret_iwmo = ret_vnga = 0.0
        if prices_bench.get("IWMO.MI") and prev_bench.get("IWMO.MI") and prev_bench["IWMO.MI"] > 0:
            ret_iwmo = prices_bench["IWMO.MI"] / prev_bench["IWMO.MI"] - 1
        if prices_bench.get("VNGA80.MI") and prev_bench.get("VNGA80.MI") and prev_bench["VNGA80.MI"] > 0:
            ret_vnga = prices_bench["VNGA80.MI"] / prev_bench["VNGA80.MI"] - 1

        new_nav  = round(prev_nav  * (1 + ret_port), 4)
        new_iwmo = round(prev_iwmo * (1 + ret_iwmo), 4)
        new_vnga = round(prev_vnga * (1 + ret_vnga), 4)

        entry = {
            "date":       today_str,
            "nav":        new_nav,
            "iwmo":       new_iwmo,
            "vnga80":     new_vnga,
            "prices":     {e["ticker_full"]: e["price"] for e in portfolio_list if e["price"]},
            "bench_px":   prices_bench,
            "weights":    {e["ticker_full"]: e["weight"] for e in portfolio_list},
            "ret_port":   round(ret_port * 100, 4),
            "ret_iwmo":   round(ret_iwmo * 100, 4),
            "ret_vnga80": round(ret_vnga * 100, 4),
        }

        if nav_history[-1].get("date") == today_str:
            nav_history[-1] = entry   # aggiorna stesso giorno (run multipli)
        else:
            nav_history.append(entry)

        print(f"\n💹 NAV {prev_nav:.2f} → {new_nav:.2f} ({ret_port*100:+.3f}%)")
        print(f"   IWMO   {prev_iwmo:.2f} → {new_iwmo:.2f} ({ret_iwmo*100:+.3f}%)")
        print(f"   VNGA80 {prev_vnga:.2f} → {new_vnga:.2f} ({ret_vnga*100:+.3f}%)")

    nav_history = nav_history[-500:]  # max ~2 anni (4 punti/gg × 250gg)
    nav_file.parent.mkdir(parents=True, exist_ok=True)
    with open(nav_file, "w", encoding="utf-8") as f:
        json.dump(nav_history, f, ensure_ascii=False, indent=2)
    print(f"✅ {nav_file.name} — {len(nav_history)} punti")


# ── SEGNALE RIBILANCIAMENTO (generico) ─────────────────────────────
def rebalance_signal(new_w: dict, prev_w: dict, prev_regime: str, curr_regime: str) -> tuple:
    if not prev_w:
        return "INIT", "Prima configurazione del portafoglio"
    all_tickers = set(new_w.keys()) | set(prev_w.keys())
    deviations  = {tk: abs(new_w.get(tk,0) - prev_w.get(tk,0)) for tk in all_tickers}
    max_dev     = max(deviations.values()) if deviations else 0
    avg_dev     = sum(deviations.values()) / len(deviations) if deviations else 0
    entered     = [tk for tk in new_w if tk not in prev_w]
    exited      = [tk for tk in prev_w if tk not in new_w]
    regime_changed = prev_regime != curr_regime
    if max_dev > 8 or regime_changed:
        if regime_changed:
            reason = f"Cambio regime: {prev_regime} → {curr_regime}"
        else:
            tk_max = max(deviations, key=deviations.get)
            reason = f"Deviazione massima {max_dev:.0f}% su {tk_max}"
        if entered or exited:
            reason += f" · {', '.join(e.replace('.MI','') for e in entered)} in · {', '.join(e.replace('.MI','') for e in exited)} out"
        return "REBALANCE", reason
    if max_dev > 3 or avg_dev > 2:
        return "PARTIAL", f"Deviazione {max_dev:.0f}% (avg {avg_dev:.1f}%)"
    return "HOLD", f"Portafoglio stabile (dev max {max_dev:.1f}%)"


def update_nav_history_bond(nav_file: Path, portfolio_list: list, prices_bench: dict, today_str: str):
    """
    Variante bond: 3 benchmark (XEON, VAGF, XGIU) invece di IWMO/VNGA80.
    """
    nav_history = []
    if nav_file.exists():
        try:
            with open(nav_file, encoding="utf-8") as f:
                nav_history = json.load(f)
        except Exception as e:
            print(f"Errore lettura {nav_file.name}: {e}")

    if not nav_history:
        entry = {
            "date":       today_str,
            "nav":        100.0,
            "xeon":       100.0,
            "vagf":       100.0,
            "xgiu":       100.0,
            "prices":     {e["ticker_full"]: e["price"] for e in portfolio_list if e["price"]},
            "bench_px":   prices_bench,
            "weights":    {e["ticker_full"]: e["weight"] for e in portfolio_list},
            "ret_port":   0.0,
            "ret_xeon":   0.0,
            "ret_vagf":   0.0,
            "ret_xgiu":   0.0,
        }
        nav_history.append(entry)
        print(f"NAV Bond inizializzata a 100.00 — {today_str}")
    else:
        prev       = nav_history[-1]
        prev_px    = prev.get("prices", {})
        prev_bench = prev.get("bench_px", {})
        prev_nav   = prev.get("nav",  100.0)
        prev_xeon  = prev.get("xeon", 100.0)
        prev_vagf  = prev.get("vagf", 100.0)
        prev_xgiu  = prev.get("xgiu", 100.0)

        ret_port = 0.0
        for etf in portfolio_list:
            tk     = etf["ticker_full"]
            w      = etf["weight"] / 100.0
            px_new = etf.get("price")
            px_old = prev_px.get(tk)
            if px_new and px_old and px_old > 0:
                ret_port += w * (px_new / px_old - 1)

        def bench_ret(key):
            px_new = prices_bench.get(key)
            px_old = prev_bench.get(key)
            if px_new and px_old and px_old > 0:
                return px_new / px_old - 1
            return 0.0

        ret_xeon = bench_ret("XEON.MI")
        ret_vagf = bench_ret("VAGF.MI")
        ret_xgiu = bench_ret("XGIU.MI")

        new_nav  = round(prev_nav  * (1 + ret_port), 4)
        new_xeon = round(prev_xeon * (1 + ret_xeon), 4)
        new_vagf = round(prev_vagf * (1 + ret_vagf), 4)
        new_xgiu = round(prev_xgiu * (1 + ret_xgiu), 4)

        entry = {
            "date":       today_str,
            "nav":        new_nav,
            "xeon":       new_xeon,
            "vagf":       new_vagf,
            "xgiu":       new_xgiu,
            "prices":     {e["ticker_full"]: e["price"] for e in portfolio_list if e["price"]},
            "bench_px":   prices_bench,
            "weights":    {e["ticker_full"]: e["weight"] for e in portfolio_list},
            "ret_port":   round(ret_port * 100, 4),
            "ret_xeon":   round(ret_xeon * 100, 4),
            "ret_vagf":   round(ret_vagf * 100, 4),
            "ret_xgiu":   round(ret_xgiu * 100, 4),
        }

        if nav_history[-1].get("date") == today_str:
            nav_history[-1] = entry
        else:
            nav_history.append(entry)

        print(f"NAV Bond {prev_nav:.2f} -> {new_nav:.2f} ({ret_port*100:+.3f}%)")
        print(f"   XEON {prev_xeon:.2f} -> {new_xeon:.2f} | VAGF {prev_vagf:.2f} -> {new_vagf:.2f} | XGIU {prev_xgiu:.2f} -> {new_xgiu:.2f}")

    nav_history = nav_history[-500:]
    nav_file.parent.mkdir(parents=True, exist_ok=True)
    with open(nav_file, "w", encoding="utf-8") as f:
        json.dump(nav_history, f, ensure_ascii=False, indent=2)
    print(f"{nav_file.name} — {len(nav_history)} punti")


def dominant(scenarios: dict) -> str:
    return max(scenarios, key=lambda k: scenarios.get(k,0)) if scenarios else "NEUTRO"


# ── CHART DATA: KAMA + SAR + BUY/SELL ────────────────────────────
def compute_chart_data(ticker: str, days: int = 120) -> dict:
    """
    Scarica prezzi storici e calcola KAMA, SAR parabolico, segnali BUY/SELL.
    Ritorna dict con array date/close/kama/sar/signals per il grafico HTML.
    """
    try:
        end   = datetime.now(timezone.utc)
        start = end - timedelta(days=days + 60)  # warm-up extra per KAMA

        # Prova suffissi alternativi
        hist = None
        for suffix in [ticker, ticker.replace(".MI", ".DE"), ticker.replace(".MI", ".L"), ticker.replace(".MI", ".PA")]:
            try:
                h = yf.Ticker(suffix).history(
                    start=start.strftime("%Y-%m-%d"),
                    end=end.strftime("%Y-%m-%d"),
                    auto_adjust=True)
                if len(h) >= 20:
                    hist = h
                    break
            except Exception:
                continue

        if hist is None or len(hist) < 20:
            return {}

        closes = hist["Close"].dropna()
        dates  = [d.strftime("%Y-%m-%d") for d in closes.index]
        prices_arr = [round(float(p), 4) for p in closes]

        # ── KAMA (Kaufman Adaptive Moving Average) ────────────────
        # Parametri: fast=2, slow=30, er_period=10
        n = len(closes)
        fast_sc = 2.0 / (2  + 1)
        slow_sc = 2.0 / (30 + 1)
        er_period = 10
        kama = [None] * n
        kama[0] = prices_arr[0]

        for i in range(1, n):
            if i < er_period:
                kama[i] = kama[i-1]
                continue
            direction = abs(prices_arr[i] - prices_arr[i - er_period])
            volatility = sum(abs(prices_arr[j] - prices_arr[j-1]) for j in range(i - er_period + 1, i + 1))
            er  = direction / volatility if volatility > 0 else 0
            sc  = (er * (fast_sc - slow_sc) + slow_sc) ** 2
            kama[i] = kama[i-1] + sc * (prices_arr[i] - kama[i-1])

        kama_r = [round(k, 4) if k is not None else None for k in kama]

        # ── SAR PARABOLICO ────────────────────────────────────────
        af_step = 0.02
        af_max  = 0.20
        sar  = [None] * n
        bull = True
        af   = af_step
        ep   = prices_arr[0]  # extreme point
        sar[0] = prices_arr[0] * 0.99

        for i in range(1, n):
            prev_sar = sar[i-1]
            if bull:
                sar[i] = prev_sar + af * (ep - prev_sar)
                sar[i] = min(sar[i], prices_arr[i-1], prices_arr[i-2] if i > 1 else prices_arr[i-1])
                if prices_arr[i] < sar[i]:
                    bull  = False
                    sar[i] = ep
                    ep    = prices_arr[i]
                    af    = af_step
                else:
                    if prices_arr[i] > ep:
                        ep = prices_arr[i]
                        af = min(af + af_step, af_max)
            else:
                sar[i] = prev_sar + af * (ep - prev_sar)
                sar[i] = max(sar[i], prices_arr[i-1], prices_arr[i-2] if i > 1 else prices_arr[i-1])
                if prices_arr[i] > sar[i]:
                    bull  = True
                    sar[i] = ep
                    ep    = prices_arr[i]
                    af    = af_step
                else:
                    if prices_arr[i] < ep:
                        ep = prices_arr[i]
                        af = min(af + af_step, af_max)

        sar_r = [round(s, 4) if s is not None else None for s in sar]

        # ── SEGNALI BUY/SELL ──────────────────────────────────────
        signals = []
        for i in range(1, n):
            if kama[i] is None or kama[i-1] is None:
                continue
            # BUY: prezzo attraversa KAMA verso l'alto
            if prices_arr[i] > kama[i] and prices_arr[i-1] <= kama[i-1]:
                signals.append({"i": i, "type": "BUY",  "price": prices_arr[i], "date": dates[i]})
            # SELL: prezzo attraversa KAMA verso il basso
            elif prices_arr[i] < kama[i] and prices_arr[i-1] >= kama[i-1]:
                signals.append({"i": i, "type": "SELL", "price": prices_arr[i], "date": dates[i]})

        # Taglia ai soli ultimi `days` giorni (escluso warm-up)
        cutoff = max(0, n - days)
        return {
            "dates":   dates[cutoff:],
            "close":   prices_arr[cutoff:],
            "kama":    kama_r[cutoff:],
            "sar":     sar_r[cutoff:],
            "signals": [s for s in signals if s["i"] >= cutoff],
        }

    except Exception as e:
        print(f"  ⚠  chart_data {ticker}: {e}")
        return {}
