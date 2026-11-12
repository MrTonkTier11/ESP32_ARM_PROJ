#include <Arduino.h>
#include <ESP32Servo.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <WiFi.h>
#include <WebServer.h>

// =====================================
// BLUETOOTH CONFIGURATION
// =====================================
// Set to 1 to enable Bluetooth Serial SPP (e.g., "ESP32_RoboticArm")
// Set to 0 if you only want Wi-Fi and USB Serial
#define ENABLE_BLUETOOTH 1

#if ENABLE_BLUETOOTH
#include <BluetoothSerial.h>
BluetoothSerial SerialBT;
#endif

// =====================================
// ESP32 WIFI ACCESS POINT & SERVERS
// =====================================

const char* AP_SSID = "RoboticArm-ESP32";
const char* AP_PASSWORD = "ArmControlESP32";

// TCP Server on port 5000 (for laptop Python GUI)
WiFiServer tcpServer(5000);
WiFiClient tcpClient;

// HTTP Web Server on port 80 (for smartphone & laptop browsers)
WebServer webServer(80);

// =====================================
// SERVO PINS
// =====================================

#define SERVO1_PIN 4   // Shoulder (SG90)
#define SERVO2_PIN 18  // Elbow (SG90)
#define SERVO3_PIN 19  // Claw / Gripper (SG90)
#define SERVO4_PIN 21  // Base Rotation (MG90S Continuous)

// =====================================
// SERVO OBJECTS
// =====================================

Servo servo1;
Servo servo2;
Servo servo3;
Servo servo4;

// =====================================
// SG90 SETTINGS
// =====================================

const int SERVO_MIN_US = 600;
const int SERVO_MAX_US = 2300;

int pos1 = 90; // Shoulder
int pos2 = 90; // Elbow
int pos3 = 90; // Claw

// =====================================
// MG90S CONTINUOUS ROTATION SETTINGS
// =====================================

// Continuous-rotation servos use pulse width as speed/direction, not angle.
// Tune BASE_STOP_US for the exact servo so the horn is stationary at idle.
const int BASE_STOP_US = 1500;
const int BASE_CW_US = 1700;
const int BASE_CCW_US = 1300;
const float BASE_MS_PER_DEG = 12.0f;
const float BASE_ESTIMATE_PERIOD_DEG = 360.0f;

float basePosition = 90.0f;
float baseTarget = 90.0f;
int baseDirection = 0;
unsigned long lastBaseUpdate = 0;
bool baseManualJog = false;

// =====================================
// BUFFER DEFINITIONS
// =====================================

#define BUFFER_SIZE 64
char serialBuffer[BUFFER_SIZE];
int serialBufIndex = 0;

char tcpBuffer[BUFFER_SIZE];
int tcpBufIndex = 0;

#if ENABLE_BLUETOOTH
char btBuffer[BUFFER_SIZE];
int btBufIndex = 0;
#endif

// =====================================
// FORWARD DECLARATIONS
// =====================================

void stopBase();
void updateBase();
void setBaseTarget(int newTarget);
void processCommand(const char *command, Stream *replyStream);
void handleRoot();
void handleApiSet();
void handleApiStatus();
void handleApiStop();
void handleApiReset();
void handleNotFound();

// =====================================
// HTML/JS/CSS FOR SMARTPHONE WEB GUI
// =====================================

const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <title>ESP32 Robotic Arm Control</title>
  <style>
    :root {
      --bg: #0b0f19;
      --card-bg: #151c2e;
      --card-border: #23304c;
      --accent: #00d9ff;
      --accent-glow: rgba(0, 217, 255, 0.35);
      --green: #00e676;
      --red: #ff3d71;
      --text: #ffffff;
      --subtext: #8e9bb3;
      --btn-bg: #1e2840;
      --btn-active: #00d9ff;
    }
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-tap-highlight-color: transparent;
      user-select: none;
    }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      padding: 12px;
      padding-bottom: 30px;
      max-width: 600px;
      margin: 0 auto;
    }
    header {
      text-align: center;
      padding: 10px 0 16px 0;
    }
    h1 {
      font-size: 1.35rem;
      font-weight: 800;
      letter-spacing: 1px;
      color: var(--accent);
      text-transform: uppercase;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }
    .status-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: 8px 14px;
      font-size: 0.8rem;
      margin-bottom: 12px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-weight: 600;
    }
    .indicator {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--green);
      box-shadow: 0 0 8px var(--green);
    }
    /* Visual Arm Canvas */
    .visualizer-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 12px;
      margin-bottom: 14px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .visualizer-title {
      font-size: 0.75rem;
      font-weight: 700;
      color: var(--subtext);
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 6px;
    }
    svg.arm-svg {
      width: 100%;
      max-width: 320px;
      height: 160px;
    }
    /* Joint Card */
    .joint-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 14px;
      margin-bottom: 12px;
      box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .joint-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }
    .joint-name {
      font-size: 0.95rem;
      font-weight: 700;
      color: var(--accent);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .joint-type {
      font-size: 0.7rem;
      color: var(--subtext);
      font-weight: 400;
    }
    .angle-badge {
      font-size: 1.15rem;
      font-weight: 800;
      color: #fff;
      background: #0d1322;
      padding: 2px 10px;
      border-radius: 8px;
      border: 1px solid var(--card-border);
      min-width: 54px;
      text-align: center;
    }
    /* Control Row: Arrow Left - Slider - Arrow Right */
    .control-row {
      display: flex;
      align-items: center;
      gap: 10px;
      margin: 10px 0;
    }
    .arrow-btn {
      width: 44px;
      height: 44px;
      border-radius: 10px;
      background: var(--btn-bg);
      border: 1px solid var(--card-border);
      color: var(--text);
      font-size: 1.25rem;
      font-weight: bold;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.15s ease;
      flex-shrink: 0;
    }
    .arrow-btn:active {
      background: var(--accent);
      color: #000;
      transform: scale(0.92);
      box-shadow: 0 0 10px var(--accent-glow);
    }
    .arrow-sub {
      font-size: 0.55rem;
      font-weight: 600;
      text-transform: uppercase;
      margin-top: -2px;
    }
    .slider-container {
      flex: 1;
      display: flex;
      flex-direction: column;
      position: relative;
    }
    input[type=range] {
      -webkit-appearance: none;
      width: 100%;
      height: 10px;
      border-radius: 5px;
      background: #0d1322;
      outline: none;
      margin: 12px 0;
    }
    input[type=range]::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 26px;
      height: 26px;
      border-radius: 50%;
      background: var(--accent);
      cursor: pointer;
      box-shadow: 0 0 10px var(--accent);
      border: 2px solid #fff;
    }
    input[type=range]::-moz-range-thumb {
      width: 26px;
      height: 26px;
      border-radius: 50%;
      background: var(--accent);
      cursor: pointer;
      box-shadow: 0 0 10px var(--accent);
      border: 2px solid #fff;
    }
    /* Step & Action Buttons */
    .action-row {
      display: flex;
      gap: 6px;
      justify-content: space-between;
      margin-top: 6px;
    }
    .btn-step {
      flex: 1;
      padding: 6px 0;
      font-size: 0.72rem;
      font-weight: 600;
      background: #101626;
      border: 1px solid var(--card-border);
      color: var(--subtext);
      border-radius: 6px;
      text-align: center;
      cursor: pointer;
    }
    .btn-step:active {
      background: var(--card-border);
      color: #fff;
    }
    .btn-action {
      flex: 1;
      padding: 9px 0;
      font-size: 0.8rem;
      font-weight: 700;
      border-radius: 8px;
      border: none;
      cursor: pointer;
      text-align: center;
      transition: transform 0.1s;
    }
    .btn-action:active {
      transform: scale(0.95);
    }
    .btn-claw-open {
      background: #194060;
      color: #80d8ff;
      border: 1px solid #0091ea;
    }
    .btn-claw-grip {
      background: #4a2800;
      color: #ffd54f;
      border: 1px solid #ff9100;
    }
    .btn-stop-base {
      background: #4a1220;
      color: #ff8a80;
      border: 1px solid var(--red);
    }
    /* Global Control Grid */
    .global-controls {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 10px;
    }
    .btn-global {
      padding: 12px;
      font-size: 0.85rem;
      font-weight: 800;
      border-radius: 12px;
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .btn-reset {
      background: #1e2840;
      color: var(--accent);
      border: 1px solid var(--card-border);
    }
    .btn-stop-all {
      background: var(--red);
      color: #fff;
    }
    .preset-panel {
      display: flex;
      gap: 6px;
      margin-top: 10px;
    }
    .btn-preset {
      flex: 1;
      padding: 8px 4px;
      background: #131a2b;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      color: var(--subtext);
      font-size: 0.72rem;
      font-weight: 600;
      cursor: pointer;
      text-align: center;
    }
    .btn-preset:active {
      background: var(--accent);
      color: #000;
    }
  </style>
</head>
<body>

  <header>
    <h1>🤖 Robotic Arm</h1>
  </header>

  <div class="status-bar">
    <div class="badge">
      <div class="indicator" id="status-dot"></div>
      <span id="status-text">Connected (Wi-Fi AP)</span>
    </div>
    <span style="color:var(--subtext); font-size:0.75rem;" id="ip-text">192.168.4.1</span>
  </div>

  <!-- SVG Visual Mimic Display -->
  <div class="visualizer-card">
    <div class="visualizer-title">Live Joint Mimic Pose</div>
    <svg class="arm-svg" viewBox="0 0 320 160">
      <defs>
        <linearGradient id="armGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#00d9ff" />
          <stop offset="100%" stop-color="#0066ff" />
        </linearGradient>
      </defs>
      <!-- Base Platform -->
      <rect x="120" y="145" width="80" height="12" rx="4" fill="#23304c" stroke="#3b4d75" stroke-width="1.5"/>
      <circle cx="160" cy="145" r="14" fill="#151c2e" stroke="#00d9ff" stroke-width="2"/>
      <text x="160" y="149" fill="#00d9ff" font-size="8" font-weight="bold" text-anchor="middle" id="svg-base-text">90°</text>

      <!-- Arm Kinematic Group -->
      <g id="arm-shoulder-group" transform="translate(160, 145) rotate(0)">
        <!-- Shoulder Segment -->
        <line x1="0" y1="0" x2="0" y2="-55" stroke="url(#armGrad)" stroke-width="7" stroke-linecap="round"/>
        <circle cx="0" cy="0" r="6" fill="#fff" stroke="#00d9ff" stroke-width="2"/>

        <!-- Elbow Group -->
        <g id="arm-elbow-group" transform="translate(0, -55) rotate(0)">
          <!-- Forearm Segment -->
          <line x1="0" y1="0" x2="0" y2="-45" stroke="url(#armGrad)" stroke-width="5" stroke-linecap="round"/>
          <circle cx="0" cy="0" r="5" fill="#fff" stroke="#0066ff" stroke-width="2"/>

          <!-- Claw Group -->
          <g id="arm-claw-group" transform="translate(0, -45)">
            <circle cx="0" cy="0" r="4" fill="#ffd54f"/>
            <!-- Left Claw Finger -->
            <line id="svg-claw-l" x1="0" y1="0" x2="-10" y2="-14" stroke="#ffd54f" stroke-width="3" stroke-linecap="round"/>
            <!-- Right Claw Finger -->
            <line id="svg-claw-r" x1="0" y1="0" x2="10" y2="-14" stroke="#ffd54f" stroke-width="3" stroke-linecap="round"/>
          </g>
        </g>
      </g>
    </svg>
  </div>

  <!-- JOINT 4: BASE ROTATION (MG90S) -->
  <div class="joint-card">
    <div class="joint-header">
      <div>
        <div class="joint-name">↺ BASE ROTATION</div>
        <div class="joint-type">MG90S Continuous · Timed Tracking</div>
      </div>
      <div class="angle-badge" id="val4">90°</div>
    </div>
    <div class="control-row">
      <button class="arrow-btn" onclick="stepServo(4, -5)" title="Rotate Counter-Clockwise">
        <span>◀</span>
        <span class="arrow-sub">CCW</span>
      </button>
      <div class="slider-container">
        <input type="range" id="slider4" min="0" max="180" value="90" oninput="onSlider(4, this.value)">
      </div>
      <button class="arrow-btn" onclick="stepServo(4, 5)" title="Rotate Clockwise">
        <span>▶</span>
        <span class="arrow-sub">CW</span>
      </button>
    </div>
    <div class="action-row">
      <button class="btn-step" onclick="stepServo(4, -1)">-1°</button>
      <button class="btn-step" onclick="stepServo(4, 1)">+1°</button>
      <button class="btn-action btn-stop-base" onclick="stopBaseCmd()">⏹ STOP BASE</button>
    </div>
  </div>

  <!-- JOINT 1: SHOULDER (SG90) -->
  <div class="joint-card">
    <div class="joint-header">
      <div>
        <div class="joint-name">▲ SHOULDER JOINT</div>
        <div class="joint-type">Servo 1 (SG90) · Main Arm Pitch</div>
      </div>
      <div class="angle-badge" id="val1">90°</div>
    </div>
    <div class="control-row">
      <button class="arrow-btn" onclick="stepServo(1, -5)" title="Lower Arm">
        <span>▼</span>
        <span class="arrow-sub">DOWN</span>
      </button>
      <div class="slider-container">
        <input type="range" id="slider1" min="0" max="180" value="90" oninput="onSlider(1, this.value)">
      </div>
      <button class="arrow-btn" onclick="stepServo(1, 5)" title="Raise Arm">
        <span>▲</span>
        <span class="arrow-sub">UP</span>
      </button>
    </div>
    <div class="action-row">
      <button class="btn-step" onclick="stepServo(1, -5)">-5°</button>
      <button class="btn-step" onclick="stepServo(1, -1)">-1°</button>
      <button class="btn-step" onclick="stepServo(1, 1)">+1°</button>
      <button class="btn-step" onclick="stepServo(1, 5)">+5°</button>
    </div>
  </div>

  <!-- JOINT 2: ELBOW (SG90) -->
  <div class="joint-card">
    <div class="joint-header">
      <div>
        <div class="joint-name">↶ ELBOW JOINT</div>
        <div class="joint-type">Servo 2 (SG90) · Forearm Pitch</div>
      </div>
      <div class="angle-badge" id="val2">90°</div>
    </div>
    <div class="control-row">
      <button class="arrow-btn" onclick="stepServo(2, -5)" title="Retract Forearm">
        <span>↶</span>
        <span class="arrow-sub">BACK</span>
      </button>
      <div class="slider-container">
        <input type="range" id="slider2" min="0" max="180" value="90" oninput="onSlider(2, this.value)">
      </div>
      <button class="arrow-btn" onclick="stepServo(2, 5)" title="Extend Forearm">
        <span>↷</span>
        <span class="arrow-sub">FWD</span>
      </button>
    </div>
    <div class="action-row">
      <button class="btn-step" onclick="stepServo(2, -5)">-5°</button>
      <button class="btn-step" onclick="stepServo(2, -1)">-1°</button>
      <button class="btn-step" onclick="stepServo(2, 1)">+1°</button>
      <button class="btn-step" onclick="stepServo(2, 5)">+5°</button>
    </div>
  </div>

  <!-- JOINT 3: CLAW / GRIPPER (SG90) -->
  <div class="joint-card">
    <div class="joint-header">
      <div>
        <div class="joint-name">🤏 CLAW / GRIPPER</div>
        <div class="joint-type">Servo 3 (SG90) · Pincer Grip</div>
      </div>
      <div class="angle-badge" id="val3">90°</div>
    </div>
    <div class="control-row">
      <button class="arrow-btn" onclick="stepServo(3, -5)" title="Open Claw">
        <span>◄</span>
        <span class="arrow-sub">OPEN</span>
      </button>
      <div class="slider-container">
        <input type="range" id="slider3" min="0" max="180" value="90" oninput="onSlider(3, this.value)">
      </div>
      <button class="arrow-btn" onclick="stepServo(3, 5)" title="Grip / Close Claw">
        <span>►</span>
        <span class="arrow-sub">GRIP</span>
      </button>
    </div>
    <div class="action-row">
      <button class="btn-action btn-claw-open" onclick="setJoint(3, 30)">🔓 FULL OPEN</button>
      <button class="btn-step" onclick="stepServo(3, -2)">-2°</button>
      <button class="btn-step" onclick="stepServo(3, 2)">+2°</button>
      <button class="btn-action btn-claw-grip" onclick="setJoint(3, 150)">🔒 FULL GRIP</button>
    </div>
  </div>

  <!-- PRESETS -->
  <div class="preset-panel">
    <button class="btn-preset" onclick="applyPreset(90, 90, 90, 90)">🏠 HOME (90°)</button>
    <button class="btn-preset" onclick="applyPreset(130, 45, 30, 90)">📦 PICK POSE</button>
    <button class="btn-preset" onclick="applyPreset(70, 110, 150, 140)">📍 DROP POSE</button>
    <button class="btn-preset" onclick="applyPreset(45, 135, 90, 90)">💤 REST / FOLD</button>
  </div>

  <!-- GLOBAL BUTTONS -->
  <div class="global-controls">
    <button class="btn-global btn-reset" onclick="resetAllCmd()">↺ RESET ALL</button>
    <button class="btn-global btn-stop-all" onclick="stopBaseCmd()">⏹ STOP BASE</button>
  </div>

  <script>
    const state = { 1: 90, 2: 90, 3: 90, 4: 90 };
    let sendTimers = {};

    function updateVisualizer() {
      // Shoulder rotates between -60° and +60° around base
      const sAngle = (state[1] - 90) * 0.8;
      // Elbow rotates relative to shoulder
      const eAngle = (state[2] - 90) * 0.8;
      // Claw spread: 0° is narrow/closed, 180° is wide/open
      const clawSpread = Math.max(2, Math.min(22, (180 - state[3]) * 0.12));

      const shoulderGroup = document.getElementById('arm-shoulder-group');
      const elbowGroup = document.getElementById('arm-elbow-group');
      const baseText = document.getElementById('svg-base-text');
      const clawL = document.getElementById('svg-claw-l');
      const clawR = document.getElementById('svg-claw-r');

      if (shoulderGroup) shoulderGroup.setAttribute('transform', `translate(160, 145) rotate(${sAngle})`);
      if (elbowGroup) elbowGroup.setAttribute('transform', `translate(0, -55) rotate(${eAngle})`);
      if (baseText) baseText.textContent = `${state[4]}°`;
      if (clawL) {
        clawL.setAttribute('x2', -clawSpread);
        clawL.setAttribute('y2', -14);
      }
      if (clawR) {
        clawR.setAttribute('x2', clawSpread);
        clawR.setAttribute('y2', -14);
      }
    }

    function setJoint(servoId, value) {
      value = Math.max(0, Math.min(180, parseInt(value)));
      state[servoId] = value;
      const slider = document.getElementById('slider' + servoId);
      const valBadge = document.getElementById('val' + servoId);
      if (slider) slider.value = value;
      if (valBadge) valBadge.textContent = value + '°';
      updateVisualizer();

      clearTimeout(sendTimers[servoId]);
      sendTimers[servoId] = setTimeout(() => {
        fetch(`/api/set?s=${servoId}&v=${value}`)
          .catch(e => console.warn('Fetch error:', e));
      }, 30);
    }

    function onSlider(servoId, value) {
      setJoint(servoId, value);
    }

    function stepServo(servoId, delta) {
      setJoint(servoId, state[servoId] + delta);
    }

    function stopBaseCmd() {
      fetch('/api/stop').catch(e => console.warn(e));
    }

    function resetAllCmd() {
      applyPreset(90, 90, 90, 90);
      fetch('/api/reset').catch(e => console.warn(e));
    }

    function applyPreset(s1, s2, s3, s4) {
      setJoint(1, s1);
      setJoint(2, s2);
      setJoint(3, s3);
      setJoint(4, s4);
    }

    // Sync initial state from ESP32
    fetch('/api/status')
      .then(res => res.json())
      .then(data => {
        if (data.s1 !== undefined) setJoint(1, data.s1);
        if (data.s2 !== undefined) setJoint(2, data.s2);
        if (data.s3 !== undefined) setJoint(3, data.s3);
        if (data.s4 !== undefined) setJoint(4, data.s4);
      })
      .catch(() => updateVisualizer());
  </script>
</body>
</html>
)rawliteral";

// =====================================
// POSITIONAL SERVO CONTROL
// =====================================

void movePositionalServo(Servo &servo, int &currentPosition, int newPosition) {
    newPosition = constrain(newPosition, 0, 180);
    if (newPosition == currentPosition) {
        return;
    }
    currentPosition = newPosition;
    servo.write(newPosition);
}

// =====================================
// STOP MG90S
// =====================================

void stopBase() {
    servo4.writeMicroseconds(BASE_STOP_US);
    baseDirection = 0;
    baseManualJog = false;
    // Keep the UI's virtual target in its documented 0..180° range.
    baseTarget = constrain(basePosition, 0.0f, 180.0f);
}

// =====================================
// UPDATE ESTIMATED BASE POSITION
// =====================================

void updateBase() {
    unsigned long now = millis();

    if (lastBaseUpdate == 0) {
        lastBaseUpdate = now;
        return;
    }

    unsigned long elapsed = now - lastBaseUpdate;
    lastBaseUpdate = now;

    // Prevent huge jump if loop was delayed
    if (elapsed > 500) {
        elapsed = 50;
    }

    if (baseManualJog) {
        // Continuous manual jog
        float movement = (float)elapsed / BASE_MS_PER_DEG;
        basePosition += baseDirection * movement;
        while (basePosition >= BASE_ESTIMATE_PERIOD_DEG) basePosition -= BASE_ESTIMATE_PERIOD_DEG;
        while (basePosition < 0.0f) basePosition += BASE_ESTIMATE_PERIOD_DEG;
        return;
    }

    // Estimated movement toward target
    if (baseDirection != 0) {
        float movement = (float)elapsed / BASE_MS_PER_DEG;
        basePosition += baseDirection * movement;

        if (baseDirection > 0) {
            basePosition = min(basePosition, baseTarget);
        } else {
            basePosition = max(basePosition, baseTarget);
        }
    }

    float difference = baseTarget - basePosition;

    if (fabs(difference) < 0.5f) {
        basePosition = baseTarget;
        if (baseDirection != 0) {
            stopBase();
        }
        return;
    }

    int requestedDirection = (difference > 0) ? 1 : -1;

    if (requestedDirection != baseDirection) {
        baseDirection = requestedDirection;
        if (baseDirection > 0) {
            servo4.writeMicroseconds(BASE_CW_US);
        } else {
            servo4.writeMicroseconds(BASE_CCW_US);
        }
    }
}

// =====================================
// SET MG90S TARGET
// =====================================

void setBaseTarget(int newTarget) {
    updateBase();
    baseManualJog = false;
    baseTarget = constrain(newTarget, 0, 180);
}

// =====================================
// COMMAND PROCESSING
// =====================================

void processCommand(const char *command, Stream *replyStream) {
    if (command == nullptr || strlen(command) == 0) {
        return;
    }

    // Trim leading whitespace
    while (*command == ' ' || *command == '\t') command++;

    // Emergency or normal base stop
    if (strcmp(command, "STOP4") == 0 || strcmp(command, "STOP") == 0) {
        updateBase();
        stopBase();
        if (replyStream) replyStream->println("BASE STOPPED");
        return;
    }

    // Reset all servos to 90 degrees
    if (strcmp(command, "RESET") == 0) {
        movePositionalServo(servo1, pos1, 90);
        movePositionalServo(servo2, pos2, 90);
        movePositionalServo(servo3, pos3, 90);
        setBaseTarget(90);
        if (replyStream) replyStream->println("RESET OK");
        return;
    }

    // Ping / Pong test
    if (strcmp(command, "PING") == 0) {
        if (replyStream) replyStream->println("PONG");
        return;
    }

    // Status query
    if (strcmp(command, "STATUS") == 0) {
        if (replyStream) {
            replyStream->printf("STATUS,S1:%d,S2:%d,S3:%d,S4:%d\n", pos1, pos2, pos3, (int)round(basePosition));
        }
        return;
    }

    // Continuous manual jog for base: J4,CW or J4,CCW or J4,STOP
    if (strncmp(command, "J4,", 3) == 0) {
        const char *dir = command + 3;
        updateBase();
        if (strcmp(dir, "CW") == 0) {
            baseManualJog = true;
            baseDirection = 1;
            servo4.writeMicroseconds(BASE_CW_US);
            if (replyStream) replyStream->println("JOG CW");
        } else if (strcmp(dir, "CCW") == 0) {
            baseManualJog = true;
            baseDirection = -1;
            servo4.writeMicroseconds(BASE_CCW_US);
            if (replyStream) replyStream->println("JOG CCW");
        } else {
            stopBase();
            if (replyStream) replyStream->println("JOG STOP");
        }
        return;
    }

    // Parse servo position: S1,90 or S2,120 etc.
    const char *separator = strchr(command, ',');
    if (separator == nullptr) {
        return;
    }

    int prefixLen = separator - command;
    char servoID[8];
    if (prefixLen >= sizeof(servoID)) return;
    strncpy(servoID, command, prefixLen);
    servoID[prefixLen] = '\0';

    const char *valueText = separator + 1;
    char *endPointer;
    long parsedValue = strtol(valueText, &endPointer, 10);

    if (valueText == endPointer || (*endPointer != '\0' && *endPointer != '\r' && *endPointer != '\n')) {
        return;
    }

    if (parsedValue < 0 || parsedValue > 180) {
        return;
    }

    int value = (int)parsedValue;

    if (strcmp(servoID, "S1") == 0) {
        movePositionalServo(servo1, pos1, value);
        if (replyStream) replyStream->printf("ACK,S1,%d\n", pos1);
    }
    else if (strcmp(servoID, "S2") == 0) {
        movePositionalServo(servo2, pos2, value);
        if (replyStream) replyStream->printf("ACK,S2,%d\n", pos2);
    }
    else if (strcmp(servoID, "S3") == 0) {
        movePositionalServo(servo3, pos3, value);
        if (replyStream) replyStream->printf("ACK,S3,%d\n", pos3);
    }
    else if (strcmp(servoID, "S4") == 0) {
        setBaseTarget(value);
        if (replyStream) replyStream->printf("ACK,S4,%d\n", value);
    }
}

// =====================================
// WEB SERVER HANDLERS
// =====================================

void handleRoot() {
    webServer.send_P(200, "text/html", INDEX_HTML);
}

void handleApiSet() {
    if (webServer.hasArg("s") && webServer.hasArg("v")) {
        int servoNum = webServer.arg("s").toInt();
        int val = webServer.arg("v").toInt();
        val = constrain(val, 0, 180);

        if (servoNum == 1) movePositionalServo(servo1, pos1, val);
        else if (servoNum == 2) movePositionalServo(servo2, pos2, val);
        else if (servoNum == 3) movePositionalServo(servo3, pos3, val);
        else if (servoNum == 4) setBaseTarget(val);

        char json[100];
        snprintf(json, sizeof(json), "{\"status\":\"ok\",\"s\":%d,\"v\":%d}", servoNum, val);
        webServer.send(200, "application/json", json);
        return;
    }
    webServer.send(400, "application/json", "{\"error\":\"Missing parameters\"}");
}

void handleApiStatus() {
    char json[120];
    snprintf(json, sizeof(json), "{\"s1\":%d,\"s2\":%d,\"s3\":%d,\"s4\":%d,\"basePos\":%d}",
             pos1, pos2, pos3, (int)round(baseTarget), (int)round(basePosition));
    webServer.send(200, "application/json", json);
}

void handleApiStop() {
    updateBase();
    stopBase();
    webServer.send(200, "application/json", "{\"status\":\"stopped\"}");
}

void handleApiReset() {
    movePositionalServo(servo1, pos1, 90);
    movePositionalServo(servo2, pos2, 90);
    movePositionalServo(servo3, pos3, 90);
    setBaseTarget(90);
    webServer.send(200, "application/json", "{\"status\":\"reset\"}");
}

void handleNotFound() {
    webServer.send(404, "text/plain", "Not Found");
}

// =====================================
// READ STREAM HELPER
// =====================================

void checkStreamInput(Stream &stream, char *buffer, int &bufIndex, Stream *replyStream) {
    while (stream.available() > 0) {
        char received = stream.read();

        if (received == '\n') {
            buffer[bufIndex] = '\0';
            if (bufIndex > 0) {
                // Strip possible trailing \r
                if (buffer[bufIndex - 1] == '\r') {
                    buffer[bufIndex - 1] = '\0';
                }
                processCommand(buffer, replyStream);
            }
            bufIndex = 0;
        }
        else if (received != '\r') {
            if (bufIndex < BUFFER_SIZE - 1) {
                buffer[bufIndex++] = received;
            } else {
                bufIndex = 0; // Discard oversized input
            }
        }
    }
}

// =====================================
// SETUP
// =====================================

void setup() {
    Serial.begin(115200);
    delay(200);

    Serial.println();
    Serial.println("==========================================");
    Serial.println("  ESP32 ROBOTIC ARM CONTROLLER INITIALIZING");
    Serial.println("==========================================");

    // Initialize Servo PWM
    servo1.setPeriodHertz(50);
    servo2.setPeriodHertz(50);
    servo3.setPeriodHertz(50);
    servo4.setPeriodHertz(50);

    servo1.attach(SERVO1_PIN, SERVO_MIN_US, SERVO_MAX_US);
    servo2.attach(SERVO2_PIN, SERVO_MIN_US, SERVO_MAX_US);
    servo3.attach(SERVO3_PIN, SERVO_MIN_US, SERVO_MAX_US);
    servo4.attach(SERVO4_PIN, 1000, 2000);

    // Initial positions
    servo1.write(pos1);
    servo2.write(pos2);
    servo3.write(pos3);
    stopBase();

    lastBaseUpdate = millis();

    // =====================================
    // START WIFI ACCESS POINT
    // =====================================
    WiFi.mode(WIFI_AP);
    bool apStarted = WiFi.softAP(AP_SSID, AP_PASSWORD);

    if (apStarted) {
        Serial.println("[WIFI] Access Point Started successfully!");
        Serial.print("  SSID:        "); Serial.println(AP_SSID);
        Serial.print("  Password:    "); Serial.println(AP_PASSWORD);
        Serial.print("  IP Address:  "); Serial.println(WiFi.softAPIP());
    } else {
        Serial.println("[WIFI] Failed to start SoftAP!");
    }

    // Start TCP Socket Server on Port 5000 (for Laptop Python GUI)
    tcpServer.begin();
    tcpServer.setNoDelay(true);
    Serial.println("[TCP] Server listening on port 5000");

    // Start HTTP Web Server on Port 80 (for Smartphones & Web Browsers)
    webServer.on("/", HTTP_GET, handleRoot);
    webServer.on("/api/set", HTTP_GET, handleApiSet);
    webServer.on("/api/status", HTTP_GET, handleApiStatus);
    webServer.on("/api/stop", HTTP_GET, handleApiStop);
    webServer.on("/api/reset", HTTP_GET, handleApiReset);
    webServer.onNotFound(handleNotFound);
    webServer.begin();
    Serial.println("[HTTP] Web GUI ready at http://192.168.4.1");

    // =====================================
    // START BLUETOOTH SERIAL (IF ENABLED)
    // =====================================
#if ENABLE_BLUETOOTH
    if (SerialBT.begin("ESP32_RoboticArm")) {
        Serial.println("[BT] Bluetooth Classic SPP ready as 'ESP32_RoboticArm'");
    } else {
        Serial.println("[BT] Failed to start Bluetooth");
    }
#endif

    Serial.println("==========================================");
    Serial.println("  ESP32 READY: USB, WI-FI & BT ACTIVE");
    Serial.println("==========================================");
}

// =====================================
// MAIN LOOP
// =====================================

void loop() {
    // 1. Update continuous rotation base estimation
    updateBase();

    // 2. Handle HTTP Web Server requests (Smartphone Web GUI)
    webServer.handleClient();

    // 3. Read USB Serial input (PC connected via USB cable)
    checkStreamInput(Serial, serialBuffer, serialBufIndex, &Serial);

    // 4. Read Bluetooth Serial input (if enabled)
#if ENABLE_BLUETOOTH
    checkStreamInput(SerialBT, btBuffer, btBufIndex, &SerialBT);
#endif

    // 5. Manage TCP Wi-Fi Client (Laptop Python GUI)
    if (!tcpClient.connected()) {
        if (tcpClient) {
            stopBase();
            tcpClient.stop();
            Serial.println("[TCP] Client disconnected");
        }

        WiFiClient newClient = tcpServer.accept();
        if (newClient) {
            tcpClient = newClient;
            tcpClient.setNoDelay(true);
            tcpBufIndex = 0;
            Serial.println("[TCP] Client connected from laptop");
        }
    } else {
        checkStreamInput(tcpClient, tcpBuffer, tcpBufIndex, &tcpClient);
    }
}
