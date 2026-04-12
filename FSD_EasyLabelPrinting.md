# Functional Specification Document (FSD)

**Project:** Dynamic Label Printing System with Raspberry Pi, E-Paper Display, and MQTT
**Version:** 1.7
**Date:** 12.04.2026
**Author:** Bernd Heisterkamp

------

## 1. Introduction

### 1.1 Purpose

This document describes the functionality of a pull-to-print label system that:

- Uses **static QR codes** (printed once, placed at workstations) to open a PWA where users prepare label content.
- The PWA **immediately publishes** label data to an MQTT topic — no key required.
- The **Raspberry Pi** stores the latest received label data in memory (single slot, overwritten by each new publish).
- Uses a **dynamic QR code** (on an E-Paper display next to the printer) as a print-release trigger — scanned with the phone camera, no camera API needed in the PWA.
- Prints labels on a **Brother QL-820NWB** printer using 50mm endless media.

### 1.2 Scope

- **Hardware:** Raspberry Pi 2B, Brother QL-820NWB via USB, 1.54" E-Paper display (SPI), Edimax USB WiFi adapter.
- **Software:** Python script (Raspberry Pi), PWA (frontend), MQTT broker (public cloud).
- **Protocols:** MQTT over TLS, Wi-Fi.

------

## 2. System Overview

### 2.1 Pull-to-Print Concept

The system separates label **preparation** from label **release** using two independent MQTT topics:

| Step | Action | Who | MQTT Topic |
|------|--------|-----|------------|
| 1 | User scans **static QR** at workstation | User | — |
| 2 | PWA opens (no key), user enters label data, taps "Prepare" | PWA | — |
| 3 | PWA publishes label data | PWA → Pi | `easylabel/data` |
| 4 | Pi stores label data in memory, shows **release QR** on e-paper | Pi | — |
| 5 | User walks to printer, scans **dynamic QR** on e-ink display with phone camera | User | — |
| 6 | PWA reopens with `?key=<key>` in URL, **immediately** publishes release signal — no user interaction needed | PWA → Pi | `easylabel/release` |
| 7 | Pi validates key, prints stored label data, rotates key, shows **home screen** on e-paper | Pi | — |

### 2.2 Components

| Component             | Description                                                                 |
| --------------------- | --------------------------------------------------------------------------- |
| **Static QR Codes**   | Printed once, placed at workstations. Encode a fixed PWA URL (no key). One QR per label type or location. |
| **Raspberry Pi 2B**   | Controls printer, display, and MQTT. Stores latest pending label in memory. |
| **Brother QL-820NWB** | Prints labels via USB. Media: 50mm endless. |
| **E-Paper Display**   | 1.54" DEBO EPA 1.54 (Waveshare, 200×200px, SPI). Two states: home screen (default) and release QR (when label pending). |
| **Edimax USB WiFi**   | USB WiFi adapter. Connects automatically to home or Fablab network via NetworkManager. Credentials stored only on the Pi. |
| **PWA**               | Two modes: prepare (no key — publish data) and release (key in URL — publish release). Hosted on GitHub Pages. |
| **MQTT Broker**       | HiveMQ public cloud broker (`broker.hivemq.com`). TLS port 8883 (Pi) / WSS port 8884 (browser). |

### 2.3 MQTT Topics

| Topic               | Direction  | Retained | Purpose                                      |
| ------------------- | ---------- | -------- | -------------------------------------------- |
| `easylabel/data`    | PWA → Pi   | No  | Label content submission. No key required. Pi stores latest, overwrites previous. |
| `easylabel/release` | PWA → Pi   | No  | Print-release trigger. Contains session key for validation. |
| `easylabel/status`  | Pi → PWA   | Yes | Printer online/offline status. Published on change; retained so new PWA sessions receive it immediately. |

### 2.4 Data Flow Detail

```plaintext
Prepare phase (at workstation):
1. User scans static QR → PWA opens without key (?type=freetext).
2. User enters label data, taps "Prepare".
3. PWA publishes to easylabel/data:
   {"label_type": "freetext", "data": {"text": "Material XY\nReserved: Max"}}
4. Pi receives, stores in memory. Any previous pending job is overwritten.
5. Pi switches e-paper from home screen to full-size release QR.
6. PWA shows confirmation: "Label prepared — go to printer to release."

Release phase (at printer):
7. User scans dynamic QR on e-ink display with phone camera.
   → QR encodes: https://jonahpi.github.io/EasyLabelPrinting/?key=<key>
8. PWA opens in release mode (key detected in URL), immediately publishes to easylabel/release:
   {"key": "<key>"}
9. Pi validates key (constant-time compare).
10. Pi prints stored label data on 50mm endless media.
11. Pi rotates session key, clears pending job, shows home screen on e-paper.

Printer status:
- Pi checks printer availability every 60 seconds.
- Publishes {"printer": "online"/"offline"} to easylabel/status (retained) only when status changes.
- PWA subscribes on connect and receives the retained message immediately.
- PWA shows "Printer ON" / "Printer OFF" badge in the header.
```

### 2.5 E-Paper Display States

| State | Shown when | Content |
|-------|-----------|---------|
| **Home screen** | No label pending (startup, after print, after key rotation) | "Easy Label Printer" title + small QR code linking to PWA home |
| **Release QR** | Label data received and pending | Full-size QR code encoding `PWA_URL?key=<key>` |

The periodic 5-minute refresh shows the appropriate state based on whether a job is pending.

### 2.6 Static QR Codes

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
| FR1  | Connect to Brother printer via USB.                            | `brother_ql`, backend `pyusb`, identifier `usb://0x04f9:0x209d` (QL-820NWB). | Done   |
| FR2  | Show home screen on e-paper at startup and after each print.  | "Easy Label Printer" title + small QR to PWA base URL. `qrcode` + `Pillow`, Waveshare driver. | Done   |
| FR3  | Subscribe to `easylabel/data` and store latest label in memory. Switch e-paper to release QR. | Overwrites any previously stored job. One slot only. | Done   |
| FR4  | Subscribe to `easylabel/release` and validate session key.     | Constant-time compare (`secrets.compare_digest`). Reject if no pending job stored. | Done   |
| FR5  | On valid release: print stored label, rotate key, clear stored job, show home screen. | `brother_ql` convert + send. | Done   |
| FR6  | Render all label types as images for 50mm endless media.       | Fixed width 720px, DejaVuSans-Bold, auto-shrink font 60→20. All 5 types implemented. | Done   |
| FR7  | Periodic QR/display refresh every 5 minutes.                   | Background thread. Shows home screen or release QR based on pending state. | Done   |
| FR8  | Run as systemd service with auto-restart.                      | `systemd/easylabel.service`.                                            | Done   |
| FR9  | Detect printer availability and publish status.                | Check every 60s via pyusb/file path. Publish `easylabel/status` retained on change. | Done   |

### 3.2 Progressive Web App (PWA)

#### Prepare Mode (no `?key=` in URL)

| ID   | Requirement                                                  | Details                                                    | Status |
| ---- | ------------------------------------------------------------ | ---------------------------------------------------------- | ------ |
| FR10 | Detect absence of `?key=` and enter prepare mode.           | Show home page with label type selection.                  | Done   |
| FR11 | Pre-select label type from `?type=` URL parameter.          | Default to home if absent.                                 | Done   |
| FR12 | Provide label form and "Prepare" button per label type.      | All 5 label types implemented.                             | Done   |
| FR13 | On "Prepare": publish to `easylabel/data` via MQTT.         | Payload per label type. Show confirmation.                 | Done   |

#### Release Mode (`?key=` present in URL)

| ID   | Requirement                                                  | Details                                                    | Status |
| ---- | ------------------------------------------------------------ | ---------------------------------------------------------- | ------ |
| FR14 | Detect `?key=` and enter release mode.                      | Immediately publish to `easylabel/release` on page load — no user interaction required. | Done   |
| FR15 | Publish to `easylabel/release` via MQTT.                    | Payload: `{"key": "<key>"}`. QoS 1.                        | Done   |
| FR16 | Show confirmation after publish.                            | "Druckauftrag gesendet" on success.                        | Done   |

#### Printer Status

| ID   | Requirement                                                  | Details                                                    | Status |
| ---- | ------------------------------------------------------------ | ---------------------------------------------------------- | ------ |
| FR17 | Subscribe to `easylabel/status` on MQTT connect.            | Receive retained message immediately on connect.           | Done   |
| FR18 | Display printer status in PWA header.                        | "Printer ON" / "Printer OFF" text badge. Warning banner when offline. | Done   |

#### General

| ID   | Requirement                                                  | Details                                                    | Status |
| ---- | ------------------------------------------------------------ | ---------------------------------------------------------- | ------ |
| FR19 | Offline capability via Service Worker.                      | Cache-first for all static assets. Cache version `easylabel-v4`. | Done   |
| FR20 | Hosted on GitHub Pages.                                     | Auto-deploy via GitHub Actions on push to `main`.          | Done   |

------

## 4. Non-Functional Requirements

| ID   | Requirement                                    | Details                                                         |
| ---- | ---------------------------------------------- | --------------------------------------------------------------- |
| NF1  | System must run stably and energy-efficiently. | Systemd auto-restart; e-paper sleeps between updates.           |
| NF2  | MQTT communication must be encrypted (TLS).    | TLS port 8883 (Pi); WSS port 8884 (browser). CA cert verified. |
| NF3  | PWA must be offline-capable.                   | Service Worker and Cache API.                                   |
| NF4  | Display must refresh every 5 minutes.          | Background timer thread in Python script.                       |
| NF5  | USB printer access without sudo.               | `pi` user added to `lp` and `dialout` groups.                  |
| NF6  | Only one pending label job at a time on the Pi.| New `easylabel/data` message always overwrites the stored job.  |
| NF7  | WiFi credentials must not be in the repository.| Stored only in `/etc/wpa_supplicant/wpa_supplicant-wlan0.conf` on the Pi. |

------

## 5. Technical Details

### 5.1 Hardware

| Component       | Model / Spec                          | Interface |
| --------------- | ------------------------------------- | --------- |
| Raspberry Pi    | 2B                                    | —         |
| Label Printer   | Brother QL-820NWB                     | USB (`usb://0x04f9:0x209d`) |
| E-Paper Display | DEBO EPA 1.54 / Waveshare 1.54" 200×200px | SPI   |
| WiFi Adapter    | Edimax USB                            | USB       |

**Label media:** 50mm endless (`LABEL_MEDIA = "50"`)

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
| Raspberry Pi | `Pillow`                | ≥10.0.0     | Image rendering (`Image.ANTIALIAS` monkey-patched for `brother_ql` compatibility) |
| Raspberry Pi | `brother_ql`            | 0.9.4       | Label printer driver           |
| Raspberry Pi | `RPi.GPIO`, `spidev`    | 0.7.1 / 3.6 | E-paper SPI control            |
| Raspberry Pi | Waveshare epd1in54      | vendored    | E-paper display driver (V1, requires `lut_full_update`) |
| PWA          | `MQTT.js`               | 5.3.4       | MQTT over WebSocket            |

### 5.3 Repository Structure

```
EasyLabelPrinting/
├── pi/
│   ├── config.py            # All constants
│   ├── key_manager.py       # Session key generation and validation
│   ├── qr_generator.py      # QR code + home screen image generation
│   ├── epaper_display.py    # E-paper SPI driver wrapper
│   ├── mqtt_client.py       # MQTT client (data + release + status topics)
│   ├── printer.py           # Label rendering and printing (all 5 types)
│   ├── main.py              # Entry point, pending job store, display state machine
│   ├── requirements.txt
│   ├── lib/waveshare_epd/   # Vendored Waveshare driver
│   └── systemd/
│       └── easylabel.service
└── docs/                    # PWA (GitHub Pages)
    ├── index.html
    ├── app.js
    ├── sw.js
    └── manifest.json
```

### 5.4 Key Configuration (`pi/config.py`)

```python
MQTT_BROKER                  = "broker.hivemq.com"
MQTT_PORT_TLS                = 8883
PWA_BASE_URL                 = "https://jonahpi.github.io/EasyLabelPrinting/"
QR_REFRESH_INTERVAL_SECONDS  = 300   # 5 minutes
PRINTER_CHECK_INTERVAL_SECONDS = 60  # 1 minute
PRINTER_IDENTIFIER           = "usb://0x04f9:0x209d"  # QL-820NWB
PRINTER_MODEL                = "QL-820NWB"
PRINTER_BACKEND              = "pyusb"
LABEL_MEDIA                  = "50"  # 50mm endless
```

------

## 6. Risks and Decisions

| Topic                              | Decision / Status                                                   |
| ---------------------------------- | ------------------------------------------------------------------- |
| Pull-to-print concept              | Data submission and print release are fully decoupled via two MQTT topics. No key needed to submit data. |
| Single pending job slot            | Pi holds only the most recent label. New submission overwrites previous — concurrent use by multiple users is a known limitation. |
| No camera API in PWA               | Dynamic QR is scanned with the phone's native camera app, which opens the PWA URL directly. No in-app scanning needed. |
| No localStorage needed             | Label data is published immediately to MQTT on "Prepare" — no client-side persistence required. |
| MQTT broker                        | HiveMQ public broker. Security relies on rotating session key (48-bit entropy, valid for max 5 min or one print). |
| Pillow version                     | `>=10.0.0`. `Image.ANTIALIAS` monkey-patched in `printer.py` for `brother_ql 0.9.4` compatibility. Pillow 9.5.0 does not build on Python 3.13. |
| E-paper display                    | Import optional in `main.py` — app runs without display attached. V1 driver requires `lut_full_update` argument in `init()`. |
| WiFi credentials                   | Stored only in `/etc/wpa_supplicant/wpa_supplicant-wlan0.conf` on the Pi, managed by NetworkManager. Not in repository. |
| Printer status emoji on iOS        | Replaced with text badge ("Printer ON" / "Printer OFF") — emoji renders as hamburger icon on iPhone. |
| systemd / venv                     | No virtual environment — packages installed system-wide with `--break-system-packages`. `ExecStart` uses `/usr/bin/python3`. |

------

## 7. Label Types

### 7.1 Overview

| ID | `label_type` | Title on label | Multi-print | Status |
|----|-------------|----------------|-------------|--------|
| 1 | `freetext` | — (first line is bold title) | Yes — `copies` field | Done |
| 2 | `qrcode` | — | No | Done |
| 3 | `material_storage` | "Privates Material" | Yes — prints `pieces` labels | Done |
| 4 | `filament` | Value of `filament_type` | No | Done |
| 5 | `3d_print` | "3D Print" | No | Done |

### 7.2 Label Type Details

#### Type 1 — Free Text (`freetext`)
User enters arbitrary text. First line is printed bold and larger as a title; remaining lines are body text. Optional `copies` field for multi-print.

**MQTT payload:**
```json
{ "label_type": "freetext", "data": { "text": "Title\nBody line 2", "copies": 2 } }
```
`copies` is optional, defaults to 1.

**Printed layout:**
```
Title                   ← bold, larger font
Body line 2
```

---

#### Type 2 — QR Code (`qrcode`)
User provides a URL or string. Pi generates a QR code image and prints it.

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
Used to label privately stored material at the makerspace. Pi auto-calculates the pickup deadline as **today + 21 days** and prints `pieces` identical labels.

**MQTT payload:**
```json
{
  "label_type": "material_storage",
  "data": {
    "member": "Max Mustermann",
    "pieces": 3
  }
}
```

**Printed layout (each label):**
```
Privates Material
Max Mustermann
Wird abgeholt bis zum 03.05.2026
Material wird nach Ablauf der Frist vom Fablab entsorgt
```

---

#### Type 4 — Filament (`filament`)
Used to label an opened filament spool. Title is the filament type value.

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
PLA 1.75mm Black        ← bold title
Geöffnet am: 11.04.2026
```

---

#### Type 5 — 3D Print Pickup (`3d_print`)
Used to label a completed 3D print waiting for pickup.

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
3D Print
Max Mustermann
Abholung am: 15.04.2026
```

---

### 7.3 Validation Rules (Pi-side)

| `label_type` | Required fields | Constraints |
|---|---|---|
| `freetext` | `text` | Non-empty, ≤ 500 chars |
| `qrcode` | `content` | Non-empty, ≤ 500 chars |
| `material_storage` | `member`, `pieces` | `pieces` integer ≥ 1; pickup date auto-calculated |
| `filament` | `opened`, `filament_type` | `opened` valid date string |
| `3d_print` | `member`, `pickup_date` | `pickup_date` valid date string |

------

## 8. Raspberry Pi Installation

### 8.1 OS
Raspberry Pi OS Lite (64-bit), configured via Raspberry Pi Imager with SSH enabled. SPI enabled via `sudo raspi-config nonint do_spi 0`.

### 8.2 System Dependencies

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt install -y python3-pip git fonts-dejavu libopenjp2-7 libusb-1.0-0 libfreetype6
```

### 8.3 Python Packages

```bash
pip3 install -r ~/EasyLabelPrinting/pi/requirements.txt --break-system-packages
```

No virtual environment — install directly to system Python.

### 8.4 USB Printer Access

```bash
sudo usermod -aG lp pi && sudo usermod -aG dialout pi
```

Reboot after running this.

### 8.5 Waveshare E-Paper Driver

Copy vendored driver files:

```bash
cd ~/EasyLabelPrinting/pi/lib/waveshare_epd
wget https://raw.githubusercontent.com/waveshare/e-Paper/master/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epd1in54.py
wget https://raw.githubusercontent.com/waveshare/e-Paper/master/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epdconfig.py
```

Uses the V1 driver (`epd1in54.py`) which requires `lut_full_update` argument in `init()`.

### 8.6 WiFi (Edimax USB Adapter)

Set regulatory domain:
```bash
sudo raspi-config nonint do_wifi_country CH
```

Configure networks (credentials stored only on Pi, not in repo):
```bash
sudo nano /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
```

```
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=CH

network={
    ssid="HomeNetworkSSID"
    psk="HomePassword"
    priority=1
}

network={
    ssid="FabLab"
    psk="FablabPassword"
    priority=2
}
```

Enable the interface-specific wpa_supplicant service (NetworkManager manages DHCP):
```bash
sudo systemctl enable wpa_supplicant@wlan0
sudo systemctl start wpa_supplicant@wlan0
```

Note: do not use the generic `wpa_supplicant.service` — it conflicts with NetworkManager.

### 8.7 systemd Service

```bash
sudo cp ~/EasyLabelPrinting/pi/systemd/easylabel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now easylabel
```

------

## 9. Open Points

1. Generate and print **static QR codes** for workstations (one per label type).
2. Consider adding a **second pending job slot** or queue if concurrent use becomes an issue.
3. Evaluate migration to **Raspberry Pi Zero 2 W** for lower power consumption.

------

**Next Steps:**

- Generate and laminate static QR codes for workstations.
- Monitor real-world usage for edge cases (e.g., concurrent label submissions).
