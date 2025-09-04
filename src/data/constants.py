from typing import Dict, List

# Version
VERSION: str = "1.2.2"

# Currency support
SUPPORTED_CURRENCIES: List[str] = [
    "USD", "EUR", "GBP", "JPY", "AUD",
    "CAD", "CHF", "CNY", "HKD", "INR",
    "NZD", "SEK", "NOK", "DKK", "SGD",
    "KRW", "MXN", "BRL", "ZAR", "TRY",
    "PLN", "THB", "TWD", "IDR", "MYR",
    "PHP", "ILS", "AED", "SAR", "RUB",
]

# Fallback rates (base = USD). Live rates overwrite these on fetch.
EXCHANGE_RATES: Dict[str, float] = {
    "USD": 1.0,  "EUR": 0.92, "GBP": 0.79, "JPY": 149.50, "AUD": 1.55,
    "CAD": 1.35, "CHF": 0.88, "CNY": 7.25, "HKD": 7.80,   "INR": 83.00,
    "NZD": 1.68, "SEK": 10.50,"NOK": 10.60,"DKK": 6.85,   "SGD": 1.35,
    "KRW": 1330.00,"MXN":17.00,"BRL": 5.20,"ZAR": 18.20,  "TRY": 33.00,
    "PLN": 4.05, "THB": 35.50,"TWD": 32.00,"IDR": 15400.0,"MYR": 4.70,
    "PHP": 56.50,"ILS": 3.70, "AED": 3.6725,"SAR": 3.75,  "RUB": 92.00,
}

CURRENCY_SYMBOLS: Dict[str, str] = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "AUD": "A$",
    "CAD": "C$", "CHF": "CHF", "CNY": "¥", "HKD": "HK$", "INR": "₹",
    "NZD": "NZ$", "SEK": "kr", "NOK": "kr", "DKK": "kr", "SGD": "S$",
    "KRW": "₩", "MXN": "MX$", "BRL": "R$", "ZAR": "R", "TRY": "₺",
    "PLN": "zł", "THB": "฿", "TWD": "NT$", "IDR": "Rp", "MYR": "RM",
    "PHP": "₱", "ILS": "₪", "AED": "د.إ", "SAR": "ر.س", "RUB": "₽",
}


