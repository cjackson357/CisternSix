#include <Servo.h>

// ESC on pins 3, 5, 6, 9, 10 — DC motor on pin 11
Servo esc[5];
const int ESC_PINS[5] = {3, 5, 6, 9, 10};
const int DC_PIN = 11;

void setup() {
  Serial.begin(115200);

  for (int i = 0; i < 5; i++) {
    esc[i].attach(ESC_PINS[i], 1000, 2000); // min 1000us, max 2000us
    esc[i].writeMicroseconds(1000);          // send idle/arm signal
  }

  pinMode(DC_PIN, OUTPUT);
  analogWrite(DC_PIN, 0);
}

String inputBuffer = "";

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      parseCommand(inputBuffer);
      inputBuffer = "";
    } else {
      inputBuffer += c;
    }
  }
}

void parseCommand(String cmd) {
  int start = 0;
  while (start < cmd.length()) {
    int comma = cmd.indexOf(',', start);
    String token = (comma == -1) ? cmd.substring(start) : cmd.substring(start, comma);

    if (token.charAt(0) == 'M') {
      int colon = token.indexOf(':');
      if (colon != -1) {
        int motorId = token.substring(1, colon).toInt() - 1; // 0-indexed
        int value   = token.substring(colon + 1).toInt();

        if (motorId >= 0 && motorId < 5) {
          // ESCs: Pi sends 0-255, map to 1000-2000us
          int us = map(value, 0, 255, 1000, 2000);
          esc[motorId].writeMicroseconds(constrain(us, 1000, 2000));
        } else if (motorId == 5) {
          // DC motor: use raw 0-255
          analogWrite(DC_PIN, constrain(value, 0, 255));
        }
      }
    }

    if (comma == -1) break;
    start = comma + 1;
  }
}