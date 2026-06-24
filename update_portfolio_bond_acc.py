#!/usr/bin/env python3
"""
RAPTOR BOND ACC — motore portafoglio obbligazionario accumulo
══════════════════════════════════════════════════════════════
Universo: 17 ETF obbligazionari tutti ad accumulazione.
Nessun problema cedole — il momentum su r4w/r12w e' pulito.
Formula: Macro 65% x regime_fit + Momentum 35% x (r4w 50% + r12w 50%)
Vincoli: max 2 EM, max 2 HY, max 1 AGGREGATE, MAX_POSITIONS=7, MIN_W=10%
Benchmark: XEON + VAGF + XGIU (stessi di BOND distribuzione)
Nessun dividend yield (accumulo).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import raptor_common as rc

# ── UNIVERSO BOND ACC (17) ────────────────────────────────────────
UNIVERSE = [
    # ── GOVT IG ───────────────────────────────────────────────────
    {"ticker":"CSBGU7.MI","name":"iShares Global Govt Bond",      "cat":"GOVT_IG",   "risk":0.6,"cur":"USD"},
    {"ticker":"IS0F.DE",  "name":"iShares USD Treasury 1-3Y",     "cat":"GOVT_IG",   "risk":0.4,"cur":"USD"},
    {"ticker":"CSBGE3.MI","name":"iShares Euro Govt 3-7Y",        "cat":"GOVT_IG",   "risk":0.5,"cur":"EUR"},
    {"ticker":"PJSR.MI",  "name":"PIMCO Euro Short Maturity Acc", "cat":"GOVT_IG",   "risk":0.3,"cur":"EUR"},
    {"ticker":"EDMA.DE",  "name":"iShares Italy Govt USD Hed",    "cat":"GOVT_IG",   "risk":0.7,"cur":"USD"},
    {"ticker":"EUNQ.DE",  "name":"iShares Spain Govt USD Hed",    "cat":"GOVT_IG",   "risk":0.6,"cur":"USD"},
    {"ticker":"EUGO.MI",  "name":"PIMCO Adv Euro Govt Bond Acc",  "cat":"GOVT_IG",   "risk":0.6,"cur":"EUR"},
    {"ticker":"GOVB.MI",  "name":"iShares Govt Bond",             "cat":"GOVT_IG",   "risk":0.6,"cur":"EUR"},
    {"ticker":"XGIU.MI",  "name":"iShares Euro Govt Bond",        "cat":"GOVT_IG",   "risk":0.7,"cur":"EUR"},
    {"ticker":"CEMM.DE",  "name":"iShares UK Gilts EUR Hed Acc",  "cat":"GOVT_IG",   "risk":0.6,"cur":"EUR"},
    # ── AGGREGATE ─────────────────────────────────────────────────
    {"ticker":"AGGH.MI",  "name":"iShares Global Aggregate EUR Hed","cat":"AGGREGATE","risk":0.5,"cur":"EUR"},
    # ── CORP IG ───────────────────────────────────────────────────
    {"ticker":"CRPA.MI",  "name":"iShares Global Corporate Bond", "cat":"CORP_IG",   "risk":0.8,"cur":"USD"},
    {"ticker":"IEAA.MI",  "name":"iShares Core EUR Corporate Acc","cat":"CORP_IG",   "risk":0.7,"cur":"EUR"},
    # ── EM BOND ───────────────────────────────────────────────────
    {"ticker":"EMSA.MI",  "name":"iShares JP Morgan Adv USD EM",  "cat":"EM_BOND",   "risk":1.2,"cur":"USD"},
    {"ticker":"EMLB.MI",  "name":"PIMCO Adv EM Local Bond Acc",   "cat":"EM_BOND",   "risk":1.2,"cur":"USD"},
    {"ticker":"AYE8.DE",  "name":"iShares JP Morgan EM CHF Hed",  "cat":"EM_BOND",   "risk":1.1,"cur":"CHF"},
    # ── HY ────────────────────────────────────────────────────────
    {"ticker":"EUHA.MI",  "name":"PIMCO Adv Euro ST HY Acc",      "cat":"HY_EUR",    "risk":1.0,"cur":"EUR"},
    {"ticker":"JCHY.MI",  "name":"JPMorgan Global HY Multi-Factor","cat":"HY_USD",   "risk":1.1,"cur":"USD"},
]

CATS = ["GOVT_IG","AGGREGATE","CORP_IG","EM_BOND","HY_EUR","HY_USD","CASH"]
CAT_LABELS = {
    "GOVT_IG":   "Govt IG",
    "AGGREGATE": "Aggregate",
    "CORP_IG":   "Corp IG",
    "EM_BOND":   "EM Bond",
    "HY_EUR":    "HY EUR",
    "HY_USD":    "HY USD",
    "CASH":      "Cash",
}

# ── VINCOLI ───────────────────────────────────────────────────────
MAX_W = {
    "GOVT_IG":   25,   # singolo strumento, non categoria
    "AGGREGATE": 30,
    "CORP_IG":   25,
    "EM_BOND":   25,
    "HY_EUR":    20,
    "HY_USD":    20,
    "CASH":      60,
}
MIN_W_ACTIVE  = 10
MAX_POSITIONS = 7
MIN_POSITIONS = 4

CRISIS_REGIMES    = {"RISK_OFF","RECESSIONE","PANDEMIC","FINANCIAL","WAR","SOVEREIGN","GEO_SHOCK"}
TIGHTENING_REGIME = {"TIGHTENING"}

# ── REGIME FIT PER CATEGORIA ──────────────────────────────────────
REGIME_FIT = {
    "GOVT_IG": {
        "GOLDILOCKS":0.7,"REFLAZIONE":0.6,"DISINFLAZIONE":1.3,"TIGHTENING":0.4,
        "STAGFLAZIONE":0.7,"RECESSIONE":1.4,"RISK_OFF":1.3,"EUFORIA":0.5,
        "ZIRP":1.2,"GEO_SHOCK":1.2,"PANDEMIC":1.3,"FINANCIAL":1.3,"WAR":1.1,"SOVEREIGN":0.6,
    },
    "AGGREGATE": {
        "GOLDILOCKS":0.9,"REFLAZIONE":0.7,"DISINFLAZIONE":1.1,"TIGHTENING":0.5,
        "STAGFLAZIONE":0.6,"RECESSIONE":1.1,"RISK_OFF":1.0,"EUFORIA":0.8,
        "ZIRP":1.1,"GEO_SHOCK":0.9,"PANDEMIC":1.0,"FINANCIAL":1.0,"WAR":0.9,"SOVEREIGN":0.7,
    },
    "CORP_IG": {
        "GOLDILOCKS":1.1,"REFLAZIONE":0.9,"DISINFLAZIONE":1.0,"TIGHTENING":0.5,
        "STAGFLAZIONE":0.5,"RECESSIONE":0.6,"RISK_OFF":0.5,"EUFORIA":1.2,
        "ZIRP":1.1,"GEO_SHOCK":0.5,"PANDEMIC":0.5,"FINANCIAL":0.4,"WAR":0.6,"SOVEREIGN":0.7,
    },
    "EM_BOND": {
        "GOLDILOCKS":1.0,"REFLAZIONE":1.3,"DISINFLAZIONE":0.9,"TIGHTENING":0.4,
        "STAGFLAZIONE":0.6,"RECESSIONE":0.5,"RISK_OFF":0.3,"EUFORIA":1.1,
        "ZIRP":1.3,"GEO_SHOCK":0.4,"PANDEMIC":0.3,"FINANCIAL":0.3,"WAR":0.4,"SOVEREIGN":0.5,
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
    "CASH": {
        "GOLDILOCKS":0.0,"REFLAZIONE":0.0,"DISINFLAZIONE":0.1,"TIGHTENING":0.8,
        "STAGFLAZIONE":0.8,"RECESSIONE":1.0,"RISK_OFF":1.0,"EUFORIA":0.0,
        "ZIRP":0.0,"GEO_SHOCK":1.0,"PANDEMIC":1.0,"FINANCIAL":1.0,"WAR":1.0,"SOVEREIGN":0.9,
    },
}
REGIME_FIT_DEFAULT = {cat: 0.5 for cat in CATS}

# ── PREFERENZE MACRO PER CATEGORIA ───────────────────────────────
MACRO_PREF = {
    "GOLDILOCKS":    {"GOVT_IG":40,"AGGREGATE":60,"CORP_IG":70,"EM_BOND":65,"HY_EUR":75,"HY_USD":75,"CASH":0},
    "REFLAZIONE":    {"GOVT_IG":30,"AGGREGATE":55,"CORP_IG":60,"EM_BOND":80,"HY_EUR":60,"HY_USD":65,"CASH":0},
    "DISINFLAZIONE": {"GOVT_IG":80,"AGGREGATE":70,"CORP_IG":60,"EM_BOND":50,"HY_EUR":55,"HY_USD":55,"CASH":5},
    "TIGHTENING":    {"GOVT_IG":30,"AGGREGATE":35,"CORP_IG":35,"EM_BOND":25,"HY_EUR":30,"HY_USD":35,"CASH":15},
    "STAGFLAZIONE":  {"GOVT_IG":35,"AGGREGATE":40,"CORP_IG":30,"EM_BOND":30,"HY_EUR":20,"HY_USD":25,"CASH":20},
    "RECESSIONE":    {"GOVT_IG":85,"AGGREGATE":65,"CORP_IG":40,"EM_BOND":20,"HY_EUR":10,"HY_USD":15,"CASH":60},
    "RISK_OFF":      {"GOVT_IG":80,"AGGREGATE":60,"CORP_IG":35,"EM_BOND":15,"HY_EUR":10,"HY_USD":10,"CASH":65},
    "EUFORIA":       {"GOVT_IG":25,"AGGREGATE":55,"CORP_IG":75,"EM_BOND":70,"HY_EUR":85,"HY_USD":85,"CASH":0},
    "ZIRP":          {"GOVT_IG":65,"AGGREGATE":70,"CORP_IG":70,"EM_BOND":80,"HY_EUR":75,"HY_USD":75,"CASH":0},
    "GEO_SHOCK":     {"GOVT_IG":75,"AGGREGATE":55,"CORP_IG":35,"EM_BOND":20,"HY_EUR":10,"HY_USD":15,"CASH":55},
    "PANDEMIC":      {"GOVT_IG":85,"AGGREGATE":60,"CORP_IG":30,"EM_BOND":10,"HY_EUR":5, "HY_USD":5, "CASH":70},
    "FINANCIAL":     {"GOVT_IG":85,"AGGREGATE":55,"CORP_IG":25,"EM_BOND":10,"HY_EUR":5, "HY_USD":5, "CASH":70},
    "WAR":           {"GOVT_IG":75,"AGGREGATE":55,"CORP_IG":30,"EM_BOND":15,"HY_EUR":10,"HY_USD":10,"CASH":60},
    "SOVEREIGN":     {"GOVT_IG":40,"AGGREGATE":50,"CORP_IG":40,"EM_BOND":20,"HY_EUR":15,"HY_USD":15,"CASH":55},
}
MACRO_PREF_DEFAULT = {"GOVT_IG":50,"AGGREGATE":55,"CORP_IG":50,"EM_BOND":40,"HY_EUR":40,"HY_USD":40,"CASH":10}


# ── MACRO SCORE CON REGIME FIT ────────────────────────────────────
def macro_scores(scenarios: dict) -> dict:
    tot_w    = sum(scenarios.values()) or 1
    dominant = max(scenarios, key=lambda k: scenarios.get(k, 0))
    scores   = {}
    for etf in UNIVERSE:
        tk  = etf["ticker"]
        cat = etf["cat"]
        sc  = 0.0
        for code, pct in scenarios.items():
            w  = pct / tot_w
            cp = MACRO_PREF.get(code, MACRO_PREF_DEFAULT).get(cat, 50)
            sc += w * cp
        fit = REGIME_FIT.get(cat, REGIME_FIT_DEFAULT).get(dominant, 0.5)
        scores[tk] = min(100, round(sc * fit))
    return scores


# ── MOMENTUM SCORE (r4w 50% + r12w 50%, no r1w) ──────────────────
def momentum_score_acc(prices: dict) -> dict:
    composites = {}
    for tk, d in prices.items():
        r4  = d.get("r4w")
        r12 = d.get("r12w")
        vals = [v for v in [r4, r12] if v is not None]
        if not vals:
            composites[tk] = None
        elif r4 is not None and r12 is not None:
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


# ── SCORE FINALE ──────────────────────────────────────────────────
def final_scores(macro: dict, mom: dict) -> dict:
    scores = {}
    for etf in UNIVERSE:
        tk = etf["ticker"]
        m  = macro.get(tk, 50)
        mo = mom.get(tk, 50)
        scores[tk] = round(m * 0.65 + mo * 0.35)
    return scores


# ── OTTIMIZZAZIONE PESI ───────────────────────────────────────────
def optimize_weights(scores: dict, prev_weights: dict, scenarios: dict) -> dict:
    etf_map = {e["ticker"]: e for e in UNIVERSE}

    dominant_regime  = max(scenarios, key=lambda k: scenarios.get(k, 0)) if scenarios else ""
    is_crisis        = dominant_regime in CRISIS_REGIMES
    is_tightening    = dominant_regime in TIGHTENING_REGIME
    crisis_intensity = scenarios.get(dominant_regime, 0) / 100 if is_crisis else 0

    # Selezione con vincoli categoria
    HY_CATS   = {"HY_EUR", "HY_USD"}
    EM_CATS   = {"EM_BOND"}
    AGG_CATS  = {"AGGREGATE"}

    candidates = [e for e in UNIVERSE]
    sorted_etf = sorted(
        [(e["ticker"], scores.get(e["ticker"], 0)) for e in candidates],
        key=lambda x: x[1], reverse=True
    )

    selected  = []
    hy_count  = 0
    em_count  = 0
    agg_count = 0

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
        elif cat in AGG_CATS:
            if agg_count >= 1:
                continue
            agg_count += 1
        selected.append(tk)

    # XEON: entra solo in crisi o tightening
    xeon = "XEON.MI"
    if (is_crisis or is_tightening) and xeon not in selected:
        selected = selected[:-1] + [xeon]
        # Aggiungi XEON all'etf_map se non presente
        if xeon not in etf_map:
            etf_map[xeon] = {"ticker": xeon, "name": "Xtrackers EUR Overnight", "cat": "CASH", "risk": 0.0, "cur": "EUR"}

    raw = {}
    for tk in selected:
        e    = etf_map[tk]
        sc   = scores.get(tk, 50)
        risk = e["risk"]
        if e["cat"] == "CASH":
            raw[tk] = max(sc, 1)
        else:
            raw[tk] = max(sc / max(risk, 0.1), 1)

    tot     = sum(raw.values())
    weights = {tk: raw[tk] / tot * 100 for tk in selected}

    if is_crisis and xeon in weights:
        boost         = crisis_intensity * 60
        weights[xeon] = min(60, weights.get(xeon, 0) + boost)
        others        = {tk: w for tk, w in weights.items() if tk != xeon}
        tot_others    = sum(others.values())
        remaining     = 100 - weights[xeon]
        if tot_others > 0:
            weights.update({tk: w / tot_others * remaining for tk, w in others.items()})
    elif is_tightening and xeon in weights:
        weights[xeon] = min(15, weights.get(xeon, 0))
        others        = {tk: w for tk, w in weights.items() if tk != xeon}
        tot_others    = sum(others.values())
        remaining     = 100 - weights[xeon]
        if tot_others > 0:
            weights.update({tk: w / tot_others * remaining for tk, w in others.items()})

    def apply_constraints(w: dict) -> dict:
        for tk in list(w.keys()):
            cat  = etf_map[tk]["cat"]
            wmax = MAX_W.get(cat, 25)
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
    PF_OUT   = BASE / "data" / "portfolio_bond_acc.json"
    NAV_FILE = BASE / "nav_history_bond_acc.json"

    print("="*60)
    print(f"RAPTOR BOND ACC — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
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

    print("\nDownload prezzi Bond ACC...")
    tickers = [e["ticker"] for e in UNIVERSE]
    prices  = rc.fetch_prices(tickers)

    print("\nDownload benchmark (VAGF, XEON, XGIU)...")
    prices_bench = rc.fetch_benchmark_prices(["VAGF.MI"])
    if "XEON.MI" in prices and prices["XEON.MI"].get("p"):
        prices_bench["XEON.MI"] = prices["XEON.MI"]["p"]
    if "XGIU.MI" in prices and prices["XGIU.MI"].get("p"):
        prices_bench["XGIU.MI"] = prices["XGIU.MI"]["p"]

    print("\nCalcolo scores...")
    m_sc  = macro_scores(scenarios)
    mo_sc = momentum_score_acc(prices)
    f_sc  = final_scores(m_sc, mo_sc)

    print("\nOttimizzazione pesi...")
    weights = optimize_weights(f_sc, prev_weights, scenarios)

    signal, reason = rc.rebalance_signal(weights, prev_weights, prev_regime, curr_regime)
    print(f"\nSegnale: {signal} — {reason}")

    etf_map = {e["ticker"]: e for e in UNIVERSE}
    etf_map["XEON.MI"] = {"ticker":"XEON.MI","name":"Xtrackers EUR Overnight","cat":"CASH","risk":0.0,"cur":"EUR"}

    portfolio_list = []
    for tk, w in sorted(weights.items(), key=lambda x: x[1], reverse=True):
        e   = etf_map[tk]
        pd_ = prices.get(tk, {})
        portfolio_list.append({
            "ticker":         tk.replace(".MI","").replace(".DE",""),
            "ticker_full":    tk,
            "name":           e["name"],
            "cat":            e["cat"],
            "risk_factor":    e["risk"],
            "currency":       e["cur"],
            "weight":         w,
            "weight_prev":    prev_weights.get(tk, 0),
            "weight_delta":   w - prev_weights.get(tk, 0),
            "macro_score":    m_sc.get(tk, 50),
            "momentum_score": mo_sc.get(tk, 50),
            "final_score":    f_sc.get(tk, 50),
            "price":          pd_.get("p"),
            "ret_4w":         round(pd_.get("r4w") or 0, 2),
            "ret_12w":        round(pd_.get("r12w") or 0, 2),
        })

    macro_bd = {}
    for cat in CATS:
        v = sum(e["weight"] for e in portfolio_list if e["cat"]==cat)
        if v: macro_bd[cat] = v

    week_entry = {
        "date":             today_str,
        "regime":           curr_regime,
        "regime_prob":      curr_prob,
        "regime_probs":     {k:v for k,v in scenarios.items() if v>0},
        "rebalance":        signal,
        "rebalance_reason": reason,
        "portfolio":        portfolio_list,
        "macro_breakdown":  macro_bd,
        "generated_at":     datetime.now(timezone.utc).isoformat(),
    }

    print("\nPORTAFOGLIO BOND ACC:")
    print(f"   {'Ticker':<12} {'Nome':<32} {'Cat':<10} {'Peso':>5}  {'Delta':>5}  {'Score':>5}")
    print(f"   {'-'*78}")
    for e in portfolio_list:
        delta_str = f"{e['weight_delta']:+.0f}%" if e['weight_prev'] else " NEW"
        print(f"   {e['ticker']:<12} {e['name']:<32} {e['cat']:<10} {e['weight']:>4}%  {delta_str:>5}  {e['final_score']:>5}")
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

    print("\nAggiornamento NAV Bond ACC...")
    rc.update_nav_history_bond(NAV_FILE, portfolio_list, prices_bench, today_str)

if __name__ == "__main__":
    run()
