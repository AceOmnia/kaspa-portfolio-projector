"""
kpp.py
=============================

A Python application for generating Kaspa portfolio projections and reports.

This script provides a graphical user interface (GUI) for users to input their Kaspa holdings,
current market price, and circulating supply to generate a detailed portfolio projection report.
The report includes price intervals, estimated portfolio values, and market capitalization projections.
Users can export the data as a formatted PDF report.

Dependencies:
-------------
- pandas
- fpdf
- numpy
- tkinter
- PIL (Pillow)

Features:
---------
- Generates price intervals for Kaspa using linear and logarithmic scaling.
- Computes portfolio value and market capitalization at different price points.
- Exports a formatted PDF report with a Kaspa logo, portfolio summary, and data table.
- Provides a user-friendly GUI for data input and report generation.

Usage:
------
Ensure all dependencies are installed:

    pip install pandas fpdf numpy pillow

Run the script:

    python kpp.py

Author:
-------
Kaspa Community Contributor

Version:
--------
0.1

Date:
-----
2025-02-02
"""

import pandas as pd
from fpdf import FPDF
import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

# Path to the Kaspa logo
LOGO_PATH_LIGHT_BACKGROUND = r"pics\Kaspa-LDSP-Dark-Full-Color.png"
LOGO_PATH_DARK_BACKGROUND = r"pics\Kaspa-LDSP-Dark-Reverse.png"
ICON_PATH = r"pics\kaspa.ico"
VERSION = r"0.1"

# Function to generate price intervals
def generate_price_intervals(current_price):
    rounded_cent = round(current_price, 2)
    black_row_price = rounded_cent
    red_intervals = np.linspace(0.05, black_row_price - 0.01, num=7).tolist() # 7 evenly distributed intervals down to 5 cents
    black_interval = [black_row_price]
    green_intervals = np.geomspace(black_row_price + 0.01, 200, num=60).tolist() # 60 logarithmically distributed intervals up to $200 KAS
    price_intervals = sorted(set(round(price, 2) for price in (red_intervals + black_interval + green_intervals)))
    return price_intervals

# Function to generate portfolio projection DataFrame
def generate_portfolio_projection(kaspa_amount, current_price, circulating_supply_billion):
    circulating_supply = circulating_supply_billion * 1_000_000_000
    market_cap = current_price * circulating_supply
    price_intervals = generate_price_intervals(current_price)

    data = {
        "Kaspa Price ($)": [f"${price:.2f}" for price in price_intervals],
        "Portfolio Value ($)": [f"${kaspa_amount * price:,.2f}" for price in price_intervals],
        "Market Cap ($)": [f"${(market_cap / current_price) * price:,.2f}" for price in price_intervals],
        "Color": ["red" if price < round(current_price, 2) else "black" if price == round(current_price, 2) else "green"
                  for price in price_intervals],
    }
    return pd.DataFrame(data)

# Function to generate the PDF report
def generate_portfolio_pdf(df, filename, title, kaspa_amount, current_price, circulating_supply_billion,
                           purchase_price=None):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Add Logo - Center it for better appearance
    pdf.image(LOGO_PATH_LIGHT_BACKGROUND, x=80, y=10, w=50)
    pdf.ln(25)

    # Title - Make it stand out
    pdf.set_font("Helvetica", style='B', size=22)
    pdf.cell(200, 10, title, ln=True, align='C')
    pdf.ln(5)

    # Add a subtle separator
    pdf.set_draw_color(200, 200, 200)  # Light grey line
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)

    # Portfolio Facts - Better alignment
    circulating_supply = circulating_supply_billion * 1_000_000_000
    market_cap = current_price * circulating_supply
    portfolio_value = kaspa_amount * current_price
    price_needed_for_million = 1_000_000 / kaspa_amount
    market_cap_at_million = (market_cap / current_price) * price_needed_for_million

    pdf.set_font("Helvetica", style='B', size=14)
    pdf.cell(200, 8, "Portfolio Facts", ln=True, align='L')
    pdf.ln(4)

    pdf.set_font("Helvetica", size=11)
    cell_width = 90
    spacing = 7

    # Using a cleaner layout with tabular alignment
    data = [
        ("Current KAS Holdings:", f"{kaspa_amount:,} KAS"),
        ("Current KAS Portfolio Value:", f"${portfolio_value:,.2f}"),
        ("Current KAS Market Cap:", f"${market_cap:,.2f}"),
        ("KAS Price Needed for $1M Portfolio:", f"${price_needed_for_million:,.2f}"),
        ("KAS Market Cap Needed for $1M Portfolio:", f"${market_cap_at_million:,.2f}")
    ]

    for label, value in data:
        pdf.cell(cell_width, spacing, label, ln=False, align='L')
        pdf.cell(0, spacing, value, ln=True, align='R')

    if purchase_price:
        pdf.cell(cell_width, spacing, "KAS Portfolio Breakeven Price (per KAS):", ln=False, align='L')
        pdf.cell(0, spacing, f"${purchase_price:.2f}", ln=True, align='R')

    pdf.ln(8)

    # Table Header with Bold Styling
    pdf.set_font("Helvetica", style='B', size=11)
    pdf.set_fill_color(230, 230, 230)  # Light gray background for headers
    pdf.cell(50, 10, "Kaspa Price ($)", border=1, align='C', fill=True)
    pdf.cell(70, 10, "Portfolio Value ($)", border=1, align='C', fill=True)
    pdf.cell(70, 10, "Market Cap ($)", border=1, align='C', fill=True)
    pdf.ln()

    # Table Data - Adjust text colors dynamically
    pdf.set_font("Helvetica", size=10)
    for _, row in df.iterrows():
        # Set color based on row condition
        if row["Color"] == "red":
            pdf.set_text_color(255, 0, 0)  # Red
        elif row["Color"] == "black":
            pdf.set_text_color(0, 0, 0)  # Black
        else:
            pdf.set_text_color(0, 128, 0)  # Green

        pdf.cell(50, 10, row["Kaspa Price ($)"], border=1, align='C')
        pdf.cell(70, 10, row["Portfolio Value ($)"], border=1, align='C')
        pdf.cell(70, 10, row["Market Cap ($)"], border=1, align='C')
        pdf.ln()

    # Reset text color to default
    pdf.set_text_color(0, 0, 0)

    pdf.output(filename)
    messagebox.showinfo("Success", f"PDF saved at {filename}.")

# Function to generate the PDF on button click
def generate_pdf():
    try:
        portfolio = portfolio_name.get()
        kaspa = float(kaspa_amount.get())
        price = float(current_price.get())
        supply = float(circulating_supply.get())

        # Handle Purchase Price Placeholder
        purchase = purchase_price.get()
        if purchase == "e.g., 0.1735 (aka 17.35 cents)" or purchase.strip() == "":
            purchase = None  # Treat as empty if placeholder is still there
        else:
            purchase = float(purchase)  # Convert to float if user entered a value

        file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")], title="Save PDF As")
        if not file_path:
            return

        df = generate_portfolio_projection(kaspa, price, supply)
        generate_portfolio_pdf(df, file_path, f"{portfolio} Portfolio Projection", kaspa, price, supply, purchase)

    except ValueError:
        messagebox.showerror("Input Error", "Please enter valid numeric values.")


# GUI Application with Tkinter
def create_gui():
    global portfolio_name, kaspa_amount, current_price, circulating_supply, purchase_price, logo_label

    root = tk.Tk()
    root.title("Kaspa Portfolio Projection (KPP)")
    root.geometry("600x700")  # Adjusted for better layout
    root.configure(bg="#70C7BA")  # Dark teal background
    root.iconbitmap(ICON_PATH) # Change window icon

    # Create Styles
    style = ttk.Style()
    style.configure("TFrame", background="#231F20", relief="raised")  # Dark form background
    style.configure("TLabel", background="#231F20", foreground="#70C7BA", font=("Arial", 11, "bold"))  # Teal labels
    style.configure("TButton", font=("Arial", 12, "bold"), padding=10, relief="flat")  # Modern button

    # Main Frame (Dark Form Area)
    frame = ttk.Frame(root, padding=20, style="TFrame")
    frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

    # Load and Display the Kaspa Logo
    image = Image.open(LOGO_PATH_DARK_BACKGROUND)
    image = image.resize((436, 182), Image.LANCZOS) # maintaining the 2.18 ratio
    logo_img = ImageTk.PhotoImage(image)

    logo_label = tk.Label(frame, image=logo_img, bg="#231F20")
    logo_label.image = logo_img
    logo_label.grid(row=0, columnspan=2, pady=(0,8))  # Centered logo

    # Function to Create Input Fields with Greyed-Out Placeholder
    def add_input(label_text, row, placeholder_text):
        ttk.Label(frame, text=label_text).grid(row=row, column=0, sticky="w", pady=5, padx=5)

        entry_frame = tk.Frame(frame, bg="#FFFFFF", highlightbackground="#70C7BA", highlightthickness=2, bd=0)
        entry_frame.grid(row=row, column=1, padx=10, pady=5)

        entry = tk.Entry(entry_frame, width=30, font=("Arial", 11), bg="#FFFFFF", fg="grey",
                         relief="flat", bd=0)
        entry.insert(0, placeholder_text)  # Prefilled example text

        # Remove Placeholder on Focus
        def on_focus_in(event):
            if entry.get() == placeholder_text:
                entry.delete(0, tk.END)
                entry.config(fg="#231F20")  # Switch to normal text color

        # Restore Placeholder if Left Empty
        def on_focus_out(event):
            if entry.get() == "":
                entry.insert(0, placeholder_text)
                entry.config(fg="grey")  # Switch back to grey text

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

        entry.pack(ipady=5, padx=5, pady=5, fill=tk.BOTH)
        return entry

    # Create Input Fields with Examples
    portfolio_name = add_input("Portfolio Name:", 1, "e.g., My Kaspa Holdings")
    kaspa_amount = add_input("Total KAS Holdings:", 2, "e.g., 1367 (aka 1367 KAS)")
    current_price = add_input("Current KAS Price ($):", 3, "e.g., 0.2711 (aka 27.11 cents)")
    circulating_supply = add_input("Circulating Supply (Billions):", 4, "e.g., 25.6 (aka 25,600,000,000 KAS)")
    purchase_price = add_input("Avg Purchase Price (Optional):", 5, "e.g., 0.1735 (aka 17.35 cents)")

    # Generate PDF Button
    generate_button = tk.Button(frame, text="Generate PDF", command=generate_pdf,
                                bg="#70C7BA", fg="#231F20", font=("Arial", 12, "bold"),
                                relief="flat", bd=5, padx=20, pady=10, cursor="hand2")
    generate_button.grid(row=6, columnspan=2, pady=25)  # Centered with better spacing

    # Add Text Below the Button
    info_label = ttk.Label(frame, text="Developed open-source by Kaspa community member.",
                           foreground="#70C7BA", background="#231F20", font=("Arial", 10))
    info_label.grid(row=7, columnspan=2, pady=(0, 10))  # Slight padding for better spacing

    # Version
    info_label = ttk.Label(frame, text="(Version {})".format(VERSION),
                           foreground="#70C7BA", background="#231F20", font=("Arial", 10))
    info_label.grid(row=8, columnspan=2, pady=(0, 10))  # Slight padding for better spacing

    root.mainloop()

# Run GUI
if __name__ == "__main__":
    create_gui()
