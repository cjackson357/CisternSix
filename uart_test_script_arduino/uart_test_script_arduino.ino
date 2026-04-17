#include <Servo.h>

void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("READY");
}

String inputBuffer = "";

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      inputBuffer.trim();
      if (inputBuffer == "PING") {
        Serial.println("PONG");
      }
      inputBuffer = "";
    } else {
      inputBuffer += c;
    }
  }
}