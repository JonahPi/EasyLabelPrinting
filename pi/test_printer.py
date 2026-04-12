"""
Test the label printer with all label types.
Usage:
    python3 test_printer.py freetext
    python3 test_printer.py qrcode
    python3 test_printer.py material_storage
    python3 test_printer.py filament
    python3 test_printer.py 3d_print
    python3 test_printer.py all
"""
import sys
from printer import print_label
import config

SAMPLES = {
    "freetext": {
        "label_type": "freetext",
        "data": {"text": "Hello World\nThis is a test label\nLine three", "copies": 2},
    },
    "qrcode": {
        "label_type": "qrcode",
        "data": {"content": "https://github.com/JonahPi/EasyLabelPrinting"},
    },
    "material_storage": {
        "label_type": "material_storage",
        "data": {
            "member": "Max Mustermann",
            "pickup_before": "2026-04-30",
            "pieces": 3,
        },
    },
    "filament": {
        "label_type": "filament",
        "data": {
            "opened": "2026-04-11",
            "filament_type": "PLA 1.75mm Black",
        },
    },
    "3d_print": {
        "label_type": "3d_print",
        "data": {
            "member": "Max Mustermann",
            "pickup_date": "2026-04-15",
        },
    },
}

if len(sys.argv) < 2 or sys.argv[1] not in list(SAMPLES.keys()) + ["all"]:
    print(__doc__)
    sys.exit(1)

types_to_print = list(SAMPLES.keys()) if sys.argv[1] == "all" else [sys.argv[1]]

for lt in types_to_print:
    sample = SAMPLES[lt]
    print(f"Printing {lt}...")
    success = print_label(
        label_type=sample["label_type"],
        data=sample["data"],
        printer_identifier=config.PRINTER_IDENTIFIER,
        model=config.PRINTER_MODEL,
        media=config.LABEL_MEDIA,
        backend=config.PRINTER_BACKEND,
    )
    print("OK." if success else "FAILED.")
