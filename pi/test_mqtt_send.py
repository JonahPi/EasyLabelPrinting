"""
Test the two-topic MQTT flow without the PWA.

Usage:
    # Step 1 — send label data (simulates PWA prepare):
    python3 test_mqtt_send.py data freetext
    python3 test_mqtt_send.py data qrcode
    python3 test_mqtt_send.py data material_storage
    python3 test_mqtt_send.py data filament
    python3 test_mqtt_send.py data 3d_print

    # Step 2 — send release signal (simulates scanning the QR code):
    python3 test_mqtt_send.py release <key>
"""
import json
import ssl
import sys

import paho.mqtt.publish as publish

import config

BROKER  = config.MQTT_BROKER
PORT    = config.MQTT_PORT_TLS
TLS     = {'tls_version': ssl.PROTOCOL_TLS_CLIENT, 'cert_reqs': ssl.CERT_REQUIRED}

SAMPLES = {
    'freetext': {
        'label_type': 'freetext',
        'data': {'text': 'Hallo Welt\nDas ist ein Test', 'copies': 1},
    },
    'qrcode': {
        'label_type': 'qrcode',
        'data': {'content': 'https://github.com/JonahPi/EasyLabelPrinting'},
    },
    'material_storage': {
        'label_type': 'material_storage',
        'data': {'member': 'Max Mustermann', 'pickup_before': '2026-04-30', 'pieces': 2},
    },
    'filament': {
        'label_type': 'filament',
        'data': {'filament_type': 'PLA 1.75mm', 'opened': '2026-04-12'},
    },
    '3d_print': {
        'label_type': '3d_print',
        'data': {'member': 'Max Mustermann', 'pickup_date': '2026-04-15'},
    },
}


def send(topic, payload):
    print(f'Publishing to {topic}: {json.dumps(payload)}')
    publish.single(topic, payload=json.dumps(payload), hostname=BROKER,
                   port=PORT, tls=TLS, qos=1)
    print('Done.')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'data':
        label_type = sys.argv[2] if len(sys.argv) > 2 else 'freetext'
        if label_type not in SAMPLES:
            print(f'Unknown label type: {label_type}')
            sys.exit(1)
        send('easylabel/data', SAMPLES[label_type])

    elif cmd == 'release':
        if len(sys.argv) < 3:
            print('Usage: python3 test_mqtt_send.py release <key>')
            sys.exit(1)
        send('easylabel/release', {'key': sys.argv[2]})

    else:
        print(__doc__)
        sys.exit(1)
