import logging

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
FONT_SIZE_START = 60
FONT_SIZE_MIN = 20
PADDING = 20


def _render_text_image(text: str) -> Image.Image:
    """
    Render free text onto an RGB image for 62mm endless media.
    Width is fixed at 720px; height is determined by the text content.
    Font size auto-shrinks to fit within the label width.
    """
    font_size = FONT_SIZE_START
    font = None

    while font_size >= FONT_SIZE_MIN:
        font = ImageFont.truetype(FONT_PATH, font_size)
        tmp = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(tmp)
        bbox = draw.multiline_textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        if text_w <= LABEL_WIDTH_PX - 2 * PADDING:
            break
        font_size -= 2

    # Final measurement with chosen font
    tmp = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(tmp)
    bbox = draw.multiline_textbbox((0, 0), text, font=font)
    text_h = bbox[3] - bbox[1]

    img_h = text_h + 2 * PADDING
    img = Image.new("RGB", (LABEL_WIDTH_PX, img_h), "white")
    draw = ImageDraw.Draw(img)
    draw.multiline_text((PADDING, PADDING), text, fill="black", font=font, align="left")
    return img


def _render_qr_image(content: str) -> Image.Image:
    """
    Render a QR code onto an RGB image for 62mm endless media.
    The QR code is square, filling the full label width.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=1,
    )
    qr.add_data(content)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_size = LABEL_WIDTH_PX - 2 * PADDING
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    img = Image.new("RGB", (LABEL_WIDTH_PX, LABEL_WIDTH_PX), "white")
    img.paste(qr_img, (PADDING, PADDING))
    return img


def print_label(
    label_type: str,
    content: str,
    printer_identifier: str,
    model: str,
    media: str = "62",
    backend: str = "pyusb",
) -> bool:
    """
    Render and print a label.

    Args:
        label_type: "freetext" or "qrcode".
        content: Text to print, or URL/string to encode as QR code.
        printer_identifier: e.g. "usb://0x04f9:0x209b" or "file:///dev/usb/lp0".
        model: Brother QL model string, e.g. "QL-800".
        media: Label identifier — "62" for 62mm endless.
        backend: "pyusb" for USB, "network" for Wi-Fi.

    Returns:
        True on success, False on error.
    """
    try:
        if label_type == "qrcode":
            img = _render_qr_image(content)
        else:
            img = _render_text_image(content)
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
        log.info("Print job sent successfully.")
        return True
    except Exception as e:
        log.error("Print failed: %s", e)
        return False
