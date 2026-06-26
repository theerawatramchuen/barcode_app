# Barcode Generator — A4 PDF for Laser Printer

A local web application that generates Code-128 barcodes laid out on A4 PDF pages,
optimised for laser printing. Supports Thai and English product names.

---

## Requirements

Python 3.8+

## Install Dependencies

```bash
pip install flask python-barcode reportlab pillow pandas openpyxl chardet
```

| Package | Purpose |
|---|---|
| `flask` | Web server |
| `python-barcode` | Code-128 barcode generation |
| `reportlab` | PDF creation |
| `pillow` | Image compositing (label layout) |
| `pandas` | Reading products.xlsx |
| `openpyxl` | Excel (.xlsx) file engine |
| `chardet` | Optional — auto-detect file encoding |

---

## Run

```bash
python app.py
```

Then open your browser at: **http://localhost:5000**

---

## Usage

1. **Select a product** from the table — click any row to highlight it.
2. **Adjust print settings** in the left panel (size, quantity, font, offset).
3. **Click Preview** to verify the label layout on a simulated A4 page.
4. **Click Generate PDF** to download the print-ready PDF file.

---

## Label Format

Each barcode label is a 3-line composite image:

```
┌─────────────────────────┐
│      Product Name       │  ← Column A
│        Price.-          │  ← Column C  (e.g. 16.-)
│  ▐▌▐▐▌▌▐▐▌▌▐▌▌▐▌▐▐▌▐▌▐ │  ← Code-128 barcode
│     8530000001148       │  ← Column B  (barcode number)
└─────────────────────────┘
```

- Top 30% of the label — product name and price
- Bottom 70% of the label — barcode bars and number

---

## File Structure

```
barcode_app/
├── app.py              ← Flask server & barcode/PDF logic
├── products.xlsx       ← Product data (see format below)
├── settings.json       ← Default print settings
├── templates/
│   └── index.html      ← Web UI
└── README.md
```

---

## products.xlsx Format

No header row. Three columns:

| Column | Field | Example |
|---|---|---|
| A | Product name (Thai or English) | สันรูด 17 มิล |
| B | Barcode number (Code-128) | 8530000001148 |
| C | Unit price | 16 |

The price is displayed on the label as `16.-`

---

## settings.json

All default print settings are stored in `settings.json` and loaded on startup.
Edit this file to change the defaults without touching any code.

```json
{
  "barcode_width_mm":  22,
  "barcode_height_mm": 12,
  "per_page":          20,
  "total_qty":         50,
  "font_size_pt":       8,
  "font_offset_mm":     1.0
}
```

| Key | Description |
|---|---|
| `barcode_width_mm` | Label width in millimetres |
| `barcode_height_mm` | Label height in millimetres |
| `per_page` | Barcodes per page (auto-capped by label size) |
| `total_qty` | Total number of labels to generate |
| `font_size_pt` | Barcode number font size in points |
| `font_offset_mm` | Vertical shift of barcode number text (+ = down, − = up) |

---

## Page Layout

- **Margin:** 10 mm on all sides
- **Gap between labels:** 3 mm
- **Page size:** A4 (210 × 297 mm)
- The app auto-calculates how many labels fit per page and caps the *Per Page* setting accordingly.

---

## Thai Font Support

The app automatically searches for a Thai-compatible font in common locations:

- Windows: `THSarabunNew.ttf`, `Tahoma.ttf`, `Arial.ttf`
- Linux: `Sarabun-Regular.ttf`, `TlwgTypo.ttf`
- macOS: `Tahoma.ttf`, `Arial Unicode.ttf`

If none are found, it falls back to the system default font (Latin characters only).
For best Thai rendering on Windows, ensure **TH Sarabun New** is installed.
