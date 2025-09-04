from typing import Dict, Any, List
from datetime import datetime, timezone
import time
import logging

from src.data.http import get_http_session

logger = logging.getLogger("KPP")


def _retry_get_json(url: str, params: Dict[str, Any], retries: int = 2, timeout: int = 10, toast=None):
    for attempt in range(retries + 1):
        try:
            r = get_http_session().get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"GET {url} attempt {attempt+1} failed: {e}")
            if attempt < retries:
                if toast:
                    try:
                        toast("Rate limited or server busy, retrying…", 1400)
                    except Exception:
                        pass
                time.sleep(0.5)
    if toast:
        try:
            toast("Failed to fetch latest data.", 1800)
        except Exception:
            pass
    return None


def fetch_fx_rates_fast(SUPPORTED_CURRENCIES: List[str], EXCHANGE_RATES: Dict[str, float], toast=None) -> Dict[str, Any]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    params = {"base": "USD", "symbols": ",".join(SUPPORTED_CURRENCIES)}
    data = _retry_get_json("https://api.exchangerate.host/latest", params=params, retries=2, timeout=8, toast=toast)
    out_rates = {}
    if data and "rates" in data:
        rates = data["rates"]
        for k in SUPPORTED_CURRENCIES:
            v = rates.get(k, EXCHANGE_RATES.get(k, 1.0))
            try:
                v = float(v)
            except Exception:
                v = EXCHANGE_RATES.get(k, 1.0)
            out_rates[k] = v if v > 0 else EXCHANGE_RATES.get(k, 1.0)
        src = "exchangerate.host/latest (base=USD)"
    else:
        out_rates = EXCHANGE_RATES.copy()
        src = "exchangerate.host/latest (base=USD) (fallback used)"
    return {"rates": out_rates, "fetched_at": fetched_at, "source": src}


def fetch_markets_fast(ids: List[str], toast=None) -> Dict[str, Any]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    params = {
        "vs_currency": "usd",
        "ids": ",".join(ids),
        "per_page": len(ids),
        "page": 1,
        "precision": "full",
        "price_change_percentage": "24h",
        "locale": "en",
    }
    data = _retry_get_json("https://api.coingecko.com/api/v3/coins/markets", params=params, retries=2, timeout=10, toast=toast)
    out: Dict[str, Any] = {"fetched_at": fetched_at, "source": "CoinGecko /coins/markets"}
    if not data:
        return out
    try:
        by_id = {row.get("id"): row for row in data if isinstance(row, dict)}
        out["by_id"] = by_id

        kas = by_id.get("kaspa", {})
        if kas:
            out["kaspa_price"] = float(kas.get("current_price") or 0.0)
            out["kaspa_supply"] = float(kas.get("circulating_supply") or 0.0)

        btc = by_id.get("bitcoin", {})
        if btc:
            out["btc_market_cap"] = float(btc.get("market_cap") or 0.0)

        current_caps = {}
        for cid in ids:
            row = by_id.get(cid, {})
            cap = float(row.get("market_cap") or 0.0)
            current_caps[cid] = cap
        out["top_current_caps"] = current_caps

        detail = {}
        for cid in ids:
            row = by_id.get(cid, {})
            detail[cid] = {
                "circulating_supply": float(row.get("circulating_supply") or 0.0),
                "ath_price_usd": float(row.get("ath") or 0.0),
            }
        out["top_detail"] = detail

    except Exception as e:
        logger.warning(f"Failed to parse markets data: {e}")
    return out


