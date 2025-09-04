#!/usr/bin/env python3
# Kaspa Portfolio Projector (KPP) — v1.2.3 (two-tab + fast fetch + hover + sortable compare + shorter slider)

"""
Kaspa Portfolio Projector (KPP)
===============================

A Tkinter-based desktop application for projecting and analyzing the value of a Kaspa (KAS) portfolio
across varying market prices and market capitalizations. Provides real-time data fetching from CoinGecko
and exchange rate APIs, dynamic currency conversion, and export capabilities for PDF and CSV reports.

v1.2.3:
- Slider shortened (length 440) so the 'KAS Market Cap' field is no longer clipped.
- Includes prior improvements:
  - Fast parallel API fetching (FX + CoinGecko markets in one call)
  - Clickable logo with hover affordance
  - Comparisons tab that auto-updates with first-tab inputs
  - Sortable comparisons table
"""

import os
import sys
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, List, Callable, Optional

import numpy as np
import pandas as pd
from fpdf import FPDF

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from PIL import Image, ImageTk, ImageColor
import sv_ttk
import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.data.constants import (
    VERSION as KPP_VERSION,
    SUPPORTED_CURRENCIES as CONST_SUPPORTED_CURRENCIES,
    EXCHANGE_RATES as CONST_EXCHANGE_RATES,
    CURRENCY_SYMBOLS as CONST_CURRENCY_SYMBOLS,
)
from src.util.resources import resource_path as util_resource_path
from src.util.formatting import (
    currency_symbol as util_currency_symbol,
    fmt_money as util_fmt_money,
    usd_to_disp as util_usd_to_disp,
    disp_to_usd as util_disp_to_usd,
    extract_number as util_extract_number,
)
from src.data.api import fetch_fx_rates_fast as api_fetch_fx_rates_fast, fetch_markets_fast as api_fetch_markets_fast

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("KPP")

# -----------------------------------------------------------------------------
# Paths / Resources
# -----------------------------------------------------------------------------
def resource_path(relative_path: str) -> str:
    return util_resource_path(relative_path)

VERSION = KPP_VERSION

# Colors and UI constants
from src.data.ui_constants import (
    COLOR_BG, COLOR_FG, CHECKMARK_COLOR, X_MARK_COLOR, BUTTON_BG, BUTTON_FG,
    LOGO_PATH, LOGO_PATH_LIGHT, ICON_PATH,
)


PLACEHOLDERS = {
    "Portfolio Name:": "e.g., My Kaspa Holdings",
    "KAS Holdings:": "e.g., 1367",
    "Current Price (USD):": "e.g., 0.2711 (or press Fetch Data)",
    "Circulating Supply (B):": "e.g., 25.6 (or press Fetch Data)",
}
DEFAULTS = {"Portfolio Name:": "", "KAS Holdings:": "0", "Current Price (USD):": "", "Circulating Supply (B):": ""}
NUMERIC_FIELDS = ["KAS Holdings:", "Current Price (USD):", "Circulating Supply (B):"]

# -----------------------------------------------------------------------------
# Currency support
# -----------------------------------------------------------------------------
SUPPORTED_CURRENCIES = CONST_SUPPORTED_CURRENCIES

# Fallback rates (base = USD). Live rates overwrite these on fetch.
EXCHANGE_RATES = CONST_EXCHANGE_RATES

CURRENCY_SYMBOLS = CONST_CURRENCY_SYMBOLS

def currency_symbol(code: str) -> str:
    return util_currency_symbol(code)

def fmt_money(symbol: str, value: float, decimals: int = 2) -> str:
    return util_fmt_money(symbol, value, decimals)

def usd_to_disp(value_usd: float, currency: str) -> float:
    return util_usd_to_disp(value_usd, currency)

def disp_to_usd(value_disp: float, currency: str) -> float:
    return util_disp_to_usd(value_disp, currency)

# -----------------------------------------------------------------------------
# Parsing utilities
# -----------------------------------------------------------------------------
# Strings/symbols that may appear in formatted currency values
def extract_number(value: Any) -> float:
    return util_extract_number(value)

# -----------------------------------------------------------------------------
# Top coins for the Comparisons tab (CoinGecko IDs) + display names
# -----------------------------------------------------------------------------
TOP_COINS: List[str] = [
    "bitcoin",
    "ethereum",
    "binancecoin",
    "solana",
    "ripple",            # XRP
    "cardano",
    "dogecoin",
    "tron",
    "the-open-network",  # Toncoin (TON)
    "litecoin",
    # Added
    "polkadot",
    "avalanche-2",
    "chainlink",
    "matic-network",
    "internet-computer",
    "shiba-inu",
    "uniswap",
    "near",
    "stellar",
    "monero",
    "bitcoin-cash",
    "aptos",
    "arbitrum",
    "pepe",
    "render-token",
    "cosmos",
    "vechain",
    "algorand",
    "filecoin",
    "optimism",
    "lido-dao",
    "aave",
    "fantom",
    "theta-token",
]

DISPLAY_NAMES: Dict[str, str] = {
    "bitcoin": "Bitcoin (BTC)",
    "ethereum": "Ethereum (ETH)",
    "binancecoin": "BNB (Binance Coin)",
    "solana": "Solana (SOL)",
    "ripple": "XRP (Ripple)",
    "cardano": "Cardano (ADA)",
    "dogecoin": "Dogecoin (DOGE)",
    "tron": "TRON (TRX)",
    "the-open-network": "Toncoin (TON)",
    "litecoin": "Litecoin (LTC)",
    "kaspa": "Kaspa (KAS)",
    # Added
    "polkadot": "Polkadot (DOT)",
    "avalanche-2": "Avalanche (AVAX)",
    "chainlink": "Chainlink (LINK)",
    "matic-network": "Polygon (MATIC)",
    "internet-computer": "Internet Computer (ICP)",
    "shiba-inu": "Shiba Inu (SHIB)",
    "uniswap": "Uniswap (UNI)",
    "near": "NEAR Protocol (NEAR)",
    "stellar": "Stellar (XLM)",
    "monero": "Monero (XMR)",
    "bitcoin-cash": "Bitcoin Cash (BCH)",
    "aptos": "Aptos (APT)",
    "arbitrum": "Arbitrum (ARB)",
    "pepe": "Pepe (PEPE)",
    "render-token": "Render (RNDR)",
    "cosmos": "Cosmos (ATOM)",
    "vechain": "VeChain (VET)",
    "algorand": "Algorand (ALGO)",
    "filecoin": "Filecoin (FIL)",
    "optimism": "Optimism (OP)",
    "lido-dao": "Lido DAO (LDO)",
    "aave": "Aave (AAVE)",
    "fantom": "Fantom (FTM)",
    "theta-token": "Theta Network (THETA)",
}

# -----------------------------------------------------------------------------
# Styling
# -----------------------------------------------------------------------------
def apply_modern_style(root):
    sv_ttk.set_theme("dark")
    style = ttk.Style(root)
    style.configure(".", font=("Segoe UI", 11))

    style.configure("Kaspa.TButton", padding=(14, 8), background=BUTTON_BG, foreground=BUTTON_FG, borderwidth=0)
    style.configure("KaspaSmall.TButton", padding=(10, 6), background=BUTTON_BG, foreground=BUTTON_FG, borderwidth=0)
    style.map("Kaspa.TButton",
              background=[("active", COLOR_BG), ("pressed", COLOR_BG), ("disabled", "#3a3a3a")],
              foreground=[("disabled", "#b8b8b8")])
    style.map("KaspaSmall.TButton",
              background=[("active", COLOR_BG), ("pressed", COLOR_BG), ("disabled", "#3a3a3a")],
              foreground=[("disabled", "#b8b8b8")])

    style.configure("Kaspa.TCheckbutton", foreground=COLOR_BG, background=COLOR_FG, padding=(6, 4))
    style.map("Kaspa.TCheckbutton",
              background=[("active", COLOR_FG), ("selected", COLOR_FG)],
              foreground=[("disabled", "#777777")])

    style.configure("Kaspa.TEntry", fieldbackground="#2b2b2b", foreground="#e8e8e8", padding=8, borderwidth=1)
    style.map("Kaspa.TEntry", bordercolor=[("focus", COLOR_BG), ("!focus", "#3a3a3a")])

    style.configure("Kaspa.TCombobox", fieldbackground="#2b2b2b", foreground="#e8e8e8",
                    padding=6, borderwidth=1, arrowsize=14)
    style.map("Kaspa.TCombobox", bordercolor=[("focus", COLOR_BG), ("!focus", "#3a3a3a")])

    style.configure("Kaspa.Big.TCombobox", fieldbackground="#2b2b2b", foreground="#e8e8e8",
                    padding=8, borderwidth=1, arrowsize=18)
    style.map("Kaspa.Big.TCombobox", bordercolor=[("focus", COLOR_BG), ("!focus", "#3a3a3a")])

    style.configure("Treeview",
                    background="#1e1e1e", fieldbackground="#1e1e1e",
                    foreground="#eaeaea", rowheight=26, borderwidth=0, relief="flat")
    style.configure("Treeview.Heading",
                    font=("Segoe UI", 12, "bold"),
                    background=COLOR_BG, foreground="#FFFFFF",
                    relief="flat", padding=6)
    style.map("Treeview",
              background=[("selected", "#0f766e")],
              foreground=[("selected", "white")])

    style.configure("Vertical.TScrollbar", gripcount=0, arrowsize=12)
    style.configure("Kaspa.Vertical.TScale", troughcolor="#2b2b2b")
    style.map("Kaspa.Vertical.TScale",
              bordercolor=[("focus", COLOR_FG)],
              background=[("focus", COLOR_FG)])

def card_frame(parent, **kw):
    bg = kw.pop("bg", COLOR_FG)
    f = tk.Frame(parent, bg=bg, **kw)
    f.configure(highlightthickness=0, bd=0)
    return f

def section_title(parent, text: str):
    wrapper = tk.Frame(parent, bg=COLOR_FG)
    lbl = ttk.Label(wrapper, text=text, foreground=COLOR_BG,
                    background=COLOR_FG, font=("Segoe UI", 18, "bold"))
    lbl.pack(anchor="center", pady=(6, 2))
    tk.Frame(wrapper, bg=COLOR_BG, height=2).pack(fill="x")
    return wrapper

# -----------------------------------------------------------------------------
# Gradient header utilities
# -----------------------------------------------------------------------------
def _lerp(a, b, t): return int(a + (b - a) * t)
def _hex_to_rgb(hx): return ImageColor.getrgb(hx)

def make_horizontal_gradient(width, height, stops):
    img = Image.new("RGB", (width, height))
    px = img.load()
    stops = sorted(stops, key=lambda s: s[0])
    for x in range(width):
        t = x / max(1, width - 1)
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                local = 0 if p1 == p0 else (t - p0) / (p1 - p0)
                r0, g0, b0 = _hex_to_rgb(c0); r1, g1, b1 = _hex_to_rgb(c1)
                r = _lerp(r0, r1, local); g = _lerp(g0, g1, local); b = _lerp(b0, b1, local)
                for y in range(height): px[x, y] = (r, g, b)
                break
    return img

# -----------------------------------------------------------------------------
# API helpers (fast + parallel)
# -----------------------------------------------------------------------------
def _retry_get_json(url: str, params: Dict[str, Any], retries: int = 2, timeout: int = 10):
    for attempt in range(retries + 1):
        try:
            r = get_http_session().get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"GET {url} attempt {attempt+1} failed: {e}")
            if attempt < retries:
                # Emit a small toast on likely rate-limit/server hiccup
                _toast("Rate limited or server busy, retrying…", 1400)
                time.sleep(0.5)
    # Final failure
    _toast("Failed to fetch latest data.", 1800)
    return None

# -----------------------------------------------------------------------------
# HTTP session with retries
# -----------------------------------------------------------------------------
SESSION: requests.Session | None = None

def get_http_session() -> requests.Session:
    """Create or return a shared HTTP session with retry/backoff.

    Retries on 429/5xx with exponential backoff. Reuses connections for speed.
    """
    global SESSION
    if SESSION is None:
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({
            "User-Agent": f"Kaspa-Portfolio-Projector/{VERSION} (+https://www.kaspa.org)",
            "Accept": "application/json",
        })
        SESSION = session
    return SESSION

# -----------------------------------------------------------------------------
# Toast notifications (non-intrusive status messages)
# -----------------------------------------------------------------------------
TOAST_CALLBACK: Optional[Callable[[str, int], None]] = None

def register_toast_callback(cb: Callable[[str, int], None]):
    global TOAST_CALLBACK
    TOAST_CALLBACK = cb

def _toast(msg: str, duration_ms: int = 1600):
    if TOAST_CALLBACK:
        try:
            TOAST_CALLBACK(msg, duration_ms)
        except Exception:
            pass

def fetch_fx_rates_fast() -> Dict[str, Any]:
    # Delegate to data.api while preserving return shape
    return api_fetch_fx_rates_fast(SUPPORTED_CURRENCIES, EXCHANGE_RATES, toast=_toast)

def fetch_markets_fast(ids: List[str]) -> Dict[str, Any]:
    # Delegate to data.api while preserving return shape
    return api_fetch_markets_fast(ids, toast=_toast)

# -----------------------------------------------------------------------------
# Projection math
# -----------------------------------------------------------------------------
def generate_price_intervals(current_price_usd: float, min_price: float = 0.01, max_price: float = 1000.0):
    cp = round(max(current_price_usd, 0.01), 2)
    red_max = max(min(cp - 0.01, cp), min_price)
    red_intervals = np.linspace(min_price, red_max, num=9).tolist() if red_max > min_price else []
    black = [cp]
    green_start = round(cp + 0.01, 2)
    green_intervals = [] if green_start >= max_price else np.geomspace(green_start, max_price, num=240).tolist()
    return sorted({round(x, 2) for x in (red_intervals + black + green_intervals)})

def generate_portfolio_projection(kas_amount: float, current_price_usd: float,
                                  circ_supply_b: float, currency: str):
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

# -----------------------------------------------------------------------------
# PDF
# -----------------------------------------------------------------------------
from src.exporters.pdf_export import generate_portfolio_pdf

# -----------------------------------------------------------------------------
# Main App
# -----------------------------------------------------------------------------
class KaspaPortfolioApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Kaspa Portfolio Projection (KPP) - Version {VERSION}")
        self.root.geometry("1700x1005")
        self.root.minsize(1300, 850)
        try: self.root.iconbitmap(ICON_PATH)
        except Exception: pass

        apply_modern_style(self.root)
        # Debounce map per-widget to avoid cross-field cancellations
        self._debounce_after_by_widget: Dict[tk.Widget, str] = {}
        self.fetched_data: Dict[str, Any] = {}
        self._sort_state: Dict[str, bool] = {}
        self._compare_sort_state: Dict[str, bool] = {}  # comparisons table sort state
        self._watchlist_sort_state: Dict[str, bool] = {}

        # Header (canvas gradient)
        self.top_frame = tk.Frame(root, height=110, bd=0, highlightthickness=0)
        self.top_frame.pack(fill="x", pady=(0, 3))
        self.header_canvas = tk.Canvas(self.top_frame, height=110, bd=0, highlightthickness=0)
        self.header_canvas.pack(fill="both", expand=True)

        self.logo_img = None
        try:
            _logo_pil = Image.open(LOGO_PATH).resize((300, 125), Image.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(_logo_pil)
        except Exception:
            logger.warning("Logo not found, continuing without it.")

        def _redraw_header(evt=None):
            w = max(1, self.header_canvas.winfo_width())
            h = max(1, self.header_canvas.winfo_height())
            stops = [(0.0, "#0b0c0d"), (0.35, "#161718"), (0.55, "#231F20"), (0.90, "#1a2b29"), (1.0, "#153f3a")]
            img = make_horizontal_gradient(w, h, stops)
            img_tk = ImageTk.PhotoImage(img)
            self.header_canvas.delete("all")
            self.header_canvas.create_image(0, 0, image=img_tk, anchor="nw")
            self.header_canvas.image_ref = img_tk

            if self.logo_img:
                img_id = self.header_canvas.create_image(12, h // 2, image=self.logo_img, anchor="w")

                def _open_kaspa(_evt):
                    try:
                        import webbrowser
                        webbrowser.open_new_tab("https://www.kaspa.org")
                    except Exception:
                        pass

                hover_rect = {"id": None}
                def _on_enter(_evt):
                    try:
                        self.header_canvas.config(cursor="hand2")
                        if hover_rect["id"] is None:
                            x1, y1 = 8, h // 2 - 70
                            x2, y2 = 320, h // 2 + 70
                            hover_rect["id"] = self.header_canvas.create_rectangle(
                                x1, y1, x2, y2,
                                outline=COLOR_BG, width=2
                            )
                    except Exception:
                        pass

                def _on_leave(_evt):
                    try:
                        self.header_canvas.config(cursor="")
                        if hover_rect["id"] is not None:
                            self.header_canvas.delete(hover_rect["id"])
                            hover_rect["id"] = None
                    except Exception:
                        pass

                self.header_canvas.tag_bind(img_id, "<Button-1>", _open_kaspa)
                self.header_canvas.tag_bind(img_id, "<Enter>", _on_enter)
                self.header_canvas.tag_bind(img_id, "<Leave>", _on_leave)

            rx = w - 12
            self.header_canvas.create_text(rx, 38, text="Kaspa Portfolio Projector",
                                           fill="#FFFFFF", font=("Segoe UI", 30, "bold"), anchor="e")
            self.header_canvas.create_text(rx, 70, text=f"Developed by the Kaspa community | Version {VERSION}",
                                           fill="#E6E6E6", font=("Segoe UI", 10), anchor="e")
        self.header_canvas.bind("<Configure>", _redraw_header)

        self.header_line = tk.Frame(root, height=10, bg=COLOR_BG, bd=0, highlightthickness=0)
        self.header_line.pack(fill="x")

        # Body container + notebook
        self.body_container = tk.Frame(root, bg="#121212"); self.body_container.pack(fill="both", expand=True)
        self.notebook = ttk.Notebook(self.body_container); self.notebook.pack(fill="both", expand=True)
        self.tab_projection = tk.Frame(self.notebook, bg="#121212")
        self.tab_compare = tk.Frame(self.notebook, bg="#121212")
        self.notebook.add(self.tab_projection, text="Projection")
        self.notebook.add(self.tab_compare, text="Comparisons")
        self.tab_watchlist = tk.Frame(self.notebook, bg="#121212")
        self.tab_targets = tk.Frame(self.notebook, bg="#121212")
        self.tab_scenarios = tk.Frame(self.notebook, bg="#121212")
        self.notebook.add(self.tab_watchlist, text="Watchlist")
        self.notebook.add(self.tab_targets, text="Targets")
        self.notebook.add(self.tab_scenarios, text="Scenarios")
        self._build_projection_tab(self.tab_projection)
        self._build_comparisons_tab(self.tab_compare)
        self._build_watchlist_tab(self.tab_watchlist)
        self._build_targets_tab(self.tab_targets)
        self._build_scenarios_tab(self.tab_scenarios)

        # Toast label (ephemeral, top-right)
        self._toast_after = None
        self.toast_frame = tk.Frame(self.body_container, bg="#1e1e1e")
        self.toast_label = ttk.Label(self.toast_frame, text="", background="#1e1e1e", foreground="#eaeaea")
        self.toast_label.pack(padx=10, pady=6)

        def _show_toast(msg: str, duration_ms: int = 1600):
            try:
                if self._toast_after:
                    self.root.after_cancel(self._toast_after)
                self.toast_label.config(text=msg)
                # Place at top-right of the main window
                self.toast_frame.place(relx=1.0, rely=0.0, x=-20, y=20, anchor="ne")
                self._toast_after = self.root.after(duration_ms, lambda: self.toast_frame.place_forget())
            except Exception:
                pass

        register_toast_callback(lambda msg, dur: self.root.after(0, _show_toast, msg, dur))

        # Initial data pull (parallel FX + markets)
        self.fetch_data_on_startup()

    # ---- Status-bar helpers ----
    def start_status(self, text: str, indeterminate: bool = True, maximum: int = 100):
        self.status_label.config(text=text)
        self.status_bar.pack(side="bottom", fill="x")
        if indeterminate:
            self.status_progress.config(mode="indeterminate")
            self.status_progress.start(12)
        else:
            self.status_progress.config(mode="determinate", maximum=maximum, value=0)
        self.root.update_idletasks()

    def set_status(self, text: str | None = None, value: float | None = None):
        if text is not None:
            self.status_label.config(text=text)
        if value is not None:
            if str(self.status_progress.cget("mode")) != "determinate":
                self.status_progress.stop()
                self.status_progress.config(mode="determinate", maximum=100, value=0)
            self.status_progress["value"] = max(0, min(100, value))
        self.root.update_idletasks()

    def end_status(self):
        try: self.status_progress.stop()
        except Exception: pass
        self.status_label.config(text="")
        self.status_bar.pack_forget()
        self.root.update_idletasks()

    # ---- Buttons ----
    def create_button(self, text, command, row, column, small=False):
        style = "KaspaSmall.TButton" if small else "Kaspa.TButton"
        btn = ttk.Button(self.input_subframe, text=text, command=command, style=style)
        btn.grid(row=row, column=column, pady=8 if small else 12, padx=10, sticky="ew")
        return btn

    def _toggle_inputs(self, disabled: bool):
        for child in self.input_subframe.winfo_children():
            if isinstance(child, ttk.Button):
                child.state(["disabled"] if disabled else ["!disabled"])

    # ---- API plumbing (fast + parallel) ----
    @staticmethod
    @lru_cache(maxsize=1)
    def fetch_api_data():
        out: Dict[str, Any] = {}

        def fx_task(): return fetch_fx_rates_fast()
        def markets_task():
            ids = ["kaspa", "bitcoin"] + [c for c in TOP_COINS if c not in ("bitcoin", "kaspa")]
            return fetch_markets_fast(ids)

        with ThreadPoolExecutor(max_workers=2) as ex:
            futures = {ex.submit(fx_task): "fx", ex.submit(markets_task): "mkt"}
            for fut in as_completed(futures):
                tag = futures[fut]
                try:
                    data = fut.result()
                except Exception as e:
                    logger.error(f"Fetch {tag} failed: {e}")
                    data = {}
                if tag == "fx":
                    out["fx_rates"] = data.get("rates", EXCHANGE_RATES.copy())
                    out["fx_fetched_at"] = data.get("fetched_at")
                    out["fx_source"] = data.get("source", "exchangerate.host/latest (base=USD)")
                else:
                    out.update(data or {})
        return out

    def _apply_fetched(self, data: Dict[str, Any]):
        if data.get("fx_rates"):
            EXCHANGE_RATES.update(data["fx_rates"])
        if data.get("kaspa_price") is not None:
            self.entries["Current Price (USD):"].delete(0, tk.END)
            self.entries["Current Price (USD):"].insert(0, f"{float(data['kaspa_price']):.6f}")
            try: self.entries["Current Price (USD):"].configure(foreground="#e8e8e8")
            except Exception: pass
        if data.get("kaspa_supply") is not None:
            self.entries["Circulating Supply (B):"].delete(0, tk.END)
            self.entries["Circulating Supply (B):"].insert(0, f"{float(data['kaspa_supply']) / 1_000_000_000:.6f}")
            try: self.entries["Circulating Supply (B):"].configure(foreground="#e8e8e8")
            except Exception: pass
        for fld in ["Current Price (USD):", "Circulating Supply (B):"]:
            self.updated_fields[fld] = True; self.show_check_mark(fld); self.hide_x_mark(fld)

        if self.entries["KAS Holdings:"].get().strip() in [PLACEHOLDERS["KAS Holdings:"], DEFAULTS["KAS Holdings:"], ""]:
            self.entries["KAS Holdings:"].delete(0, tk.END); self.entries["KAS Holdings:"].insert(0, "0")

        self.fetched_data = data or {}
        self.slider_var.set(0)
        self.update_slider_values()
        self.update_display_if_valid()
        self._refresh_comparisons()
        # Also refresh new tabs so they show data immediately
        try: self._refresh_watchlist()
        except Exception: pass
        try: self._refresh_targets()
        except Exception: pass
        try: self._refresh_scenarios()
        except Exception: pass

    def fetch_data_on_startup(self):
        self.start_status("Fetching data (FX + Markets)…")
        self._toggle_inputs(True)
        def _worker():
            data = self.fetch_api_data()
            self.root.after(0, lambda: (self._apply_fetched(data), self.end_status(), self._toggle_inputs(False)))
        threading.Thread(target=_worker, daemon=True).start()

    def fetch_data(self):
        self.start_status("Refreshing data (FX + Markets)…")
        self._toggle_inputs(True)
        def _worker():
            fx = fetch_fx_rates_fast()
            ids = ["kaspa", "bitcoin"] + [c for c in TOP_COINS if c not in ("bitcoin", "kaspa")]
            mkt = fetch_markets_fast(ids)
            data = {"fx_rates": fx.get("rates"), "fx_fetched_at": fx.get("fetched_at"), "fx_source": fx.get("source")}
            data.update(mkt or {})
            self.root.after(0, lambda: (self._apply_fetched(data), self.end_status(), self._toggle_inputs(False)))
        threading.Thread(target=_worker, daemon=True).start()

    # ---- Help / Pulled Data ----
    def show_help(self):
        messagebox.showinfo(
            "Help",
            "1) Enter your Kaspa holdings.\n"
            "2) Click 'Fetch Real Time Data' to fill price and supply.\n"
            "3) Choose a currency (uses live FX).\n"
            "4) Explore the projection table and slider.\n"
            "5) Export a PDF or CSV."
        )

    def show_pulled_data(self):
        win = tk.Toplevel(self.root)
        win.title("Pulled Data (APIs)"); win.geometry("720x620")
        win.transient(self.root); win.grab_set()
        try: win.iconbitmap(ICON_PATH)
        except Exception: pass

        container = tk.Frame(win, bg="#1e1e1e"); container.pack(fill="both", expand=True)
        txt = tk.Text(container, wrap="word", font=("Consolas", 11),
                      bg="#1e1e1e", fg="#eaeaea", insertbackground="#eaeaea",
                      relief="flat", borderwidth=0)
        txt.pack(fill="both", expand=True, padx=10, pady=10)

        d = self.fetched_data or {}
        fx = d.get("fx_rates", EXCHANGE_RATES)
        fx_time = d.get("fx_fetched_at", "n/a")
        fx_src = d.get("fx_source", "exchangerate.host/latest (base=USD)")
        cg_time = d.get("fetched_at", "n/a")
        cg_src = d.get("source", "CoinGecko /coins/markets")

        def line(s=""): txt.insert("end", s + "\n")

        line("=== Exchange Rates (base USD) ===")
        for k in SUPPORTED_CURRENCIES:
            line(f"  {k}: {fx.get(k, 'n/a')}")
        line(f"  fetched_at: {fx_time}")
        line(f"  source    : {fx_src}")
        line()

        line("=== CoinGecko ===")
        if "kaspa_price" in d: line(f"  KAS price (USD): {d['kaspa_price']}")
        if "kaspa_supply" in d: line(f"  KAS circulating supply: {d['kaspa_supply']:,.0f}")
        if "btc_market_cap" in d: line(f"  BTC market cap (USD): {d['btc_market_cap']:,.0f}")
        if "top_current_caps" in d:
            line("  Top coins current caps (USD):")
            for cid, cap in (d["top_current_caps"] or {}).items():
                name = DISPLAY_NAMES.get(cid, cid)
                line(f"    - {name}: {cap:,.0f}")
        line(f"  fetched_at: {cg_time}")
        line(f"  source    : {cg_src}")
        line()

        line("Tip: press 'Fetch Real Time Data' to refresh this snapshot.")
        txt.configure(state="disabled")

    # ---- Placeholder & validation ----
    def clear_placeholder(self, widget, placeholder, default, label):
        if widget.get() in [placeholder, default]:
            widget.delete(0, tk.END)
            try: widget.configure(foreground="#e8e8e8")
            except Exception: pass
            self.updated_fields[label] = False
            self.hide_check_mark(label); self.show_x_mark(label)

    def restore_placeholder(self, widget, placeholder, default, label):
        value = widget.get().strip()
        if not value:
            widget.insert(0, placeholder)
            try: widget.configure(foreground="#9aa0a6")
            except Exception: pass
            self.updated_fields[label] = False
            self.hide_check_mark(label); self.show_x_mark(label)
        else:
            try: widget.configure(foreground="#e8e8e8")
            except Exception: pass
            if value != placeholder and (label == "Portfolio Name:" or self.is_valid_numeric_field(label)):
                self.updated_fields[label] = True
                if label == "KAS Holdings:":
                    try:
                        if float(value.replace(",", "")) > 0:
                            self.show_check_mark(label); self.hide_x_mark(label)
                    except ValueError: pass
                elif label in NUMERIC_FIELDS:
                    self.show_check_mark(label); self.hide_x_mark(label)
                if label in NUMERIC_FIELDS:
                    self.update_display_if_valid()

    def _debounced_update_field_and_check(self, event):
        widget = event.widget
        label = next((l for l, e in self.entries.items() if e == widget), None)
        # For non-heavy fields like Portfolio Name, update immediately for snappy feedback
        if label == "Portfolio Name:":
            self.update_field_and_check(widget)
            return
        # Debounce per widget for numeric fields
        after_id = self._debounce_after_by_widget.get(widget)
        if after_id:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
        new_id = self.root.after(200, lambda w=widget: self.update_field_and_check(w))
        self._debounce_after_by_widget[widget] = new_id

    def update_field_and_check(self, widget):
        label = next((l for l, e in self.entries.items() if e == widget), None)
        if not label: return
        value = widget.get().strip()
        if value and value != PLACEHOLDERS[label]:
            if label == "Portfolio Name:":
                self.updated_fields[label] = True; self.show_check_mark(label); self.hide_x_mark(label)
            elif label in NUMERIC_FIELDS:
                try:
                    fv = float(value.replace(",", ""))
                    if fv < 0: raise ValueError
                    self.updated_fields[label] = True
                    if label == "KAS Holdings:" and fv <= 0:
                        self.hide_check_mark(label); self.show_x_mark(label); return
                    self.show_check_mark(label); self.hide_x_mark(label)
                    self.update_display_if_valid()
                except ValueError:
                    self.updated_fields[label] = False
                    self.hide_check_mark(label); self.show_x_mark(label)
        else:
            self.updated_fields[label] = False
            self.hide_check_mark(label); self.show_x_mark(label)

    def is_valid_numeric_field(self, label):
        value = self.entries[label].get().strip()
        if not value or value == PLACEHOLDERS[label]: return False
        try:
            f = float(value.replace(",", ""))
            if label == "KAS Holdings:" and f <= 0: return False
            return f >= 0
        except ValueError:
            return False

    # ---- Table / metrics ----
    def update_display_if_valid(self, _event=None):
        if all(self.is_valid_numeric_field(f) for f in NUMERIC_FIELDS):
            kaspa = float(self.entries["KAS Holdings:"].get().replace(",", ""))
            price_usd = float(self.entries["Current Price (USD):"].get().replace(",", ""))
            supply_b = float(self.entries["Circulating Supply (B):"].get().replace(",", ""))
            currency = self.currency_var.get()
            df, sym = generate_portfolio_projection(kaspa, price_usd, supply_b, currency)
            btc_market_cap = (self.fetched_data or {}).get("btc_market_cap", 0.0)

            self.tree.delete(*self.tree.get_children())
            items = []
            for i, (_, row) in enumerate(df.iterrows()):
                projected_price_usd = row["Price_USD"]
                projected_portfolio_value = row["Portfolio"]
                projected_market_cap = row["Market Cap"]
                multiple = (projected_price_usd / price_usd) if price_usd else 0
                pct = (multiple - 1) * 100
                change_str = f"{multiple:.1f}x ({pct:+.1f}%)"
                tag = "even" if i % 2 == 0 else "odd"
                vals = [
                    fmt_money(sym, row["Price"]),
                    fmt_money(sym, projected_portfolio_value, 0),
                    fmt_money(sym, projected_market_cap, 0),
                ]
                vals.append(change_str if self.show_change_var.get() else "")
                if self.show_market_cap_vs_btc_var.get():
                    mcap_usd = disp_to_usd(projected_market_cap, currency)
                    vals.append(f"{(mcap_usd / btc_market_cap):.6f}" if btc_market_cap else "N/A")
                else:
                    vals.append("")
                item = self.tree.insert("", "end", values=vals, tags=(row["Color"], tag))
                items.append(item)

            if not df.empty:
                black_idx = df.index[df["Color"] == "black"].tolist()
                if black_idx:
                    bi = max(0, black_idx[0] - 1)
                    self.tree.see(items[bi]); self.tree.yview_moveto(bi / max(1, len(items)))

            self.update_display_columns()

            circ_supply = supply_b * 1_000_000_000
            market_cap_usd = price_usd * circ_supply
            portfolio_value_usd = kaspa * price_usd
            price_needed_for_1m_usd = (1_000_000 / kaspa) if kaspa > 0 else 0
            mcap_needed_for_1m_usd = price_needed_for_1m_usd * circ_supply

            market_cap = usd_to_disp(market_cap_usd, currency)
            portfolio_value = usd_to_disp(portfolio_value_usd, currency)
            price_needed_for_1m = usd_to_disp(price_needed_for_1m_usd, currency)
            mcap_needed_for_1m = usd_to_disp(mcap_needed_for_1m_usd, currency)
            btc_mcap_cur = usd_to_disp((btc_market_cap or 0), currency)
            ratio = (mcap_needed_for_1m_usd / btc_market_cap) if btc_market_cap else 0

            updates = [
                ("Holdings", f"{kaspa:,.2f} KAS"),
                ("Portfolio Value", fmt_money(sym, portfolio_value)),
                ("Market Cap", fmt_money(sym, market_cap)),
                ("Price Needed 1M", fmt_money(sym, price_needed_for_1m)),
                ("Market Cap Needed 1M", fmt_money(sym, mcap_needed_for_1m)),
            ]
            for key, val in updates:
                entry = self.metrics_entries[key].winfo_children()[1]
                entry.state(["!readonly"]); entry.delete(0, tk.END); entry.insert(0, val); entry.state(["readonly"])

            if btc_market_cap:
                self.btc_summary_line1.config(text="KAS Market cap needed for $1M portfolio:")
                self.btc_summary_line2.config(text=f"is about {ratio:.6f} times the")
                self.btc_summary_line3.config(text=f"current Bitcoin market cap of {fmt_money(sym, btc_mcap_cur)}.")
            else:
                self.btc_summary_line1.config(text="Bitcoin market cap data unavailable.")
                self.btc_summary_line2.config(text=""); self.btc_summary_line3.config(text="")

            self.update_slider_values()

            # keep Comparisons tab in sync whenever inputs are valid
            self._refresh_comparisons()
            # also refresh Targets and Scenarios automatically
            try: self._refresh_targets()
            except Exception: pass
            try: self._refresh_scenarios()
            except Exception: pass

    def update_display_columns(self):
        cols = ["Price", "Portfolio", "MarketCap"]
        if self.show_change_var.get(): cols.append("Change")
        if self.show_market_cap_vs_btc_var.get(): cols.append("Market Cap vs. BTC")
        self.tree["displaycolumns"] = cols
        total = 710; n = len(cols)
        if n:
            base = total // n
            for col in cols[:-1]: self.tree.column(col, width=base, anchor="center")
            self.tree.column(cols[-1], width=total - base * (n - 1), anchor="center")

    def sort_table(self, column):
        disp_cols = list(self.tree["displaycolumns"])
        if column not in disp_cols: return
        col_idx = disp_cols.index(column)
        items = [(self.tree.item(item)["values"], item) for item in self.tree.get_children()]

        def parse_tuple(val):
            s = str(val)
            if column in ["Price", "Portfolio", "MarketCap"]:
                return (0, extract_number(s))
            if column == "Market Cap vs. BTC":
                s_trim = s.strip()
                if s_trim in ("", "N/A"):
                    return (1, 0.0)
                return (0, extract_number(s))
            if column == "Change":
                # Example: '1.2x (+20.0%)' -> 1.2
                leading = s.split("x", 1)[0]
                return (0, extract_number(leading))
            return (0, str(val))

        reverse = self._sort_state.get(column, False)
        items.sort(key=lambda x: parse_tuple(x[0][col_idx]), reverse=reverse)
        self._sort_state[column] = not reverse
        for i, (_, item) in enumerate(items): self.tree.move(item, "", i)

    # ---- Slider ----
    def toggle_slider_input(self, value):
        if value == "Enter Custom Price":
            self.slider_input_menu.pack_forget()
            self.slider_price_entry.pack(side="right", padx=10); self.slider_price_entry.focus_set()
        else:
            self.slider_price_entry.pack_forget()
            self.slider_input_menu.pack(side="right", padx=10)

    def _slider_bounds(self):
        try:
            cp = float(self.entries["Current Price (USD):"].get().replace(",", ""))
            min_price = max(round(cp, 2), 0.01)
        except Exception:
            min_price = 0.01
        return min_price, 1000.0

    def update_slider_from_entry(self, _=None):
        try:
            entered = extract_number(self.slider_price_entry.get())
        except Exception:
            messagebox.showerror("Error", "Please enter a valid numeric price."); return
        min_p, max_p = self._slider_bounds()
        entered = min(max(entered, min_p), max_p)
        if max_p > min_p:
            pos = 100 * np.log(entered / min_p) / np.log(max_p / min_p)
            self.slider_var.set(pos); self.update_slider_values()

    def update_slider_values(self, _=None):
        min_p, max_p = self._slider_bounds()
        pos = float(self.slider_var.get()); pos = min(max(pos, 0.0), 100.0)
        kas_price = min_p * (max_p / min_p) ** (pos / 100.0) if max_p > min_p else min_p

        try: kas_amount = float(self.entries["KAS Holdings:"].get().replace(",", ""))
        except Exception: kas_amount = 0.0
        try:
            supply_b = float(self.entries["Circulating Supply (B):"].get().replace(",", ""))
            circ_supply = supply_b * 1_000_000_000
        except Exception: circ_supply = 0.0

        currency = self.currency_var.get()
        sym = currency_symbol(currency)

        self.slider_price_label.config(text=fmt_money("$", kas_price))

        portfolio_value = usd_to_disp(kas_amount * kas_price, currency)
        mcap = usd_to_disp(circ_supply * kas_price, currency)

        for w, val in [(self.portfolio_value_entry, fmt_money(sym, portfolio_value)),
                       (self.market_cap_entry, fmt_money(sym, mcap))]:
            w.state(["!readonly"]); w.delete(0, tk.END); w.insert(0, val); w.state(["readonly"])

        if self.link_to_slider_var.get():
            items = self.tree.get_children()
            if not items: return
            closest_index, min_diff = 0, float("inf")
            target_price_disp = usd_to_disp(kas_price, currency)
            for i, item in enumerate(items):
                price_str = self.tree.item(item, "values")[0]
                price_num = extract_number(price_str)
                diff = abs(price_num - target_price_disp)
                if diff < min_diff: min_diff, closest_index = diff, i
            tgt = max(0, closest_index - 1); self.tree.see(items[tgt]); self.tree.yview_moveto(tgt / max(1, len(items)))

    # ---- Exporters ----
    def _collect_inputs(self) -> Tuple[float, float, float, str, str]:
        kaspa = float(self.entries["KAS Holdings:"].get().replace(",", ""))
        price_usd = float(self.entries["Current Price (USD):"].get().replace(",", ""))
        supply_b = float(self.entries["Circulating Supply (B):"].get().replace(",", ""))
        currency = self.currency_var.get() or "USD"
        name = self.entries["Portfolio Name:"].get() or "Unnamed"
        return kaspa, price_usd, supply_b, currency, name

    def generate_pdf(self):
        try:
            for f in NUMERIC_FIELDS:
                if not self.is_valid_numeric_field(f):
                    raise ValueError(f"Please enter a valid positive number greater than 0 for {f} if applicable.")
            kaspa, price_usd, supply_b, currency, name = self._collect_inputs()
            df, _ = generate_portfolio_projection(kaspa, price_usd, supply_b, currency)
            path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
            if path:
                self.start_status("Saving PDF…", indeterminate=False)
                try:
                    btc_market_cap = (self.fetched_data or {}).get("btc_market_cap", 0)
                    generate_portfolio_pdf(
                        df, path, name, kaspa, price_usd, supply_b, currency, btc_market_cap,
                        progress_cb=lambda p: self.set_status(value=p)
                    )
                    messagebox.showinfo("Success", f"PDF generated at {path}.")
                finally:
                    self.end_status()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def export_csv(self):
        try:
            for f in NUMERIC_FIELDS:
                if not self.is_valid_numeric_field(f):
                    raise ValueError(f"Please enter a valid positive number greater than 0 for {f} if applicable.")
            kaspa, price_usd, supply_b, currency, name = self._collect_inputs()
            df, _ = generate_portfolio_projection(kaspa, price_usd, supply_b, currency)
            path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")],
                                                initialfile=f"{(name or 'unnamed').lower().replace(' ','_')}_projection.csv")
            if not path: return
            self.start_status("Exporting CSV…", indeterminate=False)
            try:
                sym = currency_symbol(currency)
                out = df.copy()
                out["Price"] = out["Price"].map(lambda v: fmt_money(sym, v))
                out["Portfolio"] = out["Portfolio"].map(lambda v: fmt_money(sym, v, 0))
                out["Market Cap"] = out["Market Cap"].map(lambda v: fmt_money(sym, v, 0))
                out = out.drop(columns=["Price_USD"])
                self.set_status(value=33)
                out.to_csv(path, index=False)
                self.set_status(value=100)
                messagebox.showinfo("Success", f"CSV exported to {path}.")
            finally:
                self.end_status()
        except ValueError as e:
            messagebox.showerror("Error", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"CSV export failed: {e}")

    # ---- Misc ----
    def _copy_cell(self, event):
        iid = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if iid and col:
            idx = int(col.replace("#","")) - 1
            vals = self.tree.item(iid, "values")
            if 0 <= idx < len(vals):
                val = vals[idx]
                self.root.clipboard_clear()
                self.root.clipboard_append(val)

    def update_display_on_currency_change(self, _event=None):
        self.update_display_if_valid(); self.update_slider_values()
        try:
            self.currency_combo.selection_clear()
            self.currency_combo.icursor(tk.END)
        except Exception:
            pass
        self.slider.focus_set()
        self.slider_input_var.set("Use Slider"); self.slider_price_entry.pack_forget()
        self.slider_input_menu.pack(side="right", padx=10)

        # Keep Comparisons tab currency in sync
        try:
            self.compare_currency_var.set(self.currency_var.get())
            self._refresh_comparisons()
        except Exception:
            pass

        # Sync Watchlist/Targets/Scenarios currencies and refresh
        try:
            self.watchlist_currency_var.set(self.currency_var.get())
            self._refresh_watchlist()
        except Exception:
            pass
        try:
            self.targets_currency_var.set(self.currency_var.get())
            self._refresh_targets()
        except Exception:
            pass
        try:
            self.scenarios_currency_var.set(self.currency_var.get())
            self._refresh_scenarios()
        except Exception:
            pass

    def show_check_mark(self, label):
        self.check_marks[label].grid(); self.x_marks[label].grid_remove()
    def hide_check_mark(self, label):
        self.check_marks[label].grid_remove()
    def show_x_mark(self, label):
        self.x_marks[label].grid(); self.check_marks[label].grid_remove()
    def hide_x_mark(self, label):
        self.x_marks[label].grid_remove()

    # -------------------------------------------------------------------------
    # Projection Tab Builder (original UI)
    # -------------------------------------------------------------------------
    def _build_projection_tab(self, parent):
        self.status_bar = tk.Frame(parent, bg="#1b1b1b")
        self.status_label = ttk.Label(self.status_bar, text="", background="#1b1b1b", foreground="#eaeaea")
        self.status_label.pack(side="left", padx=10, pady=4)
        self.status_progress = ttk.Progressbar(self.status_bar, mode="indeterminate", length=180)
        self.status_progress.pack(side="right", padx=10, pady=4)
        self.status_bar.pack_forget()

        self.content_frame = tk.Frame(parent, bg="#121212"); self.content_frame.pack(fill="both", expand=True)
        self.right_frame = card_frame(self.content_frame, padx=20, pady=10, width=320)
        self.right_frame.pack(side="right", fill="y", padx=(5, 10), pady=(0, 10)); self.right_frame.pack_propagate(False)
        self.left_frame = tk.Frame(self.content_frame, bg="#121212")
        self.left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.main_frame = tk.Frame(self.left_frame, bg="#121212", padx=10, pady=0)
        self.main_frame.pack(fill="both", expand=True)

        self.input_frame = card_frame(self.main_frame, padx=20, pady=10); self.input_frame.pack(fill="x", padx=0)
        self.input_subframe = tk.Frame(self.input_frame, bg=COLOR_FG, padx=10, pady=10)
        self.input_subframe.pack(side="left", fill="both", expand=True)
        self.metrics_subframe = tk.Frame(self.input_frame, bg=COLOR_FG, padx=10, pady=10)
        self.metrics_subframe.pack(side="right", fill="both", expand=True)

        section_title(self.input_subframe, "Portfolio Inputs").grid(row=0, column=0, columnspan=3, sticky="ew")
        section_title(self.metrics_subframe, "Key Portfolio Metrics").grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self.input_subframe.grid_columnconfigure(0, weight=1)
        self.input_subframe.grid_columnconfigure(1, weight=2)
        self.input_subframe.grid_columnconfigure(2, weight=1)

        self.entries: Dict[str, ttk.Entry] = {}
        self.check_marks: Dict[str, ttk.Label] = {}
        self.x_marks: Dict[str, ttk.Label] = {}
        self.updated_fields: Dict[str, bool] = {}
        self.metrics_entries: Dict[str, tk.Frame] = {}

        start_row = 1
        for i, label in enumerate(PLACEHOLDERS, start=start_row):
            ttk.Label(self.input_subframe, text=label, foreground=COLOR_BG,
                      font=("Segoe UI", 12, "bold"), background=COLOR_FG)\
                .grid(row=i, column=0, padx=10, pady=8, sticky="w")
            entry_frame = tk.Frame(self.input_subframe, bg=COLOR_FG)
            entry_frame.grid(row=i, column=1, padx=10, pady=8, sticky="e")
            entry = ttk.Entry(entry_frame, style="Kaspa.TEntry", font=("Segoe UI", 12), width=28)
            entry.insert(0, PLACEHOLDERS[label] if not DEFAULTS[label] else DEFAULTS[label])
            if not DEFAULTS[label]:
                try: entry.configure(foreground="#9aa0a6")
                except Exception: pass
            entry.grid(row=0, column=0, padx=5)
            entry.bind("<FocusIn>", lambda e, p=PLACEHOLDERS[label], d=DEFAULTS[label], l=label:
                       self.clear_placeholder(e.widget, p, d, l))
            entry.bind("<FocusOut>", lambda e, p=PLACEHOLDERS[label], d=DEFAULTS[label], l=label:
                       self.restore_placeholder(e.widget, p, d, l))
            entry.bind("<KeyRelease>", self._debounced_update_field_and_check)

            self.entries[label] = entry; self.updated_fields[label] = False

            check_mark = ttk.Label(entry_frame, text="✔", foreground=CHECKMARK_COLOR,
                                   font=("Segoe UI", 12, "bold"), background=COLOR_FG)
            check_mark.grid(row=0, column=1, padx=5); check_mark.grid_remove()
            self.check_marks[label] = check_mark

            x_mark = ttk.Label(entry_frame, text="✘", foreground=X_MARK_COLOR,
                               font=("Segoe UI", 12, "bold"), background=COLOR_FG)
            x_mark.grid(row=0, column=1, padx=5); self.x_marks[label] = x_mark

        currency_row = len(PLACEHOLDERS) + start_row
        ttk.Label(self.input_subframe, text="Currency:", foreground=COLOR_BG,
                  font=("Segoe UI", 12, "bold"), background=COLOR_FG)\
            .grid(row=currency_row, column=0, padx=10, pady=8, sticky="w")
        currency_frame = tk.Frame(self.input_subframe, bg=COLOR_FG)
        currency_frame.grid(row=currency_row, column=1, padx=10, pady=8, sticky="e")
        self.currency_var = tk.StringVar(value="USD")
        self.currency_combo = ttk.Combobox(
            currency_frame,
            textvariable=self.currency_var,
            values=SUPPORTED_CURRENCIES,
            state="readonly",
            style="Kaspa.TCombobox",
            width=12
        )
        self.currency_combo.grid(row=0, column=0, padx=5)
        self.currency_combo.bind("<<ComboboxSelected>>", self.update_display_on_currency_change)
        ttk.Label(currency_frame, text="✔", foreground=CHECKMARK_COLOR,
                  font=("Segoe UI", 12, "bold"), background=COLOR_FG).grid(row=0, column=1, padx=5)

        button_row = currency_row + 1
        self.btn_pdf = self.create_button("Generate PDF", self.generate_pdf, button_row, 0, small=False)
        self.btn_fetch = self.create_button("Fetch Real Time Data", self.fetch_data, button_row, 1, small=False)
        self.btn_csv = self.create_button("Export CSV", self.export_csv, button_row, 2, small=False)

        self.create_button("Help", self.show_help, button_row + 1, 0, small=True)
        self.create_button("Show Pulled Data", self.show_pulled_data, button_row + 1, 1, small=True)

        metrics = [
            ("Holdings", "Current KAS Holdings:"),
            ("Portfolio Value", "Current KAS Portfolio Value:"),
            ("Market Cap", "Current KAS Market Cap:"),
            ("Price Needed 1M", "KAS Price Needed for $1M Portfolio:"),
            ("Market Cap Needed 1M", "KAS Market Cap Needed for $1M Portfolio:"),
        ]
        for i, (key, label) in enumerate(metrics, 1):
            frame = tk.Frame(self.metrics_subframe, bg=COLOR_FG)
            ttk.Label(frame, text=label, foreground=COLOR_BG,
                      font=("Segoe UI", 12, "bold"), background=COLOR_FG)\
                .grid(row=0, column=0, padx=10, pady=8, sticky="w")
            entry = ttk.Entry(frame, style="Kaspa.TEntry", width=28, justify="right")
            entry.state(["readonly"])
            entry.grid(row=0, column=1, padx=5, pady=8, sticky="e")
            frame.grid(row=i, column=0, padx=(0, 10), pady=5, sticky="e")
            self.metrics_entries[key] = frame

        ttk.Label(self.metrics_subframe, text="Bitcoin Comparison", foreground=COLOR_BG,
                  font=("Segoe UI", 12, "bold"), background=COLOR_FG)\
            .grid(row=6, column=0, padx=(0, 10), pady=(5, 0), sticky="e")
        self.btc_summary_frame = tk.Frame(self.metrics_subframe, bg=COLOR_FG)
        self.btc_summary_frame.grid(row=7, column=0, padx=(10, 10), pady=(0, 5), sticky="e")
        self.btc_summary_line1 = ttk.Label(self.btc_summary_frame,
                                           text="KAS Market cap needed for $1M portfolio:",
                                           foreground=COLOR_BG, font=("Segoe UI", 11), background=COLOR_FG)
        self.btc_summary_line1.grid(row=0, column=0, sticky="e")
        self.btc_summary_line2 = ttk.Label(self.btc_summary_frame,
                                           text="is about 0.000000 times the",
                                           foreground=COLOR_BG, font=("Segoe UI", 11, "bold"), background=COLOR_FG)
        self.btc_summary_line2.grid(row=1, column=0, sticky="e")
        self.btc_summary_line3 = ttk.Label(self.btc_summary_frame,
                                           text="current Bitcoin market cap of $0.00.",
                                           foreground=COLOR_BG, font=("Segoe UI", 11, "bold"), background=COLOR_FG)
        self.btc_summary_line3.grid(row=2, column=0, sticky="e")

        self.display_frame = card_frame(self.main_frame, padx=20, pady=15, width=750)
        self.display_frame.pack(fill="both", expand=True, pady=10, padx=0)
        self.display_frame.pack_propagate(False)

        self.table_frame = tk.Frame(self.display_frame, bg=COLOR_FG, width=750)
        self.table_frame.pack(fill="both", expand=True); self.table_frame.pack_propagate(False)

        section_title(self.table_frame, "Projection Table").grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        self.checkbox_frame = tk.Frame(self.table_frame, bg=COLOR_FG)
        self.checkbox_frame.grid(row=1, column=0, columnspan=2, sticky="e", pady=(0, 5))

        self.link_to_slider_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.checkbox_frame, text="Link to Slider",
                        variable=self.link_to_slider_var, command=self.update_display_if_valid,
                        style="Kaspa.TCheckbutton").pack(side="right", padx=10)

        self.show_change_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.checkbox_frame, text="Show Change Column",
                        variable=self.show_change_var, command=self.update_display_if_valid,
                        style="Kaspa.TCheckbutton").pack(side="right", padx=10)

        self.show_market_cap_vs_btc_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.checkbox_frame, text="Show Market Cap vs. Bitcoin",
                        variable=self.show_market_cap_vs_btc_var, command=self.update_display_if_valid,
                        style="Kaspa.TCheckbutton").pack(side="right", padx=10)

        self.tree = ttk.Treeview(self.table_frame,
                                 columns=("Price", "Portfolio", "MarketCap", "Change", "Market Cap vs. BTC"),
                                 show="headings", height=20)
        for col, text in [
            ("Price", "Price"), ("Portfolio", "Portfolio Value"), ("MarketCap", "Market Cap"),
            ("Change", "Change"), ("Market Cap vs. BTC", "Market Cap vs. BTC")
        ]:
            self.tree.heading(col, text=text, command=lambda c=col: self.sort_table(c))
        self.default_widths = {"Price": 150, "Portfolio": 200, "MarketCap": 250, "Change": 150, "Market Cap vs. BTC": 150}
        for col, w in self.default_widths.items(): self.tree.column(col, width=w, anchor="center")

        self.tree["displaycolumns"] = ["Price", "Portfolio", "MarketCap"]
        self.tree.grid(row=2, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=2, column=1, sticky="ns"); self.tree.configure(yscrollcommand=scrollbar.set)
        self.table_frame.grid_rowconfigure(2, weight=1); self.table_frame.grid_columnconfigure(0, weight=1)

        self.tree.tag_configure("red", foreground="#ff6b6b")
        self.tree.tag_configure("black", foreground="#eaeaea")
        self.tree.tag_configure("green", foreground="#6ee7b7")
        self.tree.tag_configure("even", background="#212121")
        self.tree.tag_configure("odd", background="#1b1b1b")
        self.tree.bind("<Double-1>", self._copy_cell)
        self.update_display_columns()

        section_title(self.right_frame, "Price Explorer (USD)").pack(fill="x", pady=(0, 5))

        self.slider_top_frame = tk.Frame(self.right_frame, bg=COLOR_FG)
        self.slider_top_frame.pack(fill="x", pady=2)

        self.slider_price_label = tk.Label(self.slider_top_frame, text="$0.01",
                                           bg=COLOR_FG, fg=COLOR_BG, font=("Segoe UI", 12, "bold"),
                                           width=12, anchor="w")
        self.slider_price_label.pack(side="left", padx=10)

        self.slider_input_var = tk.StringVar(value="Use Slider")
        self.slider_input_menu = ttk.Combobox(self.slider_top_frame, textvariable=self.slider_input_var,
                                              values=["Use Slider", "Enter Custom Price"],
                                              state="readonly", width=24, style="Kaspa.Big.TCombobox")
        self.slider_input_menu.pack(side="right", padx=10)
        self.slider_input_menu.bind("<<ComboboxSelected>>",
                                    lambda e: self.toggle_slider_input(self.slider_input_var.get()))

        self.slider_price_entry = ttk.Entry(self.slider_top_frame, style="Kaspa.TEntry", width=16)
        self.slider_price_entry.pack(side="right", padx=10); self.slider_price_entry.pack_forget()
        self.slider_price_entry.bind("<Return>", self.update_slider_from_entry)

        # SHORTER SLIDER: length reduced from 550 to 440 (about 1/5 shorter)
        self.slider_var = tk.DoubleVar(value=0)
        self.slider = ttk.Scale(self.right_frame, from_=100, to=0, orient="vertical",
                                variable=self.slider_var, length=440, style="Kaspa.Vertical.TScale",
                                command=self.update_slider_values)
        try: self.slider.configure(takefocus=0)
        except Exception: pass
        self.slider.bind("<FocusIn>", lambda e: self.right_frame.focus_set())
        self.slider.pack(pady=10)  # no fill/expand so it keeps the chosen length

        self.values_frame = tk.Frame(self.right_frame, bg=COLOR_FG); self.values_frame.pack(fill="x", pady=10)
        ttk.Label(self.values_frame, text="Portfolio Value:", foreground=COLOR_BG,
                  font=("Segoe UI", 12, "bold"), background=COLOR_FG).pack(anchor="w", padx=10)
        self.portfolio_value_entry = ttk.Entry(self.values_frame, style="Kaspa.TEntry", width=30)
        self.portfolio_value_entry.state(["readonly"]); self.portfolio_value_entry.pack(fill="x", padx=10, pady=(0, 8))

        ttk.Label(self.values_frame, text="KAS Market Cap:", foreground=COLOR_BG,
                  font=("Segoe UI", 12, "bold"), background=COLOR_FG).pack(anchor="w", padx=10)
        self.market_cap_entry = ttk.Entry(self.values_frame, style="Kaspa.TEntry", width=30)
        self.market_cap_entry.state(["readonly"]); self.market_cap_entry.pack(fill="x", padx=10)

    # -------------------------------------------------------------------------
    # Comparisons Tab (new)
    # -------------------------------------------------------------------------
    def _build_comparisons_tab(self, parent):
        wrapper = card_frame(parent, padx=20, pady=15)
        wrapper.pack(fill="both", expand=True, padx=15, pady=15)

        section_title(wrapper, "Kaspa at Other Coins' Market Caps").pack(fill="x", pady=(0, 8))

        controls = tk.Frame(wrapper, bg=COLOR_FG)
        controls.pack(fill="x", pady=(0, 10))

        self.compare_currency_var = tk.StringVar(value="USD")
        ttk.Label(controls, text="Currency:", foreground=COLOR_BG,
                  font=("Segoe UI", 11, "bold"), background=COLOR_FG).pack(side="left", padx=(10, 6))
        self.compare_currency_combo = ttk.Combobox(
            controls, textvariable=self.compare_currency_var,
            values=SUPPORTED_CURRENCIES, state="readonly", width=12, style="Kaspa.TCombobox"
        )
        self.compare_currency_combo.pack(side="left")
        self.compare_currency_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_comparisons())

        ttk.Button(controls, text="Refresh", style="KaspaSmall.TButton",
                   command=self._refresh_comparisons).pack(side="right", padx=10)
        ttk.Button(controls, text="Export CSV", style="KaspaSmall.TButton",
                   command=self._export_comparisons_csv).pack(side="right", padx=10)

        columns = ("Coin", "Cap Type", "Ref MCap", "Implied KAS Price",
                   "Implied KAS Price (Disp)", "Implied KAS MCap", "Your Portfolio", "Multiple vs Current")
        self.compare_tree = ttk.Treeview(wrapper, columns=columns, show="headings", height=22)
        headers = {
            "Coin": "Reference Coin",
            "Cap Type": "Cap Type",
            "Ref MCap": "Reference Market Cap",
            "Implied KAS Price": "Implied KAS Price (USD)",
            "Implied KAS Price (Disp)": "Implied KAS Price",
            "Implied KAS MCap": "Implied KAS Market Cap",
            "Your Portfolio": "Your Portfolio Value",
            "Multiple vs Current": "Multiple vs Current",
        }
        for c in columns:
            self.compare_tree.heading(
                c,
                text=headers[c],
                command=lambda col=c: self._sort_compare_table(col)
            )
        widths = [190, 120, 180, 190, 180, 200, 200, 170]
        for c, w in zip(columns, widths):
            self.compare_tree.column(c, width=w, anchor="center")

        self.compare_tree.tag_configure("even", background="#212121")
        self.compare_tree.tag_configure("odd", background="#1b1b1b")
        self.compare_tree.pack(fill="both", expand=True)

        foot = tk.Label(wrapper, bg=COLOR_FG, fg="#bdbdbd", justify="left",
                        text=("Notes:\n"
                              "• 'ATH (proxy)' = other coin's ATH price × that coin's current circulating supply (approx.).\n"
                              "• Values convert using your live FX rates."),
                        font=("Segoe UI", 9))
        foot.pack(anchor="w", pady=(8, 0))

    # -------------------------------------------------------------------------
    # Watchlist Tab (markets snapshot)
    # -------------------------------------------------------------------------
    def _build_watchlist_tab(self, parent):
        wrapper = card_frame(parent, padx=20, pady=15)
        wrapper.pack(fill="both", expand=True, padx=15, pady=15)

        section_title(wrapper, "Watchlist").pack(fill="x", pady=(0, 8))

        controls = tk.Frame(wrapper, bg=COLOR_FG)
        controls.pack(fill="x", pady=(0, 10))

        self.watchlist_currency_var = tk.StringVar(value="USD")
        ttk.Label(controls, text="Currency:", foreground=COLOR_BG,
                  font=("Segoe UI", 11, "bold"), background=COLOR_FG).pack(side="left", padx=(10, 6))
        self.watchlist_currency_combo = ttk.Combobox(
            controls, textvariable=self.watchlist_currency_var,
            values=SUPPORTED_CURRENCIES, state="readonly", width=12, style="Kaspa.TCombobox"
        )
        self.watchlist_currency_combo.pack(side="left")
        self.watchlist_currency_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_watchlist())

        ttk.Button(controls, text="Refresh", style="KaspaSmall.TButton",
                   command=self._refresh_watchlist).pack(side="right", padx=10)
        ttk.Button(controls, text="Export CSV", style="KaspaSmall.TButton",
                   command=self._export_watchlist_csv).pack(side="right", padx=10)

        columns = ("Coin", "Price", "24h %", "Market Cap", "Volume", "Rank")
        self.watchlist_tree = ttk.Treeview(wrapper, columns=columns, show="headings", height=22)
        headers = {
            "Coin": "Coin",
            "Price": "Price",
            "24h %": "24h %",
            "Market Cap": "Market Cap",
            "Volume": "24h Volume",
            "Rank": "Rank",
        }
        for c in columns:
            self.watchlist_tree.heading(c, text=headers[c], command=lambda col=c: self._sort_watchlist_table(col))
        widths = [220, 160, 100, 220, 200, 90]
        for c, w in zip(columns, widths):
            self.watchlist_tree.column(c, width=w, anchor="center")

        self.watchlist_tree.tag_configure("even", background="#212121")
        self.watchlist_tree.tag_configure("odd", background="#1b1b1b")
        self.watchlist_tree.pack(fill="both", expand=True)

    def _refresh_watchlist(self):
        # Use existing fetched data
        d = self.fetched_data or {}
        by_id: Dict[str, Any] = d.get("by_id", {}) or {}
        disp_ccy = self.watchlist_currency_var.get().upper() if hasattr(self, 'watchlist_currency_var') else 'USD'
        sym = currency_symbol(disp_ccy)

        # Clear table
        if hasattr(self, 'watchlist_tree'):
            for iid in self.watchlist_tree.get_children():
                self.watchlist_tree.delete(iid)
        else:
            return

        if not by_id:
            self.watchlist_tree.insert("", "end", values=("No data", "", "", "", "", ""))
            return

        # Order by market cap desc
        ids = ["kaspa", "bitcoin", "ethereum"] + [c for c in TOP_COINS if c not in ("kaspa", "bitcoin", "ethereum")]
        rows = []
        for cid in ids:
            row = by_id.get(cid)
            if not isinstance(row, dict):
                continue
            try:
                price_usd = float(row.get("current_price") or 0.0)
                mcap_usd = float(row.get("market_cap") or 0.0)
                vol_usd = float(row.get("total_volume") or 0.0)
                rank = int(row.get("market_cap_rank") or 0)
                # Try both cg fields
                pct = row.get("price_change_percentage_24h_in_currency")
                if pct is None:
                    pct = row.get("price_change_percentage_24h")
                try:
                    pct = float(pct)
                except Exception:
                    pct = 0.0
                rows.append({
                    "coin": DISPLAY_NAMES.get(cid, row.get("symbol", cid).upper()),
                    "price_usd": price_usd,
                    "mcap_usd": mcap_usd,
                    "vol_usd": vol_usd,
                    "rank": rank,
                    "pct": pct,
                })
            except Exception:
                continue

        rows.sort(key=lambda r: r["mcap_usd"], reverse=True)
        for i, r in enumerate(rows):
            tag = "even" if i % 2 == 0 else "odd"
            price_disp = usd_to_disp(r["price_usd"], disp_ccy)
            mcap_disp = usd_to_disp(r["mcap_usd"], disp_ccy)
            vol_disp = usd_to_disp(r["vol_usd"], disp_ccy)
            pct_str = f"{r['pct']:+.2f}%"
            self.watchlist_tree.insert(
                "", "end",
                values=(
                    r["coin"],
                    fmt_money(sym, price_disp),
                    pct_str,
                    fmt_money(sym, mcap_disp, 0),
                    fmt_money(sym, vol_disp, 0),
                    r["rank"] or "",
                ),
                tags=(tag,)
            )

    def _sort_watchlist_table(self, column: str):
        cols = list(self.watchlist_tree["columns"]) if hasattr(self, 'watchlist_tree') else []
        if column not in cols:
            return
        col_idx = cols.index(column)
        items = [(self.watchlist_tree.item(iid)["values"], iid) for iid in self.watchlist_tree.get_children()]

        def key_fn(values):
            val = values[col_idx]
            if column in ("Price", "Market Cap", "Volume"):
                return (0, extract_number(val))
            if column == "24h %":
                s = str(val).replace("%", "")
                return (0, extract_number(s))
            if column == "Rank":
                try:
                    return (0, int(val))
                except Exception:
                    return (1, 0)
            return (0, str(val))

        reverse = self._watchlist_sort_state.get(column, False)
        items.sort(key=lambda x: key_fn(x[0]), reverse=reverse)
        self._watchlist_sort_state[column] = not reverse
        for i, (_, iid) in enumerate(items):
            self.watchlist_tree.move(iid, "", i)

    def _export_watchlist_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="watchlist.csv"
        )
        if not path:
            return
        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Coin", "Price", "24h %", "Market Cap", "Volume", "Rank"])
                for iid in self.watchlist_tree.get_children():
                    w.writerow(self.watchlist_tree.item(iid, "values"))
            messagebox.showinfo("Success", f"CSV exported to {path}.")
        except Exception as e:
            messagebox.showerror("Error", f"CSV export failed: {e}")

    # -------------------------------------------------------------------------
    # Targets Tab
    # -------------------------------------------------------------------------
    def _build_targets_tab(self, parent):
        wrapper = card_frame(parent, padx=20, pady=15)
        wrapper.pack(fill="both", expand=True, padx=15, pady=15)

        section_title(wrapper, "Targets").pack(fill="x", pady=(0, 8))

        controls = tk.Frame(wrapper, bg=COLOR_FG)
        controls.pack(fill="x", pady=(0, 10))

        self.targets_currency_var = tk.StringVar(value="USD")
        ttk.Label(controls, text="Currency:", foreground=COLOR_BG,
                  font=("Segoe UI", 11, "bold"), background=COLOR_FG).pack(side="left", padx=(10, 6))
        self.targets_currency_combo = ttk.Combobox(
            controls, textvariable=self.targets_currency_var,
            values=SUPPORTED_CURRENCIES, state="readonly", width=12, style="Kaspa.TCombobox"
        )
        self.targets_currency_combo.pack(side="left")
        self.targets_currency_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_targets())

        ttk.Button(controls, text="Refresh", style="KaspaSmall.TButton",
                   command=self._refresh_targets).pack(side="right", padx=10)
        ttk.Button(controls, text="Export CSV", style="KaspaSmall.TButton",
                   command=self._export_targets_csv).pack(side="right", padx=10)
        ttk.Button(controls, text="Add Custom Target", style="KaspaSmall.TButton",
                   command=self._add_custom_target_dialog).pack(side="right", padx=10)

        columns = ("Target", "Required Price", "Required Market Cap", "vs BTC")
        self.targets_tree = ttk.Treeview(wrapper, columns=columns, show="headings", height=20)
        headers = {
            "Target": "Target Portfolio",
            "Required Price": "Required KAS Price",
            "Required Market Cap": "Required KAS Market Cap",
            "vs BTC": "MCap vs. BTC",
        }
        for c in columns:
            self.targets_tree.heading(c, text=headers[c], command=lambda col=c: self._sort_targets_table(col))
            self.targets_tree.column(c, width=230 if c != "vs BTC" else 140, anchor="center")
        self.targets_tree.tag_configure("even", background="#212121")
        self.targets_tree.tag_configure("odd", background="#1b1b1b")
        self.targets_tree.pack(fill="both", expand=True)

        # store custom targets (in display currency) for this session
        self._custom_targets_disp: List[float] = []

    def _refresh_targets(self):
        disp_ccy = self.targets_currency_var.get().upper() if hasattr(self, 'targets_currency_var') else 'USD'
        sym = currency_symbol(disp_ccy)

        # Clear
        if hasattr(self, 'targets_tree'):
            for iid in self.targets_tree.get_children():
                self.targets_tree.delete(iid)
        else:
            return

        # Gather inputs
        try: kas_hold = float(self.entries["KAS Holdings:"].get().replace(",", ""))
        except Exception: kas_hold = 0.0
        try: price_usd = float(self.entries["Current Price (USD):"].get().replace(",", ""))
        except Exception: price_usd = 0.0
        try:
            supply_b = float(self.entries["Circulating Supply (B):"].get().replace(",", ""))
            circ_supply_kas = supply_b * 1_000_000_000
        except Exception:
            circ_supply_kas = 0.0
        btc_market_cap = (self.fetched_data or {}).get("btc_market_cap", 0.0)

        if kas_hold <= 0 or price_usd <= 0 or circ_supply_kas <= 0:
            self.targets_tree.insert("", "end", values=("Enter valid inputs on Projection tab", "", "", ""))
            return

        # Targets in display currency
        base_targets_disp = [100_000, 250_000, 500_000, 1_000_000, 2_500_000, 5_000_000]
        targets_disp = sorted(base_targets_disp + list(self._custom_targets_disp))
        for i, t_disp in enumerate(targets_disp):
            # Convert target to USD for computation
            t_usd = disp_to_usd(t_disp, disp_ccy)
            req_price_usd = t_usd / kas_hold if kas_hold > 0 else 0.0
            req_mcap_usd = req_price_usd * circ_supply_kas
            ratio = (req_mcap_usd / btc_market_cap) if btc_market_cap else 0.0
            self.targets_tree.insert(
                "", "end",
                values=(
                    fmt_money(sym, t_disp, 0),
                    fmt_money(sym, usd_to_disp(req_price_usd, disp_ccy)),
                    fmt_money(sym, usd_to_disp(req_mcap_usd, disp_ccy), 0),
                    f"{ratio:.6f}" if ratio else "N/A",
                ),
                tags=("even" if i % 2 == 0 else "odd",)
            )

    def _sort_targets_table(self, column: str):
        cols = list(self.targets_tree["columns"]) if hasattr(self, 'targets_tree') else []
        if column not in cols:
            return
        col_idx = cols.index(column)
        items = [(self.targets_tree.item(iid)["values"], iid) for iid in self.targets_tree.get_children()]

        def key_fn(values):
            val = values[col_idx]
            if column in ("Target", "Required Price", "Required Market Cap"):
                return (0, extract_number(val))
            if column == "vs BTC":
                s = str(val).strip()
                if not s or s.upper() == "N/A":
                    return (1, 0.0)
                return (0, extract_number(s))
            return (0, str(val))

        if not hasattr(self, '_targets_sort_state'):
            self._targets_sort_state = {}
        reverse = self._targets_sort_state.get(column, False)
        items.sort(key=lambda x: key_fn(x[0]), reverse=reverse)
        self._targets_sort_state[column] = not reverse
        for i, (_, iid) in enumerate(items):
            self.targets_tree.move(iid, "", i)

    def _add_custom_target_dialog(self):
        disp_ccy = self.targets_currency_var.get().upper() if hasattr(self, 'targets_currency_var') else 'USD'
        sym = currency_symbol(disp_ccy)
        win = tk.Toplevel(self.root)
        win.title("Add Custom Target")
        win.geometry("360x160")
        win.transient(self.root); win.grab_set()
        try: win.iconbitmap(ICON_PATH)
        except Exception: pass

        container = tk.Frame(win, bg=COLOR_FG); container.pack(fill="both", expand=True)
        ttk.Label(container, text=f"Enter target portfolio ({disp_ccy}):", background=COLOR_FG, foreground=COLOR_BG,
                  font=("Segoe UI", 11, "bold")).pack(padx=16, pady=(16, 6), anchor="w")
        var = tk.StringVar(value=f"{sym}100,000")
        entry = ttk.Entry(container, style="Kaspa.TEntry", width=22, textvariable=var)
        entry.pack(padx=16, pady=(0, 10)); entry.focus_set()

        def _ok():
            try:
                amt = extract_number(var.get())
                if amt <= 0:
                    raise ValueError
                # store in display currency
                self._custom_targets_disp.append(amt)
                self._refresh_targets()
                _toast("Custom target added", 1200)
                win.destroy()
            except Exception:
                messagebox.showerror("Invalid value", "Please enter a positive amount.")

        btns = tk.Frame(container, bg=COLOR_FG)
        btns.pack(fill="x", pady=6)
        ttk.Button(btns, text="Cancel", style="KaspaSmall.TButton", command=win.destroy).pack(side="right", padx=8)
        ttk.Button(btns, text="Add", style="KaspaSmall.TButton", command=_ok).pack(side="right", padx=8)

    def _export_targets_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="targets.csv"
        )
        if not path:
            return
        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Target Portfolio", "Required KAS Price", "Required KAS Market Cap", "MCap vs. BTC"])
                for iid in getattr(self, 'targets_tree').get_children():
                    w.writerow(self.targets_tree.item(iid, "values"))
            messagebox.showinfo("Success", f"CSV exported to {path}.")
        except Exception as e:
            messagebox.showerror("Error", f"CSV export failed: {e}")

    # -------------------------------------------------------------------------
    # Scenarios Tab
    # -------------------------------------------------------------------------
    def _build_scenarios_tab(self, parent):
        wrapper = card_frame(parent, padx=20, pady=15)
        wrapper.pack(fill="both", expand=True, padx=15, pady=15)

        section_title(wrapper, "Scenarios").pack(fill="x", pady=(0, 8))

        controls = tk.Frame(wrapper, bg=COLOR_FG)
        controls.pack(fill="x", pady=(0, 10))

        self.scenarios_currency_var = tk.StringVar(value="USD")
        ttk.Label(controls, text="Currency:", foreground=COLOR_BG,
                  font=("Segoe UI", 11, "bold"), background=COLOR_FG).pack(side="left", padx=(10, 6))
        self.scenarios_currency_combo = ttk.Combobox(
            controls, textvariable=self.scenarios_currency_var,
            values=SUPPORTED_CURRENCIES, state="readonly", width=12, style="Kaspa.TCombobox"
        )
        self.scenarios_currency_combo.pack(side="left")
        self.scenarios_currency_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_scenarios())

        ttk.Label(controls, text="Preset:", foreground=COLOR_BG,
                  font=("Segoe UI", 11, "bold"), background=COLOR_FG).pack(side="left", padx=(20, 6))
        self.scenario_preset_var = tk.StringVar(value="Base")
        self.scenario_preset_combo = ttk.Combobox(
            controls, textvariable=self.scenario_preset_var,
            values=["Bear (0.5x)", "Base (1.0x)", "Bull (2.0x)", "Supercycle (5.0x)"],
            state="readonly", width=20, style="Kaspa.TCombobox"
        )
        self.scenario_preset_combo.pack(side="left")
        self.scenario_preset_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_scenarios())

        ttk.Label(controls, text="Supply growth %:", foreground=COLOR_BG,
                  font=("Segoe UI", 11, "bold"), background=COLOR_FG).pack(side="left", padx=(20, 6))
        self.supply_growth_var = tk.StringVar(value="0")
        self.supply_growth_entry = ttk.Entry(controls, style="Kaspa.TEntry", width=8, textvariable=self.supply_growth_var)
        self.supply_growth_entry.pack(side="left")
        self.supply_growth_entry.bind("<KeyRelease>", lambda e: self._refresh_scenarios())

        ttk.Button(controls, text="Apply to Projection", style="KaspaSmall.TButton",
                   command=self._apply_scenario_to_projection).pack(side="right", padx=10)

        columns = ("Scenario", "Price", "Market Cap", "Your Portfolio")
        self.scenarios_tree = ttk.Treeview(wrapper, columns=columns, show="headings", height=18)
        headers = {
            "Scenario": "Scenario",
            "Price": "KAS Price",
            "Market Cap": "KAS Market Cap",
            "Your Portfolio": "Your Portfolio",
        }
        for c in columns:
            self.scenarios_tree.heading(c, text=headers[c])
            self.scenarios_tree.column(c, width=230 if c != "Scenario" else 250, anchor="center")
        self.scenarios_tree.tag_configure("even", background="#212121")
        self.scenarios_tree.tag_configure("odd", background="#1b1b1b")
        self.scenarios_tree.pack(fill="both", expand=True)

    def _refresh_scenarios(self):
        disp_ccy = self.scenarios_currency_var.get().upper() if hasattr(self, 'scenarios_currency_var') else 'USD'
        sym = currency_symbol(disp_ccy)
        if not hasattr(self, 'scenarios_tree'):
            return
        for iid in self.scenarios_tree.get_children():
            self.scenarios_tree.delete(iid)

        # Inputs
        try: kas_hold = float(self.entries["KAS Holdings:"].get().replace(",", ""))
        except Exception: kas_hold = 0.0
        try: price_usd = float(self.entries["Current Price (USD):"].get().replace(",", ""))
        except Exception: price_usd = 0.0
        try:
            supply_b = float(self.entries["Circulating Supply (B):"].get().replace(",", ""))
            circ_supply_kas = supply_b * 1_000_000_000
        except Exception:
            circ_supply_kas = 0.0

        # Preset multiplier
        name = self.scenario_preset_var.get() if hasattr(self, 'scenario_preset_var') else 'Base (1.0x)'
        mult_map = {
            "Bear (0.5x)": 0.5,
            "Base (1.0x)": 1.0,
            "Bull (2.0x)": 2.0,
            "Supercycle (5.0x)": 5.0,
        }
        m = mult_map.get(name, 1.0)
        try:
            supply_growth_pct = float(self.supply_growth_var.get()) if hasattr(self, 'supply_growth_var') else 0.0
        except Exception:
            supply_growth_pct = 0.0

        new_price_usd = price_usd * m
        new_supply = circ_supply_kas * (1.0 + max(-1.0, supply_growth_pct / 100.0))
        new_mcap_usd = new_price_usd * new_supply
        portfolio_usd = kas_hold * new_price_usd

        self.scenarios_tree.insert(
            "", "end",
            values=(
                name,
                fmt_money(sym, usd_to_disp(new_price_usd, disp_ccy)),
                fmt_money(sym, usd_to_disp(new_mcap_usd, disp_ccy), 0),
                fmt_money(sym, usd_to_disp(portfolio_usd, disp_ccy), 0),
            ),
            tags=("even",)
        )

    def _apply_scenario_to_projection(self):
        # Compute scenario first
        try: price_usd = float(self.entries["Current Price (USD):"].get().replace(",", ""))
        except Exception: price_usd = 0.0
        try:
            supply_b = float(self.entries["Circulating Supply (B):"].get().replace(",", ""))
        except Exception:
            supply_b = 0.0
        name = self.scenario_preset_var.get() if hasattr(self, 'scenario_preset_var') else 'Base (1.0x)'
        mult_map = {"Bear (0.5x)": 0.5, "Base (1.0x)": 1.0, "Bull (2.0x)": 2.0, "Supercycle (5.0x)": 5.0}
        m = mult_map.get(name, 1.0)
        try:
            supply_growth_pct = float(self.supply_growth_var.get()) if hasattr(self, 'supply_growth_var') else 0.0
        except Exception:
            supply_growth_pct = 0.0

        new_price_usd = price_usd * m
        new_supply_b = supply_b * (1.0 + max(-1.0, supply_growth_pct / 100.0))

        # Apply into Projection inputs
        try:
            self.entries["Current Price (USD):"].delete(0, tk.END)
            self.entries["Current Price (USD):"].insert(0, f"{new_price_usd:.6f}")
            self.entries["Circulating Supply (B):"].delete(0, tk.END)
            self.entries["Circulating Supply (B):"].insert(0, f"{new_supply_b:.6f}")
            self.update_display_if_valid()
            _toast("Scenario applied to Projection", 1400)
        except Exception:
            messagebox.showerror("Error", "Failed to apply scenario to Projection.")

    # Helpers for comparisons
    def _collect_current_inputs_for_compare(self):
        try: kas_hold = float(self.entries["KAS Holdings:"].get().replace(",", ""))
        except Exception: kas_hold = 0.0
        try: price_usd = float(self.entries["Current Price (USD):"].get().replace(",", ""))
        except Exception: price_usd = 0.0
        try:
            supply_b = float(self.entries["Circulating Supply (B):"].get().replace(",", ""))
            circ_supply_kas = supply_b * 1_000_000_000
        except Exception:
            circ_supply_kas = 0.0
        return kas_hold, price_usd, circ_supply_kas

    def _refresh_comparisons(self):
        d = self.fetched_data or {}
        current_caps: Dict[str, float] = d.get("top_current_caps", {}) or {}
        detail: Dict[str, Dict[str, float]] = d.get("top_detail", {}) or {}

        kas_hold, kas_price_usd, kas_supply = self._collect_current_inputs_for_compare()

        disp_ccy = self.compare_currency_var.get().upper() or "USD"
        sym = currency_symbol(disp_ccy)

        for iid in self.compare_tree.get_children():
            self.compare_tree.delete(iid)

        if not current_caps or kas_supply <= 0:
            self.compare_tree.insert("", "end", values=("No data", "", "", "", "", "", "", ""))
            return

        rows = []
        for coin_id in TOP_COINS:
            ref_cur = float(current_caps.get(coin_id, 0.0))
            info = detail.get(coin_id, {})
            ath_price = float(info.get("ath_price_usd") or 0.0)

            if ref_cur > 0:
                implied_kas_price_usd = ref_cur / kas_supply
                implied_kas_mcap_usd = implied_kas_price_usd * kas_supply
                portfolio_usd = kas_hold * implied_kas_price_usd
                multiple = (implied_kas_price_usd / kas_price_usd) if kas_price_usd > 0 else 0.0
                rows.append({
                    "coin": DISPLAY_NAMES.get(coin_id, coin_id.title()),
                    "type": "Current",
                    "ref_mcap_usd": ref_cur,
                    "implied_price_usd": implied_kas_price_usd,
                    "implied_mcap_usd": implied_kas_mcap_usd,
                    "portfolio_usd": portfolio_usd,
                    "multiple": multiple,
                })

            if ath_price > 0:
                circ_other = float(info.get("circulating_supply") or 0.0)
                if circ_other > 0:
                    ref_ath_proxy = ath_price * circ_other
                    implied_kas_price_usd = ref_ath_proxy / kas_supply
                    implied_kas_mcap_usd = implied_kas_price_usd * kas_supply
                    portfolio_usd = kas_hold * implied_kas_price_usd
                    multiple = (implied_kas_price_usd / kas_price_usd) if kas_price_usd > 0 else 0.0
                    rows.append({
                        "coin": DISPLAY_NAMES.get(coin_id, coin_id.title()),
                        "type": "ATH (proxy)",
                        "ref_mcap_usd": ref_ath_proxy,
                        "implied_price_usd": implied_kas_price_usd,
                        "implied_mcap_usd": implied_kas_mcap_usd,
                        "portfolio_usd": portfolio_usd,
                        "multiple": multiple,
                    })

        for i, r in enumerate(rows):
            tag = "even" if i % 2 == 0 else "odd"
            ref_mcap_disp = fmt_money(sym, usd_to_disp(r["ref_mcap_usd"], disp_ccy), 0)
            implied_price_usd = r["implied_price_usd"]
            implied_price_disp = usd_to_disp(implied_price_usd, disp_ccy)
            implied_mcap_disp = fmt_money(sym, usd_to_disp(r["implied_mcap_usd"], disp_ccy), 0)
            portfolio_disp = fmt_money(sym, usd_to_disp(r["portfolio_usd"], disp_ccy), 0)
            mult_str = f"{r['multiple']:.2f}x" if r["multiple"] > 0 else "N/A"

            self.compare_tree.insert(
                "", "end",
                values=(
                    r["coin"],
                    r["type"],
                    ref_mcap_disp,
                    f"${implied_price_usd:,.6f}",
                    fmt_money(sym, implied_price_disp),
                    implied_mcap_disp,
                    portfolio_disp,
                    mult_str,
                ),
                tags=(tag,),
            )

    def _export_comparisons_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="kaspa_comparisons.csv"
        )
        if not path:
            return
        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([
                    "Reference Coin", "Cap Type", "Reference Market Cap",
                    "Implied KAS Price (USD)", "Implied KAS Price (Display)",
                    "Implied KAS Market Cap (Display)", "Your Portfolio (Display)", "Multiple vs Current"
                ])
                for iid in self.compare_tree.get_children():
                    w.writerow(self.compare_tree.item(iid, "values"))
            messagebox.showinfo("Success", f"CSV exported to {path}.")
        except Exception as e:
            messagebox.showerror("Error", f"CSV export failed: {e}")

    # sorting for comparisons table
    def _sort_compare_table(self, column: str):
        cols = list(self.compare_tree["columns"])
        if column not in cols:
            return
        col_idx = cols.index(column)

        def parse_numeric(val):
            s = str(val).strip()
            if not s or s.upper() == "N/A":
                return (1, 0.0)
            for trash in ["A$", "C$", "NZ$", "HK$", "S$", "NT$", "MX$", "$", "€", "£", "¥",
                          "₩", "R$", "R", "₺", "zł", "฿", "Rp", "RM", "₱", "₪", "د.إ", "ر.س", "₽"]:
                s = s.replace(trash, "")
            s = s.replace(",", "").strip()
            if s.endswith("x"):
                s = s[:-1]
            try:
                return (0, float(s))
            except Exception:
                return (1, 0.0)

        numeric_columns = {
            "Ref MCap",
            "Implied KAS Price",
            "Implied KAS Price (Disp)",
            "Implied KAS MCap",
            "Your Portfolio",
            "Multiple vs Current",
        }

        items = [(self.compare_tree.item(iid)["values"], iid) for iid in self.compare_tree.get_children()]
        if column in numeric_columns:
            key_fn = lambda values: parse_numeric(values[col_idx])
        else:
            key_fn = lambda values: (0, str(values[col_idx]))

        reverse = self._compare_sort_state.get(column, False)
        items.sort(key=lambda x: key_fn(x[0]), reverse=reverse)
        self._compare_sort_state[column] = not reverse

        for i, (_, iid) in enumerate(items):
            self.compare_tree.move(iid, "", i)

# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = KaspaPortfolioApp(root)
    root.mainloop()