
#include <Arduino.h>

const int PIN_S0 = 25;
const int PIN_S1 = 26;
const int PIN_S2 = 27;

portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;

volatile uint32_t win0 = 0, win1 = 0, win2 = 0;
volatile uint32_t total0 = 0, total1 = 0, total2 = 0;

uint32_t lastPrint = 0;

void IRAM_ATTR onS0() {
  portENTER_CRITICAL_ISR(&mux);
  win0++; total0++;
  portEXIT_CRITICAL_ISR(&mux);
}

void IRAM_ATTR onS1() {
  portENTER_CRITICAL_ISR(&mux);
  win1++; total1++;
  portEXIT_CRITICAL_ISR(&mux);
}

void IRAM_ATTR onS2() {
  portENTER_CRITICAL_ISR(&mux);
  win2++; total2++;
  portEXIT_CRITICAL_ISR(&mux);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(PIN_S0, INPUT);
  pinMode(PIN_S1, INPUT);
  pinMode(PIN_S2, INPUT);

  attachInterrupt(digitalPinToInterrupt(PIN_S0), onS0, FALLING);
  attachInterrupt(digitalPinToInterrupt(PIN_S1), onS1, FALLING);
  attachInterrupt(digitalPinToInterrupt(PIN_S2), onS2, FALLING);

  lastPrint = millis();
  Serial.println("ESP32 SENSOR TEST READY");
}

void loop() {
  while (Serial.available()) {
    char cmd = Serial.read();
    if (cmd == 'r' || cmd == 'R') {
      portENTER_CRITICAL(&mux);
      total0 = total1 = total2 = 0;
      portEXIT_CRITICAL(&mux);
      Serial.println("TOTALS RESET");
    }
  }

  uint32_t now = millis();

  if (now - lastPrint >= 1000) {
    lastPrint = now;

    uint32_t a, b, c, ta, tb, tc;

    portENTER_CRITICAL(&mux);
    a = win0; b = win1; c = win2;
    win0 = win1 = win2 = 0;
    ta = total0; tb = total1; tc = total2;
    portEXIT_CRITICAL(&mux);

    Serial.printf(
      "WIN S0=%lu S1=%lu S2=%lu | TOTAL S0=%lu S1=%lu S2=%lu\n",
      (unsigned long)a, (unsigned long)b, (unsigned long)c,
      (unsigned long)ta, (unsigned long)tb, (unsigned long)tc
    );
  }

  delay(2);
}
