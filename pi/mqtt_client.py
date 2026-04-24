import json
import logging
import ssl
from typing import Callable

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)

TOPIC_DATA    = 'easylabel/data'
TOPIC_RELEASE = 'easylabel/release'
TOPIC_STATUS  = 'easylabel/status'


class MQTTClient:
    def __init__(
        self,
        broker: str,
        port: int,
        on_data:    Callable[[str, dict], None],
        on_release: Callable[[str], None],
    ):
        """
        on_data(label_type, data)  — called when a label job arrives on easylabel/data
        on_release(key)            — called when a print release arrives on easylabel/release
        """
        self._on_data    = on_data
        self._on_release = on_release
        self._broker     = broker
        self._port       = port

        self._client = mqtt.Client(
            client_id='',
            protocol=mqtt.MQTTv5,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self._client.tls_set(
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        self._client.on_connect    = self._on_connect
        self._client.on_message    = self._on_message
        self._client.on_disconnect = self._on_disconnect

    def connect(self) -> None:
        self._client.reconnect_delay_set(min_delay=1, max_delay=60)
        self._client.connect(self._broker, self._port, keepalive=30)
        self._client.loop_start()

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def publish(self, topic: str, payload: dict, retain: bool = False) -> None:
        """Publish a JSON message to the given topic (fire-and-forget)."""
        try:
            self._client.publish(topic, json.dumps(payload), qos=1, retain=retain)
        except Exception as e:
            log.warning('Publish to %s failed: %s', topic, e)

    # ── Internal callbacks ────────────────────────────────────────────────────

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            client.subscribe(TOPIC_DATA,    qos=1)
            client.subscribe(TOPIC_RELEASE, qos=1)
            log.info('MQTT connected — subscribed to %s and %s', TOPIC_DATA, TOPIC_RELEASE)
        else:
            log.error('MQTT connection failed: %s', reason_code)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            log.info('MQTT disconnected cleanly.')
        else:
            log.warning('MQTT disconnected unexpectedly (%s) — reconnecting with backoff (1–60 s)', reason_code)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            log.warning('Malformed MQTT message on %s: %s', msg.topic, e)
            return

        if msg.topic == TOPIC_DATA:
            self._handle_data(payload)
        elif msg.topic == TOPIC_RELEASE:
            self._handle_release(payload)

    def _handle_data(self, payload: dict):
        label_type = payload.get('label_type', '')
        data       = payload.get('data', {})
        valid_types = {'freetext', 'freetext_banner', 'qrcode', 'material_storage', 'filament', '3d_print'}
        if label_type not in valid_types:
            log.warning('Unknown label_type "%s" — ignoring.', label_type)
            return
        if not isinstance(data, dict):
            log.warning('Invalid data field — ignoring.')
            return
        log.info('Label data received: type=%s', label_type)
        self._on_data(label_type, data)

    def _handle_release(self, payload: dict):
        key = payload.get('key', '')
        if not key:
            log.warning('Release message missing key — ignoring.')
            return
        log.info('Release signal received.')
        self._on_release(key)
