# Barcode Generator — A4 PDF for Laser Printer

A local web application that generates Code-128 barcodes laid out on A4 PDF pages,
optimised for laser printing.

## Requirements

Python 3.8+

## Install dependencies

```bash
pip install flask python-barcode reportlab pillow pandas chardet
```

> **Note:** `chardet` is optional but recommended — it auto-detects the encoding of `products.csv` (needed for Thai / non-UTF-8 files). The app works without it using a built-in fallback chain.

## Run

```bash
python app.py
```

Then open your browser at: **http://localhost:5000**

## Usage

1. **Select a product** from the table (click any row).
2. **Adjust settings** — barcode size (width × height in mm), barcodes per page, total quantity.
3. **Click Preview** to see the first-page layout before printing.
4. **Click Generate PDF** to download the ready-to-print PDF file.

## Files

```
barcode_app/
├── app.py          ← Flask server
├── products.csv    ← Product list (Column A = name, Column B = barcode number)
├── templates/
│   └── index.html  ← UI
└── README.md
```

## CSV Format

The `products.csv` file has no header row. Column A is the product name,
Column B is the barcode number (used as Code-128 barcode data).

Example:
```
A4 Paper,1234567894
Notebook,1234567895
Pencil,1234567896
```

## Defaults

| Setting | Default |
|---|---|
| Barcode width | 22 mm |
| Barcode height | 12 mm |
| Per page | 20 |
| Total qty | 50 |
| Font Size | 8 |
| Font Offset | 1.0 |

The app automatically caps "per page" to however many barcodes fit the A4 page
given your chosen barcode size and a 10 mm margin / 3 mm gap.
