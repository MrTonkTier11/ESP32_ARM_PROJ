// ============================================================================
// ESP32 ROBOTIC ARM CONTROLLER (4-DOF Multi-Link Control)
// Firmware supporting USB Serial and Wi-Fi SoftAP (TCP Socket & Web GUI)
// ============================================================================

#include <Arduino.h>
#include <ESP32Servo.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <WiFi.h>
#include <WebServer.h>
#include <LittleFS.h>
#include "web_assets.h" // Embedded PROGMEM web fallbacks

// ============================================================================
// WI-FI ACCESS POINT & NETWORK SERVERS
// ============================================================================
const char* AP_SSID = "RoboticArm-ESP32";
const char* AP_PASSWORD = "ArmControlESP32";

// TCP Server on port 5000 (for desktop Python GUI)
WiFiServer tcpServer(5000);
WiFiClient tcpClient;

// HTTP Web Server on port 80 (for smartphone & laptop browsers)
WebServer webServer(80);

// Tracks whether LittleFS mounted successfully
bool littleFsMounted = false;

// ============================================================================
// HARDWARE PIN ASSIGNMENTS
// ============================================================================
#define SERVO1_PIN 4   // Shoulder (SG90 - 180° Positional)
#define SERVO2_PIN 18  // Elbow (SG90 - 180° Positional)
#define SERVO3_PIN 19  // Claw / Gripper (SG90 - 180° Positional)
#define SERVO4_PIN 21  // Base Rotation (MG90S 360° Continuous - Jog Control)

// ============================================================================
// SERVO OBJECTS & SETTINGS
// ============================================================================
Servo servo1;
Servo servo2;
Servo servo3;
Servo servo4;

// Standard Pulse limits (microseconds)
const int SERVO_MIN_US = 500;
const int SERVO_MAX_US = 2400;

// Current joint positions in degrees (0-180 for positional servos 1-3)
int pos1 = 90; // Shoulder
int pos2 = 90; // Elbow
int pos3 = 90; // Claw
int pos4 = 90; // Base virtual center

// ============================================================================
// BASE SERVO (MG90S 360° CONTINUOUS ROTATION) SMOOTH CONTROL CONFIGURATION
// ============================================================================
// Neutral stop pulse (microseconds). Tune with CAL4,<us> if motor creeps at idle.
int baseStopUs = 1500;

// Default cruising jog speed pulse offset from baseStopUs (range: 150 to 350)
// 260us provides reliable torque to move the robotic arm without stalling
int baseJogSpeedOffset = 260;

// Target pulse the motor smoothly ramps towards (1500 = stop)
int baseTargetUs = 1500;

// Current pulse actively written to the servo (ramps smoothly for soft-start & soft-stop)
float baseCurrentUs = 1500.0f;

// Acceleration slew rate: ~0.85 us/ms gives a smooth ~250ms ramp up and ramp down (no shaking!)
const float BASE_ACCEL_RATE = 0.85f;
unsigned long lastBaseRampTime = 0;

// Current base motor state: 0 = STOPPED, +1 = ROTATING CW, -1 = ROTATING CCW
int baseState = 0;

// Safety timeout: automatically halts continuous rotation if connection drops
unsigned long baseJogAutoStopTime = 0;
const unsigned long BASE_JOG_SAFETY_TIMEOUT_MS = 3000;

// ============================================================================
// INPUT BUFFERS FOR SERIAL STREAMS
// ============================================================================
#define BUFFER_SIZE 64

char serialBuffer[BUFFER_SIZE];
int serialBufIndex = 0;

char tcpBuffer[BUFFER_SIZE];
int tcpBufIndex = 0;

// ============================================================================
// FORWARD DECLARATIONS
// ============================================================================
void stopBase();
void jogBase(int direction, int speedOffset = 0);
void updateBase();
void testBaseServo(Stream *replyStream);
void movePositionalServo(Servo &servo, int &currentPosition, int newPosition);
void processCommand(const char *command, Stream *replyStream);
void checkStreamInput(Stream &stream, char *buffer, int &bufIndex, Stream *replyStream);
void setupWebServer();
void handleServeFile(const char* path, const char* contentType, const char* progmemFallback);
void handleApiJog();
void handleApiCal4();
void handleApiSet();
void handleApiStatus();
void handleApiStop();
void handleApiReset();
void handleNotFound();

// ============================================================================
// SERVO MOVEMENT LOGIC
// ============================================================================

// Standard positional servo movement (SG90)
void movePositionalServo(Servo &servo, int &currentPosition, int newPosition) {
    newPosition = constrain(newPosition, 0, 180);
    currentPosition = newPosition;
    servo.write(newPosition);
}

// Holds neutral stop pulse to smoothly halt the continuous base motor
void stopBase() {
    baseTargetUs = baseStopUs;
    baseState = 0;
    baseJogAutoStopTime = 0;
    pos4 = 90;
}

// Continuous Jog with smooth ramping: direction = +1 (CW), -1 (CCW), 0 (STOP)
void jogBase(int direction, int speedOffset) {
    if (direction == 0) {
        stopBase();
        return;
    }
    if (speedOffset <= 0) speedOffset = baseJogSpeedOffset;
    speedOffset = constrain(speedOffset, 150, 350);

    baseState = (direction > 0) ? 1 : -1;
    baseJogAutoStopTime = millis() + BASE_JOG_SAFETY_TIMEOUT_MS;

    baseTargetUs = (direction > 0) ? (baseStopUs + speedOffset) : (baseStopUs - speedOffset);
    pos4 = (direction > 0) ? 135 : 45;
}

// Background handler for smooth continuous base acceleration / deceleration and safety timeout
void updateBase() {
    unsigned long now = millis();

    // 1. Smoothly ramp current pulse towards target pulse (eliminates violent startup & stop shake)
    if (abs(baseCurrentUs - (float)baseTargetUs) > 0.5f) {
        float dt = (lastBaseRampTime > 0) ? (float)(now - lastBaseRampTime) : 10.0f;
        if (dt > 50.0f) dt = 50.0f; // Prevent overshooting if loop paused
        
        float maxStep = BASE_ACCEL_RATE * dt;
        if (baseCurrentUs < (float)baseTargetUs) {
            baseCurrentUs += maxStep;
            if (baseCurrentUs > (float)baseTargetUs) baseCurrentUs = (float)baseTargetUs;
        } else {
            baseCurrentUs -= maxStep;
            if (baseCurrentUs < (float)baseTargetUs) baseCurrentUs = (float)baseTargetUs;
        }
        
        servo4.writeMicroseconds((int)round(baseCurrentUs));
    } else {
        if ((int)round(baseCurrentUs) != baseTargetUs) {
            baseCurrentUs = (float)baseTargetUs;
            servo4.writeMicroseconds(baseTargetUs);
        }
    }
    lastBaseRampTime = now;

    if (baseState == 0) return;

    // 2. Safety timeout for continuous jog (halts runaway rotation if client disconnects)
    if (baseJogAutoStopTime > 0 && now >= baseJogAutoStopTime) {
        stopBase();
        Serial.println("[BASE] Safety timeout reached - Base motor smoothly stopped.");
        return;
    }
}

// Hardware diagnostic sweep test for GPIO 21 Base Continuous Servo
void testBaseServo(Stream *replyStream) {
    if (replyStream) replyStream->println("[TEST] Starting Base Servo (GPIO 21) Continuous Jog Test...");

    stopBase();
    delay(200);

    if (replyStream) replyStream->println("[TEST] Rotating Clockwise (CW)...");
    jogBase(1, 260);
    delay(600);

    if (replyStream) replyStream->println("[TEST] Rotating Counter-Clockwise (CCW)...");
    jogBase(-1, 260);
    delay(600);

    stopBase();
    if (replyStream) replyStream->println("[TEST] Base Servo Test Complete. GPIO 21 is operational!");
}

// ============================================================================
// COMMAND PARSER & DISPATCHER
// ============================================================================

void processCommand(const char *command, Stream *replyStream) {
    if (command == nullptr || strlen(command) == 0) {
        return;
    }

    // Trim leading whitespace
    while (*command == ' ' || *command == '\t') command++;

    // Emergency or normal base stop
    if (strcmp(command, "STOP4") == 0 || strcmp(command, "STOP") == 0) {
        stopBase();
        if (replyStream) replyStream->println("BASE STOPPED");
        return;
    }

    // Hardware sweep test for GPIO 21
    if (strcmp(command, "TEST4") == 0) {
        testBaseServo(replyStream);
        return;
    }

    // Calibrate neutral stop pulse: CAL4,<us> (e.g. CAL4,1500 or CAL4,1490 if motor creeps at idle)
    if (strncmp(command, "CAL4,", 5) == 0) {
        int cal = atoi(command + 5);
        if (cal >= 1400 && cal <= 1600) {
            baseStopUs = cal;
            stopBase();
            if (replyStream) replyStream->printf("BASE STOP PULSE SET: %d us\n", baseStopUs);
        }
        return;
    }

    // Direct microsecond write to base servo: US4,1500
    if (strncmp(command, "US4,", 4) == 0) {
        int us = atoi(command + 4);
        if (us >= 500 && us <= 2500) {
            servo4.writeMicroseconds(us);
            if (replyStream) replyStream->printf("ACK,US4,%d\n", us);
        }
        return;
    }

    // Continuous manual jog for base: J4,CW or J4,CCW or J4,STOP or J4,CW,250
    if (strncmp(command, "J4,", 3) == 0) {
        char dirStr[8] = {0};
        int speed = baseJogSpeedOffset;
        sscanf(command + 3, "%7[^,],%d", dirStr, &speed);
        if (strcmp(dirStr, "CW") == 0) {
            jogBase(1, speed);
            if (replyStream) replyStream->printf("ACK,J4,CW,%d\n", speed);
        } else if (strcmp(dirStr, "CCW") == 0) {
            jogBase(-1, speed);
            if (replyStream) replyStream->printf("ACK,J4,CCW,%d\n", speed);
        } else {
            stopBase();
            if (replyStream) replyStream->println("ACK,J4,STOP");
        }
        return;
    }

    // Reset all servos
    if (strcmp(command, "RESET") == 0) {
        movePositionalServo(servo1, pos1, 90);
        movePositionalServo(servo2, pos2, 90);
        movePositionalServo(servo3, pos3, 90);
        stopBase();
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
            replyStream->printf("STATUS,S1:%d,S2:%d,S3:%d,S4:%d,BASE_STATE:%d,STOP_US:%d\n",
                                pos1, pos2, pos3, pos4, baseState, baseStopUs);
        }
        return;
    }

    // Parse servo position command: S1,90 or S2,120 or S4,100 etc.
    const char *separator = strchr(command, ',');
    if (separator == nullptr) {
        return;
    }

    int prefixLen = separator - command;
    char servoID[8];
    if (prefixLen >= (int)sizeof(servoID)) return;
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
        // Slider compatibility for continuous motor:
        // Center (85-95) = STOP, >95 = rotate CW, <85 = rotate CCW
        if (abs(value - 90) <= 5) {
            stopBase();
        } else if (value > 90) {
            int speed = map(value, 95, 180, 80, 350);
            jogBase(1, speed);
        } else {
            int speed = map(value, 85, 0, 80, 350);
            jogBase(-1, speed);
        }
        if (replyStream) replyStream->printf("ACK,S4,%d\n", value);
    }
}

// ============================================================================
// WEB SERVER & ASSET SERVING LOGIC
// ============================================================================

void handleServeFile(const char* path, const char* contentType, const char* progmemFallback) {
    if (littleFsMounted) {
        // 1. Try file at LittleFS root: e.g. /index.html
        if (LittleFS.exists(path)) {
            File file = LittleFS.open(path, "r");
            if (file) {
                webServer.streamFile(file, contentType);
                file.close();
                return;
            }
        }
        // 2. Try file with /WebHostControl prefix: e.g. /WebHostControl/index.html
        char altPath[80];
        snprintf(altPath, sizeof(altPath), "/WebHostControl%s", path);
        if (LittleFS.exists(altPath)) {
            File file = LittleFS.open(altPath, "r");
            if (file) {
                webServer.streamFile(file, contentType);
                file.close();
                return;
            }
        }
    }

    // 3. Fallback to embedded PROGMEM string
    if (progmemFallback != nullptr) {
        webServer.send_P(200, contentType, progmemFallback);
    } else {
        webServer.send(404, "text/plain", "File Not Found");
    }
}

// REST API: Continuous Jog
// GET /api/jog?dir=CW&speed=200 or /api/jog?dir=CCW or /api/jog?dir=STOP
void handleApiJog() {
    if (webServer.hasArg("dir")) {
        String dir = webServer.arg("dir");
        int speed = webServer.hasArg("speed") ? webServer.arg("speed").toInt() : baseJogSpeedOffset;
        if (dir.equalsIgnoreCase("CW")) {
            jogBase(1, speed);
        } else if (dir.equalsIgnoreCase("CCW")) {
            jogBase(-1, speed);
        } else {
            stopBase();
        }
        char json[96];
        snprintf(json, sizeof(json), "{\"status\":\"ok\",\"baseState\":%d,\"speed\":%d}", baseState, speed);
        webServer.send(200, "application/json", json);
        return;
    }
    webServer.send(400, "application/json", "{\"error\":\"Missing parameter 'dir'\"}");
}


// REST API: Tune Stop Pulse
// GET /api/cal4?us=1500
void handleApiCal4() {
    if (webServer.hasArg("us")) {
        int us = webServer.arg("us").toInt();
        if (us >= 1400 && us <= 1600) {
            baseStopUs = us;
            stopBase();
            char json[96];
            snprintf(json, sizeof(json), "{\"status\":\"ok\",\"baseStopUs\":%d}", baseStopUs);
            webServer.send(200, "application/json", json);
            return;
        }
    }
    webServer.send(400, "application/json", "{\"error\":\"Invalid 'us' parameter (1400-1600)\"}");
}

void handleApiSet() {
    if (webServer.hasArg("s") && webServer.hasArg("v")) {
        int servoNum = webServer.arg("s").toInt();
        int val = constrain(webServer.arg("v").toInt(), 0, 180);

        if (servoNum == 1) movePositionalServo(servo1, pos1, val);
        else if (servoNum == 2) movePositionalServo(servo2, pos2, val);
        else if (servoNum == 3) movePositionalServo(servo3, pos3, val);
        else if (servoNum == 4) {
            if (abs(val - 90) <= 5) {
                stopBase();
            } else if (val > 90) {
                int speed = map(val, 95, 180, 80, 350);
                jogBase(1, speed);
            } else {
                int speed = map(val, 85, 0, 80, 350);
                jogBase(-1, speed);
            }
        }

        char json[96];
        snprintf(json, sizeof(json), "{\"status\":\"ok\",\"s\":%d,\"v\":%d,\"baseState\":%d}", servoNum, val, baseState);
        webServer.send(200, "application/json", json);
        return;
    }
    webServer.send(400, "application/json", "{\"error\":\"Missing parameter 's' or 'v'\"}");
}

void handleApiStatus() {
    char json[160];
    snprintf(json, sizeof(json),
             "{\"s1\":%d,\"s2\":%d,\"s3\":%d,\"s4\":%d,\"baseState\":%d,\"baseStopUs\":%d}",
             pos1, pos2, pos3, pos4, baseState, baseStopUs);
    webServer.send(200, "application/json", json);
}

void handleApiStop() {
    stopBase();
    webServer.send(200, "application/json", "{\"status\":\"stopped\",\"baseState\":0}");
}

void handleApiReset() {
    movePositionalServo(servo1, pos1, 90);
    movePositionalServo(servo2, pos2, 90);
    movePositionalServo(servo3, pos3, 90);
    stopBase();
    webServer.send(200, "application/json", "{\"status\":\"reset\"}");
}

void handleNotFound() {
    String uri = webServer.uri();

    // Check LittleFS for custom static files if mounted
    if (littleFsMounted && LittleFS.exists(uri)) {
        String contentType = "text/plain";
        if (uri.endsWith(".html")) contentType = "text/html";
        else if (uri.endsWith(".css")) contentType = "text/css";
        else if (uri.endsWith(".js")) contentType = "application/javascript";
        else if (uri.endsWith(".json")) contentType = "application/json";

        File file = LittleFS.open(uri, "r");
        if (file) {
            webServer.streamFile(file, contentType);
            file.close();
            return;
        }
    }

    webServer.send(404, "text/plain", "404 Not Found");
}

void setupWebServer() {
    // Attempt LittleFS initialization
    littleFsMounted = LittleFS.begin(true);
    if (littleFsMounted) {
        Serial.println("[FS] LittleFS mounted successfully!");
    } else {
        Serial.println("[FS] LittleFS mount failed - using PROGMEM web assets fallback.");
    }

    // HTML Page routes
    webServer.on("/", HTTP_GET, []() {
        handleServeFile("/index.html", "text/html", INDEX_HTML);
    });
    webServer.on("/index.html", HTTP_GET, []() {
        handleServeFile("/index.html", "text/html", INDEX_HTML);
    });
    webServer.on("/WebHostControl/index.html", HTTP_GET, []() {
        handleServeFile("/index.html", "text/html", INDEX_HTML);
    });

    // CSS Stylesheet routes
    webServer.on("/style.css", HTTP_GET, []() {
        handleServeFile("/style.css", "text/css", STYLE_CSS);
    });
    webServer.on("/WebHostControl/style.css", HTTP_GET, []() {
        handleServeFile("/style.css", "text/css", STYLE_CSS);
    });

    // JavaScript Controller routes
    webServer.on("/script.js", HTTP_GET, []() {
        handleServeFile("/script.js", "application/javascript", SCRIPT_JS);
    });
    webServer.on("/WebHostControl/script.js", HTTP_GET, []() {
        handleServeFile("/script.js", "application/javascript", SCRIPT_JS);
    });

    // REST API routes
    webServer.on("/api/jog", HTTP_GET, handleApiJog);
    webServer.on("/api/cal4", HTTP_GET, handleApiCal4);
    webServer.on("/api/set", HTTP_GET, handleApiSet);
    webServer.on("/api/status", HTTP_GET, handleApiStatus);
    webServer.on("/api/stop", HTTP_GET, handleApiStop);
    webServer.on("/api/reset", HTTP_GET, handleApiReset);
    webServer.onNotFound(handleNotFound);

    webServer.begin();
    Serial.println("[HTTP] Web Server listening at http://192.168.4.1");
}

// ============================================================================
// STREAM INPUT READER (USB & TCP)
// ============================================================================

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

// ============================================================================
// SYSTEM INITIALIZATION (SETUP)
// ============================================================================

void setup() {
    Serial.begin(115200);
    delay(200);

    Serial.println();
    Serial.println("==================================================");
    Serial.println("   ESP32 ROBOTIC ARM CONTROLLER INITIALIZING");
    Serial.println("==================================================");

    // 1. Allocate all 4 hardware PWM timers for ESP32Servo
    ESP32PWM::allocateTimer(0);
    ESP32PWM::allocateTimer(1);
    ESP32PWM::allocateTimer(2);
    ESP32PWM::allocateTimer(3);

    servo1.setPeriodHertz(50);
    servo2.setPeriodHertz(50);
    servo3.setPeriodHertz(50);
    servo4.setPeriodHertz(50);

    int ch1 = servo1.attach(SERVO1_PIN, SERVO_MIN_US, SERVO_MAX_US);
    int ch2 = servo2.attach(SERVO2_PIN, SERVO_MIN_US, SERVO_MAX_US);
    int ch3 = servo3.attach(SERVO3_PIN, SERVO_MIN_US, SERVO_MAX_US);
    int ch4 = servo4.attach(SERVO4_PIN, SERVO_MIN_US, SERVO_MAX_US);

    Serial.println("[SERVO] Hardware PWM Attach Status:");
    Serial.printf("  [S1] Shoulder (GPIO %2d): %s (LEDC Channel %d)\n", SERVO1_PIN, servo1.attached() ? "READY" : "FAILED", ch1);
    Serial.printf("  [S2] Elbow    (GPIO %2d): %s (LEDC Channel %d)\n", SERVO2_PIN, servo2.attached() ? "READY" : "FAILED", ch2);
    Serial.printf("  [S3] Claw     (GPIO %2d): %s (LEDC Channel %d)\n", SERVO3_PIN, servo3.attached() ? "READY" : "FAILED", ch3);
    Serial.printf("  [S4] Base     (GPIO %2d): %s (LEDC Channel %d) [MG90S 360° Smooth Eased Jog Mode]\n",
                  SERVO4_PIN, servo4.attached() ? "READY" : "FAILED", ch4);

    if (!servo4.attached()) {
        Serial.println("  [WARNING] S4 Base Servo failed to attach to GPIO 21!");
    }

    // Set initial positions: 90° for positional joints 1-3, neutral stop pulse for continuous base
    servo1.write(pos1);
    servo2.write(pos2);
    servo3.write(pos3);
    baseCurrentUs = baseStopUs;
    baseTargetUs = baseStopUs;
    lastBaseRampTime = millis();
    stopBase();

    // 2. Start Wi-Fi Access Point (SoftAP)
    WiFi.mode(WIFI_AP);
    bool apStarted = WiFi.softAP(AP_SSID, AP_PASSWORD);

    if (apStarted) {
        Serial.println("[WIFI] Access Point started successfully!");
        Serial.print("  SSID:        "); Serial.println(AP_SSID);
        Serial.print("  Password:    "); Serial.println(AP_PASSWORD);
        Serial.print("  IP Address:  "); Serial.println(WiFi.softAPIP());
    } else {
        Serial.println("[WIFI] Failed to start SoftAP!");
    }

    // 3. Start TCP Socket Server on Port 5000 (Desktop Python GUI)
    tcpServer.begin();
    tcpServer.setNoDelay(true);
    Serial.println("[TCP] Server listening on port 5000");

    // 4. Start HTTP Web Server on Port 80 (Mobile & Desktop Browsers)
    setupWebServer();

    Serial.println("==================================================");
    Serial.println("  ESP32 READY: USB & WI-FI ACTIVE (BLUETOOTH DISABLED)");
    Serial.println("  Base Mode: MG90S 360° Smooth Continuous Easing");
    Serial.println("  Tip: Send 'TEST4' over Serial to test Base Servo!");
    Serial.println("==================================================");
}

// ============================================================================
// MAIN EXECUTION LOOP
// ============================================================================

void loop() {
    // 1. Process smooth base motor ramping & safety timeout
    updateBase();

    // 2. Handle HTTP Web Server requests (Mobile Web GUI)
    webServer.handleClient();

    // 3. Process USB Serial commands (PC connected via USB cable)
    checkStreamInput(Serial, serialBuffer, serialBufIndex, &Serial);

    // 4. Manage TCP Wi-Fi Client (Desktop Python GUI)
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
