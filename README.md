# Kaspa Portfolio Projection (KPP)

A Python application for generating Kaspa portfolio projections and reports. This tool provides a user-friendly GUI where users can input their Kaspa holdings, current market price, and circulating supply to generate a comprehensive portfolio projection report.

## Features

- Generates price intervals for Kaspa using linear and logarithmic scaling.
- Computes portfolio value and market capitalization at various price points.
- Exports a well-formatted PDF report with a Kaspa logo, portfolio summary, and a price table.
- Provides a user-friendly graphical interface for seamless input and report generation.

## Installation

Ensure you have Python installed on your system. Then, install the required dependencies:

```sh
pip install pandas fpdf numpy pillow
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

3. Enter the required portfolio details in the GUI.
4. Click the **Generate PDF** button to save your portfolio projection report.

## Requirements

This script requires the following Python libraries:
- `pandas` (for handling tabular data)
- `fpdf` (for PDF report generation)
- `numpy` (for price interval calculations)
- `tkinter` (for the GUI application)
- `PIL (Pillow)` (for image handling in the GUI)

## Screenshots

_(Add relevant screenshots here if available)_

## Contributing

Contributions are welcome! Feel free to submit a pull request or open an issue.

## License

This project is open-source and maintained by the Kaspa community.

## Acknowledgments

Special thanks to the Kaspa community for supporting open-source development.

---

Developed by the Kaspa Community 🚀

