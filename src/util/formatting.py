from typing import Any, List

from src.data.constants import CURRENCY_SYMBOLS, EXCHANGE_RATES


def currency_symbol(code: str) -> str:
    return CURRENCY_SYMBOLS.get(code.upper(), "$")


def fmt_money(symbol: str, value: float, decimals: int = 2) -> str:
    return f"{symbol}{value:,.{decimals}f}"


def usd_to_disp(value_usd: float, currency: str) -> float:
    return value_usd * EXCHANGE_RATES.get(currency.upper(), 1.0)


def disp_to_usd(value_disp: float, currency: str) -> float:
    rate = EXCHANGE_RATES.get(currency.upper(), 1.0)
    return value_disp / rate if rate else 0.0


# Strings/symbols that may appear in formatted currency values
CURRENCY_TRASH_STRINGS: List[str] = [
    "A$", "C$", "NZ$", "HK$", "S$", "NT$", "MX$",
    "$", "€", "£", "¥", "₩", "R$", "R", "₺", "zł", "฿", "Rp", "RM", "₱", "₪", "د.إ", "ر.س", "₽",
]


def extract_number(value: Any) -> float:
    try:
        s = str(value)
        if 'x' in s:
            s = s.split('x', 1)[0]
        if '(' in s:
            s = s.split('(', 1)[0]
        for trash in CURRENCY_TRASH_STRINGS:
            s = s.replace(trash, "")
        s = s.replace(",", "").replace("%", "").strip()
        return float(s or 0.0)
    except Exception:
        return 0.0


