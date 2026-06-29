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
| `pandas` | In-memory product data store |
| `openpyxl` | Excel (.xlsx) read/write engine |
| `chardet` | Optional — auto-detect file encoding |

---

## Run

```bash
python app.py
```

Then open your browser at: **http://localhost:5000**

---

## Application Pages

| URL | Description |
|---|---|
| `http://localhost:5000/` | Home — select product, configure settings, preview and generate PDF |
| `http://localhost:5000/products` | Manage Products — add, edit, delete, import and export |

---

## Home Page Usage

1. **Search** — type in the search box to filter products by name, type, group, or barcode.
2. **Select a product** — click any row to highlight it.
3. **Adjust print settings** — size, quantity, font sizes, and text offset.
4. **Save Settings** — click the green *Save Settings* button to persist values to `settings.json`.
5. **Preview** — verify the label layout on a simulated A4 page before printing.
6. **Generate PDF** — download the print-ready PDF file.

---

## Products Page Usage

Reached via the **Manage Products** button in the top-right header.

| Action | How |
|---|---|
| **Add** | Click *Add Product* → fill the modal form → confirm |
| **Edit** | Click the pencil icon on any row to open the edit modal, or click directly into any cell to edit inline |
| **Delete** | Click the trash icon on any row (confirmation required) |
| **Search** | Type in the search box to filter by any field |
| **Import XLSX** | Click *Import XLSX* and select a file — replaces all products |
| **Export XLSX** | Click *Export XLSX* to download the current product list |

---

## Label Format

Each barcode label is a 3-line composite image:

```
┌─────────────────────────┐
│      Product Name       │  ← Column A  (font_line1_px)
│        Price.-          │  ← Column C  (font_line2_px)  e.g. 16.-
│  ▐▌▐▐▌▌▐▐▌▌▐▌▌▐▌▐▐▌▐▌▐ │  ← Code-128 barcode
│     8530000001148       │  ← Column B  (font_size_pt)
└─────────────────────────┘
```

- Top 30% of the label — product name and price
- Bottom 70% of the label — barcode bars and number

---

## File Structure

```
barcode_app/
├── app.py              ← Flask server, DataFrame store, barcode/PDF logic
├── products.xlsx       ← Product data (auto-saved on every change)
├── settings.json       ← Default print settings (editable in UI or directly)
├── templates/
│   ├── index.html      ← Home page (barcode generator)
│   └── products.html   ← Products management page
└── README.md
```

---

## products.xlsx Format

No header row. Six columns:

| Column | Field | Required | Example |
|---|---|---|---|
| A | Product name (Thai or English) | ✅ | สันรูด 17 มิล |
| B | Barcode number (Code-128) | ✅ | 8530000001148 |
| C | Unit price | — | 16 |
| D | Type | — | Stationery |
| E | Group | — | Office |
| F | Comment | — | Seasonal item |

The price is displayed on the label as `16.-`

When importing an XLSX file, only the columns present are read.
Missing columns default to empty string.

---

## settings.json

All default print settings are stored in `settings.json`.
Edit this file directly, or use the **Save Settings** button in the UI.

```json
{
  "barcode_width_mm":  50,
  "barcode_height_mm": 30,
  "per_page":          20,
  "total_qty":         50,
  "font_size_pt":       8,
  "font_offset_mm":     0.0,
  "font_line1_px":     36,
  "font_line2_px":     28
}
```

| Key | Description | Unit |
|---|---|---|
| `barcode_width_mm` | Label width | mm |
| `barcode_height_mm` | Label height | mm |
| `per_page` | Labels per page (auto-capped by label size) | count |
| `total_qty` | Total labels to generate across all pages | count |
| `font_size_pt` | Barcode number text size | pt |
| `font_offset_mm` | Vertical shift of barcode number (+ = down, − = up) | mm |
| `font_line1_px` | Product name font size at 300 DPI | px |
| `font_line2_px` | Price font size at 300 DPI | px |

> **Font size guide (300 DPI):** 24 px ≈ 6 pt · 36 px ≈ 9 pt · 48 px ≈ 12 pt

---

## Page Layout

- **Margin:** 10 mm on all sides
- **Gap between labels:** 3 mm
- **Page size:** A4 (210 × 297 mm)
- The app auto-calculates columns and rows that fit, and caps *Per Page* accordingly.

---

## Thai Font Support

The app automatically searches for a Thai-compatible TrueType font:

| Platform | Fonts searched |
|---|---|
| Windows | `THSarabunNew.ttf`, `Tahoma.ttf`, `Arial.ttf` |
| Linux | `Sarabun-Regular.ttf`, `TlwgTypo.ttf` |
| macOS | `Tahoma.ttf`, `Arial Unicode.ttf` |

If none are found, the system default font is used (Latin characters only).
For best Thai rendering on Windows, install **TH Sarabun New**.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Home page |
| GET | `/products` | Products management page |
| GET | `/api/products` | List all products (JSON) |
| POST | `/api/products` | Add a product |
| PUT | `/api/products/<idx>` | Update a product by index |
| DELETE | `/api/products/<idx>` | Delete a product by index |
| POST | `/api/products/import` | Import products from uploaded XLSX |
| GET | `/api/products/export` | Download products as XLSX |
| GET | `/api/settings` | Get current settings (JSON) |
| POST | `/api/settings` | Save settings to settings.json |
| POST | `/api/preview` | Generate A4 preview image (base64 PNG) |
| POST | `/api/generate` | Generate and download PDF |
