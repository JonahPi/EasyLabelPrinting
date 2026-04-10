# Functional Specification Document (FSD)

**Project:** Dynamic Label Printing System with Raspberry Pi, E-Paper Display, and MQTT
**Version:** 1.1
**Date:** 11.04.2026
**Author:** Bernd Heisterkamp

------

## 1. Introduction

### 1.1 Purpose

This document describes the functionality of a system that:

- Connects a **Brother QL-800 label printer** (USB) to a **Raspberry Pi**.
- Uses an **E-Paper display** to show a dynamic QR code.
- Provides a **Progressive Web App (PWA)** for entering free-text label content.
- Exchanges data via **MQTT** (public cloud broker) between the PWA and Raspberry Pi.
- Validates the data and sends it to the label printer.

### 1.2 Scope

- **Hardware:** Raspberry Pi 2B (→ Zero 2 W later), Brother QL-800 via USB (→ QL-820NWB later), 1.54" E-Paper display (SPI).
- **Software:** Python script (Raspberry Pi), PWA (frontend, deferred to Phase 2), MQTT broker (public cloud).
- **Protocols:** MQTT over TLS, Wi-Fi.

------

## 2. System Overview

### 2.1 Components

| Component                     | Description                                                                 |
| ----------------------------- | --------------------------------------------------------------------------- |
| **Raspberry Pi 2B**           | Controls the printer, display, and MQTT communication. Runs the Python script. Will migrate to Zero 2 W. |
| **Brother QL-800**            | Prints labels via USB. Label media: 62mm endless. Will upgrade to QL-820NWB (Wi-Fi). |
| **E-Paper Display**           | 1.54" DEBO EPA 1.54 (Waveshare-compatible, 200×200px, SPI). Displays a dynamic QR code. |
| **Progressive Web App (PWA)** | Web interface for entering free-text label content. Deferred to Phase 2.    |
| **MQTT Broker**               | HiveMQ public cloud broker (`broker.hivemq.com`). No authentication required. TLS on port 8883 (Pi) / WSS port 8884 (browser). |

### 2.2 Data Flow

```plaintext
1. Raspberry Pi generates a random session key → builds QR code URL → shows on E-Paper display.
2. User scans QR code → PWA opens with key pre-filled in URL.
3. User enters free text → PWA publishes JSON to MQTT topic labels/<key>.
4. Raspberry Pi validates key, renders text as image, sends to printer.
5. Printer prints label on 62mm endless media.
6. Pi rotates session key and updates QR code on display.
```

------

## 3. Functional Requirements

### 3.1 Raspberry Pi Python Script

| ID   | Requirement                                                    | Details                                                                 | Status |
| ---- | -------------------------------------------------------------- | ----------------------------------------------------------------------- | ------ |
| FR1  | Connect to Brother printer via USB.                            | `brother_ql` library, backend `pyusb`, identifier `usb://0x04f9:0x209b`. Fallback: `file:///dev/usb/lp0`. | Done   |
| FR2  | Generate dynamic QR code (URL + random key) and display on E-Paper. | `qrcode` + `Pillow 9.5.0`, Waveshare vendored driver. 200×200px, mode '1'. | Implemented (display deferred to Phase 2 hardware) |
| FR3  | Implement MQTT client (subscribe to topic `labels/<key>`).     | `paho-mqtt 2.1.0`, MQTTv5, TLS port 8883, QoS 1.                       | Done   |
| FR4  | Validate received data (key check + payload structure).        | Constant-time compare (`secrets.compare_digest`). Validates `label_type`, text length ≤ 500 chars. | Done   |
| FR5  | Render free text as image and print on 62mm endless media.     | Fixed width 720px, DejaVuSans-Bold font, auto-shrink from size 60 to 20. `brother_ql` convert + send. | Done   |
| FR6  | Rotate session key and refresh QR after each successful print. | New key generated with `secrets.token_hex(6)` (48-bit entropy).        | Done   |
| FR7  | Periodic QR refresh every 5 minutes (security hygiene).        | Background thread, key unchanged on timer refresh.                      | Done   |
| FR8  | Run as systemd service with auto-restart.                      | `systemd/easylabel.service`.                                            | Done   |

### 3.2 Progressive Web App (PWA) — Phase 2

| ID   | Requirement                         | Details                              | Status   |
| ---- | ----------------------------------- | ------------------------------------ | -------- |
| FR9  | Open from QR scan, extract key from URL. | `?key=<key>` query parameter.    | Deferred |
| FR10 | Provide textarea for free-text entry and Print button. | Single-page, vanilla JS. | Deferred |
| FR11 | Publish JSON to MQTT topic `labels/<key>`. | `MQTT.js 5.3.4`, WSS port 8884. | Deferred |
| FR12 | Offline capability via Service Worker. | Cache-first strategy.               | Deferred |
| FR13 | Hosted on GitHub Pages.             | Auto-deploy via GitHub Actions.      | Deferred |

### 3.3 MQTT Message Contract

Topic: `labels/<key>`

```json
{
  "key": "d28577ed4953",
  "label_type": "freetext",
  "data": {
    "text": "Hello World\nLine 2"
  }
}
```

Validation rules (Pi-side): key match, `label_type` = `"freetext"`, text non-empty and ≤ 500 chars.

------

## 4. Non-Functional Requirements

| ID   | Requirement                                    | Details                                         |
| ---- | ---------------------------------------------- | ----------------------------------------------- |
| NF1  | System must run stably and energy-efficiently. | Systemd auto-restart; e-paper sleeps between updates. |
| NF2  | MQTT communication must be encrypted (TLS).    | TLS on port 8883; CA cert verified.             |
| NF3  | PWA must be offline-capable.                   | Service Worker and Cache API (Phase 2).         |
| NF4  | QR code must update every 5 minutes.           | Background timer thread in Python script.       |
| NF5  | USB printer access without sudo.               | `pi` user added to `lp` and `dialout` groups.  |

------

## 5. Technical Details

### 5.1 Hardware

| Component       | Model / Spec                          | Interface |
| --------------- | ------------------------------------- | --------- |
| Raspberry Pi    | 2B (current) → Zero 2 W (future)     | —         |
| Label Printer   | Brother QL-800 (current) → QL-820NWB (future) | USB → Wi-Fi |
| E-Paper Display | DEBO EPA 1.54 / Waveshare 1.54" 200×200px | SPI   |

**E-Paper SPI Wiring (BCM GPIO):**

| E-Paper Pin | Pi Physical | BCM  | Function   |
|-------------|-------------|------|------------|
| VCC         | Pin 17      | 3.3V | Power      |
| GND         | Pin 20      | GND  | Ground     |
| DIN (MOSI)  | Pin 19      | 10   | SPI0 MOSI  |
| CLK         | Pin 23      | 11   | SPI0 CLK   |
| CS          | Pin 24      | 8    | SPI0 CE0   |
| DC          | Pin 22      | 25   | Data/Cmd   |
| RST         | Pin 11      | 17   | Reset      |
| BUSY        | Pin 18      | 24   | Busy flag  |

### 5.2 Software Libraries

| Component    | Library/Tool                                  | Version  | Purpose                        |
| ------------ | --------------------------------------------- | -------- | ------------------------------ |
| Raspberry Pi | `paho-mqtt`                                   | 2.1.0    | MQTT client                    |
| Raspberry Pi | `qrcode[pil]`                                 | 7.4.2    | QR code generation             |
| Raspberry Pi | `Pillow`                                      | 9.5.0    | Image rendering (9.x required — brother_ql incompatible with 10+) |
| Raspberry Pi | `brother_ql`                                  | 0.9.4    | Label printer driver           |
| Raspberry Pi | `RPi.GPIO`, `spidev`                          | 0.7.1 / 3.6 | E-paper SPI control         |
| Raspberry Pi | Waveshare epd1in54 driver                     | vendored | E-paper display                |
| PWA          | `MQTT.js`                                     | 5.3.4    | MQTT over WebSocket (Phase 2)  |

### 5.3 Repository Structure

```
EasyLabelPrinting/
├── pi/
│   ├── config.py            # All constants
│   ├── key_manager.py       # Session key generation and validation
│   ├── qr_generator.py      # QR code image generation
│   ├── epaper_display.py    # E-paper SPI driver wrapper
│   ├── mqtt_client.py       # MQTT subscriber
│   ├── printer.py           # Label rendering and printing
│   ├── main.py              # Entry point
│   ├── test_mqtt_send.py    # CLI test tool for MQTT publishing
│   ├── requirements.txt
│   ├── lib/waveshare_epd/   # Vendored Waveshare driver
│   └── systemd/
│       └── easylabel.service
└── pwa/                     # Phase 2
```

------

## 6. Risks and Decisions

| Topic                              | Decision / Status                                                   |
| ---------------------------------- | ------------------------------------------------------------------- |
| MQTT broker                        | HiveMQ public broker — no setup, sufficient security via rotating key. |
| Pillow version                     | Pinned to 9.5.0 — `brother_ql 0.9.4` uses removed `Image.ANTIALIAS` API from Pillow 10+. |
| E-paper display (Phase 1)          | Import is optional in `main.py` — app runs without display attached. |
| Brother printer USB PID            | QL-800 PID `0x209b` confirmed. Fallback: `file:///dev/usb/lp0`.    |
| Printer upgrade path               | Switch `PRINTER_MODEL`, `PRINTER_IDENTIFIER`, `PRINTER_BACKEND` in `config.py` when upgrading to QL-820NWB. |

------

## 7. Open Points

1. Connect and test the **E-Paper display** on the Raspberry Pi.
2. Build the **PWA** (Phase 2) — hosted on GitHub Pages.
3. Configure **Home Assistant** to publish MQTT messages to the public broker.
4. Migrate from Raspberry Pi 2B to **Zero 2 W** when available.
5. Upgrade printer to **QL-820NWB** (Wi-Fi) when available.

------

**Next Steps:**

- Wire and test the e-paper display (SPI).
- Build the PWA frontend.
- Set up Home Assistant MQTT automation to publish to `broker.hivemq.com`.
