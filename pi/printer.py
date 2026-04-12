import logging
import os
from datetime import datetime, timedelta

import usb.core
import qrcode
from PIL import Image, ImageDraw, ImageFont

# brother_ql uses Image.ANTIALIAS which was removed in Pillow 10 — patch it back
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

from brother_ql.conversion import convert
from brother_ql.backends.helpers import send
from brother_ql.raster import BrotherQLRaster

log = logging.getLogger(__name__)

LABEL_WIDTH_PX = 720  # 62mm at ~300dpi
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_PATH_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
TITLE_FONT_SIZE_START = 80
BODY_FONT_SIZE_START = 60
FONT_SIZE_MIN = 20
PADDING = 20
TITLE_BODY_GAP = 10  # pixels between title and body text


# ---------------------------------------------------------------------------
# Printer availability check
# ---------------------------------------------------------------------------

def is_printer_available(printer_identifier: str) -> bool:
    """
    Check whether the printer is connected and reachable.
    Supports 'usb://0xVID:0xPID' and 'file:///dev/usb/lpX' identifiers.
    """
    try:
        if printer_identifier.startswith('file://'):
            path = printer_identifier.replace('file://', '')
            return os.path.exists(path)
        elif printer_identifier.startswith('usb://'):
            parts = printer_identifier.replace('usb://', '').split(':')
            vid = int(parts[0], 16)
            pid = int(parts[1], 16)
            return usb.core.find(idVendor=vid, idProduct=pid) is not None
    except Exception as e:
        log.warning('Printer availability check failed: %s', e)
    return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fit_font(text: str, size_start: int, bold: bool = True) -> tuple:
    """Return (font, w, h) with font shrunk until text fits label width."""
    path = FONT_PATH if bold else FONT_PATH_REGULAR
    font_size = size_start
    while font_size >= FONT_SIZE_MIN:
        font = ImageFont.truetype(path, font_size)
        tmp = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(tmp)
        bbox = draw.multiline_textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if w <= LABEL_WIDTH_PX - 2 * PADDING:
            return font, w, h
        font_size -= 2
    font = ImageFont.truetype(path, FONT_SIZE_MIN)
    tmp = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(tmp)
    bbox = draw.multiline_textbbox((0, 0), text, font=font)
    return font, bbox[2] - bbox[0], bbox[3] - bbox[1]


def _fmt_date(iso: str) -> str:
    """Convert ISO date string (YYYY-MM-DD) to DD.MM.YYYY for display."""
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return iso  # return as-is if format is unexpected


def _build_image(rows: list) -> Image.Image:
    """
    Build a label image from a list of (text, font) tuples rendered top-to-bottom.
    Each row is left-aligned with PADDING. Rows are separated by TITLE_BODY_GAP.
    """
    tmp = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(tmp)
    heights = []
    for text, font in rows:
        bbox = draw.multiline_textbbox((0, 0), text, font=font)
        heights.append(bbox[3] - bbox[1])

    img_h = PADDING + sum(heights) + TITLE_BODY_GAP * (len(rows) - 1) + PADDING
    img = Image.new("RGB", (LABEL_WIDTH_PX, img_h), "white")
    draw = ImageDraw.Draw(img)

    y = PADDING
    for i, (text, font) in enumerate(rows):
        draw.multiline_text((PADDING, y), text, fill="black", font=font, align="left")
        y += heights[i] + TITLE_BODY_GAP

    return img


# ---------------------------------------------------------------------------
# Label renderers
# ---------------------------------------------------------------------------

def _render_freetext(data: dict) -> Image.Image:
    """
    First line = title (large bold font).
    Remaining lines = body (smaller bold font).
    """
    lines = data["text"].split("\n", 1)
    title = lines[0]
    body = lines[1] if len(lines) > 1 else ""

    title_font, _, _ = _fit_font(title, TITLE_FONT_SIZE_START)
    rows = [(title, title_font)]

    if body:
        body_font, _, _ = _fit_font(body, BODY_FONT_SIZE_START)
        rows.append((body, body_font))

    return _build_image(rows)


def _render_qrcode(data: dict) -> Image.Image:
    """QR code filling the full label width, square."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=1,
    )
    qr.add_data(data["content"])
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_size = LABEL_WIDTH_PX - 2 * PADDING
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    img = Image.new("RGB", (LABEL_WIDTH_PX, LABEL_WIDTH_PX), "white")
    img.paste(qr_img, (PADDING, PADDING))
    return img


def _render_material_storage(data: dict) -> Image.Image:
    """
    Privates Material  (title)
    <member name>
    Wird abgeholt bis zum DD.MM.YYYY  (auto: today + 21 days)
    Material wird nach Ablauf der Frist vom Fablab entsorgt
    """
    pickup_date = _fmt_date(
        (datetime.now() + timedelta(days=21)).strftime('%Y-%m-%d')
    )
    disclaimer = "Material wird nach Ablauf der Frist vom Fablab entsorgt"

    title_font,      _, _ = _fit_font("Privates Material", TITLE_FONT_SIZE_START)
    member_font,     _, _ = _fit_font(data["member"], BODY_FONT_SIZE_START)
    date_font,       _, _ = _fit_font(f"Wird abgeholt bis zum {pickup_date}", BODY_FONT_SIZE_START)
    disclaimer_font, _, _ = _fit_font(disclaimer, BODY_FONT_SIZE_START)

    return _build_image([
        ("Privates Material", title_font),
        (data["member"], member_font),
        (f"Wird abgeholt bis zum {pickup_date}", date_font),
        (disclaimer, disclaimer_font),
    ])


def _render_filament(data: dict) -> Image.Image:
    """
    Title:  <filament_type>  (large bold)
            Geöffnet am: DD.MM.YYYY
    """
    title_font, _, _ = _fit_font(data["filament_type"], TITLE_FONT_SIZE_START)
    date_font, _, _ = _fit_font("Geöffnet am: XX.XX.XXXX", BODY_FONT_SIZE_START)

    return _build_image([
        (data["filament_type"], title_font),
        (f"Geöffnet am: {_fmt_date(data['opened'])}", date_font),
    ])


def _render_3d_print(data: dict) -> Image.Image:
    """
    Title:  3D Print Pickup  (large bold)
    Body:   member name
            Abholung am: DD.MM.YYYY
    """
    title_font, _, _ = _fit_font("3D Print Pickup", TITLE_FONT_SIZE_START)
    member_font, _, _ = _fit_font(data["member"], BODY_FONT_SIZE_START)
    date_font, _, _ = _fit_font("Abholung am: XX.XX.XXXX", BODY_FONT_SIZE_START)

    return _build_image([
        ("3D Print Pickup", title_font),
        (data["member"], member_font),
        (f"Abholung am: {_fmt_date(data['pickup_date'])}", date_font),
    ])


# ---------------------------------------------------------------------------
# Low-level send
# ---------------------------------------------------------------------------

def _send(img: Image.Image, printer_identifier: str, model: str,
          media: str, backend: str) -> None:
    """Convert image to raster instructions and send to printer. Raises on error."""
    qlr = BrotherQLRaster(model)
    qlr.exception_on_warning = True
    instructions = convert(
        qlr=qlr,
        images=[img],
        label=media,
        rotate="0",
        threshold=70.0,
        dither=False,
        compress=False,
        red=False,
        dpi_600=False,
        hq=True,
        cut=True,
    )
    send(
        instructions=instructions,
        printer_identifier=printer_identifier,
        backend_identifier=backend,
        blocking=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def print_label(
    label_type: str,
    data: dict,
    printer_identifier: str,
    model: str,
    media: str = "62",
    backend: str = "pyusb",
) -> bool:
    """
    Render and print a label.

    Args:
        label_type: One of 'freetext', 'qrcode', 'material_storage',
                    'filament', '3d_print'.
        data: Dict of label fields as received from MQTT payload.
        printer_identifier: e.g. "usb://0x04f9:0x209b" or "file:///dev/usb/lp0".
        model: Brother QL model string, e.g. "QL-800".
        media: Label identifier — "62" for 62mm endless.
        backend: "pyusb" for USB, "network" for Wi-Fi.

    Returns:
        True on success, False on error.
    """
    try:
        if label_type == "freetext":
            copies = int(data.get("copies", 1))
            img = _render_freetext(data)
            for i in range(copies):
                _send(img, printer_identifier, model, media, backend)
                log.info("Printed copy %d of %d.", i + 1, copies)

        elif label_type == "qrcode":
            _send(_render_qrcode(data), printer_identifier, model, media, backend)

        elif label_type == "material_storage":
            total = int(data.get("pieces", 1))
            img = _render_material_storage(data)
            for piece in range(1, total + 1):
                _send(img, printer_identifier, model, media, backend)
                log.info("Printed piece %d of %d.", piece, total)

        elif label_type == "filament":
            _send(_render_filament(data), printer_identifier, model, media, backend)

        elif label_type == "3d_print":
            _send(_render_3d_print(data), printer_identifier, model, media, backend)

        else:
            log.error("Unknown label_type: %s", label_type)
            return False

        log.info("Print job '%s' completed.", label_type)
        return True

    except Exception as e:
        log.error("Print failed: %s", e)
        return False
