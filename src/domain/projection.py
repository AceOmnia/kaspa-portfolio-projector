from typing import Tuple
import numpy as np
import pandas as pd

from src.data.constants import EXCHANGE_RATES
from src.util.formatting import currency_symbol


def generate_price_intervals(current_price_usd: float, min_price: float = 0.01, max_price: float = 1000.0):
    cp = round(max(current_price_usd, 0.01), 2)
    red_max = max(min(cp - 0.01, cp), min_price)
    red_intervals = np.linspace(min_price, red_max, num=9).tolist() if red_max > min_price else []
    black = [cp]
    green_start = round(cp + 0.01, 2)
    green_intervals = [] if green_start >= max_price else np.geomspace(green_start, max_price, num=240).tolist()
    return sorted({round(x, 2) for x in (red_intervals + black + green_intervals)})


def generate_portfolio_projection(kas_amount: float, current_price_usd: float,
                                  circ_supply_b: float, currency: str) -> Tuple[pd.DataFrame, str]:
    circ_supply = circ_supply_b * 1_000_000_000
    usd_prices = generate_price_intervals(current_price_usd)
    rate = EXCHANGE_RATES.get(currency.upper(), 1.0)
    colors = ["red" if p < round(current_price_usd, 2)
              else "black" if p == round(current_price_usd, 2)
              else "green" for p in usd_prices]
    display_prices = [round(p * rate, 2) for p in usd_prices]
    portfolios = [kas_amount * p * rate for p in usd_prices]
    market_caps = [circ_supply * p * rate for p in usd_prices]

    black_idx = colors.index("black")
    black_disp = display_prices[black_idx]

    def dedupe(indices):
        rows = [(display_prices[i], usd_prices[i], portfolios[i], market_caps[i], colors[i]) for i in indices]
        rows.sort(key=lambda x: (x[0], x[1]))
        seen, out = set(), []
        for r in rows:
            if r[0] not in seen:
                seen.add(r[0]); out.append(r)
        return out

    if currency.upper() != "USD":
        red = dedupe(range(0, black_idx))
        if red and red[-1][0] == black_disp: red.pop()
        green = dedupe(range(black_idx + 1, len(usd_prices)))
        if green and green[0][0] == black_disp: green.pop(0)
        merged = red + [(display_prices[black_idx], usd_prices[black_idx], portfolios[black_idx],
                         market_caps[black_idx], colors[black_idx])] + green
        if merged:
            disp, usd, port, mcap, cols = zip(*merged)
        else:
            disp, usd, port, mcap, cols = [], [], [], [], []
    else:
        disp, usd, port, mcap, cols = display_prices, usd_prices, portfolios, market_caps, colors

    df = pd.DataFrame({"Price": disp, "Price_USD": usd, "Portfolio": port, "Market Cap": mcap, "Color": cols})
    return df, currency_symbol(currency)


