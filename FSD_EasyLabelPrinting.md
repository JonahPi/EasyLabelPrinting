# Functional Specification Document (FSD)

**Project:** Dynamic Label Printing System with Raspberry Pi, E-Paper Display, and MQTT
**Version:** 1.2
**Date:** 11.04.2026
**Author:** Bernd Heisterkamp

------

## 1. Introduction

### 1.1 Purpose

This document describes the functionality of a pull-to-print label system that:

- Uses **static QR codes** (printed once, placed at workstations) to open a PWA where users prepare label content.
- Uses a **dynamic QR code** (on an E-Paper display next to the printer) as a print-release trigger.
- Exchanges data via **MQTT** (public cloud broker) between the PWA and a Raspberry Pi.
- Prints labels on a **Brother QL-800** printer using 62mm endless media.

### 1.2 Scope

- **Hardware:** Raspberry Pi 2B (→ Zero 2 W later), Brother QL-800 via USB (→ QL-820NWB later), 1.54" E-Paper display (SPI).
- **Software:** Python script (Raspberry Pi), PWA (frontend), MQTT broker (public cloud).
- **Protocols:** MQTT over TLS, Wi-Fi.

------

## 2. System Overview

### 2.1 Pull-to-Print Concept

The system separates label **preparation** from label **release**:

| Step | Action | Location |
|------|--------|----------|
| 1 | User scans a **static QR code** at their workstation | At the workstation |
| 2 | PWA opens (no key required) — user selects label type and enters content | Phone/browser |
| 3 | User taps **"Prepare"** — label data saved locally in browser (localStorage) | Phone/browser |
| 4 | User walks to printer and scans the **dynamic QR code** on the e-paper display | At the printer |
| 5 | PWA reopens with key in URL — detects pending job — publishes to MQTT | Phone/browser |
| 6 | Raspberry Pi validates key, prints label, rotates key, updates display | Printer |

This allows label content to be prepared **anywhere** (workstation, warehouse floor, etc.) and released for printing only when the user is physically at the printer.

### 2.2 Components

| Component                     | Description                                                                 |
| ----------------------------- | --------------------------------------------------------------------------- |
| **Static QR Codes**           | Printed once and placed at workstations. Encode a fixed PWA URL (no key). One QR per label type or location. |
| **Raspberry Pi 2B**           | Controls the printer, display, and MQTT communication. Runs the Python script. Will migrate to Zero 2 W. |
| **Brother QL-800**            | Prints labels via USB. Label media: 62mm endless. Will upgrade to QL-820NWB (Wi-Fi). |
| **E-Paper Display**           | 1.54" DEBO EPA 1.54 (Waveshare-compatible, 200×200px, SPI). Shows dynamic QR code with current session key. |
| **Progressive Web App (PWA)** | Single web app with two modes: prepare mode (no key) and release mode (with key). |
| **MQTT Broker**               | HiveMQ public cloud broker (`broker.hivemq.com`). TLS port 8883 (Pi) / WSS port 8884 (browser). |

### 2.3 Data Flow

```plaintext
Prepare phase (at workstation):
1. User scans static QR → PWA opens without key.
2. User selects label type, enters free text, taps "Prepare".
3. PWA saves pending job to localStorage. Prompts user to go to printer.

Release phase (at printer):
4. User scans dynamic QR on e-paper display → PWA reopens with ?key=<key>.
5. PWA detects key in URL + retrieves pending job from localStorage.
6. PWA publishes MQTT message to topic labels/<key>.
7. Raspberry Pi validates key, renders text as image, sends to printer.
8. Printer prints label on 62mm endless media.
9. Pi rotates session key, updates e-paper display. localStorage job cleared.
```

### 2.4 Static QR Codes

Static QR codes are generated once (e.g. printed and laminated) and placed at relevant locations. They encode a fixed PWA URL without a key:

```
https://jonahpi.github.io/EasyLabelPrinting/?type=freetext
```

The `type` query parameter pre-selects the label type in the PWA. Additional label types can be added in the future (e.g. `?type=address`, `?type=shelf`). In Phase 2 only `freetext` is supported.

------

## 3. Functional Requirements

### 3.1 Raspberry Pi Python Script

| ID   | Requirement                                                    | Details                                                                 | Status |
| ---- | -------------------------------------------------------------- | ----------------------------------------------------------------------- | ------ |
| FR1  | Connect to Brother printer via USB.                            | `brother_ql` library, backend `pyusb`, identifier `usb://0x04f9:0x209b`. Fallback: `file:///dev/usb/lp0`. | Done   |
| FR2  | Generate dynamic QR code (URL + session key) and display on E-Paper. | URL: `https://jonahpi.github.io/EasyLabelPrinting/?key=<key>`. `qrcode` + `Pillow 9.5.0`, Waveshare vendored driver. 200×200px. | Implemented (e-paper hardware deferred) |
| FR3  | Implement MQTT client (subscribe to topic `labels/<key>`).     | `paho-mqtt 2.1.0`, MQTTv5, TLS port 8883, QoS 1.                       | Done   |
| FR4  | Validate received data (key check + payload structure).        | Constant-time compare (`secrets.compare_digest`). Validates `label_type`, text ≤ 500 chars. | Done   |
| FR5  | Render free text as image and print on 62mm endless media.     | Fixed width 720px, DejaVuSans-Bold, auto-shrink font 60→20. `brother_ql` convert + send. | Done   |
| FR6  | Rotate session key and refresh QR after each successful print. | New key: `secrets.token_hex(6)` (48-bit entropy).                      | Done   |
| FR7  | Periodic QR refresh every 5 minutes (security hygiene).        | Background thread, key unchanged on timer refresh.                      | Done   |
| FR8  | Run as systemd service with auto-restart.                      | `systemd/easylabel.service`.                                            | Done   |

### 3.2 Progressive Web App (PWA) — Phase 2

The PWA operates in two distinct modes depending on whether a `?key=` parameter is present in the URL.

#### Prepare Mode (no key in URL)

| ID   | Requirement                                                  | Details                                                    | Status   |
| ---- | ------------------------------------------------------------ | ---------------------------------------------------------- | -------- |
| FR9  | Detect absence of `?key=` in URL and enter prepare mode.    | Show label form, hide release UI.                          | Deferred |
| FR10 | Display label type based on `?type=` URL parameter.         | Default to `freetext` if absent.                           | Deferred |
| FR11 | Provide textarea for free-text entry and "Prepare" button.  | Validate non-empty, ≤ 500 chars.                           | Deferred |
| FR12 | Save pending job to localStorage on "Prepare".              | Store `{label_type, text, timestamp}`. Show prompt to go to printer. | Deferred |

#### Release Mode (key in URL)

| ID   | Requirement                                                  | Details                                                    | Status   |
| ---- | ------------------------------------------------------------ | ---------------------------------------------------------- | -------- |
| FR13 | Detect `?key=` in URL and enter release mode.               | Retrieve pending job from localStorage.                    | Deferred |
| FR14 | If pending job found: display summary and "Print" button.   | Show label preview (text content).                         | Deferred |
| FR15 | If no pending job found: show message to prepare first.     | Guide user to scan a workstation QR code first.            | Deferred |
| FR16 | On "Print": publish JSON to MQTT topic `labels/<key>`.      | `MQTT.js 5.3.4`, WSS port 8884, QoS 1. Clear localStorage on success. | Deferred |
| FR17 | Offline capability via Service Worker.                      | Cache-first strategy for all static assets.                | Deferred |
| FR18 | Hosted on GitHub Pages.                                     | Auto-deploy via GitHub Actions on push to `main`.          | Deferred |

### 3.3 MQTT Message Contract

Topic: `labels/<key>`

```json
{
  "key": "d28577ed4953",
  "label_type": "freetext",
  "data": {
    "text": "Material XY\nReserved for: Max\n12.04.2026"
  }
}
```

Validation rules (Pi-side): key match, `label_type` = `"freetext"`, text non-empty and ≤ 500 chars.

------

## 4. Non-Functional Requirements

| ID   | Requirement                                    | Details                                                         |
| ---- | ---------------------------------------------- | --------------------------------------------------------------- |
| NF1  | System must run stably and energy-efficiently. | Systemd auto-restart; e-paper sleeps between updates.           |
| NF2  | MQTT communication must be encrypted (TLS).    | TLS on port 8883 (Pi); WSS port 8884 (browser). CA cert verified. |
| NF3  | PWA must be offline-capable.                   | Service Worker and Cache API. localStorage persists pending jobs offline. |
| NF4  | QR code must update every 5 minutes.           | Background timer thread in Python script.                       |
| NF5  | USB printer access without sudo.               | `pi` user added to `lp` and `dialout` groups.                  |
| NF6  | Static QR codes require no network at scan time. | PWA URL is static; label data stays in localStorage until release. |

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

| Component    | Library/Tool            | Version     | Purpose                        |
| ------------ | ----------------------- | ----------- | ------------------------------ |
| Raspberry Pi | `paho-mqtt`             | 2.1.0       | MQTT client                    |
| Raspberry Pi | `qrcode[pil]`           | 7.4.2       | QR code generation             |
| Raspberry Pi | `Pillow`                | 9.5.0       | Image rendering (9.x required — brother_ql incompatible with 10+) |
| Raspberry Pi | `brother_ql`            | 0.9.4       | Label printer driver           |
| Raspberry Pi | `RPi.GPIO`, `spidev`    | 0.7.1 / 3.6 | E-paper SPI control            |
| Raspberry Pi | Waveshare epd1in54      | vendored    | E-paper display driver         |
| PWA          | `MQTT.js`               | 5.3.4       | MQTT over WebSocket (Phase 2)  |

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
| Pull-to-print concept              | Label preparation and print release are separated. No key needed to prepare a label. Key only required at print release. |
| Static QR codes                    | Generated once, printed and laminated at workstations. Encode PWA URL with `?type=` parameter. No expiry. |
| Pending job persistence            | Stored in browser localStorage. Survives page close and offline use. Only one pending job at a time per browser. |
| MQTT broker                        | HiveMQ public broker — no setup, sufficient security via rotating key and physical presence requirement. |
| Pillow version                     | Pinned to 9.5.0 — `brother_ql 0.9.4` uses removed `Image.ANTIALIAS` API from Pillow 10+. |
| E-paper display (Phase 1)          | Import is optional in `main.py` — app runs without display attached. |
| Brother printer USB PID            | QL-800 PID `0x209b` confirmed. Fallback: `file:///dev/usb/lp0`.    |
| Printer upgrade path               | Switch `PRINTER_MODEL`, `PRINTER_IDENTIFIER`, `PRINTER_BACKEND` in `config.py` when upgrading to QL-820NWB. |

------

## 7. Open Points

1. Connect and test the **E-Paper display** on the Raspberry Pi.
2. Build the **PWA** (Phase 2) — prepare mode + release mode, hosted on GitHub Pages.
3. Generate and print **static QR codes** for workstations.
4. Configure **Home Assistant** to publish MQTT messages to the public broker (optional, for automation).
5. Migrate from Raspberry Pi 2B to **Zero 2 W** when available.
6. Upgrade printer to **QL-820NWB** (Wi-Fi) when available.

------

**Next Steps:**

- Wire and test the e-paper display (SPI).
- Build the PWA frontend (prepare mode + release mode).
- Print first static QR code for a workstation.
