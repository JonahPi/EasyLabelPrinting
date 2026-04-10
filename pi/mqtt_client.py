import json
import logging
import ssl
from typing import Callable

import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)


class MQTTSubscriber:
    def __init__(
        self,
        broker: str,
        port: int,
        key_validator: Callable[[str], bool],
        on_valid_message: Callable[[str], None],
    ):
        self._validator = key_validator
        self._on_valid = on_valid_message
        self._active_topic: str = ""

        self._client = mqtt.Client(
            client_id="",
            protocol=mqtt.MQTTv5,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self._client.tls_set(
            cert_reqs=ssl.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

        self._broker = broker
        self._port = port

    def set_topic(self, key: str) -> None:
        """Switch subscription to the new key topic."""
        if self._active_topic and self._client.is_connected():
            self._client.unsubscribe(self._active_topic)
        self._active_topic = f"labels/{key}"
        if self._client.is_connected():
            self._client.subscribe(self._active_topic, qos=1)
            log.info("Subscribed to %s", self._active_topic)

    def connect(self) -> None:
        self._client.connect(self._broker, self._port, keepalive=60)
        self._client.loop_start()

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            log.info("MQTT connected to %s:%s", self._broker, self._port)
            if self._active_topic:
                client.subscribe(self._active_topic, qos=1)
                log.info("Subscribed to %s", self._active_topic)
        else:
            log.error("MQTT connection failed: reason_code=%s", reason_code)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        log.warning("MQTT disconnected: reason_code=%s — will reconnect", reason_code)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            log.warning("Malformed MQTT message: %s", e)
            return

        key = payload.get("key", "")
        label_type = payload.get("label_type", "")
        text = payload.get("data", {}).get("text", "")

        if not self._validator(key):
            log.warning("Invalid key received — ignoring message.")
            return
        if label_type != "freetext":
            log.warning("Unsupported label_type '%s' — ignoring.", label_type)
            return
        if not text or len(text) > 500:
            log.warning("Invalid text payload (empty or >500 chars) — ignoring.")
            return

        log.info("Valid print request received.")
        self._on_valid(text)
