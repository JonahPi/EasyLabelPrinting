import qrcode
from PIL import Image
from config import QR_IMAGE_SIZE, QR_BORDER_BOXES


def make_qr_image(url: str) -> Image.Image:
    """
    Returns a QR code as a PIL Image (mode '1', black/white) sized for the
    200x200 Waveshare e-paper display.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=QR_BORDER_BOXES,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.convert("1")
    img = img.resize((QR_IMAGE_SIZE, QR_IMAGE_SIZE), Image.LANCZOS)
    return img
