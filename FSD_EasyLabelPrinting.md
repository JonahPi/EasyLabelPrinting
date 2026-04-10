# Functional Specification Document (FSD)

**Project:** Dynamic Label Printing System with Raspberry Pi, E-Paper Display, and MQTT
**Version:** 1.0
**Date:** 10.04.2026
**Author:** Bernd Heisterkamp

------

## 1. Introduction

### 1.1 Purpose

This document describes the functionality of a system that:

- Connects a **Brother label printer** (via Wi-Fi or USB) to a **Raspberry Pi Zero 2 W**.
- Uses an **E-Paper display** to show a dynamic QR code.
- Provides a **Progressive Web App (PWA)** for selecting label types and entering data.
- Exchanges data via **MQTT** (hosted on GitHub) between the PWA and Raspberry Pi.
- Validates the data and sends it to the label printer.

### 1.2 Scope

- **Hardware:** Raspberry Pi Zero 2 W, Brother label printer, E-Paper display.
- **Software:** Python script (Raspberry Pi), PWA (frontend), MQTT broker (GitHub).
- **Protocols:** MQTT, HTTP/HTTPS, Wi-Fi/USB.

------

## 2. System Overview

### 2.1 Components

| Component                     | Description                                                  |
| ----------------------------- | ------------------------------------------------------------ |
| **Raspberry Pi Zero 2 W**     | Controls the printer, display, and MQTT communication. Runs the Python script. |
| **Brother Label Printer**     | Prints labels based on received data (via Wi-Fi/USB).        |
| **E-Paper Display**           | Displays a dynamic QR code (URL + random key).               |
| **Progressive Web App (PWA)** | Web interface for selecting label types and entering data.   |
| **MQTT Broker (GitHub)**      | Hosts MQTT topics for communication between PWA and Raspberry Pi. |

### 2.2 Data Flow

```plaintext
1. Raspberry Pi generates QR code (URL + random key) → E-Paper display.
2. User scans QR code → PWA opens.
3. User selects label type and enters data → PWA sends data + key to MQTT topic.
4. Raspberry Pi subscribes to MQTT topic, validates key, and sends data to printer.
5. Printer prints the label.
```

------

## 3. Functional Requirements

### 3.1 Raspberry Pi Zero 2 W

| ID   | Requirement                                                  | Details                                                      |
| ---- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| FR1  | Connect to Brother printer (Wi-Fi/USB).                      | Use `brother_ql` library or Brother APIs.                    |
| FR2  | Generate dynamic QR code (URL + random key) and display on E-Paper. | Use libraries like `qrcode` and `Pillow` for display control. |
| FR3  | Implement MQTT client (subscribe to topic).                  | Use `paho-mqtt` library.                                     |
| FR4  | Validate received data (key check).                          | Key must match the generated key.                            |
| FR5  | Format data for printer and send.                            | Use `brother_ql` library or direct printer commands.         |

### 3.2 Progressive Web App (PWA)

| ID   | Requirement                         | Details                             |
| ---- | ----------------------------------- | ----------------------------------- |
| FR6  | Scan QR code and extract URL + key. | Use `jsQR` or similar libraries.    |
| FR7  | Display label types for selection.  | Dropdown menu or tile view.         |
| FR8  | Provide form for data entry.        | Dynamic fields based on label type. |
| FR9  | Send data + key to MQTT topic.      | Use `MQTT.js` library.              |

### 3.3 MQTT Broker (GitHub)

| ID   | Requirement                            | Details                                                      |
| ---- | -------------------------------------- | ------------------------------------------------------------ |
| FR10 | Host MQTT topic for data transmission. | Topic: `labels/{key}` (e.g., `labels/abc123`).               |
| FR11 | Ensure authentication/authorization.   | Use GitHub Secrets or environment variables for credentials. |

------

## 4. Non-Functional Requirements

| ID   | Requirement                                    | Details                                 |
| ---- | ---------------------------------------------- | --------------------------------------- |
| NF1  | System must run stably and energy-efficiently. | Operate Raspberry Pi in low-power mode. |
| NF2  | MQTT communication must be encrypted (TLS).    | Use MQTT over WebSockets with TLS.      |
| NF3  | PWA must be offline-capable.                   | Use Service Worker and Cache API.       |
| NF4  | QR code must update every 5 minutes.           | Use cron job or timer in Python script. |

------

## 5. Technical Details

### 5.1 Hardware Interfaces

- **Brother Printer:** Wi-Fi (recommended) or USB (fallback).
- **E-Paper Display:** SPI or I2C (depends on display model).

### 5.2 Software Libraries

| Component    | Library/Tool                        | Purpose                |
| ------------ | ----------------------------------- | ---------------------- |
| Raspberry Pi | `brother_ql`, `paho-mqtt`, `qrcode` | Printer, MQTT, QR code |
| PWA          | `MQTT.js`, `jsQR`                   | MQTT, QR code scanning |
| MQTT Broker  | GitHub Actions + Mosquitto (Docker) | MQTT hosting           |

### 5.3 Data Format (MQTT Message)

```json
{
  "key": "abc123",
  "label_type": "address",
  "data": {
    "name": "Max Mustermann",
    "street": "Musterstraße 1",
    "city": "Berlin"
  }
}
```

------

## 6. Risks and Assumptions

| Risk/Assumption                         | Solution/Measure                                     |
| --------------------------------------- | ---------------------------------------------------- |
| MQTT broker on GitHub is slow.          | Use a local MQTT broker (e.g., Mosquitto) as backup. |
| E-Paper display responds slowly.        | Update asynchronously in the background.             |
| Brother printer does not support Wi-Fi. | Implement USB connection as fallback.                |

------

## 7. Open Points

1. Which **E-Paper display model** will be used? (SPI/I2C?)
2. Should the **MQTT broker** be hosted locally or on GitHub?
3. Are there specific **label types** that should be prioritized?

------

**Next Steps:**

- Order hardware components (Raspberry Pi, display, printer).
- Set up MQTT broker (GitHub/local).
- Test Python script for QR code generation and MQTT.