"""Curated list of popular NSE symbols + indices for the add-holding autocomplete.

Offline-friendly (no network). The user can still type any symbol that isn't here;
when Angel One is connected, the full instrument master replaces this list.
ASCII-only.
"""

from __future__ import annotations

# (symbol, display name). Kept reasonably broad: Nifty 50 large-caps + popular
# mid-caps + the tradable indices.
SYMBOLS: list[tuple[str, str]] = [
    # Indices
    ("NIFTY", "Nifty 50 Index"),
    ("BANKNIFTY", "Nifty Bank Index"),
    ("SENSEX", "BSE Sensex Index"),
    # Banks & financials
    ("HDFCBANK", "HDFC Bank"),
    ("ICICIBANK", "ICICI Bank"),
    ("SBIN", "State Bank of India"),
    ("KOTAKBANK", "Kotak Mahindra Bank"),
    ("AXISBANK", "Axis Bank"),
    ("INDUSINDBK", "IndusInd Bank"),
    ("BANKBARODA", "Bank of Baroda"),
    ("PNB", "Punjab National Bank"),
    ("BAJFINANCE", "Bajaj Finance"),
    ("BAJAJFINSV", "Bajaj Finserv"),
    ("HDFCLIFE", "HDFC Life Insurance"),
    ("SBILIFE", "SBI Life Insurance"),
    ("ICICIGI", "ICICI Lombard"),
    ("CHOLAFIN", "Cholamandalam Investment"),
    # IT
    ("TCS", "Tata Consultancy Services"),
    ("INFY", "Infosys"),
    ("WIPRO", "Wipro"),
    ("HCLTECH", "HCL Technologies"),
    ("TECHM", "Tech Mahindra"),
    ("LTIM", "LTIMindtree"),
    ("PERSISTENT", "Persistent Systems"),
    ("COFORGE", "Coforge"),
    # Energy & power
    ("RELIANCE", "Reliance Industries"),
    ("ONGC", "Oil & Natural Gas Corp"),
    ("NTPC", "NTPC"),
    ("POWERGRID", "Power Grid Corp"),
    ("COALINDIA", "Coal India"),
    ("IOC", "Indian Oil Corp"),
    ("BPCL", "Bharat Petroleum"),
    ("ADANIGREEN", "Adani Green Energy"),
    ("TATAPOWER", "Tata Power"),
    ("ADANIPOWER", "Adani Power"),
    # Auto
    ("TATAMOTORS", "Tata Motors"),
    ("MARUTI", "Maruti Suzuki"),
    ("M&M", "Mahindra & Mahindra"),
    ("BAJAJ-AUTO", "Bajaj Auto"),
    ("EICHERMOT", "Eicher Motors"),
    ("HEROMOTOCO", "Hero MotoCorp"),
    ("TVSMOTOR", "TVS Motor"),
    ("ASHOKLEY", "Ashok Leyland"),
    # FMCG & consumer
    ("HINDUNILVR", "Hindustan Unilever"),
    ("ITC", "ITC"),
    ("NESTLEIND", "Nestle India"),
    ("BRITANNIA", "Britannia Industries"),
    ("TATACONSUM", "Tata Consumer Products"),
    ("DABUR", "Dabur India"),
    ("VBL", "Varun Beverages"),
    ("TITAN", "Titan Company"),
    ("DMART", "Avenue Supermarts"),
    ("TRENT", "Trent"),
    # Pharma & healthcare
    ("SUNPHARMA", "Sun Pharmaceutical"),
    ("DRREDDY", "Dr Reddy's Labs"),
    ("CIPLA", "Cipla"),
    ("DIVISLAB", "Divi's Labs"),
    ("APOLLOHOSP", "Apollo Hospitals"),
    ("LUPIN", "Lupin"),
    ("AUROPHARMA", "Aurobindo Pharma"),
    # Metals & materials
    ("TATASTEEL", "Tata Steel"),
    ("JSWSTEEL", "JSW Steel"),
    ("HINDALCO", "Hindalco Industries"),
    ("VEDL", "Vedanta"),
    ("JINDALSTEL", "Jindal Steel & Power"),
    ("SAIL", "Steel Authority of India"),
    ("NMDC", "NMDC"),
    # Cement & infra
    ("ULTRACEMCO", "UltraTech Cement"),
    ("GRASIM", "Grasim Industries"),
    ("SHREECEM", "Shree Cement"),
    ("AMBUJACEM", "Ambuja Cements"),
    ("LT", "Larsen & Toubro"),
    ("ADANIPORTS", "Adani Ports & SEZ"),
    ("ADANIENT", "Adani Enterprises"),
    ("DLF", "DLF"),
    # Telecom & media
    ("BHARTIARTL", "Bharti Airtel"),
    ("IDEA", "Vodafone Idea"),
    # Chemicals & others
    ("ASIANPAINT", "Asian Paints"),
    ("PIDILITIND", "Pidilite Industries"),
    ("UPL", "UPL"),
    ("SRF", "SRF"),
    ("PIIND", "PI Industries"),
    ("IRCTC", "IRCTC"),
    ("ZOMATO", "Zomato"),
    ("PAYTM", "One97 (Paytm)"),
    ("NYKAA", "FSN E-Commerce (Nykaa)"),
    ("POLYCAB", "Polycab India"),
    ("HAL", "Hindustan Aeronautics"),
    ("BEL", "Bharat Electronics"),
    ("BHEL", "Bharat Heavy Electricals"),
    ("IRFC", "Indian Railway Finance"),
]


# Sector tag per symbol, so concentration/sector-exposure works on real holdings
# (offline, no data feed). Unknown symbols fall back to "Other".
_SECTOR_GROUPS: dict[str, list[str]] = {
    "Financials": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK",
                   "BANKBARODA", "PNB", "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE",
                   "ICICIGI", "CHOLAFIN", "IRFC"],
    "IT": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "PERSISTENT", "COFORGE"],
    "Energy": ["RELIANCE", "ONGC", "NTPC", "POWERGRID", "COALINDIA", "IOC", "BPCL",
               "ADANIGREEN", "TATAPOWER", "ADANIPOWER"],
    "Auto": ["TATAMOTORS", "MARUTI", "M&M", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO",
             "TVSMOTOR", "ASHOKLEY"],
    "FMCG/Consumer": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "TATACONSUM", "DABUR",
                      "VBL", "TITAN", "DMART", "TRENT"],
    "Pharma": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "APOLLOHOSP", "LUPIN", "AUROPHARMA"],
    "Metals": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "JINDALSTEL", "SAIL", "NMDC"],
    "Infra/Cement": ["ULTRACEMCO", "GRASIM", "SHREECEM", "AMBUJACEM", "LT", "ADANIPORTS",
                     "ADANIENT", "DLF"],
    "Telecom": ["BHARTIARTL", "IDEA"],
    "Index": ["NIFTY", "BANKNIFTY", "SENSEX", "NIFTY24JUNFUT"],
}
SECTOR_MAP: dict[str, str] = {
    sym: sector for sector, syms in _SECTOR_GROUPS.items() for sym in syms
}


def sector_for(symbol: str) -> str:
    return SECTOR_MAP.get(symbol.strip().upper(), "Other")


def search_symbols(query: str | None = None, limit: int = 50) -> list[dict]:
    """Return matching symbols (prefix/substring on symbol or name)."""
    items = [{"symbol": s, "name": n} for s, n in SYMBOLS]
    if not query:
        return items
    q = query.strip().upper()
    scored = []
    for it in items:
        sym, name = it["symbol"], it["name"].upper()
        if sym.startswith(q):
            scored.append((0, it))
        elif q in sym:
            scored.append((1, it))
        elif q in name:
            scored.append((2, it))
    scored.sort(key=lambda x: (x[0], x[1]["symbol"]))
    return [it for _, it in scored[:limit]]
