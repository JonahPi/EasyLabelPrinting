"""Quick test: show a QR code on the e-paper display."""
from epaper_display import EpaperDisplay
from qr_generator import make_qr_image

print("Initializing display...")
d = EpaperDisplay()

print("Generating QR code...")
img = make_qr_image("https://jonahpi.github.io/EasyLabelPrinting/?key=test1234")

print("Showing QR code on display...")
d.wake_and_show(img)

print("Done.")
