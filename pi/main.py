import logging
import signal
import subprocess
import sys
import threading

import config
from key_manager import KeyManager
from mqtt_client import MQTTClient, TOPIC_STATUS
from printer import print_label, is_printer_available
from qr_generator import make_qr_image, make_home_image

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

    # ── Display helpers ───────────────────────────────────────────────────────

    def show_home_screen() -> None:
        if display:
            img = make_home_image(config.PWA_BASE_URL)
            display.wake_and_show(img)
        log.info('Home screen shown.')

    def show_release_qr() -> None:
        url = f'{config.PWA_BASE_URL}?key={keys.current_key}'
        if display:
            img = make_qr_image(url)
            display.wake_and_show(img)
        log.info('Release QR shown. Key: %s  URL: %s', keys.current_key, url)

    def refresh_display() -> None:
        with pending_lock:
            has_pending = pending['label_type'] is not None
        if has_pending:
            show_release_qr()
        else:
            show_home_screen()

    # ── MQTT callbacks ────────────────────────────────────────────────────────

    def on_data(label_type: str, data: dict) -> None:
        with pending_lock:
            pending['label_type'] = label_type
            pending['data']       = data
        log.info('Pending job stored: type=%s', label_type)
        show_release_qr()

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
            show_home_screen()
        else:
            log.error('Print failed — key not rotated, pending job kept.')
        publish_printer_status(force=True)

    # ── Start ─────────────────────────────────────────────────────────────────

    mqtt = MQTTClient(
        broker=config.MQTT_BROKER,
        port=config.MQTT_PORT_TLS,
        on_data=on_data,
        on_release=on_release,
    )
    mqtt.connect()
    show_home_screen()

    # ── Printer status publisher ───────────────────────────────────────────────

    _last_printer_status = {'online': None}  # mutable container for closure

    def publish_printer_status(force: bool = False) -> None:
        """Check printer and publish retained status only when it changes."""
        online = is_printer_available(config.PRINTER_IDENTIFIER)
        if force or online != _last_printer_status['online']:
            _last_printer_status['online'] = online
            status = 'online' if online else 'offline'
            mqtt.publish(TOPIC_STATUS, {'printer': status}, retain=True)
            log.info('Printer status changed: %s', status)

    publish_printer_status(force=True)  # publish immediately on startup

    # Periodic QR refresh (every 5 min)
    def _refresh_loop():
        while not stop_event.wait(config.QR_REFRESH_INTERVAL_SECONDS):
            log.info('Periodic QR refresh.')
            refresh_display()

    # Printer check loop (every 60s, publish only on change)
    def _printer_check_loop():
        while not stop_event.wait(config.PRINTER_CHECK_INTERVAL_SECONDS):
            publish_printer_status()

    # Network watchdog (ping every 30s; reset wlan0 after 3 consecutive failures)
    net_fail_count = 0

    def _network_watchdog_loop():
        nonlocal net_fail_count
        while not stop_event.wait(config.NET_WATCHDOG_INTERVAL_SECONDS):
            r = subprocess.run(
                ['ping', '-c', '1', '-W', '3', config.NET_WATCHDOG_PING_HOST],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            if r.returncode == 0:
                if net_fail_count:
                    log.info('Network restored.')
                net_fail_count = 0
            else:
                net_fail_count += 1
                log.warning('Network ping failed (%d/%d)', net_fail_count, config.NET_WATCHDOG_FAIL_THRESHOLD)
                if net_fail_count >= config.NET_WATCHDOG_FAIL_THRESHOLD:
                    log.error('Resetting %s interface.', config.NET_WATCHDOG_IFACE)
                    subprocess.run(
                        ['sudo', 'ip', 'link', 'set', config.NET_WATCHDOG_IFACE, 'down'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    stop_event.wait(3)
                    subprocess.run(
                        ['sudo', 'ip', 'link', 'set', config.NET_WATCHDOG_IFACE, 'up'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    net_fail_count = 0

    threading.Thread(target=_refresh_loop,        daemon=True).start()
    threading.Thread(target=_printer_check_loop,  daemon=True).start()
    threading.Thread(target=_network_watchdog_loop, daemon=True).start()

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
