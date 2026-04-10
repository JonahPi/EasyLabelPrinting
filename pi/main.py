import logging
import signal
import sys
import threading

import config
from key_manager import KeyManager
from mqtt_client import MQTTSubscriber
from printer import print_label
from qr_generator import make_qr_image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("main")

# E-paper display is imported lazily so the app can run (partially) without
# the SPI hardware attached — useful for Phase 1 testing without the display.
try:
    from epaper_display import EpaperDisplay
    _display_available = True
except Exception as e:
    log.warning("E-paper display not available: %s — display updates skipped.", e)
    _display_available = False


def main():
    keys = KeyManager()
    display = EpaperDisplay() if _display_available else None
    stop_event = threading.Event()

    def refresh_display(key: str) -> None:
        if display is None:
            log.info("(no display) QR URL would be: %s?key=%s", config.PWA_BASE_URL, key)
            return
        url = f"{config.PWA_BASE_URL}?key={key}"
        img = make_qr_image(url)
        display.wake_and_show(img)
        log.info("Display updated. Active key: %s", key)

    def rotate_and_refresh() -> None:
        """Rotate session key, update display, update MQTT subscription."""
        keys.rotate()
        refresh_display(keys.current_key)
        mqtt.set_topic(keys.current_key)

    def on_valid_print(text: str) -> None:
        success = print_label(
            text=text,
            printer_identifier=config.PRINTER_IDENTIFIER,
            model=config.PRINTER_MODEL,
            media=config.LABEL_MEDIA,
            backend=config.PRINTER_BACKEND,
        )
        if success:
            rotate_and_refresh()
        else:
            log.error("Print failed — key not rotated, try again.")

    mqtt = MQTTSubscriber(
        broker=config.MQTT_BROKER,
        port=config.MQTT_PORT_TLS,
        key_validator=keys.validate,
        on_valid_message=on_valid_print,
    )

    # Initial display + MQTT subscription
    refresh_display(keys.current_key)
    mqtt.connect()
    mqtt.set_topic(keys.current_key)

    # Background thread: periodic QR refresh (security hygiene — key unchanged)
    def _refresh_loop():
        while not stop_event.wait(config.QR_REFRESH_INTERVAL_SECONDS):
            log.info("Periodic QR refresh (key unchanged).")
            refresh_display(keys.current_key)

    threading.Thread(target=_refresh_loop, daemon=True).start()

    def _shutdown(sig, frame):
        log.info("Shutdown signal received.")
        stop_event.set()
        mqtt.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info("EasyLabelPrinting running. Active key: %s", keys.current_key)
    signal.pause()


if __name__ == "__main__":
    main()
