# Kaspa Portfolio Projection (KPP) - GUI Application

A Python application for generating Kaspa portfolio projections and reports. This tool provides a user-friendly GUI where users can input their Kaspa holdings, current market price, and circulating supply to generate a comprehensive portfolio projection report. The application also fetches real-time Kaspa price data from CoinGecko and allows users to export detailed projections in a well-formatted PDF.

## Features

- Fetches real-time Kaspa price data and circulating supply from CoinGecko.
- Generates price intervals for Kaspa using both linear and logarithmic scaling.
- Computes portfolio value and market capitalization at various price points.
- Provides an interactive graphical interface with input validation and tooltips.
- Displays portfolio projections in a sortable table with color-coded price levels.
- Exports a professional-grade PDF report including a price table and key portfolio metrics.
- Supports multiple currencies (USD, EUR, BTC) for price and portfolio value conversions.
- Features a slider that can link to the chart for ease of portfolio projections.

## Installation

Ensure you have Python installed on your system. Then, install the required dependencies:

```sh
pip install pandas fpdf numpy pillow tkinter pycoingecko fpdf logging
```

<details>
<summary><strong>Getting Python on Windows</strong> (Click to expand)</summary>

If you do not have Python installed on your Windows computer, follow these steps:

1. Visit the official Python website: [https://www.python.org/downloads/windows/](https://www.python.org/downloads/windows/)
2. Download the latest stable version of Python.
3. Run the installer and ensure you check the box **"Add Python to PATH"** before proceeding with the installation.
4. Verify the installation by opening Command Prompt (`cmd`) and running:
   ```sh
   python --version
   ```
   If Python is installed correctly, it will display the installed version number.

</details>

## Usage

1. Clone this repository or download the script.
2. Run the script using Python:

   ```sh
   python kpp.py
   ```

3. Enter the required portfolio details in the GUI or fetch real-time data.
4. Click the **Generate PDF** button to save your portfolio projection report.

## Requirements

This script requires the following Python libraries:
- `pandas` (for handling tabular data)
- `fpdf` (for PDF report generation)
- `numpy` (for price interval calculations)
- `tkinter` (for the GUI application)
- `PIL (Pillow)` (for image handling in the GUI)
- `pycoingecko` (for real-time price fetching)
- `logging` (for error tracking and debugging)

## Examples

### Main Application GUI
![Main GUI](screenshots/KPP-App-Screenshot.png)

### Main Application GUI - Filled In
![Main GUI - Filled In](screenshots/KPP-App-Screenshot-Filled_In.png)

### Main Application GUI - Filled In with Linked Slider in use and additional columns added to chart.
![Main GUI - Slider & More Columns](screenshots/KPP-App-Screenshot-Filled_In-Slider.png)

### Sample PDF Report
![Sample PDF - view in /docs](docs/KPP-App-Example-PDF.pdf)

## Compiled Executable

If you would like a compiled executable, install the required dependencies for compiled executable generation:

```sh
pip install pyinstaller
```

I've compiled the python application into an executable that can be run usinig the following command:
   ```sh
   pyinstaller --noconsole --onefile --name="Kaspa Projection Projection (KPP)" `
   --icon="pics\kaspa.ico" `
   --add-data "pics\kaspa.ico;pics" `
   --add-data "pics\Kaspa-LDSP-Dark-Full-Color.png;pics" `
   --add-data "pics\Kaspa-LDSP-Dark-Reverse.png;pics" `
   kpp.py
   ```

The compiled file can be found in the `compiled/` directory. A checksum is included for verification.

## Contributing

Contributions are welcome! Feel free to submit a pull request or open an issue.

## License

This project is open-source and maintained by the Kaspa community.

## Acknowledgments

Special thanks to the Kaspa community for supporting open-source development.

---

Developed by the Kaspa Community 🚀

