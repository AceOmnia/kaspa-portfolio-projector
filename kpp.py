import pandas as pd
from fpdf import FPDF
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import os
import sys
from pycoingecko import CoinGeckoAPI
import logging
from functools import lru_cache
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Resource path handling for PyInstaller
def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# Constants
LOGO_PATH = resource_path(r"pics\Kaspa-LDSP-Dark-Reverse.png")
LOGO_PATH_LIGHT = resource_path(r"pics\Kaspa-LDSP-Dark-Full-Color.png")
ICON_PATH = resource_path(r"pics\kaspa.ico")
VERSION = "0.4.0"  # Changed from 0.3.3 to 0.4.0
COLOR_BG = "#70C7BA"  # Teal (used for borders)
COLOR_FG = "#231F20"  # Dark gray
COLOR_TOP_BG = "#231F20"  # Matches lower dark area
CHECKMARK_COLOR = "#006600"  # Green
X_MARK_COLOR = "#FF0000"  # Red for the "X"
BUTTON_BG = "#00C4B4"  # Cyan
BUTTON_FG = "#000000"  # Black

PLACEHOLDERS = {
    "Portfolio Name:": "e.g., My Kaspa Holdings",
    "KAS Holdings:": "e.g., 1367",
    "Current Price (USD):": "e.g., 0.2711 (or press Fetch Data)",
    "Circulating Supply (B):": "e.g., 25.6 (or press Fetch Data)"
}

DEFAULTS = {
    "Portfolio Name:": "",
    "KAS Holdings:": "0",
    "Current Price (USD):": "",
    "Circulating Supply (B):": ""
}

NUMERIC_FIELDS = ["KAS Holdings:", "Current Price (USD):", "Circulating Supply (B):"]
EXCHANGE_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "JPY": 149.50,
    "AUD": 1.55
}


# Generate price intervals for projection
def generate_price_intervals(current_price, min_price=0.01, max_price=1000):
    rounded_cent = round(current_price, 2)
    red_intervals = np.linspace(min_price, rounded_cent - 0.01, num=9).tolist()
    black_interval = [rounded_cent]
    green_intervals = np.geomspace(rounded_cent + 0.01, max_price, num=240).tolist()
    return sorted(set(round(price, 2) for price in (red_intervals + black_interval + green_intervals)))


# Generate portfolio projection data
def generate_portfolio_projection(kaspa_amount, current_price, circulating_supply_billion, currency):
    circulating_supply = circulating_supply_billion * 1_000_000_000
    price_intervals_usd = generate_price_intervals(current_price)  # Generate intervals in USD
    rate = EXCHANGE_RATES.get(currency.upper(), 1.0)
    symbol = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "AUD": "A$"}.get(currency.upper(), "$")

    # Determine colors based on USD prices
    colors = ["red" if price < round(current_price, 2) else "black" if price == round(current_price, 2) else "green" for
              price in price_intervals_usd]

    # Convert price intervals to selected currency for display
    price_intervals_display = [round(price * rate, 2) for price in price_intervals_usd]

    # Calculate portfolio values and market caps
    portfolio_values = [kaspa_amount * price * rate for price in price_intervals_usd]
    market_caps = [circulating_supply * price * rate for price in price_intervals_usd]

    # Find the index of the black price
    black_idx = colors.index("black")
    black_display_price = price_intervals_display[black_idx]

    if currency.upper() != "USD":
        # Handle red section
        red_indices = list(range(black_idx))
        red_data = [
            (price_intervals_display[i], price_intervals_usd[i], portfolio_values[i], market_caps[i], colors[i])
            for i in red_indices
        ]
        red_data.sort(key=lambda x: (x[0], x[1]))
        seen = {}
        deduplicated_red_data = []
        for data in red_data:
            display_price = data[0]
            if display_price not in seen:
                seen[display_price] = data
                deduplicated_red_data.append(data)
        if deduplicated_red_data and deduplicated_red_data[-1][0] == black_display_price:
            deduplicated_red_data.pop()
        red_display_prices = [data[0] for data in deduplicated_red_data]
        red_usd_prices = [data[1] for data in deduplicated_red_data]
        red_portfolio_values = [data[2] for data in deduplicated_red_data]
        red_market_caps = [data[3] for data in deduplicated_red_data]
        red_colors = [data[4] for data in deduplicated_red_data]

        # Handle green section
        green_indices = list(range(black_idx + 1, len(price_intervals_usd)))
        green_data = [
            (price_intervals_display[i], price_intervals_usd[i], portfolio_values[i], market_caps[i], colors[i])
            for i in green_indices
        ]
        green_data.sort(key=lambda x: (x[0], x[1]))
        seen = {}
        deduplicated_green_data = []
        for data in green_data:
            display_price = data[0]
            if display_price not in seen:
                seen[display_price] = data
                deduplicated_green_data.append(data)
        if deduplicated_green_data and deduplicated_green_data[0][0] == black_display_price:
            deduplicated_green_data.pop(0)
        green_display_prices = [data[0] for data in deduplicated_green_data]
        green_usd_prices = [data[1] for data in deduplicated_green_data]
        green_portfolio_values = [data[2] for data in deduplicated_green_data]
        green_market_caps = [data[3] for data in deduplicated_green_data]
        green_colors = [data[4] for data in deduplicated_green_data]

        # Reconstruct the full data
        final_display_prices = red_display_prices + [price_intervals_display[black_idx]] + green_display_prices
        final_usd_prices = red_usd_prices + [price_intervals_usd[black_idx]] + green_usd_prices
        final_portfolio_values = red_portfolio_values + [portfolio_values[black_idx]] + green_portfolio_values
        final_market_caps = red_market_caps + [market_caps[black_idx]] + green_market_caps
        final_colors = red_colors + [colors[black_idx]] + green_colors

        data = {
            "Price": final_display_prices,
            "Price_USD": final_usd_prices,
            "Portfolio": final_portfolio_values,
            "Market Cap": final_market_caps,
            "Color": final_colors
        }
    else:
        data = {
            "Price": price_intervals_display,
            "Price_USD": price_intervals_usd,
            "Portfolio": portfolio_values,
            "Market Cap": market_caps,
            "Color": colors
        }
    return pd.DataFrame(data), symbol


# Generate PDF report
def generate_portfolio_pdf(df, filename, title, kaspa_amount, current_price, circulating_supply_billion, currency,
                           btc_market_cap):
    formatted_title = title.capitalize() + " Portfolio Projection" if title else "Unnamed Portfolio Projection"
    pdf = FPDF()
    pdf.add_page()
    pdf.image(LOGO_PATH_LIGHT, x=10, y=6, w=50)
    pdf.set_font("Helvetica", 'B', 22)
    title_width = pdf.get_string_width(formatted_title)
    pdf.set_xy(200 - title_width - 10, 10)
    pdf.cell(0, 10, formatted_title, ln=True, align='R')
    pdf.set_font("Helvetica", '', 7)
    subtitle_width = pdf.get_string_width("Generated by Kaspa Portfolio Projector (KPP)")
    pdf.set_xy(200 - subtitle_width - 10, 20)
    pdf.cell(0, 5, "Generated by Kaspa Portfolio Projector (KPP)", ln=True, align='R')
    current_date = datetime.now().strftime("%B %d, %Y")
    date_width = pdf.get_string_width(current_date)
    pdf.set_xy(200 - date_width - 10, 25)
    pdf.cell(0, 5, current_date, ln=True, align='R')
    pdf.set_draw_color(128, 128, 128)
    pdf.line(10, 30, 200, 30)
    pdf.ln(10)
    pdf.set_font("Helvetica", 'B', 14)
    pdf.cell(0, 8, "Portfolio Facts", ln=True)
    pdf.ln(4)
    circulating_supply = circulating_supply_billion * 1_000_000_000
    rate = EXCHANGE_RATES.get(currency.upper(), 1.0)
    symbol = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "AUD": "A$"}.get(currency.upper(), "$")
    market_cap = current_price * circulating_supply * rate
    portfolio_value = kaspa_amount * current_price * rate
    price_needed_for_1m = 1_000_000 / kaspa_amount if kaspa_amount > 0 else 0
    market_cap_needed_for_1m = price_needed_for_1m * circulating_supply
    btc_market_cap_in_currency = btc_market_cap * rate
    market_cap_ratio = market_cap_needed_for_1m / btc_market_cap if btc_market_cap > 0 else 0
    summary = (
        f"The {formatted_title[:-21]} Kaspa portfolio, holding {kaspa_amount:,.2f} KAS with a current portfolio "
        f"value of {symbol}{portfolio_value:,.2f} and a KAS market cap of {symbol}{market_cap:,.2f}, "
        f"would require a KAS price of {symbol}{price_needed_for_1m:,.2f} and a market cap of "
        f"{symbol}{market_cap_needed_for_1m:,.2f} - approximately {market_cap_ratio:.2f} times the "
        f"current Bitcoin market cap of {symbol}{btc_market_cap_in_currency:,.2f} - to reach a $1M valuation."
    )
    pdf.set_font("Helvetica", '', 10)
    pdf.multi_cell(0, 5, summary)
    pdf.ln(5)
    pdf.set_font("Helvetica", '', 11)
    for label, value in [
        ("Current KAS Price:", f"{symbol}{current_price:.4f}"),
        ("Current KAS Holdings:", f"{kaspa_amount:,.2f} KAS"),
        ("Current KAS Portfolio Value:", f"{symbol}{portfolio_value:,.2f}"),
        ("Current KAS Market Cap:", f"{symbol}{market_cap:,.2f}"),
        ("KAS Price Needed for $1M Portfolio:", f"{symbol}{price_needed_for_1m:,.2f}"),
        ("KAS Market Cap Needed for $1M Portfolio:", f"{symbol}{market_cap_needed_for_1m:,.2f}")
    ]:
        pdf.cell(90, 6, label, ln=False)
        pdf.cell(0, 6, value, ln=True, align='R')
    pdf.ln(5)
    pdf.set_font("Helvetica", 'B', 11)
    pdf.set_fill_color(230, 230, 230)
    for header in [f"Price ({currency})", f"Portfolio ({currency})", f"Market Cap ({currency})"]:
        pdf.cell(63, 8, header, border=1, align='C', fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", '', 10)
    for _, row in df.iterrows():
        pdf.set_text_color(*{"red": (255, 0, 0), "black": (0, 0, 0), "green": (0, 128, 0)}[row["Color"]])
        pdf.cell(63, 8, f"{symbol}{row['Price']:.2f}", border=1, align='C')
        pdf.cell(63, 8, f"{symbol}{row['Portfolio']:,.2f}", border=1, align='C')
        pdf.cell(63, 8, f"{symbol}{row['Market Cap']:,.2f}", border=1, align='C')
        pdf.ln()
    pdf.set_y(-10)
    pdf.set_font("Helvetica", '', 7)
    pdf.cell(0, 5, "Generated by Kaspa Portfolio Projector (KPP)", 0, 0, 'C')
    pdf.output(filename)
    messagebox.showinfo("Success", f"PDF generated at {filename}.")


# Tooltip class for hover text
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event):
        x, y = self.widget.winfo_rootx() + 25, self.widget.winfo_rooty() + 25
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.geometry(f"+{x}+{y}")
        label = tk.Label(self.tooltip, text=self.text, background="lightyellow", relief="solid", borderwidth=1)
        label.pack()

    def hide_tooltip(self, event):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


# Main Application Class
class KaspaPortfolioApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Kaspa Portfolio Projection (KPP) - Version {VERSION}")
        # Increase window height to accommodate the new slider frame (100 pixels taller)
        self.root.geometry("1300x1000")  # Changed from 1300x900 to 1300x1000
        self.root.iconbitmap(ICON_PATH)
        self.root.configure(bg=COLOR_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Top frame with logo and title
        self.top_frame = tk.Frame(root, bg=COLOR_TOP_BG, height=100)
        self.top_frame.pack(fill="x", pady=(0, 3))
        image = Image.open(LOGO_PATH).resize((300, 125), Image.LANCZOS)
        self.logo = ImageTk.PhotoImage(image)
        tk.Label(self.top_frame, image=self.logo, bg=COLOR_TOP_BG).pack(side="left", padx=(10, 0), pady=5)
        self.header_text_frame = tk.Frame(self.top_frame, bg=COLOR_TOP_BG)
        self.header_text_frame.pack(side="right", padx=(20, 10), pady=3)
        self.title_label = tk.Label(self.header_text_frame, text="Kaspa Portfolio Projector", bg=COLOR_TOP_BG,
                                    fg="white", font=("Helvetica", 30, "bold"), justify="right")
        self.title_label.pack(anchor="e")
        tk.Label(self.header_text_frame, text=f"Developed by the Kaspa community | Version {VERSION}", bg=COLOR_TOP_BG,
                 fg="white", font=("Helvetica", 10), justify="right").pack(anchor="e")
        self.header_line = tk.Frame(root, height=10, bg=COLOR_BG)
        self.header_line.pack(fill="x")
        self.main_frame = tk.Frame(root, bg=COLOR_BG, padx=10, pady=0)
        self.main_frame.pack(fill="both", expand=True)
        self.loading_label = ttk.Label(self.main_frame, text="Loading...")
        self.loading_label.pack_forget()

        # Input frame
        self.input_frame = tk.Frame(self.main_frame, bg=COLOR_FG, bd=4, relief="ridge", padx=20, pady=0)
        self.input_frame.pack(fill="x", padx=0)
        self.input_subframe = tk.Frame(self.input_frame, bg=COLOR_FG, padx=10, pady=10)
        self.input_subframe.pack(side="left", fill="both", expand=True)
        self.metrics_subframe = tk.Frame(self.input_frame, bg=COLOR_FG, padx=10, pady=10)
        self.metrics_subframe.pack(side="right", fill="both", expand=True)
        self.input_subframe.grid_columnconfigure(0, weight=1)
        self.input_subframe.grid_columnconfigure(1, weight=2)
        self.input_subframe.grid_columnconfigure(2, weight=1)
        tk.Label(self.input_subframe, text="Portfolio Input", bg=COLOR_FG, fg=COLOR_BG,
                 font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=3, pady=(5, 5), sticky="nsew")
        self.entries = {}
        self.check_marks = {}
        self.x_marks = {}
        self.updated_fields = {}
        self.metrics_entries = {}
        self.fetched_data = {}

        # Input fields
        for i, label in enumerate(PLACEHOLDERS, start=1):
            tk.Label(self.input_subframe, text=label, bg=COLOR_FG, fg=COLOR_BG, font=("Arial", 12, "bold")).grid(row=i,
                                                                                                                 column=0,
                                                                                                                 padx=10,
                                                                                                                 pady=8,
                                                                                                                 sticky="w")
            entry_frame = tk.Frame(self.input_subframe, bg=COLOR_FG)
            entry_frame.grid(row=i, column=1, padx=10, pady=8, sticky="e")
            entry = tk.Entry(entry_frame, bg="white", fg="grey", font=("Arial", 12), relief="flat", bd=1,
                             highlightbackground=COLOR_BG, highlightthickness=2, width=30)
            entry.insert(0, PLACEHOLDERS[label] if not DEFAULTS[label] else DEFAULTS[label])
            entry.grid(row=0, column=0, padx=5)
            entry.bind("<FocusIn>",
                       lambda e, p=PLACEHOLDERS[label], d=DEFAULTS[label], l=label: self.clear_placeholder(e.widget, p,
                                                                                                           d, l))
            entry.bind("<FocusOut>",
                       lambda e, p=PLACEHOLDERS[label], d=DEFAULTS[label], l=label: self.restore_placeholder(e.widget,
                                                                                                             p, d, l))
            entry.bind("<KeyRelease>", lambda e: self.update_field_and_check(e.widget))
            self.entries[label] = entry
            self.updated_fields[label] = False
            check_mark = tk.Label(entry_frame, text="✔", bg=COLOR_FG, fg=CHECKMARK_COLOR, font=("Arial", 12, "bold"))
            check_mark.grid(row=0, column=1, padx=5)
            check_mark.grid_remove()
            self.check_marks[label] = check_mark
            x_mark = tk.Label(entry_frame, text="✘", bg=COLOR_FG, fg=X_MARK_COLOR, font=("Arial", 12, "bold"))
            x_mark.grid(row=0, column=1, padx=5)
            self.x_marks[label] = x_mark

        # Currency selection
        currency_row = len(PLACEHOLDERS) + 1
        tk.Label(self.input_subframe, text="Currency:", bg=COLOR_FG, fg=COLOR_BG, font=("Arial", 12, "bold")).grid(
            row=currency_row, column=0, padx=10, pady=8, sticky="w")
        currency_frame = tk.Frame(self.input_subframe, bg=COLOR_FG)
        currency_frame.grid(row=currency_row, column=1, padx=10, pady=8, sticky="e")
        self.currency_var = tk.StringVar(value="USD")
        currency_menu = tk.OptionMenu(currency_frame, self.currency_var, "USD", "EUR", "GBP", "JPY", "AUD",
                                      command=self.update_display_on_currency_change)
        currency_menu.config(bg=COLOR_FG, fg=COLOR_BG, font=("Arial", 12), relief="flat", bd=1,
                             highlightbackground=COLOR_BG, highlightthickness=2, width=10)
        currency_menu.grid(row=0, column=0, padx=5)
        currency_check_mark = tk.Label(currency_frame, text="✔", bg=COLOR_FG, fg=CHECKMARK_COLOR,
                                       font=("Arial", 12, "bold"))
        currency_check_mark.grid(row=0, column=1, padx=5)
        Tooltip(currency_menu, "Select the currency for your portfolio projections")

        # Buttons
        button_row = currency_row + 1
        self.create_styled_button("Generate PDF", self.generate_pdf, button_row, 0)
        self.create_styled_button("Fetch Real Time Data", self.fetch_data, button_row, 1)
        self.create_styled_button("Help", self.show_help, button_row + 1, 0, columnspan=2)

        # Metrics subframe
        tk.Label(self.metrics_subframe, text="Portfolio Metrics", bg=COLOR_FG, fg=COLOR_BG,
                 font=("Arial", 14, "bold")).grid(row=0, column=0, pady=(5, 5), sticky="nsew")
        metrics = [
            ("Holdings", "Current KAS Holdings:", "Total KAS coins currently held"),
            ("Portfolio Value", "Current KAS Portfolio Value:", "Value of your KAS holdings"),
            ("Market Cap", "Current KAS Market Cap:", "Total market cap of Kaspa"),
            ("Price Needed 1M", "KAS Price Needed for $1M Portfolio:", "Price per KAS for $1M portfolio"),
            ("Market Cap Needed 1M", "KAS Market Cap Needed for $1M Portfolio:", "Market cap for $1M portfolio")
        ]
        for i, (key, label, tooltip) in enumerate(metrics, 1):
            frame = self.create_metric_entry(self.metrics_subframe, label, tooltip)
            frame.grid(row=i, column=0, padx=(0, 10), pady=5, sticky="e")
            self.metrics_entries[key] = frame

        tk.Label(self.metrics_subframe, text="Bitcoin Comparison", bg=COLOR_FG, fg=COLOR_BG,
                 font=("Arial", 12, "bold")).grid(row=6, column=0, padx=(0, 10), pady=(5, 0), sticky="e")
        self.btc_summary_frame = tk.Frame(self.metrics_subframe, bg=COLOR_FG)
        self.btc_summary_frame.grid(row=7, column=0, padx=(10, 10), pady=(0, 5), sticky="e")
        self.btc_summary_line1 = tk.Label(self.btc_summary_frame, text="KAS Market cap needed for $1M portfolio:",
                                          bg=COLOR_FG, fg=COLOR_BG, font=("Arial", 11), justify="left")
        self.btc_summary_line1.grid(row=0, column=0, sticky="e")
        self.btc_summary_line2 = tk.Label(self.btc_summary_frame, text="is about 0.000000 times the", bg=COLOR_FG,
                                          fg=COLOR_BG, font=("Arial", 11, "bold"), justify="left")
        self.btc_summary_line2.grid(row=1, column=0, sticky="e")
        self.btc_summary_line3 = tk.Label(self.btc_summary_frame, text="current Bitcoin market cap of $0.00.",
                                          bg=COLOR_FG, fg=COLOR_BG, font=("Arial", 11, "bold"), justify="left")
        self.btc_summary_line3.grid(row=2, column=0, sticky="e")

        # New Slider Frame
        self.slider_frame = tk.Frame(self.main_frame, bg=COLOR_FG, bd=4, relief="ridge", padx=20, pady=10)
        self.slider_frame.pack(fill="x", pady=10)
        tk.Label(self.slider_frame, text="KAS Price Slider", bg=COLOR_FG, fg=COLOR_BG, font=("Arial", 14, "bold")).pack(
            pady=(0, 5))

        # Label to display the KAS price with a dollar sign
        self.slider_price_label = tk.Label(self.slider_frame, text="$0.01", bg=COLOR_FG, fg=COLOR_BG,
                                           font=("Arial", 12))
        self.slider_price_label.pack(pady=(0, 2))

        # Slider for KAS price (range from 0 to 100, mapped logarithmically to rounded current price to 1000)
        self.slider_var = tk.DoubleVar(value=0)  # Default to minimum position
        self.slider = tk.Scale(self.slider_frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.slider_var,
                               length=600, bg=COLOR_FG, fg=COLOR_BG, font=("Arial", 12), showvalue=0,
                               command=self.update_slider_values)
        self.slider.pack(pady=5)

        # Frame to hold the labels for Portfolio Value and Market Cap (using grid for stationary positioning)
        self.slider_labels_frame = tk.Frame(self.slider_frame, bg=COLOR_FG)
        self.slider_labels_frame.pack(fill="x", pady=5)

        # Labels to display the values using grid layout
        self.slider_labels_frame.grid_columnconfigure(0, weight=1)
        self.slider_labels_frame.grid_columnconfigure(1, weight=1)

        tk.Label(self.slider_labels_frame, text="Portfolio Value:", bg=COLOR_FG, fg=COLOR_BG,
                 font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="w", padx=20)
        self.portfolio_value_label = tk.Label(self.slider_labels_frame, text="$0.00", bg=COLOR_FG, fg=COLOR_BG,
                                              font=("Arial", 12))
        self.portfolio_value_label.grid(row=0, column=1, sticky="w", padx=20)

        tk.Label(self.slider_labels_frame, text="KAS Market Cap:", bg=COLOR_FG, fg=COLOR_BG,
                 font=("Arial", 12, "bold")).grid(row=1, column=0, sticky="w", padx=20)
        self.market_cap_label = tk.Label(self.slider_labels_frame, text="$0.00", bg=COLOR_FG, fg=COLOR_BG,
                                         font=("Arial", 12))
        self.market_cap_label.grid(row=1, column=1, sticky="w", padx=20)

        # Display frame with projection table
        self.display_frame = tk.Frame(self.main_frame, bg=COLOR_FG, bd=4, relief="ridge", padx=20, pady=15)
        self.display_frame.pack(fill="both", expand=True, pady=10, padx=0)
        tk.Label(self.display_frame, text="Your Portfolio Projection", bg=COLOR_FG, fg=COLOR_BG,
                 font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 5), sticky="n")

        # Frame for checkboxes
        self.checkbox_frame = tk.Frame(self.display_frame, bg=COLOR_FG)
        self.checkbox_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 5))
        self.show_change_var = tk.BooleanVar(value=False)
        self.show_change_checkbox = tk.Checkbutton(self.checkbox_frame, text="Show Change Column",
                                                   variable=self.show_change_var, command=self.update_display_if_valid,
                                                   bg=COLOR_FG, fg=COLOR_BG, font=("Arial", 12))
        self.show_change_checkbox.pack(side="left", padx=10)
        self.show_market_cap_vs_btc_var = tk.BooleanVar(value=False)
        self.show_market_cap_vs_btc_checkbox = tk.Checkbutton(self.checkbox_frame, text="Show Market Cap vs. Bitcoin",
                                                              variable=self.show_market_cap_vs_btc_var,
                                                              command=self.update_display_if_valid, bg=COLOR_FG,
                                                              fg=COLOR_BG, font=("Arial", 12))
        self.show_market_cap_vs_btc_checkbox.pack(side="left", padx=10)

        self.tree = ttk.Treeview(self.display_frame,
                                 columns=("Price", "Portfolio", "MarketCap", "Change", "Market Cap vs. BTC"),
                                 show="headings", height=20)
        self.tree.heading("Price", text="Price", command=lambda: self.sort_table("Price"))
        self.tree.heading("Portfolio", text="Portfolio Value", command=lambda: self.sort_table("Portfolio"))
        self.tree.heading("MarketCap", text="Market Cap", command=lambda: self.sort_table("MarketCap"))
        self.tree.heading("Change", text="Change", command=lambda: self.sort_table("Change"))
        self.tree.heading("Market Cap vs. BTC", text="Market Cap vs. BTC",
                          command=lambda: self.sort_table("Market Cap vs. BTC"))
        self.default_widths = {
            "Price": 150,
            "Portfolio": 200,
            "MarketCap": 250,
            "Change": 150,
            "Market Cap vs. BTC": 150
        }
        for col, width in self.default_widths.items():
            self.tree.column(col, width=width, anchor="center")

        # Set the initial displayed columns to exclude "Change" and "Market Cap vs. BTC"
        self.tree["displaycolumns"] = ["Price", "Portfolio", "MarketCap"]

        self.tree.grid(row=2, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self.display_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.display_frame.grid_rowconfigure(2, weight=1)
        self.display_frame.grid_columnconfigure(0, weight=1)

        # Treeview styling
        style = ttk.Style()
        style.configure("Treeview", background="white", foreground=COLOR_FG, font=("Arial", 12))
        style.map("Treeview", background=[("selected", COLOR_BG)], foreground=[("selected", COLOR_FG)])
        self.tree.tag_configure("red", foreground="red")
        self.tree.tag_configure("black", foreground="black")
        self.tree.tag_configure("green", foreground="green")
        self.tree.tag_configure("even", background="#F0F0F0")
        self.tree.tag_configure("odd", background="white")
        style.configure("Treeview.Heading", background=COLOR_BG, foreground=COLOR_FG, font=("Arial", 14, "bold"))

        # Explicitly call update_display_columns to set the initial state
        self.update_display_columns()

        self.fetch_data_on_startup()

    def create_styled_button(self, text, command, row, column, columnspan=1):
        button = tk.Button(self.input_subframe, text=text, command=command, bg=BUTTON_BG, fg=BUTTON_FG,
                           font=("Arial", 12, "bold"), relief="flat", bd=0, padx=20, pady=12)
        button.grid(row=row, column=column, columnspan=columnspan, pady=12, padx=10, sticky="ew")
        button.bind("<Enter>", lambda e: button.config(bg=COLOR_FG, fg=BUTTON_FG))
        button.bind("<Leave>", lambda e: button.config(bg=BUTTON_BG, fg=BUTTON_FG))
        return button

    def create_metric_entry(self, parent, label_text, tooltip_text=""):
        frame = tk.Frame(parent, bg=COLOR_FG)
        tk.Label(frame, text=label_text, bg=COLOR_FG, fg=COLOR_BG, font=("Arial", 12, "bold")).grid(row=0, column=0,
                                                                                                    padx=10, pady=8,
                                                                                                    sticky="w")
        entry = tk.Entry(frame, bg="white", fg=COLOR_FG, font=("Arial", 12), relief="flat", bd=1,
                         highlightbackground=COLOR_BG, highlightthickness=2, width=30, justify="right",
                         state='disabled')
        entry.grid(row=0, column=1, padx=5, pady=8, sticky="e")
        if tooltip_text:
            Tooltip(entry, tooltip_text)
        return frame

    @staticmethod
    @lru_cache(maxsize=1)
    def fetch_api_data():
        try:
            cg = CoinGeckoAPI()
            kaspa_data = cg.get_price(ids='kaspa', vs_currencies='usd')
            kaspa_supply = cg.get_coin_by_id(id='kaspa')['market_data']['circulating_supply']
            btc_data = cg.get_price(ids='bitcoin', vs_currencies='usd', include_market_cap=True)
            return {
                'kaspa_price': kaspa_data['kaspa']['usd'],
                'kaspa_supply': kaspa_supply,
                'btc_market_cap': btc_data['bitcoin']['usd_market_cap']
            }
        except Exception as e:
            logger.error(f"Failed to fetch data: {str(e)}")
            return {}

    def fetch_data_on_startup(self):
        self.show_loading()
        try:
            self.fetched_data = self.fetch_api_data()
            if not self.fetched_data:
                raise Exception("No data fetched")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch data on startup: {str(e)}")
        finally:
            self.hide_loading()
            self.update_display_if_valid()
            # Update the slider's initial position to the current price if available
            try:
                current_price = float(self.entries["Current Price (USD):"].get().replace(',', ''))
                rounded_current_price = round(current_price, 2)
                # Map the current price to the slider position (0 to 100)
                min_price = rounded_current_price if rounded_current_price > 0 else 0.01
                max_price = 1000
                if min_price != max_price:
                    slider_position = 0  # Start at the minimum (current price)
                    self.slider_var.set(slider_position)
                    self.update_slider_values()
            except (ValueError, KeyError):
                pass  # If price isn't available yet, slider remains at default

    def fetch_data(self):
        self.show_loading()
        try:
            self.fetched_data = self.fetch_api_data()
            if not self.fetched_data:
                raise Exception("No data fetched")
            self.entries["Current Price (USD):"].delete(0, tk.END)
            self.entries["Current Price (USD):"].insert(0, f"{self.fetched_data['kaspa_price']:.4f}")
            self.entries["Circulating Supply (B):"].delete(0, tk.END)
            self.entries["Circulating Supply (B):"].insert(0,
                                                           f"{self.fetched_data['kaspa_supply'] / 1_000_000_000:.4f}")
            self.updated_fields["Current Price (USD):"] = True
            self.show_check_mark("Current Price (USD):")
            self.hide_x_mark("Current Price (USD):")
            self.updated_fields["Circulating Supply (B):"] = True
            self.show_check_mark("Circulating Supply (B):")
            self.hide_x_mark("Circulating Supply (B):")
            if self.entries["KAS Holdings:"].get().strip() in [PLACEHOLDERS["KAS Holdings:"], DEFAULTS["KAS Holdings:"],
                                                               ""]:
                self.entries["KAS Holdings:"].delete(0, tk.END)
                self.entries["KAS Holdings:"].insert(0, "0")
            self.updated_fields["KAS Holdings:"] = True
            kas_holdings_value = float(self.entries["KAS Holdings:"].get().replace(',', ''))
            if kas_holdings_value > 0:
                self.show_check_mark("KAS Holdings:")
                self.hide_x_mark("KAS Holdings:")
                self.update_display_if_valid()
            else:
                self.hide_check_mark("KAS Holdings:")
                self.show_x_mark("KAS Holdings:")

            # Update the slider's initial position to the current price
            current_price = float(self.entries["Current Price (USD):"].get().replace(',', ''))
            rounded_current_price = round(current_price, 2)
            # Map the current price to the slider position (0 to 100)
            min_price = rounded_current_price if rounded_current_price > 0 else 0.01
            max_price = 1000
            if min_price != max_price:
                # Inverse of the logarithmic mapping: position = 100 * log(price / min_price) / log(max_price / min_price)
                slider_position = 0  # Start at the minimum (current price)
                self.slider_var.set(slider_position)
                self.update_slider_values()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch data: {str(e)}")
        finally:
            self.hide_loading()

    def clear_placeholder(self, widget, placeholder, default, label):
        if widget.get() in [placeholder, default]:
            widget.delete(0, tk.END)
            widget.config(fg=COLOR_FG)
            self.updated_fields[label] = False
            self.hide_check_mark(label)
            self.show_x_mark(label)

    def restore_placeholder(self, widget, placeholder, default, label):
        value = widget.get().strip()
        if not value:
            widget.insert(0, placeholder)
            widget.config(fg="grey")
            self.updated_fields[label] = False
            self.hide_check_mark(label)
            self.show_x_mark(label)
        else:
            widget.config(fg=COLOR_FG)
            if value != placeholder and (label == "Portfolio Name:" or self.is_valid_numeric_field(label)):
                self.updated_fields[label] = True
                if label == "KAS Holdings:" and float(value.replace(',', '')) > 0:
                    self.show_check_mark(label)
                    self.hide_x_mark(label)
                elif label in NUMERIC_FIELDS:
                    self.show_check_mark(label)
                    self.hide_x_mark(label)
                if label in NUMERIC_FIELDS:
                    self.update_display_if_valid()

    def show_check_mark(self, label):
        self.check_marks[label].grid()
        self.x_marks[label].grid_remove()

    def hide_check_mark(self, label):
        self.check_marks[label].grid_remove()

    def show_x_mark(self, label):
        self.x_marks[label].grid()
        self.check_marks[label].grid_remove()

    def hide_x_mark(self, label):
        self.x_marks[label].grid_remove()

    def update_field_and_check(self, widget):
        label = next(l for l, e in self.entries.items() if e == widget)
        value = widget.get().strip()
        if value and value != PLACEHOLDERS[label]:
            if label == "Portfolio Name:":
                widget.config(fg=COLOR_FG)
                self.updated_fields[label] = True
                self.show_check_mark(label)
                self.hide_x_mark(label)
            elif label in NUMERIC_FIELDS:
                try:
                    float_value = float(value.replace(',', ''))
                    if float_value < 0:
                        raise ValueError("Please enter a positive number.")
                    widget.config(fg=COLOR_FG)
                    self.updated_fields[label] = True
                    if label == "KAS Holdings:":
                        if float_value > 0:
                            self.show_check_mark(label)
                            self.hide_x_mark(label)
                        else:
                            self.hide_check_mark(label)
                            self.show_x_mark(label)
                            raise ValueError("KAS Holdings must be greater than 0.")
                    else:
                        if float_value >= 0:
                            self.show_check_mark(label)
                            self.hide_x_mark(label)
                        else:
                            self.hide_check_mark(label)
                            self.show_x_mark(label)
                    self.update_display_if_valid()
                except ValueError as e:
                    self.updated_fields[label] = False
                    self.hide_check_mark(label)
                    self.show_x_mark(label)
                    if widget == self.root.focus_get():
                        messagebox.showerror("Error", str(e))
        else:
            self.updated_fields[label] = False
            self.hide_check_mark(label)
            self.show_x_mark(label)

    def is_valid_numeric_field(self, label):
        value = self.entries[label].get().strip()
        if not value or value == PLACEHOLDERS[label]:
            return False
        try:
            float_value = float(value.replace(',', ''))
            if label == "KAS Holdings:" and float_value <= 0:
                return False
            return float_value >= 0
        except ValueError:
            return False

    def update_display_if_valid(self, event=None):
        if all(self.is_valid_numeric_field(field) for field in NUMERIC_FIELDS) and self.fetched_data:
            kaspa = float(self.entries["KAS Holdings:"].get().replace(',', ''))
            price_usd = float(self.entries["Current Price (USD):"].get().replace(',', ''))
            supply = float(self.entries["Circulating Supply (B):"].get().replace(',', ''))
            currency = self.currency_var.get()
            df, symbol = generate_portfolio_projection(kaspa, price_usd, supply, currency)
            rate = EXCHANGE_RATES.get(currency.upper(), 1.0)
            btc_market_cap = self.fetched_data.get('btc_market_cap', 0)

            self.tree.delete(*self.tree.get_children())
            items = []
            for i, (_, row) in enumerate(df.iterrows()):
                projected_price_usd = row["Price_USD"]
                projected_portfolio_value = row["Portfolio"]
                projected_market_cap = row["Market Cap"]
                multiple = projected_price_usd / price_usd if price_usd != 0 else 0
                percentage_change = (multiple - 1) * 100
                change_str = f"{multiple:.1f}x ({percentage_change:+.1f}%)"
                tag = "even" if i % 2 == 0 else "odd"
                values = [f"{symbol}{row['Price']:.2f}", f"{symbol}{projected_portfolio_value:,.0f}",
                          f"{symbol}{projected_market_cap:,.0f}"]

                # Ensure the values list has an element for the "Change" column
                if self.show_change_var.get():
                    values.append(change_str)
                else:
                    values.append("")

                # Ensure the values list has an element for the "Market Cap vs. BTC" column
                if self.show_market_cap_vs_btc_var.get():
                    if btc_market_cap > 0:
                        market_cap_vs_btc = (projected_market_cap / rate) / btc_market_cap
                        values.append(f"{market_cap_vs_btc:.6f}")
                    else:
                        values.append("N/A")
                else:
                    values.append("")

                item = self.tree.insert("", "end", values=values, tags=(row["Color"], tag))
                items.append(item)

            black_line_index = df.index[df['Color'] == "black"].tolist()[0]
            if black_line_index > 0:
                self.tree.see(items[black_line_index - 1])
                self.tree.yview_moveto((black_line_index - 1) / len(items))

            self.update_display_columns()

            # Update portfolio metrics
            circulating_supply = supply * 1_000_000_000
            market_cap_usd = price_usd * circulating_supply
            portfolio_value_usd = kaspa * price_usd
            price_needed_for_1m_usd = 1_000_000 / kaspa if kaspa > 0 else 0
            market_cap_needed_for_1m_usd = price_needed_for_1m_usd * circulating_supply
            market_cap = market_cap_usd * rate
            portfolio_value = portfolio_value_usd * rate
            price_needed_for_1m = price_needed_for_1m_usd * rate
            market_cap_needed_for_1m = market_cap_needed_for_1m_usd * rate
            btc_market_cap_currency = btc_market_cap * rate
            market_cap_ratio = market_cap_needed_for_1m_usd / btc_market_cap if btc_market_cap > 0 else 0

            for key, value in [
                ("Holdings", f"{kaspa:,.2f} KAS"),
                ("Portfolio Value", f"{symbol}{portfolio_value:,.2f}"),
                ("Market Cap", f"{symbol}{market_cap:,.2f}"),
                ("Price Needed 1M", f"{symbol}{price_needed_for_1m:,.2f}"),
                ("Market Cap Needed 1M", f"{symbol}{market_cap_needed_for_1m:,.2f}")
            ]:
                entry = self.metrics_entries[key].winfo_children()[1]
                entry.config(state='normal')
                entry.delete(0, tk.END)
                entry.insert(0, value)
                entry.config(state='disabled')

            if btc_market_cap > 0:
                self.btc_summary_line1.config(text="KAS Market cap needed for $1M portfolio:")
                self.btc_summary_line2.config(text=f"is about {market_cap_ratio:.6f} times the")
                self.btc_summary_line3.config(
                    text=f"current Bitcoin market cap of {symbol}{btc_market_cap_currency:,.2f}.")
            else:
                self.btc_summary_line1.config(text="Bitcoin market cap data unavailable.")
                self.btc_summary_line2.config(text="")
                self.btc_summary_line3.config(text="")

    def update_slider_values(self, event=None):
        # Get the current KAS price (rounded to 2 decimal places, as in generate_price_intervals)
        try:
            current_price = float(self.entries["Current Price (USD):"].get().replace(',', ''))
            min_price = round(current_price, 2)  # This is the "black row" price
        except (ValueError, KeyError):
            min_price = 0.01  # Fallback if price is not available

        max_price = 1000  # Upper bound of the slider

        # Get the slider position (0 to 100)
        slider_position = self.slider_var.get()

        # Map the slider position to a logarithmic price from min_price to max_price
        if min_price <= 0:  # Prevent log of zero or negative
            min_price = 0.01
        kas_price = min_price * (max_price / min_price) ** (slider_position / 100)

        # Get the current KAS holdings, circulating supply, and currency
        try:
            kaspa_amount = float(self.entries["KAS Holdings:"].get().replace(',', ''))
        except (ValueError, KeyError):
            kaspa_amount = 0  # Default to 0 if invalid

        try:
            circulating_supply_billion = float(self.entries["Circulating Supply (B):"].get().replace(',', ''))
            circulating_supply = circulating_supply_billion * 1_000_000_000
        except (ValueError, KeyError):
            circulating_supply = 0  # Default to 0 if invalid

        currency = self.currency_var.get()
        rate = EXCHANGE_RATES.get(currency.upper(), 1.0)
        symbol = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "AUD": "A$"}.get(currency.upper(), "$")

        # Calculate portfolio value and market cap
        portfolio_value = kaspa_amount * kas_price * rate
        market_cap = circulating_supply * kas_price * rate

        # Update the labels
        self.slider_price_label.config(text=f"{symbol}{kas_price:.2f}")
        self.portfolio_value_label.config(text=f"{symbol}{portfolio_value:,.2f}")
        self.market_cap_label.config(text=f"{symbol}{market_cap:,.2f}")

    def update_display_columns(self):
        display_columns = ["Price", "Portfolio", "MarketCap"]
        if self.show_change_var.get():
            display_columns.append("Change")
        if self.show_market_cap_vs_btc_var.get():
            display_columns.append("Market Cap vs. BTC")

        self.tree["displaycolumns"] = display_columns
        num_columns = len(display_columns)
        if num_columns > 0:
            for col in display_columns:
                self.tree.column(col, width=750 // num_columns)

    def sort_table(self, column):
        items = [(self.tree.item(item)["values"], item) for item in self.tree.get_children()]
        col_idx = self.tree["displaycolumns"].index(column)
        items.sort(key=lambda x: self.parse_value(x[0][col_idx], column))
        for i, (_, item) in enumerate(items):
            self.tree.move(item, '', i)

    def parse_value(self, value, column):
        if column in ["Price", "Portfolio", "MarketCap"]:
            return float(
                value.replace('$', '').replace('€', '').replace('£', '').replace('¥', '').replace('A$', '').replace(',',
                                                                                                                    ''))
        elif column == "Market Cap vs. BTC":
            if value == "N/A":
                return float('inf')  # Handle N/A for sorting
            return float(value)
        elif column == "Change":
            return float(value.split('x')[0])
        else:
            return value

    def generate_pdf(self):
        self.show_loading()
        try:
            for field in NUMERIC_FIELDS:
                if not self.is_valid_numeric_field(field):
                    raise ValueError(f"Please enter a valid positive number greater than 0 for {field} if applicable.")
            kaspa = float(self.entries["KAS Holdings:"].get().replace(',', ''))
            price_usd = float(self.entries["Current Price (USD):"].get().replace(',', ''))
            supply = float(self.entries["Circulating Supply (B):"].get().replace(',', ''))
            currency = self.currency_var.get() or "USD"
            name = self.entries["Portfolio Name:"].get() or "Unnamed"
            df, _ = generate_portfolio_projection(kaspa, price_usd, supply, currency)
            file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
            if file_path:
                btc_market_cap = self.fetched_data.get('btc_market_cap', 0)
                generate_portfolio_pdf(df, file_path, name, kaspa, price_usd, supply, currency, btc_market_cap)
                self.updated_fields["Portfolio Name:"] = True
                self.show_check_mark("Portfolio Name:")
                self.hide_x_mark("Portfolio Name:")
        except ValueError as e:
            messagebox.showerror("Error", str(e))
        finally:
            self.hide_loading()

    def show_loading(self):
        self.loading_label.pack(pady=10)
        self.root.update()

    def hide_loading(self):
        self.loading_label.pack_forget()
        self.root.update()

    def show_help(self):
        messagebox.showinfo("Help",
                            "Enter your Kaspa portfolio details and fetch real-time data. Select a currency and generate a PDF report.\n\nSupport: github.com/AceOmnia/kaspa-portfolio-projector/")

    def update_display_on_currency_change(self, event=None):
        self.update_display_if_valid()
        self.update_slider_values()  # Update slider values when currency changes

    def on_closing(self):
        self.root.destroy()
        sys.exit(0)


if __name__ == "__main__":
    root = tk.Tk()
    app = KaspaPortfolioApp(root)
    root.mainloop()