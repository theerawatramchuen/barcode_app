import os
import io
import json
import base64
import pandas as pd

try:
    import chardet
    _CHARDET = True
except ImportError:
    _CHARDET = False

from flask import Flask, render_template, request, jsonify, send_file
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from barcode import Code128
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)
BASE_DIR = os.path.dirname(__file__)

A4_W_MM = 210
A4_H_MM = 297

# ── Custom writer that supports a vertical text offset ──────────────────────
class OffsetImageWriter(ImageWriter):
    def __init__(self, font_offset_mm=0.0):
        super().__init__()
        self._font_offset_mm = font_offset_mm

    def _paint_text(self, xpos, ypos):
        super()._paint_text(xpos, ypos + self._font_offset_mm)

# ── Helpers ──────────────────────────────────────────────────────────────────
def load_settings():
    with open(os.path.join(BASE_DIR, 'settings.json'), 'r') as f:
        return json.load(f)

def load_products():
    """Load products.xlsx — col A: name, col B: barcode, col C: price."""
    path = os.path.join(BASE_DIR, 'products.xlsx')
    df = pd.read_excel(path, header=None, dtype={0: str, 1: str, 2: str})
    df.columns = ['name', 'barcode', 'price']
    df['barcode'] = df['barcode'].astype(str).str.strip()
    df['price']   = df['price'].astype(str).str.strip()
    df['name']    = df['name'].astype(str).str.strip()
    return df.to_dict('records')

def find_font(size_px):
    """Find a font that supports Thai; fall back to default."""
    candidates = [
        # Thai fonts common on Windows / Linux / Mac
        'C:/Windows/Fonts/THSarabunNew.ttf',
        'C:/Windows/Fonts/tahoma.ttf',
        'C:/Windows/Fonts/arial.ttf',
        '/usr/share/fonts/truetype/thai/Sarabun-Regular.ttf',
        '/usr/share/fonts/truetype/tlwg/TlwgTypo.ttf',
        '/System/Library/Fonts/Supplemental/Tahoma.ttf',
        '/Library/Fonts/Arial Unicode.ttf',
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                from PIL import ImageFont
                return ImageFont.truetype(path, size_px)
            except Exception:
                continue
    from PIL import ImageFont
    return ImageFont.load_default()

def generate_barcode_image(product_name, price_str, barcode_str,
                           width_mm, height_mm,
                           font_size_pt=8, font_offset_mm=0.0):
    """
    Build a composite label image:
      Line 1 — product name
      Line 2 — price + '.-'
      Line 3 — Code-128 barcode + number
    """
    DPI = 300
    px_per_mm = DPI / 25.4
    total_w   = int(width_mm  * px_per_mm)
    total_h   = int(height_mm * px_per_mm)

    # ── Proportions ─────────────────────────────────────────────────────────
    # Top text area: ~30% of height; barcode area: ~70%
    text_h  = int(total_h * 0.30)
    bc_h    = total_h - text_h

    # ── 1. Render the barcode strip ──────────────────────────────────────────
    bc_buf = io.BytesIO()
    options = {
        'module_width':  0.2,
        'module_height': (bc_h / px_per_mm) * 0.60,
        'quiet_zone':    1,
        'font_size':     int(font_size_pt),
        'text_distance': 1.5,
        'write_text':    True,
        'dpi':           DPI,
    }
    writer = OffsetImageWriter(font_offset_mm=font_offset_mm)
    Code128(barcode_str, writer=writer).write(bc_buf, options=options)
    bc_buf.seek(0)
    bc_img = Image.open(bc_buf).convert('RGB')
    bc_img = bc_img.resize((total_w, bc_h), Image.LANCZOS)

    # ── 2. Render the top text area ──────────────────────────────────────────
    text_img = Image.new('RGB', (total_w, text_h), 'white')
    draw     = ImageDraw.Draw(text_img)

    line1 = product_name
    line2 = f"{price_str}.-"

    font_px = max(12, int(text_h * 0.40))   # each line ~40% of text area
    font    = find_font(font_px)

    # Centre line 1
    try:
        bb = draw.textbbox((0, 0), line1, font=font)
        tw = bb[2] - bb[0]
    except AttributeError:
        tw, _ = draw.textsize(line1, font=font)
    x1 = max(0, (total_w - tw) // 2)
    draw.text((x1, 2), line1, font=font, fill='black')

    # Centre line 2
    try:
        bb = draw.textbbox((0, 0), line2, font=font)
        tw = bb[2] - bb[0]
    except AttributeError:
        tw, _ = draw.textsize(line2, font=font)
    x2 = max(0, (total_w - tw) // 2)
    y2 = text_h // 2
    draw.text((x2, y2), line2, font=font, fill='black')

    # ── 3. Stack text + barcode ──────────────────────────────────────────────
    final = Image.new('RGB', (total_w, total_h), 'white')
    final.paste(text_img, (0, 0))
    final.paste(bc_img,   (0, text_h))

    return final


def create_pdf(product_name, price_str, barcode_str,
               barcode_w_mm, barcode_h_mm,
               per_page, total_qty,
               font_size_pt=8, font_offset_mm=0.0):
    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)
    a4_w, a4_h = A4

    margin_mm = 10
    gap_mm    = 3

    cols = max(1, int((A4_W_MM - 2*margin_mm + gap_mm) / (barcode_w_mm + gap_mm)))
    rows = max(1, int((A4_H_MM - 2*margin_mm + gap_mm) / (barcode_h_mm + gap_mm)))
    per_page_effective = min(per_page, cols * rows)

    img = generate_barcode_image(product_name, price_str, barcode_str,
                                 barcode_w_mm, barcode_h_mm,
                                 font_size_pt, font_offset_mm)
    img_buf = io.BytesIO()
    img.save(img_buf, format='PNG')

    printed = page_count = 0
    while printed < total_qty:
        if page_count > 0:
            c.showPage()
        page_count += 1
        on_this_page = min(per_page_effective, total_qty - printed)
        col_idx = row_idx = 0
        for _ in range(on_this_page):
            x_mm = margin_mm + col_idx * (barcode_w_mm + gap_mm)
            y_mm = margin_mm + row_idx * (barcode_h_mm + gap_mm)
            x_pt = x_mm * mm
            y_pt = a4_h - (y_mm + barcode_h_mm) * mm
            img_buf.seek(0)
            c.drawImage(ImageReader(img_buf), x_pt, y_pt,
                        width=barcode_w_mm*mm, height=barcode_h_mm*mm)
            col_idx += 1
            if col_idx >= cols:
                col_idx = 0
                row_idx += 1
        printed += on_this_page

    c.save()
    buf.seek(0)
    return buf

# ── Routes ───────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html',
                           products=load_products(),
                           settings=load_settings())

@app.route('/api/settings')
def api_settings():
    return jsonify(load_settings())

@app.route('/api/preview', methods=['POST'])
def preview():
    d             = request.json
    w             = float(d['width_mm'])
    h             = float(d['height_mm'])
    per_page      = int(d['per_page'])
    total_qty     = int(d['total_qty'])
    font_size_pt  = int(d.get('font_size_pt', 8))
    font_offset   = float(d.get('font_offset_mm', 0.0))

    margin_mm, gap_mm = 10, 3
    cols         = max(1, int((A4_W_MM - 2*margin_mm + gap_mm) / (w + gap_mm)))
    rows_max     = max(1, int((A4_H_MM - 2*margin_mm + gap_mm) / (h + gap_mm)))
    per_page_eff = min(per_page, cols * rows_max)
    total_prev   = min(total_qty, per_page_eff)

    DPI = 96
    bc_img = generate_barcode_image(
        d['product_name'], d['price'], d['barcode'],
        w, h, font_size_pt, font_offset)
    bc_w_px = int(w / 25.4 * DPI)
    bc_h_px = int(h / 25.4 * DPI)
    bc_small = bc_img.resize((bc_w_px, bc_h_px), Image.LANCZOS)

    a4_w_px = int(A4_W_MM / 25.4 * DPI)
    a4_h_px = int(A4_H_MM / 25.4 * DPI)
    page    = Image.new('RGB', (a4_w_px, a4_h_px), 'white')

    margin_px = int(margin_mm / 25.4 * DPI)
    gap_px    = int(gap_mm    / 25.4 * DPI)
    col_idx = row_idx = 0
    for _ in range(total_prev):
        page.paste(bc_small,
                   (margin_px + col_idx*(bc_w_px+gap_px),
                    margin_px + row_idx*(bc_h_px+gap_px)))
        col_idx += 1
        if col_idx >= cols:
            col_idx = 0
            row_idx += 1

    out = io.BytesIO()
    page.save(out, format='PNG')
    b64 = base64.b64encode(out.getvalue()).decode()
    return jsonify({
        'preview_image':    f'data:image/png;base64,{b64}',
        'cols':             cols,
        'rows':             rows_max,
        'per_page_effective': per_page_eff,
        'total_pages':      -(-total_qty // per_page_eff),
    })

@app.route('/api/generate', methods=['POST'])
def generate():
    d            = request.json
    w            = float(d['width_mm'])
    h            = float(d['height_mm'])
    per_page     = int(d['per_page'])
    total_qty    = int(d['total_qty'])
    font_size_pt = int(d.get('font_size_pt', 8))
    font_offset  = float(d.get('font_offset_mm', 0.0))

    pdf = create_pdf(d['product_name'], d['price'], d['barcode'],
                     w, h, per_page, total_qty, font_size_pt, font_offset)
    safe = "".join(c for c in d['product_name'] if c.isalnum() or c in ' _-').strip()
    return send_file(pdf, mimetype='application/pdf',
                     as_attachment=True, download_name=f"barcode_{safe}.pdf")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
