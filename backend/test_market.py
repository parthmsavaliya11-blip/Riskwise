"""Verify the Angel market-data feed (data only). ASCII-only prints."""
from app.market import AngelMarket

m = AngelMarket()
m._build()
print("equity instruments:", len(m._equity), "| F&O instruments:", len(m._fno))

print("\n-- equity search RELIANCE --")
for r in m.search_equity("RELIANCE", 3):
    print(" ", r)
print("-- equity search AXISBANK (user holding) --")
for r in m.search_equity("AXISBANK", 2):
    print(" ", r)
print("-- equity search TATA (NSE+BSE) --")
for r in m.search_equity("TATA", 6):
    print(" ", r["symbol"], r["exchange"], r["token"])

print("\n-- F&O search NIFTY (futures first) --")
for r in m.search_fno("NIFTY", 8):
    print(" ", r["symbol"], "| exch", r["exchange"], "| lot", r["lot_size"], "| kind", r["kind"], "| exp", r["expiry"], "| strike", r["strike"])
print("-- F&O search RELIANCE --")
for r in m.search_fno("RELIANCE", 4):
    print(" ", r["symbol"], "| lot", r["lot_size"], "| kind", r["kind"])
print("-- F&O search BANKNIFTY --")
for r in m.search_fno("BANKNIFTY", 3):
    print(" ", r["symbol"], "| lot", r["lot_size"])

print("\n-- live LTP for user holdings --")
for sym in ["AXISBANK", "HDFCLIFE", "DRREDDY", "M&M", "TATAPOWER"]:
    rec = m.resolve_equity(sym)
    if rec:
        ltp = m.ltp_by_token(rec["exchange"], rec["token"])
        print("  {:>10}  {}  token {}  LTP {}".format(sym, rec["exchange"], rec["token"], ltp))
    else:
        print("  {:>10}  NOT FOUND".format(sym))

print("\nDone.")
