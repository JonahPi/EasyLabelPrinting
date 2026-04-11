"""
Test the label printer with both label types.
Usage:
    python3 test_printer.py freetext "Hello World"
    python3 test_printer.py qrcode "https://example.com"
"""
import sys
from printer import print_label
import config

if len(sys.argv) < 3:
    print("Usage: python3 test_printer.py <freetext|qrcode> <content>")
    sys.exit(1)

label_type = sys.argv[1]
content = sys.argv[2]

if label_type not in ("freetext", "qrcode"):
    print("label_type must be 'freetext' or 'qrcode'")
    sys.exit(1)

print(f"Printing {label_type} label: {content}")
success = print_label(
    label_type=label_type,
    content=content,
    printer_identifier=config.PRINTER_IDENTIFIER,
    model=config.PRINTER_MODEL,
    media=config.LABEL_MEDIA,
    backend=config.PRINTER_BACKEND,
)
print("Done." if success else "Print failed — check logs.")
