# MQTT
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT_TLS = 8883
MQTT_KEEPALIVE = 60

# PWA
PWA_BASE_URL = "https://jonahpi.github.io/EasyLabelPrinting/"

# Timing
QR_REFRESH_INTERVAL_SECONDS = 300   # 5 minutes
PRINTER_CHECK_INTERVAL_SECONDS = 60 # 1 minute

# Printer — QL-800 via USB (upgrade to QL-820NWB + "network" backend later)
PRINTER_IDENTIFIER = "usb://0x04f9:0x209b"  # verify PID with lsusb; fallback: "file:///dev/usb/lp0"
PRINTER_MODEL = "QL-800"
PRINTER_BACKEND = "pyusb"
LABEL_MEDIA = "62"  # 62mm endless

# Network watchdog
NET_WATCHDOG_INTERVAL_SECONDS = 30   # ping interval
NET_WATCHDOG_FAIL_THRESHOLD   = 3    # consecutive failures before interface reset
NET_WATCHDOG_PING_HOST        = "8.8.8.8"
NET_WATCHDOG_IFACE            = "wlan0"

# E-Paper (Waveshare 1.54" 200x200, SPI)
EPAPER_WIDTH = 200
EPAPER_HEIGHT = 200

# QR image
QR_IMAGE_SIZE = 200   # pixels — fills the 200x200 display
QR_BORDER_BOXES = 1   # minimal quiet zone
