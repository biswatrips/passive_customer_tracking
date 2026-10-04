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
2. Use the arrow keys to navigate to Interface Options (or Interfacing Options depending on your OS version) and press Enter.
3. Select I6 Serial Port (or Serial).
4. Answer the prompt: "Would you like a login shell to be accessible over serial?" $\rightarrow$ Select No.
5. Answer the prompt: "Would you like the serial port hardware to be enabled?" $\rightarrow$ Select Yes.
6. Exit raspi-config and reboot your Raspberry Pi to apply changes:
   ```bash
   sudo reboot

---

### Step 3: Install System Dependencies
Install system libraries required for Bluetooth and serial communication:

  ```bash
  sudo apt-get update
  sudo apt-get install -y python3-pip python3-venv libglib2.0-dev bluetooth bluez

---

### Step 4: Python Dependencies & Execution

1. Install requirements from requirements.txt:
   ```bash
   pip install -r requirements.txt
2. Execute the tracker script:
   ```bash
   python3 zone_node_tracker.py

---

Database Schema Reference
The application automatically manages retail_analytics.db with SQLite WAL mode:

telemetry_logs (Raw 2-second interval logs): Tracks timestamp, presence, mmWave distance, BLE density, and RSSI.

bay_probabilities (2-minute rolling analytics batches): Tracks engagement categories (Focused Single Browsing, Crowded Engagement, Low-Intent Traffic), probability scores, and estimated dwell times.
