#!/usr/bin/env python3
"""
RAPTOR BOND — motore portafoglio obbligazionario
══════════════════════════════════════════════════
Universo: 12 strumenti obbligazionari + XEON come rifugio.
Formula: Macro 65% x regime_fit + Momentum 35% x (r4w 50% + r12w 50%)
Nessun momentum geografico (non rilevante per bond).
Dividend yield calcolato da Ticker.dividends ultimi 12 mesi.
Benchmark: XEON + VAGF + XGIU (gia' nell'universo, zero costo aggiuntivo).

Riusa fetch_prices, fetch_benchmark_prices, update_nav_history, rebalance_signal
dal modulo condiviso raptor_common.py.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import raptor_common as rc

try:
    import yfinance as yf
except ImportError:
    import os; os.system("pip install yfinance --break-system-packages -q")
    import yfinance as yf

# ── UNIVERSO BOND (12 + XEON) ─────────────────────────────────────
UNIVERSE = [
    {"ticker":"PJS1.MI",  "name":"PIMCO Euro Short Mat",    "cat":"GOVT_IG",  "risk":0.5, "cur":"EUR", "cedola":"mensile"},
    {"ticker":"XGIU.MI",  "name":"iShares Euro Govt Bond",  "cat":"GOVT_IG",  "risk":0.7, "cur":"EUR", "cedola":"trimestrale"},
    {"ticker":"STHY.MI",  "name":"PIMCO US HY USD",         "cat":"HY_USD",   "risk":1.0, "cur":"USD", "cedola":"mensile"},
    {"ticker":"STHE.MI",  "name":"PIMCO US HY EUR Hed",     "cat":"HY_USD",   "risk":1.0, "cur":"EUR", "cedola":"mensile"},
    {"ticker":"EUHI.MI",  "name":"PIMCO Euro HY",           "cat":"HY_EUR",   "risk":1.0, "cur":"EUR", "cedola":"mensile"},
    {"ticker":"IHYG.MI",  "name":"iShares Euro HY Corp",    "cat":"HY_EUR",   "risk":1.0, "cur":"EUR", "cedola":"trimestrale"},
    {"ticker":"EMLI.MI",  "name":"PIMCO EM Local Bond",     "cat":"EM_BOND",  "risk":1.2, "cur":"USD", "cedola":"mensile"},
    {"ticker":"SEML.MI",  "name":"iShares EM Local Govt",   "cat":"EM_BOND",  "risk":1.2, "cur":"USD", "cedola":"trimestrale"},
    {"ticker":"IEMB.MI",  "name":"iShares JP Morgan EM",    "cat":"EM_BOND",  "risk":1.2, "cur":"USD", "cedola":"trimestrale"},
    {"ticker":"XAT1.MI",  "name":"Invesco AT1 CoCo Bond",   "cat":"AT1",      "risk":1.5, "cur":"EUR", "cedola":"trimestrale"},
    {"ticker":"XEON.MI",  "name":"Xtrackers EUR Overnight", "cat":"CASH",     "risk":0.0, "cur":"EUR", "cedola":"accumulo"},
]

CATS = ["GOVT_IG","HY_USD","HY_EUR","EM_BOND","AT1","CASH"]
CAT_LABELS = {
    "GOVT_IG": "Govt IG",
    "HY_USD":  "HY USD",
    "HY_EUR":  "HY EUR",
    "EM_BOND": "EM Bond",
    "AT1":     "AT1/CoCo",
    "CASH":    "Cash",
}

# ── VINCOLI ───────────────────────────────────────────────────────
MAX_W = {
    "GOVT_IG": 40,
    "HY_USD":  35,
    "HY_EUR":  35,
    "EM_BOND": 30,
    "AT1":     20,
    "CASH":    60,   # crisi; in tightening max 15%
}
MIN_W_ACTIVE  = 10
MAX_POSITIONS = 7
MIN_POSITIONS = 4

CRISIS_REGIMES    = {"RISK_OFF","RECESSIONE","PANDEMIC","FINANCIAL","WAR","SOVEREIGN","GEO_SHOCK"}
TIGHTENING_REGIME = {"TIGHTENING"}

# ── REGIME FIT PER CATEGORIA ──────────────────────────────────────
# Moltiplicatore 0.1-1.5 applicato al macro score
REGIME_FIT = {
    "GOVT_IG": {
        "GOLDILOCKS":0.7,"REFLAZIONE":0.6,"DISINFLAZIONE":1.3,"TIGHTENING":0.4,
        "STAGFLAZIONE":0.7,"RECESSIONE":1.4,"RISK_OFF":1.3,"EUFORIA":0.5,
        "ZIRP":1.2,"GEO_SHOCK":1.2,"PANDEMIC":1.3,"FINANCIAL":1.3,"WAR":1.1,"SOVEREIGN":0.6,
    },
    "HY_EUR": {
        "GOLDILOCKS":1.3,"REFLAZIONE":1.1,"DISINFLAZIONE":1.0,"TIGHTENING":0.5,
        "STAGFLAZIONE":0.4,"RECESSIONE":0.3,"RISK_OFF":0.2,"EUFORIA":1.4,
        "ZIRP":1.2,"GEO_SHOCK":0.3,"PANDEMIC":0.2,"FINANCIAL":0.2,"WAR":0.3,"SOVEREIGN":0.4,
    },
    "HY_USD": {
        "GOLDILOCKS":1.2,"REFLAZIONE":1.0,"DISINFLAZIONE":1.0,"TIGHTENING":0.5,
        "STAGFLAZIONE":0.4,"RECESSIONE":0.3,"RISK_OFF":0.2,"EUFORIA":1.3,
        "ZIRP":1.1,"GEO_SHOCK":0.3,"PANDEMIC":0.2,"FINANCIAL":0.2,"WAR":0.3,"SOVEREIGN":0.4,
    },
    "EM_BOND": {
        "GOLDILOCKS":1.0,"REFLAZIONE":1.3,"DISINFLAZIONE":0.9,"TIGHTENING":0.4,
        "STAGFLAZIONE":0.6,"RECESSIONE":0.5,"RISK_OFF":0.3,"EUFORIA":1.1,
        "ZIRP":1.3,"GEO_SHOCK":0.4,"PANDEMIC":0.3,"FINANCIAL":0.3,"WAR":0.4,"SOVEREIGN":0.5,
    },
    "AT1": {
        "GOLDILOCKS":1.3,"REFLAZIONE":1.0,"DISINFLAZIONE":0.9,"TIGHTENING":0.6,
        "STAGFLAZIONE":0.3,"RECESSIONE":0.2,"RISK_OFF":0.1,"EUFORIA":1.4,
        "ZIRP":1.1,"GEO_SHOCK":0.2,"PANDEMIC":0.1,"FINANCIAL":0.1,"WAR":0.2,"SOVEREIGN":0.3,
    },
    "CASH": {
        "GOLDILOCKS":0.0,"REFLAZIONE":0.0,"DISINFLAZIONE":0.1,"TIGHTENING":0.8,
        "STAGFLAZIONE":0.8,"RECESSIONE":1.0,"RISK_OFF":1.0,"EUFORIA":0.0,
        "ZIRP":0.0,"GEO_SHOCK":1.0,"PANDEMIC":1.0,"FINANCIAL":1.0,"WAR":1.0,"SOVEREIGN":0.9,
    },
}
REGIME_FIT_DEFAULT = {cat: 0.5 for cat in CATS}

# ── PREFERENZE MACRO PER CATEGORIA ───────────────────────────────
MACRO_PREF = {
    "GOLDILOCKS":    {"GOVT_IG":40,"HY_USD":75,"HY_EUR":75,"EM_BOND":65,"AT1":70,"CASH":0},
    "REFLAZIONE":    {"GOVT_IG":30,"HY_USD":65,"HY_EUR":60,"EM_BOND":80,"AT1":60,"CASH":0},
    "DISINFLAZIONE": {"GOVT_IG":80,"HY_USD":55,"HY_EUR":55,"EM_BOND":50,"AT1":45,"CASH":5},
    "TIGHTENING":    {"GOVT_IG":30,"HY_USD":35,"HY_EUR":30,"EM_BOND":25,"AT1":40,"CASH":15},
    "STAGFLAZIONE":  {"GOVT_IG":35,"HY_USD":25,"HY_EUR":20,"EM_BOND":30,"AT1":15,"CASH":20},
    "RECESSIONE":    {"GOVT_IG":85,"HY_USD":15,"HY_EUR":10,"EM_BOND":20,"AT1":5,"CASH":60},
    "RISK_OFF":      {"GOVT_IG":80,"HY_USD":10,"HY_EUR":10,"EM_BOND":15,"AT1":5,"CASH":65},
    "EUFORIA":       {"GOVT_IG":25,"HY_USD":85,"HY_EUR":85,"EM_BOND":70,"AT1":80,"CASH":0},
    "ZIRP":          {"GOVT_IG":65,"HY_USD":75,"HY_EUR":75,"EM_BOND":80,"AT1":70,"CASH":0},
    "GEO_SHOCK":     {"GOVT_IG":75,"HY_USD":15,"HY_EUR":10,"EM_BOND":20,"AT1":10,"CASH":55},
    "PANDEMIC":      {"GOVT_IG":85,"HY_USD":5, "HY_EUR":5, "EM_BOND":10,"AT1":5,"CASH":70},
    "FINANCIAL":     {"GOVT_IG":85,"HY_USD":5, "HY_EUR":5, "EM_BOND":10,"AT1":0,"CASH":70},
    "WAR":           {"GOVT_IG":75,"HY_USD":10,"HY_EUR":10,"EM_BOND":15,"AT1":5,"CASH":60},
    "SOVEREIGN":     {"GOVT_IG":40,"HY_USD":15,"HY_EUR":15,"EM_BOND":20,"AT1":10,"CASH":55},
}
MACRO_PREF_DEFAULT = {"GOVT_IG":50,"HY_USD":40,"HY_EUR":40,"EM_BOND":40,"AT1":35,"CASH":10}


# ── MACRO SCORE CON REGIME FIT ────────────────────────────────────
def macro_scores(scenarios: dict) -> dict:
    """Calcola macro score pesato per scenario, moltiplicato per regime_fit della categoria."""
    tot_w = sum(scenarios.values()) or 1
    dominant = max(scenarios, key=lambda k: scenarios.get(k, 0))

    scores = {}
    for etf in UNIVERSE:
        tk  = etf["ticker"]
        cat = etf["cat"]
        sc  = 0.0
        for code, pct in scenarios.items():
            w  = pct / tot_w
            cp = MACRO_PREF.get(code, MACRO_PREF_DEFAULT).get(cat, 50)
            sc += w * cp

        # Applica regime_fit del regime dominante
        fit = REGIME_FIT.get(cat, REGIME_FIT_DEFAULT).get(dominant, 0.5)
        scores[tk] = min(100, round(sc * fit))
    return scores


# ── MOMENTUM SCORE (solo r4w + r12w, no r1w per bond) ─────────────
def momentum_score_bond(prices: dict) -> dict:
    """
    Momentum bond: usa r4w (50%) e r12w (50%).
    Esclude r1w perche' su bond a cedola mensile e' troppo rumoroso.
    """
    composites = {}
    for tk, d in prices.items():
        r4  = d.get("r4w")
        r12 = d.get("r12w")
        vals = [v for v in [r4, r12] if v is not None]
        if not vals:
            composites[tk] = None
            continue
        if r4 is not None and r12 is not None:
            composites[tk] = r4 * 0.5 + r12 * 0.5
        elif r4 is not None:
            composites[tk] = r4
        else:
            composites[tk] = r12

    known = {tk: v for tk, v in composites.items() if v is not None}
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


# ── SCORE FINALE (Macro 65% + Momentum 35%) ──────────────────────
def final_scores(macro: dict, mom: dict) -> dict:
    scores = {}
    for etf in UNIVERSE:
        tk = etf["ticker"]
        m  = macro.get(tk, 50)
        mo = mom.get(tk, 50)
        scores[tk] = round(m * 0.65 + mo * 0.35)
    return scores


# ── DIVIDEND YIELD ────────────────────────────────────────────────
def fetch_dividend_yields(universe: list, prices: dict) -> dict:
    """
    Calcola dividend yield annualizzato: dividendi ultimi 12 mesi / prezzo corrente.
    Fallback a None se dati non disponibili (ETF accumulo o dati mancanti).
    """
    yields = {}
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=370)  # 12 mesi + margine

    for etf in universe:
        tk = etf["ticker"]
        # XEON e EUHA sono accumulo — nessuna cedola
        if etf["cedola"] == "accumulo":
            yields[tk] = None
            continue
        try:
            divs = yf.Ticker(tk).dividends
            if divs is None or len(divs) == 0:
                yields[tk] = None
                continue
            # Filtra ultimi 12 mesi
            cutoff = (end - timedelta(days=365)).replace(tzinfo=None)
            try:
                recent = divs[divs.index >= cutoff]
            except Exception:
                recent = divs.iloc[-4:] if len(divs) >= 4 else divs
            annual_div = float(recent.sum()) if len(recent) > 0 else 0.0
            px = prices.get(tk, {}).get("p")
            if px and px > 0 and annual_div > 0:
                yields[tk] = round(annual_div / px * 100, 2)
            else:
                yields[tk] = None
        except Exception:
            yields[tk] = None

    return yields


# ── OTTIMIZZAZIONE PESI ───────────────────────────────────────────
def optimize_weights(scores: dict, prev_weights: dict, scenarios: dict) -> dict:
    etf_map = {e["ticker"]: e for e in UNIVERSE}

    dominant_regime = max(scenarios, key=lambda k: scenarios.get(k, 0)) if scenarios else ""
    is_crisis       = dominant_regime in CRISIS_REGIMES
    is_tightening   = dominant_regime in TIGHTENING_REGIME
    crisis_intensity = scenarios.get(dominant_regime, 0) / 100 if is_crisis else 0

    # XEON: solo in crisi o tightening
    candidates = [e for e in UNIVERSE if e["cat"] != "CASH"]
    sorted_etf = sorted(
        [(e["ticker"], scores[e["ticker"]]) for e in candidates],
        key=lambda x: x[1], reverse=True
    )

    # Applica vincoli max 2 HY e max 2 EM prima della selezione
    HY_CATS = {"HY_EUR", "HY_USD"}
    EM_CATS = {"EM_BOND"}
    selected = []
    hy_count = 0
    em_count = 0
    for tk, sc in sorted_etf:
        if len(selected) >= MAX_POSITIONS:
            break
        cat = etf_map[tk]["cat"]
        if cat in HY_CATS:
            if hy_count >= 2:
                continue
            hy_count += 1
        elif cat in EM_CATS:
            if em_count >= 2:
                continue
            em_count += 1
        selected.append(tk)

    xeon = "XEON.MI"
    if is_crisis or is_tightening:
        if xeon not in selected:
            selected = selected[:-1] + [xeon]

    raw = {}
    for tk in selected:
        e    = etf_map[tk]
        sc   = scores[tk]
        risk = e["risk"]
        if e["cat"] == "CASH":
            raw[tk] = max(sc, 1)
        else:
            raw[tk] = max(sc / max(risk, 0.1), 1)

    tot     = sum(raw.values())
    weights = {tk: raw[tk] / tot * 100 for tk in selected}

    # Boost XEON in crisi
    if is_crisis and xeon in weights:
        boost = crisis_intensity * MAX_W["CASH"]
        weights[xeon] = min(MAX_W["CASH"], weights.get(xeon, 0) + boost)
        others     = {tk: w for tk, w in weights.items() if tk != xeon}
        tot_others = sum(others.values())
        remaining  = 100 - weights[xeon]
        if tot_others > 0:
            weights.update({tk: w / tot_others * remaining for tk, w in others.items()})
    # In tightening: XEON max 15%
    elif is_tightening and xeon in weights:
        weights[xeon] = min(15, weights.get(xeon, 0))
        others     = {tk: w for tk, w in weights.items() if tk != xeon}
        tot_others = sum(others.values())
        remaining  = 100 - weights[xeon]
        if tot_others > 0:
            weights.update({tk: w / tot_others * remaining for tk, w in others.items()})

    def apply_constraints(w: dict) -> dict:
        for tk in list(w.keys()):
            cat  = etf_map[tk]["cat"]
            wmax = MAX_W.get(cat, 30)
            w[tk] = max(MIN_W_ACTIVE, min(wmax, w[tk]))
        s = sum(w.values())
        return {tk: v / s * 100 for tk, v in w.items()}

    for _ in range(4):
        weights = apply_constraints(weights)

    rounded = {tk: int(v) for tk, v in weights.items()}
    diff    = 100 - sum(rounded.values())
    if diff != 0:
        keys = sorted(rounded, key=lambda k: weights[k], reverse=True)
        for i in range(abs(diff)):
            rounded[keys[i % len(keys)]] += 1 if diff > 0 else -1

    return {tk: w for tk, w in rounded.items() if w > 0}


# ── MAIN ──────────────────────────────────────────────────────────
def run():
    BASE     = Path(__file__).parent
    LATEST   = BASE / "data" / "latest.json"
    PF_OUT   = BASE / "data" / "portfolio_bond.json"
    NAV_FILE = BASE / "nav_history_bond.json"

    print("="*60)
    print(f"RAPTOR BOND — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*60)

    with open(LATEST, encoding="utf-8") as f:
        latest = json.load(f)
    sw = latest.get("scenario_weights", [])
    if not sw:
        print("scenario_weights vuoto"); return

    current     = sw[-1]
    scenarios   = current.get("scenarios", {})
    curr_regime = rc.dominant(scenarios)
    curr_prob   = scenarios.get(curr_regime, 0)
    today_str   = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"Regime: {curr_regime} ({curr_prob}%)")

    history      = []
    prev_weights = {}
    prev_regime  = ""
    if PF_OUT.exists():
        try:
            with open(PF_OUT, encoding="utf-8") as f:
                pf_data = json.load(f)
            history = pf_data.get("history", [])
            if history:
                prev_week    = history[0]
                prev_weights = {e["ticker_full"]: e["weight"] for e in prev_week.get("portfolio",[])}
                prev_regime  = prev_week.get("regime","")
            print(f"Storico: {len(history)} settimane")
        except Exception as e:
            print(f"Errore storico: {e}")

    print("\nDownload prezzi bond...")
    tickers = [e["ticker"] for e in UNIVERSE]
    prices  = rc.fetch_prices(tickers)

    print("\nDownload benchmark (XEON, VAGF, XGIU)...")
    # XEON e XGIU sono gia' nell'universo, VAGF e' il solo aggiuntivo
    prices_bench = rc.fetch_benchmark_prices(["VAGF.MI"])
    # Aggiungi XEON e XGIU dai prezzi universo gia' scaricati
    if "XEON.MI" in prices and prices["XEON.MI"].get("p"):
        prices_bench["XEON.MI"] = prices["XEON.MI"]["p"]
    if "XGIU.MI" in prices and prices["XGIU.MI"].get("p"):
        prices_bench["XGIU.MI"] = prices["XGIU.MI"]["p"]

    print("\nCalcolo dividend yields...")
    div_yields = fetch_dividend_yields(UNIVERSE, prices)
    for tk, y in div_yields.items():
        if y:
            print(f"  {tk}: yield {y:.2f}%")

    print("\nCalcolo chart data (KAMA + SAR)...")
    chart_data = {}
    for etf in UNIVERSE:
        tk = etf["ticker"]
        print(f"  → {tk}")
        chart_data[tk] = rc.compute_chart_data(tk, days=120)

    print("\nCalcolo scores...")
    m_sc  = macro_scores(scenarios)
    mo_sc = momentum_score_bond(prices)
    f_sc  = final_scores(m_sc, mo_sc)

    print("\nOttimizzazione pesi...")
    weights = optimize_weights(f_sc, prev_weights, scenarios)

    signal, reason = rc.rebalance_signal(weights, prev_weights, prev_regime, curr_regime)
    print(f"\nSegnale: {signal} — {reason}")

    etf_map = {e["ticker"]: e for e in UNIVERSE}
    portfolio_list = []
    for tk, w in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        e   = etf_map[tk]
        pd_ = prices.get(tk, {})
        portfolio_list.append({
            "ticker":         tk.replace(".MI",""),
            "ticker_full":    tk,
            "name":           e["name"],
            "cat":            e["cat"],
            "risk_factor":    e["risk"],
            "currency":       e["cur"],
            "cedola":         e["cedola"],
            "weight":         w,
            "weight_prev":    prev_weights.get(tk, 0),
            "weight_delta":   w - prev_weights.get(tk, 0),
            "macro_score":    m_sc.get(tk, 50),
            "momentum_score": mo_sc.get(tk, 50),
            "final_score":    f_sc.get(tk, 50),
            "div_yield":      div_yields.get(tk),
            "price":          pd_.get("p"),
            "ret_4w":         round(pd_.get("r4w") or 0, 2),
            "ret_12w":        round(pd_.get("r12w") or 0, 2),
            "chart":          chart_data.get(tk, {}),
        })

    macro_bd = {}
    for cat in CATS:
        v = sum(e["weight"] for e in portfolio_list if e["cat"]==cat)
        if v: macro_bd[cat] = v

    # Yield medio ponderato portafoglio
    weighted_yield = 0.0
    for e in portfolio_list:
        if e["div_yield"] and e["div_yield"] > 0:
            weighted_yield += e["weight"] / 100 * e["div_yield"]
    weighted_yield = round(weighted_yield, 2) if weighted_yield > 0 else None

    week_entry = {
        "date":             today_str,
        "regime":           curr_regime,
        "regime_prob":      curr_prob,
        "regime_probs":     {k:v for k,v in scenarios.items() if v>0},
        "rebalance":        signal,
        "rebalance_reason": reason,
        "portfolio":        portfolio_list,
        "macro_breakdown":  macro_bd,
        "weighted_yield":   weighted_yield,
        "generated_at":     datetime.now(timezone.utc).isoformat(),
    }

    print("\nPORTAFOGLIO BOND:")
    print(f"   {'Ticker':<10} {'Nome':<28} {'Cat':<10} {'Peso':>5}  {'Delta':>5}  {'Score':>5}  {'Yield':>6}")
    print(f"   {'-'*80}")
    for e in portfolio_list:
        delta_str = f"{e['weight_delta']:+.0f}%" if e['weight_prev'] else " NEW"
        yield_str = f"{e['div_yield']:.1f}%" if e['div_yield'] else "n.d."
        print(f"   {e['ticker']:<10} {e['name']:<28} {e['cat']:<10} {e['weight']:>4}%  {delta_str:>5}  {e['final_score']:>5}  {yield_str:>6}")
    if weighted_yield:
        print(f"\n   Yield medio ponderato: {weighted_yield:.2f}%")
    print(f"\n   BREAKDOWN: " + " | ".join(f"{k}: {v}%" for k,v in macro_bd.items()))

    idx = next((i for i,h in enumerate(history) if h.get("date")==today_str), None)
    if idx is not None:
        history[idx] = week_entry
    else:
        history.insert(0, week_entry)
    history = history[:52]

    PF_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(PF_OUT, "w", encoding="utf-8") as f:
        json.dump({"history": history}, f, ensure_ascii=False, indent=2)
    print(f"\nSalvato {PF_OUT} ({len(history)} settimane)")

    print("\nAggiornamento NAV Bond...")
    rc.update_nav_history_bond(NAV_FILE, portfolio_list, prices_bench, today_str)

if __name__ == "__main__":
    run()
