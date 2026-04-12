import logging
import signal
import sys
import threading

import config
from key_manager import KeyManager
from mqtt_client import MQTTClient, TOPIC_STATUS
from printer import print_label, is_printer_available
from qr_generator import make_qr_image

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
)
log = logging.getLogger('main')

try:
    from epaper_display import EpaperDisplay
    _display_available = True
except Exception as e:
    log.warning('E-paper display not available: %s — display updates skipped.', e)
    _display_available = False


def main():
    keys    = KeyManager()
    display = EpaperDisplay() if _display_available else None

    # In-memory pending job store — one slot, overwritten by each new submission
    pending = {'label_type': None, 'data': None}
    pending_lock = threading.Lock()

    stop_event = threading.Event()

    # ── Display helper ────────────────────────────────────────────────────────

    def refresh_display() -> None:
        url = f'{config.PWA_BASE_URL}?key={keys.current_key}'
        if display:
            img = make_qr_image(url)
            display.wake_and_show(img)
        log.info('Active key: %s  QR URL: %s', keys.current_key, url)

    # ── MQTT callbacks ────────────────────────────────────────────────────────

    def on_data(label_type: str, data: dict) -> None:
        with pending_lock:
            pending['label_type'] = label_type
            pending['data']       = data
        log.info('Pending job stored: type=%s', label_type)

    def on_release(key: str) -> None:
        if not keys.validate(key):
            log.warning('Release key mismatch — ignoring.')
            return

        with pending_lock:
            label_type = pending['label_type']
            data       = pending['data']

        if label_type is None:
            log.warning('Release received but no pending job — ignoring.')
            return

        log.info('Printing pending job: type=%s', label_type)
        success = print_label(
            label_type=label_type,
            data=data,
            printer_identifier=config.PRINTER_IDENTIFIER,
            model=config.PRINTER_MODEL,
            media=config.LABEL_MEDIA,
            backend=config.PRINTER_BACKEND,
        )

        if success:
            with pending_lock:
                pending['label_type'] = None
                pending['data']       = None
            keys.rotate()
            refresh_display()
        else:
            log.error('Print failed — key not rotated, pending job kept.')
        publish_printer_status()

    # ── Start ─────────────────────────────────────────────────────────────────

    mqtt = MQTTClient(
        broker=config.MQTT_BROKER,
        port=config.MQTT_PORT_TLS,
        on_data=on_data,
        on_release=on_release,
    )
    mqtt.connect()
    refresh_display()

    # ── Printer status publisher ───────────────────────────────────────────────

    def publish_printer_status() -> None:
        online = is_printer_available(config.PRINTER_IDENTIFIER)
        mqtt.publish(TOPIC_STATUS, {'printer': 'online' if online else 'offline'})
        log.info('Printer status: %s', 'online' if online else 'offline')

    publish_printer_status()  # publish immediately on startup

    # Periodic QR refresh + printer status check
    def _refresh_loop():
        while not stop_event.wait(config.QR_REFRESH_INTERVAL_SECONDS):
            log.info('Periodic QR refresh.')
            refresh_display()
            publish_printer_status()

    threading.Thread(target=_refresh_loop, daemon=True).start()

    def _shutdown(sig, frame):
        log.info('Shutdown signal received.')
        stop_event.set()
        mqtt.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT,  _shutdown)

    log.info('EasyLabelPrinting running.')
    signal.pause()


if __name__ == '__main__':
    main()
