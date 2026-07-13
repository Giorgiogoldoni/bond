#!/usr/bin/env python3
"""
BOND_UNIVERSE — modulo condiviso con gli universi ETF di tutte le 4 linee RAPTOR BOND.
════════════════════════════════════════════════════════════════════════════════════
Fonte unica di verita' per ticker, categorie, vincoli e regime-fit.
Usato da: update_portfolio_bond.py, update_portfolio_bond_acc.py,
          update_bond_antonacci.py, update_bond_faber.py, backtest_all.py.

Prima di questo modulo, bond.py e bond_acc.py duplicavano ~350 righe su 500
con rischio di disallineamento ad ogni modifica. Ora ogni linea importa da qui.
"""

# ════════════════════════════════════════════════════════════════════════
# LINEA 1 — BOND DISTRIBUZIONE (12 strumenti + XEON)
# ════════════════════════════════════════════════════════════════════════
BOND_DIST_UNIVERSE = [
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
BOND_DIST_CATS = ["GOVT_IG","HY_USD","HY_EUR","EM_BOND","AT1","CASH"]
BOND_DIST_CAT_LABELS = {
    "GOVT_IG": "Govt IG", "HY_USD": "HY USD", "HY_EUR": "HY EUR",
    "EM_BOND": "EM Bond", "AT1": "AT1/CoCo", "CASH": "Cash",
}
BOND_DIST_MAX_W = {"GOVT_IG":40, "HY_USD":35, "HY_EUR":35, "EM_BOND":30, "AT1":20, "CASH":60}
BOND_DIST_MIN_W_ACTIVE  = 10
BOND_DIST_MAX_POSITIONS = 7
BOND_DIST_MIN_POSITIONS = 4
BOND_DIST_REGIME_FIT = {
    "GOVT_IG": {"GOLDILOCKS":0.7,"REFLAZIONE":0.6,"DISINFLAZIONE":1.3,"TIGHTENING":0.4,
                "STAGFLAZIONE":0.7,"RECESSIONE":1.4,"RISK_OFF":1.3,"EUFORIA":0.5,
                "ZIRP":1.2,"GEO_SHOCK":1.2,"PANDEMIC":1.3,"FINANCIAL":1.3,"WAR":1.1,"SOVEREIGN":0.6},
    "HY_EUR": {"GOLDILOCKS":1.3,"REFLAZIONE":1.1,"DISINFLAZIONE":1.0,"TIGHTENING":0.5,
               "STAGFLAZIONE":0.4,"RECESSIONE":0.3,"RISK_OFF":0.2,"EUFORIA":1.4,
               "ZIRP":1.2,"GEO_SHOCK":0.3,"PANDEMIC":0.2,"FINANCIAL":0.2,"WAR":0.3,"SOVEREIGN":0.4},
    "HY_USD": {"GOLDILOCKS":1.2,"REFLAZIONE":1.0,"DISINFLAZIONE":1.0,"TIGHTENING":0.5,
               "STAGFLAZIONE":0.4,"RECESSIONE":0.3,"RISK_OFF":0.2,"EUFORIA":1.3,
               "ZIRP":1.1,"GEO_SHOCK":0.3,"PANDEMIC":0.2,"FINANCIAL":0.2,"WAR":0.3,"SOVEREIGN":0.4},
    "EM_BOND": {"GOLDILOCKS":1.0,"REFLAZIONE":1.3,"DISINFLAZIONE":0.9,"TIGHTENING":0.4,
                "STAGFLAZIONE":0.6,"RECESSIONE":0.5,"RISK_OFF":0.3,"EUFORIA":1.1,
                "ZIRP":1.3,"GEO_SHOCK":0.4,"PANDEMIC":0.3,"FINANCIAL":0.3,"WAR":0.4,"SOVEREIGN":0.5},
    "AT1": {"GOLDILOCKS":1.3,"REFLAZIONE":1.0,"DISINFLAZIONE":0.9,"TIGHTENING":0.6,
            "STAGFLAZIONE":0.3,"RECESSIONE":0.2,"RISK_OFF":0.1,"EUFORIA":1.4,
            "ZIRP":1.1,"GEO_SHOCK":0.2,"PANDEMIC":0.1,"FINANCIAL":0.1,"WAR":0.2,"SOVEREIGN":0.3},
    "CASH": {"GOLDILOCKS":0.0,"REFLAZIONE":0.0,"DISINFLAZIONE":0.1,"TIGHTENING":0.8,
             "STAGFLAZIONE":0.8,"RECESSIONE":1.0,"RISK_OFF":1.0,"EUFORIA":0.0,
             "ZIRP":0.0,"GEO_SHOCK":1.0,"PANDEMIC":1.0,"FINANCIAL":1.0,"WAR":1.0,"SOVEREIGN":0.9},
}
BOND_DIST_MACRO_PREF = {
    "GOLDILOCKS":    {"GOVT_IG":40,"HY_USD":75,"HY_EUR":75,"EM_BOND":65,"AT1":70,"CASH":0},
    "REFLAZIONE":    {"GOVT_IG":30,"HY_USD":65,"HY_EUR":60,"EM_BOND":80,"AT1":60,"CASH":0},
    "DISINFLAZIONE": {"GOVT_IG":80,"HY_USD":55,"HY_EUR":55,"EM_BOND":50,"AT1":45,"CASH":5},
    "TIGHTENING":    {"GOVT_IG":30,"HY_USD":35,"HY_EUR":30,"EM_BOND":25,"AT1":40,"CASH":15},
    "STAGFLAZIONE":  {"GOVT_IG":35,"HY_USD":25,"HY_EUR":20,"EM_BOND":30,"AT1":15,"CASH":20},
    "RECESSIONE":    {"GOVT_IG":85,"HY_USD":15,"HY_EUR":10,"EM_BOND":20,"AT1":5, "CASH":60},
    "RISK_OFF":      {"GOVT_IG":80,"HY_USD":10,"HY_EUR":10,"EM_BOND":15,"AT1":5, "CASH":65},
    "EUFORIA":       {"GOVT_IG":25,"HY_USD":85,"HY_EUR":85,"EM_BOND":70,"AT1":80,"CASH":0},
    "ZIRP":          {"GOVT_IG":65,"HY_USD":75,"HY_EUR":75,"EM_BOND":80,"AT1":70,"CASH":0},
    "GEO_SHOCK":     {"GOVT_IG":75,"HY_USD":15,"HY_EUR":10,"EM_BOND":20,"AT1":10,"CASH":55},
    "PANDEMIC":      {"GOVT_IG":85,"HY_USD":5, "HY_EUR":5, "EM_BOND":10,"AT1":5, "CASH":70},
    "FINANCIAL":     {"GOVT_IG":85,"HY_USD":5, "HY_EUR":5, "EM_BOND":10,"AT1":0, "CASH":70},
    "WAR":           {"GOVT_IG":75,"HY_USD":10,"HY_EUR":10,"EM_BOND":15,"AT1":5, "CASH":60},
    "SOVEREIGN":     {"GOVT_IG":40,"HY_USD":15,"HY_EUR":15,"EM_BOND":20,"AT1":10,"CASH":55},
}
BOND_DIST_MACRO_PREF_DEFAULT = {"GOVT_IG":50,"HY_USD":40,"HY_EUR":40,"EM_BOND":40,"AT1":35,"CASH":10}

# ════════════════════════════════════════════════════════════════════════
# LINEA 2 — BOND ACCUMULO (17 strumenti)
# ════════════════════════════════════════════════════════════════════════
BOND_ACC_UNIVERSE = [
    {"ticker":"CSBGU7.MI","name":"iShares Global Govt Bond",       "cat":"GOVT_IG",   "risk":0.6,"cur":"USD"},
    {"ticker":"IS0F.DE",  "name":"iShares USD Treasury 1-3Y",      "cat":"GOVT_IG",   "risk":0.4,"cur":"USD"},
    {"ticker":"CSBGE3.MI","name":"iShares Euro Govt 3-7Y",         "cat":"GOVT_IG",   "risk":0.5,"cur":"EUR"},
    {"ticker":"PJSR.MI",  "name":"PIMCO Euro Short Maturity Acc",  "cat":"GOVT_IG",   "risk":0.3,"cur":"EUR"},
    {"ticker":"EDMA.DE",  "name":"iShares Italy Govt USD Hed",     "cat":"GOVT_IG",   "risk":0.7,"cur":"USD"},
    {"ticker":"EUNQ.DE",  "name":"iShares Spain Govt USD Hed",     "cat":"GOVT_IG",   "risk":0.6,"cur":"USD"},
    {"ticker":"EUGO.MI",  "name":"PIMCO Adv Euro Govt Bond Acc",   "cat":"GOVT_IG",   "risk":0.6,"cur":"EUR"},
    {"ticker":"GOVB.MI",  "name":"iShares Govt Bond",              "cat":"GOVT_IG",   "risk":0.6,"cur":"EUR"},
    {"ticker":"XGIU.MI",  "name":"iShares Euro Govt Bond",         "cat":"GOVT_IG",   "risk":0.7,"cur":"EUR"},
    {"ticker":"CEMM.DE",  "name":"iShares UK Gilts EUR Hed Acc",   "cat":"GOVT_IG",   "risk":0.6,"cur":"EUR"},
    {"ticker":"AGGH.MI",  "name":"iShares Global Aggregate EUR Hed","cat":"AGGREGATE","risk":0.5,"cur":"EUR"},
    {"ticker":"CRPA.MI",  "name":"iShares Global Corporate Bond",  "cat":"CORP_IG",   "risk":0.8,"cur":"USD"},
    {"ticker":"IEAA.MI",  "name":"iShares Core EUR Corporate Acc", "cat":"CORP_IG",   "risk":0.7,"cur":"EUR"},
    {"ticker":"EMSA.MI",  "name":"iShares JP Morgan Adv USD EM",   "cat":"EM_BOND",   "risk":1.2,"cur":"USD"},
    {"ticker":"EMLB.MI",  "name":"PIMCO Adv EM Local Bond Acc",    "cat":"EM_BOND",   "risk":1.2,"cur":"USD"},
    {"ticker":"AYE8.DE",  "name":"iShares JP Morgan EM CHF Hed",   "cat":"EM_BOND",   "risk":1.1,"cur":"CHF"},
    {"ticker":"EUHA.MI",  "name":"PIMCO Adv Euro ST HY Acc",       "cat":"HY_EUR",    "risk":1.0,"cur":"EUR"},
    {"ticker":"JCHY.MI",  "name":"JPMorgan Global HY Multi-Factor","cat":"HY_USD",    "risk":1.1,"cur":"USD"},
]
BOND_ACC_CATS = ["GOVT_IG","AGGREGATE","CORP_IG","EM_BOND","HY_EUR","HY_USD","CASH"]
BOND_ACC_CAT_LABELS = {
    "GOVT_IG":"Govt IG", "AGGREGATE":"Aggregate", "CORP_IG":"Corp IG",
    "EM_BOND":"EM Bond", "HY_EUR":"HY EUR", "HY_USD":"HY USD", "CASH":"Cash",
}
BOND_ACC_MAX_W = {"GOVT_IG":25, "AGGREGATE":30, "CORP_IG":25, "EM_BOND":25, "HY_EUR":20, "HY_USD":20, "CASH":60}
BOND_ACC_MIN_W_ACTIVE  = 10
BOND_ACC_MAX_POSITIONS = 7
BOND_ACC_MIN_POSITIONS = 4
# NOTA: BOND_ACC non ha un ETF CASH dedicato nell'universo -> in scenari di crisi
# lo scoring routes verso XGIU.MI (GOVT_IG piu' difensivo), da verificare a runtime.

# ════════════════════════════════════════════════════════════════════════
# LINEA 3/4 — ANTONACCI + FABER (universo condiviso, 8 strumenti acc)
# ════════════════════════════════════════════════════════════════════════
MOMENTUM_UNIVERSE = [
    {"ticker":"XEON.MI", "name":"Amundi Govt MMF",           "cat":"CASH",     "risk":0.0, "cur":"EUR"},
    {"ticker":"IS02.MI", "name":"iShares EUR Govt 1-3Y",     "cat":"GOVT_IG",  "risk":0.3, "cur":"EUR"},
    {"ticker":"VAGF.MI", "name":"Vanguard EUR Govt",         "cat":"GOVT_IG",  "risk":0.5, "cur":"EUR"},
    {"ticker":"SXRI.MI", "name":"iShares EUR Corp Bond",     "cat":"CORP_IG",  "risk":0.6, "cur":"EUR"},
    {"ticker":"XHYA.MI", "name":"Xtrackers EUR HY",          "cat":"HY_EUR",   "risk":1.0, "cur":"EUR"},
    {"ticker":"AT1.MI",  "name":"WisdomTree AT1 CoCo",       "cat":"AT1",      "risk":1.5, "cur":"EUR"},
    {"ticker":"SEMB.MI", "name":"iShares EM Bond EUR Hed",   "cat":"EM_BOND",  "risk":1.2, "cur":"EUR"},
    {"ticker":"XGIU.MI", "name":"Xtrackers TIPS",            "cat":"INFLATION","risk":0.7, "cur":"EUR"},
]
# Benchmark per il filtro momentum assoluto (regola 1 Antonacci)
MOMENTUM_ABS_FILTER_BENCH = "VAGF.MI"

# ════════════════════════════════════════════════════════════════════════
# UNIONE — usata dal backtest e dalla pagina Renko satellite
# ════════════════════════════════════════════════════════════════════════
def all_tickers_unique() -> list:
    """Ritorna la lista deduplicata di tutti i ticker usati in tutte le 4 linee."""
    seen = {}
    for u in (BOND_DIST_UNIVERSE, BOND_ACC_UNIVERSE, MOMENTUM_UNIVERSE):
        for etf in u:
            seen[etf["ticker"]] = etf  # ultima definizione vince, i campi sono coerenti
    return list(seen.values())

# Ticker macro classifier (mercati globali) — serve al backtest per ricostruire
# lo storico dei regimi. Import diretto da scripts/update.py per non duplicare.
MACRO_CLASSIFIER_MODULE = "scripts.update"
