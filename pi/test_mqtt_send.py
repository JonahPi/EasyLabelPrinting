"""
Quick test: publish a freetext label message to the public MQTT broker.
Usage:
    python3 test_mqtt_send.py <key> [text]

Example:
    python3 test_mqtt_send.py d28577ed4953 "Hello World"
"""
import json
import ssl
import sys

import paho.mqtt.publish as publish

import config


def send_test_message(key: str, text: str) -> None:
    topic = f"labels/{key}"
    payload = json.dumps({
        "key": key,
        "label_type": "freetext",
        "data": {"text": text},
    })
    print(f"Publishing to topic '{topic}': {payload}")
    publish.single(
        topic=topic,
        payload=payload,
        hostname=config.MQTT_BROKER,
        port=config.MQTT_PORT_TLS,
        tls={"tls_version": ssl.PROTOCOL_TLS_CLIENT, "cert_reqs": ssl.CERT_REQUIRED},
        qos=1,
    )
    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 test_mqtt_send.py <key> [text]")
        sys.exit(1)
    key = sys.argv[1]
    text = sys.argv[2] if len(sys.argv) > 2 else "Test label from Pi"
    send_test_message(key, text)
