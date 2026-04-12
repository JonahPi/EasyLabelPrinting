# Functional Specification Document (FSD)

**Project:** Dynamic Label Printing System with Raspberry Pi, E-Paper Display, and MQTT
**Version:** 1.6
**Date:** 11.04.2026
**Author:** Bernd Heisterkamp

------

## 1. Introduction

### 1.1 Purpose

This document describes the functionality of a pull-to-print label system that:

- Uses **static QR codes** (printed once, placed at workstations) to open a PWA where users prepare label content.
- The PWA **immediately publishes** label data to an MQTT topic — no key required.
- The **Raspberry Pi** stores the latest received label data in memory (single slot, overwritten by each new publish).
- Uses a **dynamic QR code** (on an E-Paper display next to the printer) as a print-release trigger — scanned with the phone camera, no camera API needed in the PWA.
- Prints labels on a **Brother QL-800** printer using 62mm endless media.

### 1.2 Scope

- **Hardware:** Raspberry Pi 2B (→ Zero 2 W later), Brother QL-800 via USB (→ QL-820NWB later), 1.54" E-Paper display (SPI).
- **Software:** Python script (Raspberry Pi), PWA (frontend), MQTT broker (public cloud).
- **Protocols:** MQTT over TLS, Wi-Fi.

------

## 2. System Overview

### 2.1 Pull-to-Print Concept

The system separates label **preparation** from label **release** using two independent MQTT topics:

| Step | Action | Who | MQTT Topic |
|------|--------|-----|------------|
| 1 | User scans **static QR** at workstation | User | — |
| 2 | PWA opens (no key), user enters label text, taps "Prepare" | PWA | — |
| 3 | PWA publishes label data | PWA → Pi | `easylabel/data` |
| 4 | Pi stores label data in memory (overwrites any previous job) | Pi | — |
| 5 | User walks to printer, scans **dynamic QR** on e-ink display with phone camera | User | — |
| 6 | PWA reopens with `?key=<key>` in URL, **immediately** publishes release signal — no user interaction needed | PWA → Pi | `easylabel/release` |
| 8 | Pi validates key, prints stored label data, rotates key, updates display | Pi | — |

### 2.2 Components

| Component             | Description                                                                 |
| --------------------- | --------------------------------------------------------------------------- |
| **Static QR Codes**   | Printed once, placed at workstations. Encode a fixed PWA URL (no key). One QR per label type or location. |
| **Raspberry Pi 2B**   | Controls printer, display, and MQTT. Stores latest pending label in memory. Will migrate to Zero 2 W. |
| **Brother QL-800**    | Prints labels via USB. Media: 62mm endless. Will upgrade to QL-820NWB (Wi-Fi). |
| **E-Paper Display**   | 1.54" DEBO EPA 1.54 (Waveshare, 200×200px, SPI). Shows dynamic QR code with current session key. |
| **PWA**               | Two modes: prepare (no key — publish data) and release (key in URL — publish release). No camera API needed. |
| **MQTT Broker**       | HiveMQ public cloud broker (`broker.hivemq.com`). TLS port 8883 (Pi) / WSS port 8884 (browser). |

### 2.3 MQTT Topics

| Topic               | Direction  | Purpose                                      |
| ------------------- | ---------- | -------------------------------------------- |
| `easylabel/data`    | PWA → Pi   | Label content submission. No key required. Pi stores latest, overwrites previous. |
| `easylabel/release` | PWA → Pi   | Print-release trigger. Contains session key for validation. |

### 2.4 Data Flow Detail

```plaintext
Prepare phase (at workstation):
1. User scans static QR → PWA opens without key (?type=freetext).
2. User enters free text, taps "Prepare".
3. PWA publishes to easylabel/data:
   {"label_type": "freetext", "data": {"text": "Material XY\nReserved: Max"}}
4. Pi receives, stores in memory. Any previous pending job is overwritten.
5. PWA shows confirmation: "Label prepared — go to printer to release."

Release phase (at printer):
6. User scans dynamic QR on e-ink display with phone camera.
   → QR encodes: https://jonahpi.github.io/EasyLabelPrinting/?key=<key>
7. PWA opens in release mode (key detected in URL), immediately publishes to easylabel/release — no user interaction required:
   {"key": "<key>"}
9. Pi validates key (constant-time compare).
10. Pi prints stored label data on 62mm endless media.
11. Pi rotates session key, updates e-ink display.
12. Pi clears stored pending job from memory.
```

### 2.5 Static QR Codes

Static QR codes encode a fixed PWA URL without a key:

```
https://jonahpi.github.io/EasyLabelPrinting/?type=freetext
```

The `?type=` parameter pre-selects the label type in the PWA. Generated once, printed and laminated at workstations. No expiry.

------

## 3. Functional Requirements

### 3.1 Raspberry Pi Python Script

| ID   | Requirement                                                    | Details                                                                 | Status |
| ---- | -------------------------------------------------------------- | ----------------------------------------------------------------------- | ------ |
| FR1  | Connect to Brother printer via USB.                            | `brother_ql`, backend `pyusb`, identifier `usb://0x04f9:0x209b`. Fallback: `file:///dev/usb/lp0`. | Done   |
| FR2  | Generate dynamic QR code (PWA URL + session key) and display on E-Paper. | URL: `https://jonahpi.github.io/EasyLabelPrinting/?key=<key>`. `qrcode` + `Pillow 10.x+`, Waveshare driver. | Done   |
| FR3  | Subscribe to `easylabel/data` and store latest label in memory. | Overwrites any previously stored job. One slot only.                   | To do  |
| FR4  | Subscribe to `easylabel/release` and validate session key.     | Constant-time compare (`secrets.compare_digest`). Reject if no pending job stored. | To do  |
| FR5  | On valid release: print stored label, rotate key, clear stored job. | `brother_ql` convert + send. Update e-ink display after print.        | To do  |
| FR6  | Render free text as image for 62mm endless media.              | Fixed width 720px, DejaVuSans-Bold, auto-shrink font 60→20.            | Done   |
| FR7  | Periodic QR refresh every 5 minutes (security hygiene).        | Background thread, key unchanged on timer refresh.                      | Done   |
| FR8  | Run as systemd service with auto-restart.                      | `systemd/easylabel.service`.                                            | Done   |

### 3.2 Progressive Web App (PWA) — Phase 2

#### Prepare Mode (no `?key=` in URL)

| ID   | Requirement                                                  | Details                                                    | Status   |
| ---- | ------------------------------------------------------------ | ---------------------------------------------------------- | -------- |
| FR9  | Detect absence of `?key=` and enter prepare mode.           | Show label form.                                           | Deferred |
| FR10 | Pre-select label type from `?type=` URL parameter.          | Default to `freetext` if absent.                           | Deferred |
| FR11 | Provide textarea and "Prepare" button.                       | Validate non-empty, ≤ 500 chars.                           | Deferred |
| FR12 | On "Prepare": publish to `easylabel/data` via MQTT.         | Payload: `{"label_type": "freetext", "data": {"text": "..."}}`. Show confirmation. | Deferred |

#### Release Mode (`?key=` present in URL)

| ID   | Requirement                                                  | Details                                                    | Status   |
| ---- | ------------------------------------------------------------ | ---------------------------------------------------------- | -------- |
| FR13 | Detect `?key=` and enter release mode.                      | Immediately publish to `easylabel/release` on page load — no user interaction required. | Deferred |
| FR14 | Publish to `easylabel/release` via MQTT.                    | Payload: `{"key": "<key>"}`. QoS 1.                        | Deferred |
| FR15 | Show confirmation or error feedback after publish.          | "Sent to printer" on success, error message on failure.    | Deferred |
| FR16 | Offline capability via Service Worker.                      | Cache-first for all static assets.                         | Deferred |
| FR17 | Hosted on GitHub Pages.                                     | Auto-deploy via GitHub Actions on push to `main`.          | Deferred |

------

## 4. Non-Functional Requirements

| ID   | Requirement                                    | Details                                                         |
| ---- | ---------------------------------------------- | --------------------------------------------------------------- |
| NF1  | System must run stably and energy-efficiently. | Systemd auto-restart; e-paper sleeps between updates.           |
| NF2  | MQTT communication must be encrypted (TLS).    | TLS port 8883 (Pi); WSS port 8884 (browser). CA cert verified. |
| NF3  | PWA must be offline-capable.                   | Service Worker and Cache API. Prepare mode works offline (publishes when reconnected). |
| NF4  | QR code must update every 5 minutes.           | Background timer thread in Python script.                       |
| NF5  | USB printer access without sudo.               | `pi` user added to `lp` and `dialout` groups.                  |
| NF6  | Only one pending label job at a time on the Pi.| New `easylabel/data` message always overwrites the stored job.  |

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
│   ├── mqtt_client.py       # MQTT subscriber (easylabel/data + easylabel/release)
│   ├── printer.py           # Label rendering and printing
│   ├── main.py              # Entry point, pending job store
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
| Pull-to-print concept              | Data submission and print release are fully decoupled via two MQTT topics. No key needed to submit data. |
| Single pending job slot            | Pi holds only the most recent label. New submission overwrites previous — keeps the system simple; concurrent use by multiple users is a known limitation. |
| No camera API in PWA               | Dynamic QR is scanned with the phone's native camera app, which opens the PWA URL directly. No in-app scanning needed. |
| No localStorage needed             | Label data is published immediately to MQTT on "Prepare" — no client-side persistence required. |
| MQTT broker                        | HiveMQ public broker. Security relies on rotating session key (48-bit entropy, valid max 5 min or one print). |
| Pillow version                     | Unpinned (10.x+). `Image.ANTIALIAS` monkey-patched in `printer.py` for `brother_ql 0.9.4` compatibility. Pillow 9.5.0 does not build on Python 3.13. |
| E-paper display (Phase 1)          | Import optional in `main.py` — app runs without display attached.   |
| Brother printer USB PID            | QL-800 PID `0x209b` confirmed. Fallback: `file:///dev/usb/lp0`.    |
| Printer upgrade path               | Switch `PRINTER_MODEL`, `PRINTER_IDENTIFIER`, `PRINTER_BACKEND` in `config.py` when upgrading to QL-820NWB. |

------

## 7. Label Types

### 7.1 Overview

| ID | `label_type` | Title on label | Multi-print | Status |
|----|-------------|----------------|-------------|--------|
| 1 | `freetext` | — | Yes — user selects number of copies | Done |
| 2 | `qrcode` | — | No | Done |
| 3 | `material_storage` | "Private Material" | Yes — prints y labels (piece 1 of y … y of y) | To do |
| 4 | `filament` | "Filament" | No | To do |
| 5 | `3d_print` | "3D Print Pickup" | No | To do |

### 7.2 Label Type Details

#### Type 1 — Free Text (`freetext`)
User enters arbitrary text in the PWA. Printed as-is with auto-shrinking font.

**MQTT payload:**
```json
{ "label_type": "freetext", "data": { "text": "Hello World\nLine 2", "copies": 2 } }
```
`copies` is optional, defaults to 1.

**Printed layout:**
```
[free text, multi-line]
```

---

#### Type 2 — QR Code (`qrcode`)
User provides a URL or string. Pi generates a QR code image and prints it as a square label.

**MQTT payload:**
```json
{ "label_type": "qrcode", "data": { "content": "https://example.com" } }
```

**Printed layout:**
```
[QR code, square, full label width]
```

---

#### Type 3 — Temporary Material Storage (`material_storage`)
Used to label privately stored material at the makerspace. PWA provides member name, pick-up deadline, and total number of pieces. Pi prints **y labels in sequence**, with the piece counter (x of y) incrementing automatically.

**MQTT payload:**
```json
{
  "label_type": "material_storage",
  "data": {
    "member": "Max Mustermann",
    "pickup_before": "2026-04-30",
    "pieces": 3
  }
}
```

**Print behavior:** Pi prints `pieces` labels sequentially, x = 1 … y.

**Printed layout (each label):**
```
Privates Material
Max Mustermann
Entsorgung vor: 30.04.2026
Stück 1 von 3
```

---

#### Type 4 — Filament (`filament`)
Used to label a spool of filament after opening. PWA provides the opening date and filament type.

**MQTT payload:**
```json
{
  "label_type": "filament",
  "data": {
    "opened": "2026-04-11",
    "filament_type": "PLA 1.75mm Black"
  }
}
```

**Printed layout:**
```
PLA 1.75mm Black
Geöffnet am: 11.04.2026
```

---

#### Type 5 — 3D Print Pickup (`3d_print`)
Used to label a completed 3D print waiting for pickup. PWA provides member name and pickup date.

**MQTT payload:**
```json
{
  "label_type": "3d_print",
  "data": {
    "member": "Max Mustermann",
    "pickup_date": "2026-04-15"
  }
}
```

**Printed layout:**
```
3D Print Pickup
Max Mustermann
Abholung am: 15.04.2026
```

---

### 7.3 Validation Rules (Pi-side)

| `label_type` | Required fields | Constraints |
|---|---|---|
| `freetext` | `text` | Non-empty, ≤ 500 chars |
| `qrcode` | `content` | Non-empty, ≤ 500 chars |
| `material_storage` | `member`, `pickup_before`, `pieces` | `pieces` integer ≥ 1 |
| `filament` | `opened`, `filament_type` | `opened` valid date string |
| `3d_print` | `member`, `pickup_date` | `pickup_date` valid date string |

------

## 8. Raspberry Pi Installation

### 7.1 OS
Raspberry Pi OS Lite (64-bit), configured via Raspberry Pi Imager with SSH and Wi-Fi enabled. SPI enabled via `sudo raspi-config nonint do_spi 0`.

### 7.2 System Dependencies

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt install -y python3-pip git fonts-dejavu libopenjp2-7 libusb-1.0-0 libfreetype6
```

| Package          | Purpose                                      |
|------------------|----------------------------------------------|
| `python3-pip`    | Python package installer                     |
| `git`            | Clone repository                             |
| `fonts-dejavu`   | DejaVuSans-Bold font for label text rendering |
| `libopenjp2-7`   | Required by Pillow for image processing      |
| `libusb-1.0-0`   | Required by pyusb for USB printer access     |
| `libfreetype6`   | Required by Pillow for font rendering        |

### 7.3 Python Packages

```bash
pip3 install -r ~/EasyLabelPrinting/pi/requirements.txt --break-system-packages
```

Note: do not use a virtual environment — install directly to system Python.

### 7.4 USB Printer Access

```bash
sudo usermod -aG lp pi && sudo usermod -aG dialout pi
```

Log out and back in (or reboot) after running this.

### 7.5 Waveshare E-Paper Driver

Copy vendored driver files from the Waveshare GitHub repository:

```bash
cd ~/EasyLabelPrinting/pi/lib/waveshare_epd
wget https://raw.githubusercontent.com/waveshare/e-Paper/master/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epd1in54.py
wget https://raw.githubusercontent.com/waveshare/e-Paper/master/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epdconfig.py
```

Note: uses the V1 driver (`epd1in54.py`) which requires `lut_full_update` argument in `init()`.

------

## 9. Open Points

1. Refactor Pi Python script to use two topics (`easylabel/data`, `easylabel/release`) and in-memory job store.
2. Build the **PWA** (Phase 2) — prepare mode + release mode, hosted on GitHub Pages.
3. Generate and print **static QR codes** for workstations.
4. Migrate from Raspberry Pi 2B to **Zero 2 W** when available.
5. Upgrade printer to **QL-820NWB** (Wi-Fi) when available.

------

**Next Steps:**

- Refactor `mqtt_client.py` and `main.py` for the two-topic architecture.
- Build the PWA frontend (Phase 2).
- Generate and print static QR codes for workstations.
