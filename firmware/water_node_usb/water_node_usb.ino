/* ESP32-WROOM-32D, 3 YF-S401: USB Serial, no Wi-Fi or MQTT.
   MAIN GPIO27, Zone 1 GPIO26, Zone 2 GPIO25. No pressure sensor.
   Calibrate all three sensors before reporting L/min; zero values are intentional.
   Condition sensor signals to 0-3.3V logic; power 12V pump separately. */
#include <Arduino.h>
#include <esp_system.h>

constexpr bool CALIBRATION_MODE = true;
constexpr float PULSES_PER_LITER_MAIN = 0.0f;
constexpr float PULSES_PER_LITER_Z1 = 0.0f;
constexpr float PULSES_PER_LITER_Z2 = 0.0f;
constexpr uint8_t PIN_MAIN = 27, PIN_Z1 = 26, PIN_Z2 = 25;
constexpr uint32_t SAMPLE_INTERVAL_MS = 1000;
const char* DEVICE_ID = "water-node-01";
portMUX_TYPE flowMux = portMUX_INITIALIZER_UNLOCKED;
volatile uint32_t winMain = 0, winZ1 = 0, winZ2 = 0;
volatile uint32_t totalMain = 0, totalZ1 = 0, totalZ2 = 0;
uint32_t lastSampleMs = 0, sampleSequence = 0;
char bootId[17] = {0};

void IRAM_ATTR pulseMainISR() {
  portENTER_CRITICAL_ISR(&flowMux); ++winMain; ++totalMain; portEXIT_CRITICAL_ISR(&flowMux);
}
void IRAM_ATTR pulseZ1ISR() {
  portENTER_CRITICAL_ISR(&flowMux); ++winZ1; ++totalZ1; portEXIT_CRITICAL_ISR(&flowMux);
}
void IRAM_ATTR pulseZ2ISR() {
  portENTER_CRITICAL_ISR(&flowMux); ++winZ2; ++totalZ2; portEXIT_CRITICAL_ISR(&flowMux);
}
bool calibrationValid() {
  return PULSES_PER_LITER_MAIN > 0.0f && PULSES_PER_LITER_Z1 > 0.0f && PULSES_PER_LITER_Z2 > 0.0f;
}
void readSerialCommands() {
  while (Serial.available()) {
    const char cmd = static_cast<char>(Serial.read());
    if (CALIBRATION_MODE && (cmd == 'r' || cmd == 'R')) {
      portENTER_CRITICAL(&flowMux);
      totalMain = totalZ1 = totalZ2 = 0;
      portEXIT_CRITICAL(&flowMux);
      Serial.println("RESET_TOTALS: 0");
    }
  }
}
void setup() {
  Serial.begin(115200);
  delay(250);
  pinMode(PIN_MAIN, INPUT); pinMode(PIN_Z1, INPUT); pinMode(PIN_Z2, INPUT);
  attachInterrupt(digitalPinToInterrupt(PIN_MAIN), pulseMainISR, FALLING);
  attachInterrupt(digitalPinToInterrupt(PIN_Z1), pulseZ1ISR, FALLING);
  attachInterrupt(digitalPinToInterrupt(PIN_Z2), pulseZ2ISR, FALLING);
  lastSampleMs = millis();
  snprintf(bootId, sizeof(bootId), "%08lx%08lx",
           (unsigned long)esp_random(), (unsigned long)esp_random());
  if (CALIBRATION_MODE)
    Serial.println("CALIBRATION: pulse counts only. Send r to reset totals.");
  else if (!calibrationValid())
    Serial.println("ERROR: set measured pulses/L for all three sensors.");
  else
    Serial.println("USB SERIAL: JSON telemetry each second at 115200 baud.");
}
void loop() {
  readSerialCommands();
  const uint32_t now = millis();
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
        (unsigned long)elapsedMs, (unsigned long)m, (unsigned long)z1, (unsigned long)z2,
        (unsigned long)tm, (unsigned long)tz1, (unsigned long)tz2);
    } else if (calibrationValid()) {
      const uint32_t seq = sampleSequence++;
      const float flowM = m * (60000.0f / elapsedMs) / PULSES_PER_LITER_MAIN;
      const float flowZ1 = z1 * (60000.0f / elapsedMs) / PULSES_PER_LITER_Z1;
      const float flowZ2 = z2 * (60000.0f / elapsedMs) / PULSES_PER_LITER_Z2;
      char json[256];
      snprintf(json, sizeof(json),
        "{\"device_id\":\"%s\",\"boot_id\":\"%s\",\"seq\":%lu,\"ts_ms\":%lu,\"flow_main\":%.3f,\"flow_z1\":%.3f,\"flow_z2\":%.3f}",
        DEVICE_ID, bootId, (unsigned long)seq, (unsigned long)now, flowM, flowZ1, flowZ2);
      Serial.println(json);
    }
  }
  delay(2);
}
