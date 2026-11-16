// ============================================================================
// ESP32 ROBOTIC ARM CONTROLLER (4-DOF Multi-Link Control)
// Firmware supporting USB Serial, Wi-Fi SoftAP (TCP Socket & Web GUI), and BT SPP
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
// BLUETOOTH CONFIGURATION
// ============================================================================
// Set to 1 to enable Bluetooth Serial SPP (e.g., "ESP32_RoboticArm")
// Set to 0 if you only want Wi-Fi and USB Serial
#define ENABLE_BLUETOOTH 1

#if ENABLE_BLUETOOTH
#include <BluetoothSerial.h>
BluetoothSerial SerialBT;
#endif

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
#define SERVO4_PIN 21  // Base Rotation (MG90S - 360° Continuous)

// ============================================================================
// SERVO OBJECTS & SETTINGS
// ============================================================================
Servo servo1;
Servo servo2;
Servo servo3;
Servo servo4;

// SG90 Pulse limits (microseconds)
const int SERVO_MIN_US = 600;
const int SERVO_MAX_US = 2300;

// Current joint positions (degrees 0-180)
int pos1 = 90; // Shoulder
int pos2 = 90; // Elbow
int pos3 = 90; // Claw

// MG90S Continuous Rotation calibration & tracking
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

// ============================================================================
// INPUT BUFFERS FOR SERIAL STREAMS
// ============================================================================
#define BUFFER_SIZE 64

char serialBuffer[BUFFER_SIZE];
int serialBufIndex = 0;

char tcpBuffer[BUFFER_SIZE];
int tcpBufIndex = 0;

#if ENABLE_BLUETOOTH
char btBuffer[BUFFER_SIZE];
int btBufIndex = 0;
#endif

// ============================================================================
// FORWARD DECLARATIONS
// ============================================================================
void stopBase();
void updateBase();
void setBaseTarget(int newTarget);
void movePositionalServo(Servo &servo, int &currentPosition, int newPosition);
void processCommand(const char *command, Stream *replyStream);
void checkStreamInput(Stream &stream, char *buffer, int &bufIndex, Stream *replyStream);
void setupWebServer();
void handleServeFile(const char* path, const char* contentType, const char* progmemFallback);
void handleApiSet();
void handleApiStatus();
void handleApiStop();
void handleApiReset();
void handleNotFound();

// ============================================================================
// SERVO MOVEMENT LOGIC
// ============================================================================

void movePositionalServo(Servo &servo, int &currentPosition, int newPosition) {
    newPosition = constrain(newPosition, 0, 180);
    if (newPosition == currentPosition) {
        return;
    }
    currentPosition = newPosition;
    servo.write(newPosition);
}

void stopBase() {
    servo4.writeMicroseconds(BASE_STOP_US);
    baseDirection = 0;
    baseManualJog = false;
    baseTarget = constrain(basePosition, 0.0f, 180.0f);
}

void updateBase() {
    unsigned long now = millis();

    if (lastBaseUpdate == 0) {
        lastBaseUpdate = now;
        return;
    }

    unsigned long elapsed = now - lastBaseUpdate;
    lastBaseUpdate = now;

    // Prevent jump if loop was delayed
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

    // Estimated movement toward target angle
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

void setBaseTarget(int newTarget) {
    updateBase();
    baseManualJog = false;
    baseTarget = constrain(newTarget, 0, 180);
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

    // Parse servo position command: S1,90 or S2,120 etc.
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
        setBaseTarget(value);
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

void handleApiSet() {
    if (webServer.hasArg("s") && webServer.hasArg("v")) {
        int servoNum = webServer.arg("s").toInt();
        int val = constrain(webServer.arg("v").toInt(), 0, 180);

        if (servoNum == 1) movePositionalServo(servo1, pos1, val);
        else if (servoNum == 2) movePositionalServo(servo2, pos2, val);
        else if (servoNum == 3) movePositionalServo(servo3, pos3, val);
        else if (servoNum == 4) setBaseTarget(val);

        char json[96];
        snprintf(json, sizeof(json), "{\"status\":\"ok\",\"s\":%d,\"v\":%d}", servoNum, val);
        webServer.send(200, "application/json", json);
        return;
    }
    webServer.send(400, "application/json", "{\"error\":\"Missing parameter 's' or 'v'\"}");
}

void handleApiStatus() {
    char json[128];
    snprintf(json, sizeof(json),
             "{\"s1\":%d,\"s2\":%d,\"s3\":%d,\"s4\":%d,\"basePos\":%d}",
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
    webServer.on("/api/set", HTTP_GET, handleApiSet);
    webServer.on("/api/status", HTTP_GET, handleApiStatus);
    webServer.on("/api/stop", HTTP_GET, handleApiStop);
    webServer.on("/api/reset", HTTP_GET, handleApiReset);
    webServer.onNotFound(handleNotFound);

    webServer.begin();
    Serial.println("[HTTP] Web Server listening at http://192.168.4.1");
}

// ============================================================================
// STREAM INPUT READER (USB, TCP, BT)
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
    Serial.println("==========================================");
    Serial.println("  ESP32 ROBOTIC ARM CONTROLLER INITIALIZING");
    Serial.println("==========================================");

    // 1. Initialize Servos
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

    // 5. Start Bluetooth Classic SPP (if enabled)
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

// ============================================================================
// MAIN EXECUTION LOOP
// ============================================================================

void loop() {
    // 1. Update continuous rotation base estimation
    updateBase();

    // 2. Handle HTTP Web Server requests (Mobile Web GUI)
    webServer.handleClient();

    // 3. Process USB Serial commands (PC connected via USB cable)
    checkStreamInput(Serial, serialBuffer, serialBufIndex, &Serial);

    // 4. Process Bluetooth Serial commands (if enabled)
#if ENABLE_BLUETOOTH
    checkStreamInput(SerialBT, btBuffer, btBufIndex, &SerialBT);
#endif

    // 5. Manage TCP Wi-Fi Client (Desktop Python GUI)
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
