#!/usr/bin/env python3
# Kaspa Portfolio Projector (KPP) — v1.0.0 (status-bar + headings edition)

"""
Kaspa Portfolio Projector (KPP)
===============================

A Tkinter-based desktop application for projecting and analyzing the value of a Kaspa (KAS) portfolio
across varying market prices and market capitalizations. Provides real-time data fetching from CoinGecko
and exchange rate APIs, dynamic currency conversion, and export capabilities for PDF and CSV reports.

Key Features
------------
- **Automated Data Fetching**
  - Retrieves current KAS price, circulating supply, Bitcoin market cap, and FX rates on startup.
  - Safe API calls with timeouts, caching, and graceful fallback handling.

- **Interactive Projection Table**
  - Displays portfolio value and market cap for a range of KAS prices.
  - Optional columns for Market Cap vs. Bitcoin and percentage change.
  - Clickable cells for quick copy to clipboard.

- **KAS Price Slider Panel**
  - Allows exploration of portfolio value at arbitrary KAS prices.
  - Supports slider input or direct price entry.
  - Synchronized with portfolio inputs for instant updates.

- **Portfolio Metrics Summary**
  - Current holdings, value, market cap, and required metrics for a $1M portfolio.
  - Currency conversion support for multiple fiat currencies.

- **Export & Reporting**
  - Generate professionally formatted PDF reports.
  - Export projection table to CSV.

- **Enhanced UI/UX**
  - Modern dark-themed interface styled for readability.
  - Centered, clearly labeled section headers.
  - Full-width status bar with progress indicator for background tasks.
  - Inputs disabled during long-running operations to prevent conflicts.

Dependencies
------------
- Python 3.10+
- Tkinter (bundled with Python)
- `pandas` for data handling
- `reportlab` for PDF generation
- `pycoingecko` for CoinGecko API integration
- `requests` for FX rate retrieval

Author
------
Developed by the Kaspa community. Enhanced with automated data syncing, improved UX,
and robust background task handling as of this version.
"""


import os
import sys
import logging
import threading
from functools import lru_cache
from datetime import datetime, timezone
from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd
from fpdf import FPDF

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from PIL import Image, ImageTk, ImageColor
from pycoingecko import CoinGeckoAPI
import sv_ttk
import requests
import time

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("KPP")

# -----------------------------------------------------------------------------
# Paths / Resources
# -----------------------------------------------------------------------------
def resource_path(relative_path: str) -> str:
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

VERSION = "1.0.0"

# Colors and UI constants
COLOR_BG = "#70C7BA"        # Teal accent
COLOR_FG = "#231F20"        # Dark card
CHECKMARK_COLOR = "#00e676"
X_MARK_COLOR = "#ff6b6b"
BUTTON_BG = "#00C4B4"
BUTTON_FG = "#FFFFFF"

LOGO_PATH = resource_path(os.path.join("pics", "Kaspa-LDSP-Dark-Reverse.png"))
LOGO_PATH_LIGHT = resource_path(os.path.join("pics", "Kaspa-LDSP-Dark-Full-Color.png"))
ICON_PATH = resource_path(os.path.join("pics", "kaspa.ico"))

PLACEHOLDERS = {
    "Portfolio Name:": "e.g., My Kaspa Holdings",
    "KAS Holdings:": "e.g., 1367",
    "Current Price (USD):": "e.g., 0.2711 (or press Fetch Data)",
    "Circulating Supply (B):": "e.g., 25.6 (or press Fetch Data)",
}
DEFAULTS = {"Portfolio Name:": "", "KAS Holdings:": "0", "Current Price (USD):": "", "Circulating Supply (B):": ""}
NUMERIC_FIELDS = ["KAS Holdings:", "Current Price (USD):", "Circulating Supply (B):"]

# FX defaults used until/if live rates arrive
EXCHANGE_RATES = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79, "JPY": 149.50, "AUD": 1.55}
CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "AUD": "A$"}

def currency_symbol(code: str) -> str:
    return CURRENCY_SYMBOLS.get(code.upper(), "$")

def fmt_money(symbol: str, value: float, decimals: int = 2) -> str:
    return f"{symbol}{value:,.{decimals}f}"

def usd_to_disp(value_usd: float, currency: str) -> float:
    return value_usd * EXCHANGE_RATES.get(currency.upper(), 1.0)

def disp_to_usd(value_disp: float, currency: str) -> float:
    rate = EXCHANGE_RATES.get(currency.upper(), 1.0)
    return value_disp / rate if rate else 0.0

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
    """Large, distinct section header with an accent underline."""
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
# API helpers
# -----------------------------------------------------------------------------
def fetch_fx_rates(retries: int = 2, timeout: int = 8) -> Dict[str, Any]:
    fetched_at = datetime.now(timezone.utc).isoformat()
    source = "exchangerate.host/latest (base=USD)"
    params = {"base": "USD", "symbols": "USD,EUR,GBP,JPY,AUD"}
    for attempt in range(retries + 1):
        try:
            r = requests.get("https://api.exchangerate.host/latest", params=params, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            rates = data.get("rates", {})
            out = {k: float(rates.get(k, EXCHANGE_RATES[k])) for k in ["USD", "EUR", "GBP", "JPY", "AUD"]}
            for k, v in out.items():
                if v <= 0: out[k] = EXCHANGE_RATES[k]
            return {"rates": out, "fetched_at": fetched_at, "source": source}
        except Exception as e:
            logger.warning(f"FX fetch attempt {attempt+1} failed: {e}")
            if attempt < retries:
                time.sleep(0.5)
    return {"rates": EXCHANGE_RATES.copy(), "fetched_at": fetched_at, "source": source + " (fallback used)"}

def _safe_get(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as e:
        logger.warning(f"pycoingecko call failed: {e}")
        return None

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
def generate_portfolio_pdf(df, filename, title, kas_amount, current_price_usd,
                           circ_supply_b, currency, btc_market_cap, progress_cb=None):
    formatted_title = (title.capitalize() + " Portfolio Projection") if title else "Unnamed Portfolio Projection"
    rate = EXCHANGE_RATES.get(currency.upper(), 1.0)
    sym = currency_symbol(currency)

    circ_supply = circ_supply_b * 1_000_000_000
    market_cap = current_price_usd * circ_supply * rate
    portfolio_value = kas_amount * current_price_usd * rate

    price_needed_for_1m_usd = 1_000_000 / kas_amount if kas_amount > 0 else 0
    mcap_needed_for_1m_usd = price_needed_for_1m_usd * circ_supply
    mcap_needed_for_1m = mcap_needed_for_1m_usd * rate
    btc_mcap_cur = (btc_market_cap or 0) * rate
    ratio = (mcap_needed_for_1m_usd / btc_market_cap) if btc_market_cap else 0

    pdf = FPDF()
    pdf.set_auto_page_break(auto=False, margin=12)
    pdf.add_page()
    try: pdf.image(LOGO_PATH_LIGHT, x=10, y=6, w=50)
    except Exception: pass

    pdf.set_font("Helvetica", "B", 22)
    title_w = pdf.get_string_width(formatted_title)
    pdf.set_xy(200 - title_w - 10, 10); pdf.cell(0, 10, formatted_title, ln=True, align="R")

    pdf.set_font("Helvetica", "", 7)
    sub = "Generated by Kaspa Portfolio Projector (KPP)"
    sub_w = pdf.get_string_width(sub)
    pdf.set_xy(200 - sub_w - 10, 20); pdf.cell(0, 5, sub, ln=True, align="R")

    date = datetime.now(timezone.utc).strftime("%B %d, %Y")
    date_w = pdf.get_string_width(date)
    pdf.set_xy(200 - date_w - 10, 25); pdf.cell(0, 5, date, ln=True, align="R")

    pdf.set_draw_color(150, 150, 150); pdf.line(10, 30, 200, 30); pdf.ln(10)

    pdf.set_text_color(20, 20, 20)
    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 8, "Portfolio Facts", ln=True); pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)

    def mm(v): return f"{sym}{v:,.2f}"
    summary = (
        f"The {title or 'Unnamed'} Kaspa portfolio holds {kas_amount:,.2f} KAS. "
        f"Current portfolio value: {mm(portfolio_value)}. "
        f"Kaspa market cap: {mm(market_cap)}. "
        f"To reach a $1M portfolio: KAS price {mm(price_needed_for_1m_usd*rate)} "
        f"and market cap {mm(mcap_needed_for_1m)} "
        f"(~{ratio:.2f} × current Bitcoin market cap of {mm(btc_mcap_cur)})."
    )
    pdf.multi_cell(0, 5, summary); pdf.ln(4)

    header_bg = (230, 230, 230)
    row_fill_a = (248, 248, 248)
    row_fill_b = (255, 255, 255)
    text_norm = (20, 20, 20)
    red = (200, 0, 0); green = (0, 140, 70); black = text_norm

    def table_header():
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_fill_color(*header_bg); pdf.set_text_color(*text_norm)
        pdf.cell(63, 8, f"Price ({currency.upper()})", border=1, align="C", fill=True)
        pdf.cell(63, 8, f"Portfolio ({currency.upper()})", border=1, align="C", fill=True)
        pdf.cell(63, 8, f"Market Cap ({currency.upper()})", border=1, align="C", fill=True)
        pdf.ln()
        pdf.set_font("Helvetica", "", 10)

    def page_break_if_needed():
        if pdf.get_y() > 265:
            pdf.add_page(); table_header()

    table_header()
    total = len(df)
    for i, (_, row) in enumerate(df.iterrows(), 1):
        page_break_if_needed()
        fill_color = row_fill_a if i % 2 == 0 else row_fill_b
        pdf.set_fill_color(*fill_color)
        color = red if row["Color"] == "red" else green if row["Color"] == "green" else black
        pdf.set_text_color(*color)
        pdf.cell(63, 8, f"{sym}{row['Price']:,.2f}", border=1, align="C", fill=True)
        pdf.set_text_color(*text_norm)
        pdf.cell(63, 8, f"{sym}{row['Portfolio']:,.2f}", border=1, align="C", fill=True)
        pdf.cell(63, 8, f"{sym}{row['Market Cap']:,.2f}", border=1, align="C", fill=True)
        pdf.ln()
        if progress_cb and total:
            progress_cb(i * 100.0 / total)

    pdf.set_y(-10); pdf.set_text_color(0, 0, 0); pdf.set_font("Helvetica", "", 7)
    pdf.cell(0, 5, "Generated by Kaspa Portfolio Projector (KPP)", 0, 0, "C")
    pdf.output(filename)

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
        self._debounce_after = None
        self.fetched_data: Dict[str, Any] = {}
        self._sort_state: Dict[str, bool] = {}

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
                self.header_canvas.create_image(12, h // 2, image=self.logo_img, anchor="w")
            rx = w - 12
            self.header_canvas.create_text(rx, 38, text="Kaspa Portfolio Projector",
                                           fill="#FFFFFF", font=("Segoe UI", 30, "bold"), anchor="e")
            self.header_canvas.create_text(rx, 70, text=f"Developed by the Kaspa community | Version {VERSION}",
                                           fill="#E6E6E6", font=("Segoe UI", 10), anchor="e")
        self.header_canvas.bind("<Configure>", _redraw_header)

        self.header_line = tk.Frame(root, height=10, bg=COLOR_BG, bd=0, highlightthickness=0)
        self.header_line.pack(fill="x")

        # Layout columns
        self.content_frame = tk.Frame(root, bg="#121212"); self.content_frame.pack(fill="both", expand=True)
        self.right_frame = card_frame(self.content_frame, padx=20, pady=10, width=320)
        self.right_frame.pack(side="right", fill="y", padx=(5, 10), pady=(0, 10)); self.right_frame.pack_propagate(False)
        self.left_frame = tk.Frame(self.content_frame, bg="#121212")
        self.left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.main_frame = tk.Frame(self.left_frame, bg="#121212", padx=10, pady=0)
        self.main_frame.pack(fill="both", expand=True)

        # Status bar
        self.status_bar = tk.Frame(self.left_frame, bg="#1b1b1b")
        self.status_label = ttk.Label(self.status_bar, text="", background="#1b1b1b", foreground="#eaeaea")
        self.status_label.pack(side="left", padx=10, pady=4)
        self.status_progress = ttk.Progressbar(self.status_bar, mode="indeterminate", length=180)
        self.status_progress.pack(side="right", padx=10, pady=4)
        self.status_bar.pack_forget()

        # Input + metrics container
        self.input_frame = card_frame(self.main_frame, padx=20, pady=10); self.input_frame.pack(fill="x", padx=0)
        self.input_subframe = tk.Frame(self.input_frame, bg=COLOR_FG, padx=10, pady=10)
        self.input_subframe.pack(side="left", fill="both", expand=True)
        self.metrics_subframe = tk.Frame(self.input_frame, bg=COLOR_FG, padx=10, pady=10)
        self.metrics_subframe.pack(side="right", fill="both", expand=True)

        # Section headers (improved)
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

        # Inputs
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

        # Currency
        currency_row = len(PLACEHOLDERS) + start_row
        ttk.Label(self.input_subframe, text="Currency:", foreground=COLOR_BG,
                  font=("Segoe UI", 12, "bold"), background=COLOR_FG)\
            .grid(row=currency_row, column=0, padx=10, pady=8, sticky="w")
        currency_frame = tk.Frame(self.input_subframe, bg=COLOR_FG)
        currency_frame.grid(row=currency_row, column=1, padx=10, pady=8, sticky="e")
        self.currency_var = tk.StringVar(value="USD")
        self.currency_combo = ttk.Combobox(currency_frame, textvariable=self.currency_var,
                                           values=["USD", "EUR", "GBP", "JPY", "AUD"],
                                           state="readonly", style="Kaspa.TCombobox", width=12)
        self.currency_combo.grid(row=0, column=0, padx=5)
        self.currency_combo.bind("<<ComboboxSelected>>", self.update_display_on_currency_change)
        ttk.Label(currency_frame, text="✔", foreground=CHECKMARK_COLOR,
                  font=("Segoe UI", 12, "bold"), background=COLOR_FG).grid(row=0, column=1, padx=5)

        # Buttons (PDF / Fetch / CSV ; Help / Pulled)
        button_row = currency_row + 1
        self.btn_pdf = self.create_button("Generate PDF", self.generate_pdf, button_row, 0, small=False)
        self.btn_fetch = self.create_button("Fetch Real Time Data", self.fetch_data, button_row, 1, small=False)
        self.btn_csv = self.create_button("Export CSV", self.export_csv, button_row, 2, small=False)

        self.create_button("Help", self.show_help, button_row + 1, 0, small=True)
        self.create_button("Show Pulled Data", self.show_pulled_data, button_row + 1, 1, small=True)

        # Metrics labels/fields
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

        # Display / table
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

        # Right column (slider + readouts)
        section_title(self.right_frame, "Price Explorer (USD)").pack(fill="x", pady=(0, 5))

        self.slider_top_frame = tk.Frame(self.right_frame, bg=COLOR_FG)
        self.slider_top_frame.pack(fill="x", pady=2)

        self.slider_price_label = tk.Label(self.slider_top_frame, text="$0.01",
                                           bg=COLOR_FG, fg=COLOR_BG, font=("Segoe UI", 12, "bold"),
                                           width=12, anchor="w")
        self.slider_price_label.pack(side="left", padx=10)

        self.slider_input_var = tk.StringVar(value="Use Slider")
        # widened so "Use Slider" text is fully visible
        self.slider_input_menu = ttk.Combobox(self.slider_top_frame, textvariable=self.slider_input_var,
                                              values=["Use Slider", "Enter Custom Price"],
                                              state="readonly", width=24, style="Kaspa.Big.TCombobox")
        self.slider_input_menu.pack(side="right", padx=10)
        self.slider_input_menu.bind("<<ComboboxSelected>>",
                                    lambda e: self.toggle_slider_input(self.slider_input_var.get()))

        self.slider_price_entry = ttk.Entry(self.slider_top_frame, style="Kaspa.TEntry", width=16)
        self.slider_price_entry.pack(side="right", padx=10); self.slider_price_entry.pack_forget()
        self.slider_price_entry.bind("<Return>", self.update_slider_from_entry)

        self.slider_var = tk.DoubleVar(value=0)
        self.slider = ttk.Scale(self.right_frame, from_=100, to=0, orient="vertical",
                                variable=self.slider_var, length=550, style="Kaspa.Vertical.TScale",
                                command=self.update_slider_values)
        try: self.slider.configure(takefocus=0)
        except Exception: pass
        self.slider.bind("<FocusIn>", lambda e: self.right_frame.focus_set())
        self.slider.pack(fill="y", expand=False, pady=10)

        self.values_frame = tk.Frame(self.right_frame, bg=COLOR_FG); self.values_frame.pack(fill="x", pady=10)
        ttk.Label(self.values_frame, text="Portfolio Value:", foreground=COLOR_BG,
                  font=("Segoe UI", 12, "bold"), background=COLOR_FG).pack(anchor="w", padx=10)
        self.portfolio_value_entry = ttk.Entry(self.values_frame, style="Kaspa.TEntry", width=30)
        self.portfolio_value_entry.state(["readonly"]); self.portfolio_value_entry.pack(fill="x", padx=10, pady=(0, 8))

        ttk.Label(self.values_frame, text="KAS Market Cap:", foreground=COLOR_BG,
                  font=("Segoe UI", 12, "bold"), background=COLOR_FG).pack(anchor="w", padx=10)
        self.market_cap_entry = ttk.Entry(self.values_frame, style="Kaspa.TEntry", width=30)
        self.market_cap_entry.state(["readonly"]); self.market_cap_entry.pack(fill="x", padx=10)

        # Initial data pull (includes FX)
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
        try:
            self.status_progress.stop()
        except Exception:
            pass
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

    # ---- API plumbing ----
    @staticmethod
    @lru_cache(maxsize=1)
    def fetch_api_data():
        out: Dict[str, Any] = {}
        fx_info = fetch_fx_rates()
        out["fx_rates"] = fx_info["rates"]
        out["fx_fetched_at"] = fx_info["fetched_at"]
        out["fx_source"] = fx_info["source"]

        try:
            cg = CoinGeckoAPI()
            price = _safe_get(cg.get_price, ids="kaspa", vs_currencies="usd")
            supply = _safe_get(cg.get_coin_by_id, id="kaspa")
            btc = _safe_get(cg.get_price, ids="bitcoin", vs_currencies="usd", include_market_cap=True)
            nowz = datetime.now(timezone.utc).isoformat()
            if price and "kaspa" in price:
                out["kaspa_price"] = float(price["kaspa"]["usd"])
            if supply and "market_data" in supply:
                out["kaspa_supply"] = float(supply["market_data"]["circulating_supply"])
            if btc and "bitcoin" in btc:
                out["btc_market_cap"] = float(btc["bitcoin"]["usd_market_cap"])
            out["coingecko_fetched_at"] = nowz
            out["coingecko_source"] = "CoinGecko API"
        except Exception as e:
            logger.error(f"CoinGecko fetch failed: {e}")
        return out

    def fetch_data_on_startup(self):
        self.start_status("Fetching data (FX + CoinGecko)…")
        self._toggle_inputs(True)
        def _worker():
            data = self.fetch_api_data()
            def _apply():
                try:
                    self.set_status("Applying data to UI…")
                    if data.get("fx_rates"):
                        EXCHANGE_RATES.update(data["fx_rates"])
                    if "kaspa_price" in data:
                        self.entries["Current Price (USD):"].delete(0, tk.END)
                        self.entries["Current Price (USD):"].insert(0, f"{data['kaspa_price']:.4f}")
                        try: self.entries["Current Price (USD):"].configure(foreground="#e8e8e8")
                        except Exception: pass
                    if "kaspa_supply" in data:
                        self.entries["Circulating Supply (B):"].delete(0, tk.END)
                        self.entries["Circulating Supply (B):"].insert(0, f"{data['kaspa_supply'] / 1_000_000_000:.4f}")
                        try: self.entries["Circulating Supply (B):"].configure(foreground="#e8e8e8")
                        except Exception: pass
                    for fld in ["Current Price (USD):", "Circulating Supply (B):"]:
                        self.updated_fields[fld] = True; self.show_check_mark(fld); self.hide_x_mark(fld)

                    if self.entries["KAS Holdings:"].get().strip() in [PLACEHOLDERS["KAS Holdings:"], DEFAULTS["KAS Holdings:"], ""]:
                        self.entries["KAS Holdings:"].delete(0, tk.END); self.entries["KAS Holdings:"].insert(0, "0")

                    self.fetched_data = data
                    self.slider_var.set(0)
                    self.update_slider_values()
                    self.update_display_if_valid()
                finally:
                    self.end_status()
                    self._toggle_inputs(False)
            self.root.after(0, _apply)
        threading.Thread(target=_worker, daemon=True).start()

    def fetch_data(self):
        self.start_status("Refreshing data (FX + CoinGecko)…")
        self._toggle_inputs(True)
        def _worker():
            data: Dict[str, Any] = {}
            fx_info = fetch_fx_rates()
            data.update({"fx_rates": fx_info["rates"], "fx_fetched_at": fx_info["fetched_at"], "fx_source": fx_info["source"]})
            try:
                cg = CoinGeckoAPI()
                kaspa_price = _safe_get(cg.get_price, ids="kaspa", vs_currencies="usd")
                kaspa_supply = _safe_get(cg.get_coin_by_id, id="kaspa")
                btc = _safe_get(cg.get_price, ids="bitcoin", vs_currencies="usd", include_market_cap=True)
                nowz = datetime.now(timezone.utc).isoformat()
                if kaspa_price and "kaspa" in kaspa_price:
                    data["kaspa_price"] = float(kaspa_price["kaspa"]["usd"])
                if kaspa_supply and "market_data" in kaspa_supply:
                    data["kaspa_supply"] = float(kaspa_supply["market_data"]["circulating_supply"])
                if btc and "bitcoin" in btc:
                    data["btc_market_cap"] = float(btc["bitcoin"]["usd_market_cap"])
                data["coingecko_fetched_at"] = nowz
                data["coingecko_source"] = "CoinGecko API"
            except Exception as e:
                logger.error(f"CoinGecko fetch failed: {e}")

            def _apply():
                try:
                    if not data:
                        raise Exception("No data fetched")
                    if data.get("fx_rates"):
                        EXCHANGE_RATES.update(data["fx_rates"])
                    self.fetched_data = data

                    if "kaspa_price" in data:
                        self.entries["Current Price (USD):"].delete(0, tk.END)
                        self.entries["Current Price (USD):"].insert(0, f"{data['kaspa_price']:.4f}")
                    if "kaspa_supply" in data:
                        self.entries["Circulating Supply (B):"].delete(0, tk.END)
                        self.entries["Circulating Supply (B):"].insert(0, f"{data['kaspa_supply'] / 1_000_000_000:.4f}")
                    for field in ["Current Price (USD):", "Circulating Supply (B):"]:
                        self.updated_fields[field] = True; self.show_check_mark(field); self.hide_x_mark(field)

                    if self.entries["KAS Holdings:"].get().strip() in [PLACEHOLDERS["KAS Holdings:"], DEFAULTS["KAS Holdings:"], ""] :
                        self.entries["KAS Holdings:"].delete(0, tk.END); self.entries["KAS Holdings:"].insert(0, "0")

                    self.slider_var.set(0)
                    self.update_slider_values()
                    self.update_display_if_valid()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to fetch data: {e}")
                finally:
                    self.end_status()
                    self._toggle_inputs(False)
            self.root.after(0, _apply)
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
        win.title("Pulled Data (APIs)"); win.geometry("680x560")
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
        cg_time = d.get("coingecko_fetched_at", "n/a")
        cg_src = d.get("coingecko_source", "CoinGecko API")

        def line(s=""): txt.insert("end", s + "\n")

        line("=== Exchange Rates (base USD) ===")
        for k in ["USD", "EUR", "GBP", "JPY", "AUD"]:
            line(f"  {k}: {fx.get(k, 'n/a')}")
        line(f"  fetched_at: {fx_time}")
        line(f"  source    : {fx_src}")
        line()

        line("=== CoinGecko ===")
        if "kaspa_price" in d: line(f"  KAS price (USD): {d['kaspa_price']}")
        if "kaspa_supply" in d: line(f"  KAS circulating supply: {d['kaspa_supply']:,.0f}")
        if "btc_market_cap" in d: line(f"  BTC market cap (USD): {d['btc_market_cap']:,.0f}")
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
        if self._debounce_after: self.root.after_cancel(self._debounce_after)
        self._debounce_after = self.root.after(200, lambda: self.update_field_and_check(event.widget))

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

            # NEW: also refresh the slider panel to current inputs
            self.update_slider_values()

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
            if column in ["Price", "Portfolio", "MarketCap"]:
                s = str(val).replace("A$", "").replace("$", "").replace("€", "").replace("£", "").replace("¥", "")
                try:
                    v = float(s.replace(",", "") or 0.0)
                except Exception:
                    v = 0.0
                return (0, v)
            if column == "Market Cap vs. BTC":
                if val in ("", "N/A"): return (1, 0.0)
                try:
                    return (0, float(val))
                except Exception:
                    return (1, 0.0)
            if column == "Change":
                try:
                    return (0, float(str(val).split("x")[0]))
                except Exception:
                    return (1, 0.0)
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
            entered = float(self.slider_price_entry.get().replace("$", "").replace(",", ""))
        except ValueError:
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
                price_num = float(str(price_str).replace("A$", "").replace("$", "").replace("€", "")
                                  .replace("£", "").replace("¥", "").replace(",", "") or 0.0)
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
                # Simple staged updates to show progress
                total_steps = 3
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

    def show_check_mark(self, label):
        self.check_marks[label].grid(); self.x_marks[label].grid_remove()
    def hide_check_mark(self, label):
        self.check_marks[label].grid_remove()
    def show_x_mark(self, label):
        self.x_marks[label].grid(); self.check_marks[label].grid_remove()
    def hide_x_mark(self, label):
        self.x_marks[label].grid_remove()

# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = KaspaPortfolioApp(root)
    root.mainloop()
