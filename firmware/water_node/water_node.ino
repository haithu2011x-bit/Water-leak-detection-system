/*
  Project II | ESP32-WROOM-32 + 3 YF-S401 | Flow-only v1
  - MAIN GPIO27, Z1 GPIO26, Z2 GPIO25
  - Publish topic: building/water/node1/telemetry
  - JSON v2 adds device_id, boot_id, seq to the existing four fields.
  - seq increases every 1-second sampling window, even when MQTT is offline.
  - No pressure sensor. No scenario/label in real telemetry.

  SAFETY: YF-S401 can be powered from 5V, but ESP32 GPIO is 3.3V only.
  CONDITION EVERY SIGNAL to 3.3V before connecting. Do NOT connect a
  sensor's 5V output directly to GPIO. Use compatible logic-level interface.

  The initial mode intentionally produces NO MQTT telemetry until three
  pulse-per-litre constants have been measured on your actual hardware.
*/
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <esp_system.h>

// --- EDIT WHEN HARDWARE ARRIVES ---
constexpr bool CALIBRATION_MODE = true; // true: serial pulse counts only; false: publish MQTT
constexpr float PULSES_PER_LITER_MAIN = 0.0f; // measured pulses / collected litres
constexpr float PULSES_PER_LITER_Z1   = 0.0f;
constexpr float PULSES_PER_LITER_Z2   = 0.0f;
const char* WIFI_SSID = "REPLACE_WIFI_SSID";
const char* WIFI_PASSWORD = "REPLACE_WIFI_PASSWORD";
const char* MQTT_HOST = "192.168.1.10"; // EXAMPLE: replace with LAN IP of laptop
constexpr uint16_t MQTT_PORT = 1883;
const char* MQTT_TOPIC = "building/water/node1/telemetry";

// GPIOs are configured as INPUT because a suitable external 3.3V signal
// conditioning circuit is REQUIRED and must deliver defined HIGH/LOW levels.
constexpr uint8_t PIN_MAIN = 27;
constexpr uint8_t PIN_Z1 = 26;
constexpr uint8_t PIN_Z2 = 25;
constexpr uint32_t SAMPLE_INTERVAL_MS = 1000;
constexpr uint32_t RECONNECT_INTERVAL_MS = 5000;
const char* DEVICE_ID = "water-node-01";

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
portMUX_TYPE flowMux = portMUX_INITIALIZER_UNLOCKED;
volatile uint32_t winMain = 0, winZ1 = 0, winZ2 = 0;
volatile uint32_t totalMain = 0, totalZ1 = 0, totalZ2 = 0;
uint32_t lastSampleMs = 0;
uint32_t lastWifiAttemptMs = 0, lastMqttAttemptMs = 0;
uint32_t sampleSequence = 0;  // wrap-around is valid (uint32)
char bootId[17] = {0};  // 16 hex digits, identifies a single power-on cycle

void IRAM_ATTR pulseMainISR() {
  portENTER_CRITICAL_ISR(&flowMux);
  ++winMain; ++totalMain;
  portEXIT_CRITICAL_ISR(&flowMux);
}
void IRAM_ATTR pulseZ1ISR() {
  portENTER_CRITICAL_ISR(&flowMux);
  ++winZ1; ++totalZ1;
  portEXIT_CRITICAL_ISR(&flowMux);
}
void IRAM_ATTR pulseZ2ISR() {
  portENTER_CRITICAL_ISR(&flowMux);
  ++winZ2; ++totalZ2;
  portEXIT_CRITICAL_ISR(&flowMux);
}

bool calibrationValid() {
  return PULSES_PER_LITER_MAIN > 0.0f &&
         PULSES_PER_LITER_Z1 > 0.0f &&
         PULSES_PER_LITER_Z2 > 0.0f;
}

void resetTotalCountersIfRequested() {
  while (Serial.available() > 0) {
    char cmd = static_cast<char>(Serial.read());
    if (cmd == 'r' || cmd == 'R') {
      portENTER_CRITICAL(&flowMux);
      totalMain = totalZ1 = totalZ2 = 0;
      portEXIT_CRITICAL(&flowMux);
      Serial.println("RESET_TOTALS: all cumulative pulse counts set to 0");
    }
  }
}

void maintainNetwork(uint32_t nowMs) {
  if (WiFi.status() != WL_CONNECTED) {
    if (static_cast<uint32_t>(nowMs - lastWifiAttemptMs) >= RECONNECT_INTERVAL_MS) {
      lastWifiAttemptMs = nowMs;
      WiFi.reconnect();
      Serial.println("WiFi reconnect requested");
    }
    return;
  }
  if (!mqtt.connected()) {
    if (static_cast<uint32_t>(nowMs - lastMqttAttemptMs) >= RECONNECT_INTERVAL_MS) {
      lastMqttAttemptMs = nowMs;
      if (mqtt.connect("water-node-01")) {
        Serial.println("MQTT connected");
      } else {
        Serial.printf("MQTT reconnect pending; state=%d\n", mqtt.state());
      }
    }
  } else {
    mqtt.loop();
  }
}

void setup() {
  Serial.begin(115200);
  delay(250);
  pinMode(PIN_MAIN, INPUT);
  pinMode(PIN_Z1, INPUT);
  pinMode(PIN_Z2, INPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_MAIN), pulseMainISR, FALLING);
  attachInterrupt(digitalPinToInterrupt(PIN_Z1), pulseZ1ISR, FALLING);
  attachInterrupt(digitalPinToInterrupt(PIN_Z2), pulseZ2ISR, FALLING);
  lastSampleMs = millis();
  Serial.println("Project II | 3 flow sensors | no pressure");
  if (CALIBRATION_MODE) {
    Serial.println("CALIBRATION MODE: no WiFi/MQTT. Send 'r' to reset total pulses.");
    return;
  }
  if (!calibrationValid()) {
    Serial.println("ERROR: set 3 measured PULSES_PER_LITER values before disabling CALIBRATION_MODE.");
    return;
  }
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  // Diagnostic run ID, not a security/authentication token.
  snprintf(bootId, sizeof(bootId), "%08lx%08lx",
           (unsigned long)esp_random(), (unsigned long)esp_random());
  Serial.printf("device_id=%s boot_id=%s\n", DEVICE_ID, bootId);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);
  Serial.println("NETWORK MODE: connecting WiFi and MQTT...");
}

void loop() {
  resetTotalCountersIfRequested();
  const uint32_t now = millis();

  // Interrupt-driven pulse counts continue even when network is unavailable.
  if (static_cast<uint32_t>(now - lastSampleMs) >= SAMPLE_INTERVAL_MS) {
    const uint32_t elapsedMs = static_cast<uint32_t>(now - lastSampleMs);
    lastSampleMs = now;
    uint32_t m, z1, z2, tm, tz1, tz2;
    portENTER_CRITICAL(&flowMux);
    m = winMain; z1 = winZ1; z2 = winZ2;
    winMain = winZ1 = winZ2 = 0;
    tm = totalMain; tz1 = totalZ1; tz2 = totalZ2;
    portEXIT_CRITICAL(&flowMux);

    if (CALIBRATION_MODE) {
      Serial.printf("dt=%lu ms | win M=%lu Z1=%lu Z2=%lu | TOTAL M=%lu Z1=%lu Z2=%lu\n",
        (unsigned long)elapsedMs,
        (unsigned long)m, (unsigned long)z1, (unsigned long)z2,
        (unsigned long)tm, (unsigned long)tz1, (unsigned long)tz2);
    } else if (calibrationValid()) {
      const uint32_t seq = sampleSequence++; // count samples, NOT publish successes
      // (pulses / (pulses/L)) / (elapsedMs / 60000 ms/min) => L/min
      const float flowM = m * (60000.0f / elapsedMs) / PULSES_PER_LITER_MAIN;
      const float flowZ1 = z1 * (60000.0f / elapsedMs) / PULSES_PER_LITER_Z1;
      const float flowZ2 = z2 * (60000.0f / elapsedMs) / PULSES_PER_LITER_Z2;
      char json[256];
      snprintf(json, sizeof(json),
        "{\"device_id\":\"%s\",\"boot_id\":\"%s\",\"seq\":%lu,\"ts_ms\":%lu,\"flow_main\":%.3f,\"flow_z1\":%.3f,\"flow_z2\":%.3f}",
        DEVICE_ID, bootId, (unsigned long)seq, (unsigned long)now, flowM, flowZ1, flowZ2);
      if (mqtt.connected()) {
        bool ok = mqtt.publish(MQTT_TOPIC, json);
        Serial.printf("%s | publish=%s\n", json, ok ? "OK" : "FAILED");
      } else {
        Serial.printf("MQTT offline, sample not sent | %s\n", json);
      }
    }
  }
  if (!CALIBRATION_MODE && calibrationValid()) {
    maintainNetwork(now);
  }
  delay(2);
}
