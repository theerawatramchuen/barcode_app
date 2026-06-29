import os, io, json, base64
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
A4_W_MM, A4_H_MM = 210, 297

# ── In-memory product store (pandas DataFrame) ────────────────────────────────
COLUMNS = ['name', 'barcode', 'price', 'type', 'group', 'comment']

def _empty_df():
    return pd.DataFrame(columns=COLUMNS)

def _load_xlsx():
    path = os.path.join(BASE_DIR, 'products.xlsx')
    if not os.path.exists(path):
        return _empty_df()
    df = pd.read_excel(path, header=None, dtype=str).fillna('')
    # Map however many columns exist → our schema
    col_map = COLUMNS[:len(df.columns)]
    df.columns = col_map
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ''
    return df[COLUMNS].copy()

# Initialise global DataFrame
_df = _load_xlsx()

def get_df():
    return _df

def save_df():
    """Persist DataFrame back to products.xlsx."""
    global _df
    path = os.path.join(BASE_DIR, 'products.xlsx')
    _df.to_excel(path, index=False, header=False)

# ── Settings ──────────────────────────────────────────────────────────────────
SETTINGS_PATH = os.path.join(BASE_DIR, 'settings.json')

def load_settings():
    with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_settings(data):
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ── Barcode / PDF helpers ─────────────────────────────────────────────────────
class OffsetImageWriter(ImageWriter):
    def __init__(self, font_offset_mm=0.0):
        super().__init__()
        self._font_offset_mm = font_offset_mm
    def _paint_text(self, xpos, ypos):
        super()._paint_text(xpos, ypos + self._font_offset_mm)

def find_font(size_px):
    candidates = [
        'C:/Windows/Fonts/THSarabunNew.ttf',
        'C:/Windows/Fonts/tahoma.ttf',
        'C:/Windows/Fonts/arial.ttf',
        '/usr/share/fonts/truetype/thai/Sarabun-Regular.ttf',
        '/usr/share/fonts/truetype/tlwg/TlwgTypo.ttf',
        '/System/Library/Fonts/Supplemental/Tahoma.ttf',
        '/Library/Fonts/Arial Unicode.ttf',
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size_px)
            except Exception:
                continue
    return ImageFont.load_default()

def _centre_text(draw, text, font, canvas_w, y):
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        tw = bb[2] - bb[0]
    except AttributeError:
        tw, _ = draw.textsize(text, font=font)
    x = max(0, (canvas_w - tw) // 2)
    draw.text((x, y), text, font=font, fill='black')

def generate_barcode_image(product_name, price_str, barcode_str,
                           width_mm, height_mm,
                           font_size_pt=8, font_offset_mm=0.0,
                           font_line1_px=36, font_line2_px=28):
    DPI = 300
    px_per_mm = DPI / 25.4
    total_w = int(width_mm  * px_per_mm)
    total_h = int(height_mm * px_per_mm)

    text_h = int(total_h * 0.30)
    bc_h   = total_h - text_h

    # Barcode strip
    bc_buf = io.BytesIO()
    opts = {
        'module_width':  0.2,
        'module_height': (bc_h / px_per_mm) * 0.60,
        'quiet_zone':    1,
        'font_size':     int(font_size_pt),
        'text_distance': 1.5,
        'write_text':    True,
        'dpi':           DPI,
    }
    Code128(barcode_str, writer=OffsetImageWriter(font_offset_mm)).write(bc_buf, options=opts)
    bc_buf.seek(0)
    bc_img = Image.open(bc_buf).convert('RGB').resize((total_w, bc_h), Image.LANCZOS)

    # Text area — line1 and line2 with independent font sizes
    text_img = Image.new('RGB', (total_w, text_h), 'white')
    draw     = ImageDraw.Draw(text_img)
    f1 = find_font(max(8, font_line1_px))
    f2 = find_font(max(8, font_line2_px))
    _centre_text(draw, product_name,       f1, total_w, 2)
    _centre_text(draw, f"{price_str}.-",   f2, total_w, text_h // 2)

    final = Image.new('RGB', (total_w, total_h), 'white')
    final.paste(text_img, (0, 0))
    final.paste(bc_img,   (0, text_h))
    return final

def create_pdf(product_name, price_str, barcode_str,
               barcode_w_mm, barcode_h_mm, per_page, total_qty,
               font_size_pt=8, font_offset_mm=0.0,
               font_line1_px=36, font_line2_px=28):
    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=A4)
    _, a4_h = A4
    margin_mm, gap_mm = 10, 3
    cols = max(1, int((A4_W_MM - 2*margin_mm + gap_mm) / (barcode_w_mm + gap_mm)))
    rows = max(1, int((A4_H_MM - 2*margin_mm + gap_mm) / (barcode_h_mm + gap_mm)))
    ppe  = min(per_page, cols * rows)

    img = generate_barcode_image(product_name, price_str, barcode_str,
                                 barcode_w_mm, barcode_h_mm,
                                 font_size_pt, font_offset_mm,
                                 font_line1_px, font_line2_px)
    img_buf = io.BytesIO()
    img.save(img_buf, format='PNG')

    printed = page_n = 0
    while printed < total_qty:
        if page_n > 0: c.showPage()
        page_n += 1
        on_page = min(ppe, total_qty - printed)
        ci = ri = 0
        for _ in range(on_page):
            x_pt = (margin_mm + ci*(barcode_w_mm+gap_mm)) * mm
            y_pt = a4_h - (margin_mm + ri*(barcode_h_mm+gap_mm) + barcode_h_mm) * mm
            img_buf.seek(0)
            c.drawImage(ImageReader(img_buf), x_pt, y_pt,
                        width=barcode_w_mm*mm, height=barcode_h_mm*mm)
            ci += 1
            if ci >= cols: ci, ri = 0, ri+1
        printed += on_page
    c.save()
    buf.seek(0)
    return buf

# ── Routes — main page ────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html',
                           products=get_df().to_dict('records'),
                           settings=load_settings())

# ── Routes — settings ─────────────────────────────────────────────────────────
@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    return jsonify(load_settings())

@app.route('/api/settings', methods=['POST'])
def api_save_settings():
    data = request.json
    save_settings(data)
    return jsonify({'ok': True})

# ── Routes — products CRUD ────────────────────────────────────────────────────
@app.route('/products')
def products_page():
    return render_template('products.html', settings=load_settings())

@app.route('/api/products', methods=['GET'])
def api_get_products():
    return jsonify(get_df().to_dict('records'))

@app.route('/api/products', methods=['POST'])
def api_add_product():
    global _df
    row = {c: request.json.get(c, '') for c in COLUMNS}
    _df = pd.concat([_df, pd.DataFrame([row])], ignore_index=True)
    save_df()
    return jsonify({'ok': True, 'total': len(_df)})

@app.route('/api/products/<int:idx>', methods=['PUT'])
def api_update_product(idx):
    global _df
    if idx < 0 or idx >= len(_df):
        return jsonify({'error': 'Index out of range'}), 404
    for col in COLUMNS:
        if col in request.json:
            _df.at[idx, col] = request.json[col]
    save_df()
    return jsonify({'ok': True})

@app.route('/api/products/<int:idx>', methods=['DELETE'])
def api_delete_product(idx):
    global _df
    if idx < 0 or idx >= len(_df):
        return jsonify({'error': 'Index out of range'}), 404
    _df = _df.drop(index=idx).reset_index(drop=True)
    save_df()
    return jsonify({'ok': True, 'total': len(_df)})


@app.route('/api/products/import', methods=['POST'])
def api_import_products():
    global _df
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    f = request.files['file']
    try:
        df = pd.read_excel(f, header=None, dtype=str).fillna('')
        col_map = COLUMNS[:len(df.columns)]
        df.columns = col_map
        for c in COLUMNS:
            if c not in df.columns:
                df[c] = ''
        _df = df[COLUMNS].copy()
        save_df()
        return jsonify({'ok': True, 'count': len(_df)})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/products/export')
def api_export_products():
    buf = io.BytesIO()
    get_df().to_excel(buf, index=False, header=False)
    buf.seek(0)
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='products.xlsx')

# ── Routes — barcode preview & generate ───────────────────────────────────────
@app.route('/api/preview', methods=['POST'])
def preview():
    d = request.json
    w, h         = float(d['width_mm']), float(d['height_mm'])
    per_page     = int(d['per_page'])
    total_qty    = int(d['total_qty'])
    fsp          = int(d.get('font_size_pt', 8))
    foff         = float(d.get('font_offset_mm', 0.0))
    fl1          = int(d.get('font_line1_px', 36))
    fl2          = int(d.get('font_line2_px', 28))

    margin_mm, gap_mm = 10, 3
    cols = max(1, int((A4_W_MM - 2*margin_mm + gap_mm) / (w + gap_mm)))
    rows = max(1, int((A4_H_MM - 2*margin_mm + gap_mm) / (h + gap_mm)))
    ppe  = min(per_page, cols * rows)
    prev = min(total_qty, ppe)

    DPI = 96
    bc_img = generate_barcode_image(d['product_name'], d['price'], d['barcode'],
                                    w, h, fsp, foff, fl1, fl2)
    bw = int(w / 25.4 * DPI); bh = int(h / 25.4 * DPI)
    sm = bc_img.resize((bw, bh), Image.LANCZOS)

    page = Image.new('RGB', (int(A4_W_MM/25.4*DPI), int(A4_H_MM/25.4*DPI)), 'white')
    mp = int(margin_mm/25.4*DPI); gp = int(gap_mm/25.4*DPI)
    ci = ri = 0
    for _ in range(prev):
        page.paste(sm, (mp + ci*(bw+gp), mp + ri*(bh+gp)))
        ci += 1
        if ci >= cols: ci, ri = 0, ri+1

    out = io.BytesIO(); page.save(out, format='PNG')
    b64 = base64.b64encode(out.getvalue()).decode()
    return jsonify({'preview_image': f'data:image/png;base64,{b64}',
                    'cols': cols, 'rows': rows,
                    'per_page_effective': ppe,
                    'total_pages': -(-total_qty // ppe)})

@app.route('/api/generate', methods=['POST'])
def generate():
    d = request.json
    pdf = create_pdf(d['product_name'], d['price'], d['barcode'],
                     float(d['width_mm']), float(d['height_mm']),
                     int(d['per_page']), int(d['total_qty']),
                     int(d.get('font_size_pt', 8)),
                     float(d.get('font_offset_mm', 0.0)),
                     int(d.get('font_line1_px', 36)),
                     int(d.get('font_line2_px', 28)))
    safe = "".join(c for c in d['product_name'] if c.isalnum() or c in ' _-').strip()
    return send_file(pdf, mimetype='application/pdf',
                     as_attachment=True, download_name=f"barcode_{safe}.pdf")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
