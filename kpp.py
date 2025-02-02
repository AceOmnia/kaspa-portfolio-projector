import pandas as pd
from fpdf import FPDF
import numpy as np
import re
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

# if the above is not installed in your env, run the following in the proj terminal:
# pip install pandas fpdf numpy pillow

# Path to the Kaspa logo
LOGO_PATH_LIGHT_BACKGROUND = r"pics\Kaspa-LDSP-Dark-Full-Color.png"
LOGO_PATH_DARK_BACKGROUND = r"pics\Kaspa-LDSP-Dark-Reverse.png"

# Function to sanitize filenames (removes special characters)
def clean_filename(name):
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)

# Function to generate price intervals
def generate_price_intervals(current_price):
    rounded_cent = round(current_price, 2)
    black_row_price = rounded_cent
    red_intervals = np.linspace(black_row_price - 0.01, 0.05, num=7).tolist()
    black_interval = [black_row_price]
    green_intervals = np.geomspace(black_row_price + 0.01, 100, num=50).tolist()
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
def generate_portfolio_pdf(df, filename, title, kaspa_amount, current_price, circulating_supply_billion, purchase_price=None):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Add logo to the PDF (Ensure the path is correct)
    pdf.image(LOGO_PATH_LIGHT_BACKGROUND, x=10, y=10, w=40)
    pdf.ln(20)

    # Title
    pdf.set_font("Arial", style='B', size=16)
    pdf.cell(200, 10, title, ln=True, align='C')
    pdf.ln(10)

    # Portfolio Facts
    circulating_supply = circulating_supply_billion * 1_000_000_000
    market_cap = current_price * circulating_supply
    portfolio_value = kaspa_amount * current_price
    price_needed_for_million = 1_000_000 / kaspa_amount
    market_cap_at_million = (market_cap / current_price) * price_needed_for_million

    pdf.set_font("Arial", style='B', size=12)
    pdf.cell(200, 8, "Portfolio Facts", ln=True, align='L')
    pdf.ln(3)

    pdf.set_font("Arial", size=11)
    pdf.cell(200, 8, f"Total KAS Holdings: {kaspa_amount:,}", ln=True, align='L')
    pdf.cell(200, 8, f"Portfolio Value: ${portfolio_value:,.2f}", ln=True, align='L')
    pdf.cell(200, 8, f"Current Market Cap: ${market_cap:,.2f}", ln=True, align='L')
    pdf.cell(200, 8, f"Price Needed for $1M: ${price_needed_for_million:.2f}", ln=True, align='L')
    pdf.cell(200, 8, f"Market Cap at $1M: ${market_cap_at_million:,.2f}", ln=True, align='L')

    if purchase_price:
        pdf.cell(200, 8, f"Breakeven Price: ${purchase_price:.2f}", ln=True, align='L')

    pdf.ln(10)

    # Table header
    pdf.set_font("Arial", style='B', size=10)
    pdf.cell(50, 10, "Kaspa Price ($)", border=1, align='C')
    pdf.cell(70, 10, "Portfolio Value ($)", border=1, align='C')
    pdf.cell(70, 10, "Market Cap ($)", border=1, align='C')
    pdf.ln()

    # Table data
    pdf.set_font("Arial", size=10)
    for _, row in df.iterrows():
        pdf.set_text_color(255, 0, 0) if row["Color"] == "red" else pdf.set_text_color(0, 0, 0) if row["Color"] == "black" else pdf.set_text_color(0, 128, 0)
        pdf.cell(50, 10, row["Kaspa Price ($)"], border=1, align='C')
        pdf.cell(70, 10, row["Portfolio Value ($)"], border=1, align='C')
        pdf.cell(70, 10, row["Market Cap ($)"], border=1, align='C')
        pdf.ln()

    pdf.output(filename)
    messagebox.showinfo("Success", f"PDF saved as {filename} in execution directory.")

# Function to generate the PDF on button click
def generate_pdf():
    try:
        portfolio = portfolio_name.get()
        kaspa = float(kaspa_amount.get())
        price = float(current_price.get())
        supply = float(circulating_supply.get())

        # **Handle Purchase Price Placeholder**
        purchase = purchase_price.get()
        if purchase == "e.g., 0.1735 (aka 17.35 cents)" or purchase.strip() == "":
            purchase = None  # Treat as empty if placeholder is still there
        else:
            purchase = float(purchase)  # Convert to float if user entered a value

        cleaned_name = clean_filename(portfolio)
        filename = f"{cleaned_name}_Portfolio_Projection.pdf"

        df = generate_portfolio_projection(kaspa, price, supply)
        generate_portfolio_pdf(df, filename, f"{portfolio} Portfolio Projection", kaspa, price, supply, purchase)

    except ValueError:
        messagebox.showerror("Input Error", "Please enter valid numeric values.")


# GUI Application with Tkinter
def create_gui():
    global portfolio_name, kaspa_amount, current_price, circulating_supply, purchase_price, logo_label

    root = tk.Tk()
    root.title("Kaspa Portfolio Projection (KPP)")
    root.geometry("600x680")  # Adjusted for better layout
    root.configure(bg="#70C7BA")  # Dark teal background

    # **Create Styles**
    style = ttk.Style()
    style.configure("TFrame", background="#231F20", relief="raised")  # Dark form background
    style.configure("TLabel", background="#231F20", foreground="#70C7BA", font=("Arial", 11, "bold"))  # Teal labels
    style.configure("TButton", font=("Arial", 12, "bold"), padding=10, relief="flat")  # Modern button

    # Main Frame (Dark Form Area)
    frame = ttk.Frame(root, padding=20, style="TFrame")
    frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

    # Load and Display the Kaspa Logo
    image = Image.open(LOGO_PATH_DARK_BACKGROUND)
    image = image.resize((436, 182), Image.LANCZOS)
    logo_img = ImageTk.PhotoImage(image)

    logo_label = tk.Label(frame, image=logo_img, bg="#231F20")
    logo_label.image = logo_img
    logo_label.grid(row=0, columnspan=2, pady=5)  # Centered logo

    # Function to Create Input Fields with Greyed-Out Placeholder
    def add_input(label_text, row, placeholder_text):
        ttk.Label(frame, text=label_text).grid(row=row, column=0, sticky="w", pady=5, padx=5)

        entry_frame = tk.Frame(frame, bg="#FFFFFF", highlightbackground="#70C7BA", highlightthickness=2, bd=0)
        entry_frame.grid(row=row, column=1, padx=10, pady=5)

        entry = tk.Entry(entry_frame, width=30, font=("Arial", 11), bg="#FFFFFF", fg="grey",
                         relief="flat", bd=0)
        entry.insert(0, placeholder_text)  # Prefilled example text

        # **Remove Placeholder on Focus**
        def on_focus_in(event):
            if entry.get() == placeholder_text:
                entry.delete(0, tk.END)
                entry.config(fg="#231F20")  # Switch to normal text color

        # **Restore Placeholder if Left Empty**
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
    current_price = add_input("Current KAS Price ($):", 3, "e.g., 0.1211 (aka 12.11 cents)")
    circulating_supply = add_input("Circulating Supply (Billions):", 4, "e.g., 25.6 (aka 25,600,000,000 KAS)")
    purchase_price = add_input("Avg Purchase Price (Optional):", 5, "e.g., 0.1735 (aka 17.35 cents)")

    # **Generate PDF Button**
    generate_button = tk.Button(frame, text="Generate PDF", command=generate_pdf,
                                bg="#70C7BA", fg="#231F20", font=("Arial", 12, "bold"),
                                relief="flat", bd=5, padx=20, pady=10, cursor="hand2")
    generate_button.grid(row=6, columnspan=2, pady=25)  # Centered with better spacing

    # Add Text Below the Button
    info_label = ttk.Label(frame, text="PDF saved in execution directory. App generated by Kaspa community member.",
                           foreground="#70C7BA", background="#231F20", font=("Arial", 9))
    info_label.grid(row=7, columnspan=2, pady=(0, 10))  # Slight padding for better spacing

    root.mainloop()


# Run GUI
if __name__ == "__main__":
    create_gui()
