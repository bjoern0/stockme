import logging
logging.basicConfig(level=logging.DEBUG)

from src import data

for sym in ["NVDA", "MU", "NFLX"]:
    df = data.fetch_history(sym)
    if df is None:
        print(sym, "FAILED")
    else:
        print(sym, "OK, rows:", len(df), "last close:", df["Close"].iloc[-1])

movers = data.fetch_top_movers("day_gainers", count=5)
print("day_gainers sample:", movers[:2])
