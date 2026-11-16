# ESP32 Robotic Arm Project (4-DOF Multi-Link Control)

An advanced 4-DOF robotic arm controller supporting **USB Serial**, **Wi-Fi Hotspot (TCP Socket & Mobile Web GUI)**, and **Bluetooth Classic SPP**.

---

## 🚀 Key Features

1. **Multi-Channel Control**:
   - **USB Serial (COM Port)**: Direct control when plugged into a PC/laptop via USB cable (115200 baud).
   - **Wi-Fi SoftAP**: Broadcasts its own hotspot (`RoboticArm-ESP32`) for standalone external-power operation.
   - **Smartphone Mobile Web GUI**: Built-in responsive web application served on port 80 (`http://192.168.4.1`) for iPhones, Android phones, tablets, or laptops—**zero app installation required!**
   - **Desktop Python GUI**: Dual-mode (USB Serial & Wi-Fi TCP socket on port 5000) with auto-port detection and interactive 2D kinematics display.
   - **Bluetooth Classic SPP**: Wireless serial connection named `ESP32_RoboticArm`.

2. **Intuitive Joint Mimic Controls & Directional Arrows**:
   - **Joint 4: Base Rotation (MG90S 360° Continuous)**: Hold-to-jog (`◀ ROTATE LEFT` / `ROTATE RIGHT ▶`), timed nudges (`80ms`, `200ms`), speed selection (Slow/Normal/Fast), and instant `⏹ STOP BASE`.
   - **Joint 1: Shoulder (SG90 180°)**: `▼ LOWER` & `RAISE ▲`, with fine adjustment buttons.
   - **Joint 2: Elbow (SG90 180°)**: `↶ RETRACT` & `EXTEND ↷`, with fine adjustment buttons.
   - **Joint 3: Claw / Gripper (SG90 180°)**: `◄ OPEN 🔓` & `GRIP 🔒 ►`, with `🔓 FULL OPEN` (30°) and `🔒 FULL GRIP` (150°) quick buttons.

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
| **Base Rotation** | MG90S | Continuous (360°) | `GPIO 21` | Directional Jog (Stop: 1500µs; CW: 1700µs; CCW: 1300µs) |

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

## 🌐 Web Host Control Files (`WebHostControl/`)

The web interface is modularized in the dedicated `WebHostControl/` directory:
- **`index.html`**: Clean semantic HTML structure, responsive SVG kinematic mimic visualizer, joint cards, presets, and action buttons.
- **`style.css`**: Cyber-dark theme with glowing accents, tactile touch buttons, animated connection indicators, and mobile-responsive viewport styling.
- **`script.js`**: Frontend JavaScript controller managing debounced REST calls (`/api/set`, `/api/stop`, `/api/reset`), live SVG arm pose calculations, and bi-directional status synchronization.

### Dual Serving Mechanism (LittleFS + PROGMEM Fallback)
The firmware supports both:
1. **LittleFS filesystem streaming**: Serves live files from flash memory if uploaded. `platformio.ini` is configured with `data_dir = WebHostControl`.
2. **PROGMEM embedded fallback (`include/web_assets.h`)**: If LittleFS is unformatted or not uploaded yet, the ESP32 automatically serves the embedded assets. Flashing firmware alone works 100% out of the box!

To rebuild `include/web_assets.h` after modifying files in `WebHostControl/`:
```powershell
python tools/build_web_assets.py
```

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
   python GUI_ROBOTIC_ARM\main.py
   ```
4. **Choose your connection mode**:
   - **USB Serial**: Select your COM port (e.g. `COM6`), baud `115200`, and click **CONNECT**.
   - **Wi-Fi AP**: Connect your laptop's Wi-Fi to `RoboticArm-ESP32`, then enter IP `192.168.4.1` : `5000` and click **CONNECT**.

---

## 🔧 Building & Flashing Firmware

To compile and upload using PlatformIO:
```powershell
# Upload firmware:
pio run --target upload

# Upload LittleFS filesystem image (optional, embedded fallback is built-in):
pio run --target uploadfs
```
Partition table is configured as `huge_app.csv` (3 MB app space) to comfortably hold Wi-Fi SoftAP, Web Server, TCP Server, and Bluetooth simultaneously.

### Base Servo (Joint 4 / GPIO 21) Modes & Troubleshooting

The base servo supports two operational modes:

1. **Standard 180° Positional Mode (Default - Recommended)**:
   - Works with all standard SG90 and MG90S 180° servos.
   - When the computer or web interface sends an angle (e.g. `S4,45` or `S4,120`), the servo immediately turns to that exact angle and holds position.
   - Initialized at 90° center on boot.

2. **Continuous 360° Rotation Mode**:
   - For modified/continuous rotation servos.
   - Toggle in `src/main.cpp` via `#define BASE_DEFAULT_CONTINUOUS 1`, or switch on-the-fly by sending `MODE4,CONT` (or `MODE4,POS` to return to positional).
   - If a continuous servo creeps while stationary, tune `baseStopUs` in `src/main.cpp`.

#### Hardware Diagnostic Test (`TEST4`)
To verify that GPIO 21 and the base servo are physically working:
1. Open Serial Monitor (115200 baud) or Python GUI log.
2. Send command: `TEST4`
3. The ESP32 will sweep the base servo (`90° -> 60° -> 120° -> 90°`) and report progress.

#### Alternative Pins
If GPIO 21 has an electrical conflict with an onboard I2C device (e.g. OLED display) or is damaged, change `#define SERVO4_PIN 21` in `src/main.cpp` to another PWM-capable pin: `22`, `23`, `25`, `26`, `27`, `32`, or `33`.
