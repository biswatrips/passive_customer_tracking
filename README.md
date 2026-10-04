# Raspberry Pi Retail Bay Analytics Node

An asynchronous, privacy-compliant retail analytics system running on a Raspberry Pi. It monitors customer engagement at specific product display bays using sensor fusion combining an **HLK-LD2410C mmWave radar** and **passive BLE sniffing**.

---

## Features

* **Asynchronous Binary Radar Parsing:** Direct serial parsing of HLK-LD2410C frames via hardware serial (`/dev/serial0`) to extract moving and stationary energy thresholds.
* **Gated BLE Sniffing:** Passively scans nearby Bluetooth advertisements using `bleak`, gating data collection strictly behind mmWave human presence detection to eliminate false positives from empty rooms.
* **Behavioral Intent Classification:** Analyzes rolling data windows to categorize customer behavior into distinct retail metrics:
  * *Focused Single Browsing*
  * *Crowded Engagement (High Traffic)*
  * *Low-Intent Traffic (Passerby)*
* **SQLite Persistence:** Logs raw telemetry every 2 seconds and aggregates rolling batches into probabilistic analytical summaries with dwell time calculations.

---

## Hardware Requirements

* **Raspberry Pi** (Zero 2 W, Model 3, 4, or 5) running Raspberry Pi OS.
* **HLK-LD2410C** 24GHz mmWave Radar Sensor.
* Jumper wires for connections.

---

## Step-by-Step Installation & Setup

### Step 1: Physical Wiring
Connect the HLK-LD2410C radar module to your Raspberry Pi's GPIO header using the hardware serial pins:

| HLK-LD2410C Pin | Raspberry Pi GPIO Pin | Description |
| :--- | :--- | :--- |
| **VCC** | Pin 2 or 4 (5V) | Power Supply |
| **GND** | Pin 6, 9, 14, or 20 (GND) | Ground |
| **TX** | Pin 10 (GPIO 15 / RXD) | Radar Transmit $\to$ Pi Receive |
| **RX** | Pin 8 (GPIO 14 / TXD) | Radar Receive $\leftarrow$ Pi Transmit |

> *Note: Ensure your Pi and radar share a common ground.*

---

### Step 2: Configure Raspberry Pi Serial Port
Free up the hardware serial port from login shell/Bluetooth use:

1. Open the configuration tool in your terminal:
   ```bash
   sudo raspi-config
