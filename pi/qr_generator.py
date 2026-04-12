import qrcode
from PIL import Image, ImageDraw, ImageFont
from config import QR_IMAGE_SIZE, QR_BORDER_BOXES


def make_home_image(url: str) -> Image.Image:
    """
    Returns a 200x200 home screen image: title at top, smaller QR code below.
    Shown when no label is pending.
    """
    img = Image.new('1', (200, 200), 1)  # white background
    draw = ImageDraw.Draw(img)

    # Title text
    title1 = "Easy Label"
    title2 = "Printer"
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
    except Exception:
        font = ImageFont.load_default()

    for i, line in enumerate([title1, title2]):
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        draw.text(((200 - w) // 2, 4 + i * 22), line, font=font, fill=0)

    # Smaller QR code below title
    qr_size = 150
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color='black', back_color='white').convert('1')
    qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
    img.paste(qr_img, ((200 - qr_size) // 2, 48))

    return img


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
