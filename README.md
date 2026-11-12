# ESP32 Robotic Arm Project (4-DOF Multi-Link Control)

An advanced 4-DOF robotic arm controller supporting **USB Serial**, **Wi-Fi Hotspot (TCP Socket & Mobile Web GUI)**, and **Bluetooth Classic SPP**.

---

## 🚀 Key Features

1. **Multi-Channel Control**:
   - **USB Serial (COM Port)**: Direct control when plugged into a PC/laptop via USB cable (115200 baud).
   - **Wi-Fi SoftAP**: Broadcasts its own hotspot (`RoboticArm-ESP32`) for standalone external-power operation.
   - **Smartphone Mobile Web GUI**: Built-in responsive web application served on port 80 (`http://192.168.4.1`) for iPhones, Android phones, tablets, or laptops—**zero app installation required!**
   - **Desktop Python GUI**: Dual-mode (USB Serial & Wi-Fi TCP socket on port 5000) with auto-port detection.
   - **Bluetooth Classic SPP**: Wireless serial connection named `ESP32_RoboticArm`.

2. **Intuitive Joint Mimic Controls & Directional Arrows**:
   - **Joint 4: Base Rotation (MG90S Continuous)**: `↺ ◀ CCW` (Counter-Clockwise) & `CW ▶ ↻` (Clockwise), with timed tracking and instant `⏹ STOP BASE`.
   - **Joint 1: Shoulder (SG90 180°)**: `▼ LOWER` & `RAISE ▲`.
   - **Joint 2: Elbow (SG90 180°)**: `↶ RETRACT` & `EXTEND ↷`.
   - **Joint 3: Claw / Gripper (SG90 180°)**: `◄ OPEN 🔓` & `GRIP 🔒 ►`, with `🔓 FULL OPEN` and `🔒 FULL GRIP` quick buttons.
   - Fine-step adjustment buttons: `[-5°]`, `[-1°]`, `[+1°]`, `[+5°]`.

3. **Live 2D Kinematic Mimic Visualizer**:
   - Both the Desktop Python GUI and Smartphone Web GUI feature real-time vector graphics that bend the shoulder, elbow, and open/close the claw pincers in sync with your commands.

4. **1-Click Presets**:
   - `🏠 Home (90°)`: Resets all joints to centered 90°.
   - `📦 Pick Pose`: Low forward reach for object acquisition.
   - `📍 Drop Pose`: Elevated release position.
   - `💤 Rest / Fold`: Compact folded storage posture.

---

## 📌 Hardware Pinout

| Joint / Component | Servo Model | Servo Type | ESP32 GPIO | Operating Range |
| :--- | :--- | :--- | :--- | :--- |
| **Shoulder** | SG90 | Positional (180°) | `GPIO 4` | 0° – 180° (Center: 90°) |
| **Elbow** | SG90 | Positional (180°) | `GPIO 18` | 0° – 180° (Center: 90°) |
| **Claw / Gripper** | SG90 | Positional (180°) | `GPIO 19` | 0° – 180° (Open: ~30°, Grip: ~150°) |
| **Base Rotation** | MG90S | Continuous (360°) | `GPIO 21` | Timed tracking (Stop: 1500µs; CW: 1700µs; CCW: 1300µs) |

---

## 📱 How to Control via Smartphone (Zero App Install)

When the ESP32 is powered via battery, power bank, or 5V DC adapter:
1. On your smartphone (iPhone or Android), open **Wi-Fi Settings**.
2. Connect to the Wi-Fi network:
   - **SSID**: `RoboticArm-ESP32`
   - **Password**: `ArmControlESP32`
3. Open your mobile browser (Safari, Chrome, etc.) and go to:
   - **`http://192.168.4.1`**
4. Control the arm in real-time with touch sliders, directional arrow buttons, preset poses, and live animated arm graphics!

---

## 💻 How to Run the Desktop Python GUI

1. Open PowerShell or Command Prompt in the project folder:
   ```powershell
   cd D:\ARDUINO_PROJS\ESP_ROBOTIK_ARM\ESP32_ARM_PROJ
   ```
2. Activate the virtual environment:
   ```powershell
   .\venv\Scripts\activate
   ```
3. Run the GUI:
   ```powershell
   python GUI_REMOTE_CONTROL\main.py
   ```
4. **Choose your connection mode**:
   - **USB Serial**: Select your COM port (e.g. `COM6`), baud `115200`, and click **CONNECT**.
   - **Wi-Fi AP**: Connect your laptop's Wi-Fi to `RoboticArm-ESP32`, then enter IP `192.168.4.1` : `5000` and click **CONNECT**.

---

## 🔧 Building & Flashing Firmware

To compile and upload using PlatformIO:
```powershell
# From PlatformIO in VS Code or CLI:
pio run --target upload
```
Partition table is configured as `huge_app.csv` (3 MB app space) to comfortably hold Wi-Fi SoftAP, Web Server, TCP Server, and Bluetooth simultaneously.

### Base-servo calibration

The base is a continuous-rotation servo, so its position is estimated from run time rather than measured with feedback. If the servo creeps while stopped, adjust `BASE_STOP_US` in `src/main.cpp` by small increments (typically 5–10 µs). If it does not start reliably, adjust `BASE_CW_US` and `BASE_CCW_US` farther from the stop value. The base wiring in this project is GPIO 21.
